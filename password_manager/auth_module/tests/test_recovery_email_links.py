"""Every link in a recovery email opens a page that exists, on this site's
frontend, and a cancel link carries a secret token rather than an attempt ID."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from auth_module.models import RecoveryNotice
from auth_module.quantum_recovery_models import RecoveryAttempt
from auth_module.quantum_recovery_tasks import (
    send_canary_alert,
    send_guardian_approval_request,
    send_guardian_invitation,
)
from auth_module.recovery_notice import CANCEL_WINDOW, _token_hash
from auth_module.services.notification_service import NotificationService
from auth_module.tests.test_guardian_recovery_flow import GuardianFlowBase

REPO_ROOT = Path(settings.BASE_DIR).parent
APP_JSX = (REPO_ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ROUTES = re.findall(r'<Route\s+path="([^"]+)"', APP_JSX)
LINK = re.compile(r'https?://[^\s"\'<>]+')


def _matches(route, path):
    route_parts = route.strip('/').split('/')
    path_parts = path.strip('/').split('/')
    return len(route_parts) == len(path_parts) and all(
        r.startswith(':') or r == p for r, p in zip(route_parts, path_parts))


@override_settings(FRONTEND_URL='https://app.example.com/')
class RecoveryEmailLinkTests(GuardianFlowBase):
    """FRONTEND_URL has a trailing slash here, which must not double up."""

    def setUp(self):
        super().setUp()
        self.attempt, token = self._start()
        self._confirm(self.attempt, token)
        self.approval = self.attempt.guardian_approvals.select_related('guardian').first()
        mail.outbox.clear()

    def _assert_reaches_a_page(self, link, expected_route):
        parts = urlsplit(link)
        self.assertEqual(f'{parts.scheme}://{parts.netloc}', 'https://app.example.com', link)
        self.assertFalse(parts.path.startswith('//'), link)
        self.assertTrue(any(_matches(route, parts.path) for route in ROUTES), link)
        self.assertTrue(_matches(expected_route, parts.path), link)

    def _links(self, message):
        bodies = [message.body] + [body for body, _ in getattr(message, 'alternatives', [])]
        return [link for body in bodies for link in LINK.findall(body)
                if not link.startswith(('http://www.w3.org', 'https://www.w3.org'))]

    def _assert_is_a_secret_cancel_link(self, link):
        self._assert_reaches_a_page(link, '/recovery/cancel')
        self.assertNotIn(str(self.attempt.id), link)
        token = parse_qs(urlsplit(link).query)['notice'][0]
        self.assertGreaterEqual(len(token), 40)
        notice = RecoveryNotice.objects.get(cancel_token_hash=_token_hash(token))
        self.assertEqual(notice.event, 'guardian_recovery_started')
        return token

    def _assert_only_the_token_cancels(self, token):
        url = reverse('recovery-notice-cancel')
        client = APIClient()

        # Opening a link is a GET, which a mail scanner also does.
        self.assertEqual(client.get(url, {'token': token}).status_code, 405)
        client.post(url, {'token': str(self.attempt.id)}, format='json')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'guardian_approval')

        client.post(url, {'token': token}, format='json')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'cancelled')

    def test_the_canary_task_links_to_the_cancel_page_with_a_secret_token(self):
        send_canary_alert.apply(args=[str(self.attempt.id)])
        message = mail.outbox[-1]
        links = self._links(message)
        self.assertEqual(len(links), 1, links)
        token = self._assert_is_a_secret_cancel_link(links[0])
        self.assertTrue(RecoveryNotice.objects.get(cancel_token_hash=_token_hash(token)).email_sent)
        self.assertIn(f'{int(CANCEL_WINDOW.total_seconds() // 3600)} hours', message.body)
        self._assert_only_the_token_cancels(token)

    def test_the_canary_email_links_to_the_cancel_page_with_a_secret_token(self):
        self.assertTrue(NotificationService().send_canary_alert(self.attempt))
        message = mail.outbox[-1]
        links = self._links(message)
        self.assertGreaterEqual(len(links), 2, links)  # the text part and the HTML part
        self.assertEqual(len(set(links)), 1, links)
        token = self._assert_is_a_secret_cancel_link(links[0])
        self.assertTrue(RecoveryNotice.objects.get(cancel_token_hash=_token_hash(token)).email_sent)
        self.assertIn(f'{int(CANCEL_WINDOW.total_seconds() // 3600)} hours', message.body)
        self._assert_only_the_token_cancels(token)

    def test_the_canary_sms_carries_the_same_link_as_the_email(self):
        service = NotificationService()
        service.twilio_client = MagicMock()
        self.user.phone_number = '+15550100'
        with override_settings(TWILIO_PHONE_NUMBER='+15550199'):
            self.attempt.recovery_setup.user = self.user
            self.assertTrue(service.send_canary_alert(self.attempt))
        sms = service.twilio_client.messages.create.call_args.kwargs['body']
        links = LINK.findall(sms)
        self.assertEqual(links, self._links(mail.outbox[-1])[:1])
        self._assert_is_a_secret_cancel_link(links[0])

    def test_a_notice_that_could_not_be_sent_is_not_marked_sent(self):
        earlier = list(RecoveryNotice.objects.values_list('pk', flat=True))
        with patch('auth_module.services.notification_service.EmailMultiAlternatives.send',
                   side_effect=OSError('smtp')):
            self.assertFalse(NotificationService().send_canary_alert(self.attempt))
        notice = RecoveryNotice.objects.exclude(pk__in=earlier).get()
        self.assertFalse(notice.email_sent)

    def test_the_guardian_approval_links_reach_the_approval_page(self):
        send_guardian_approval_request.apply(args=[str(self.approval.id)])
        links = self._links(mail.outbox[-1])
        self.assertEqual(len(links), 1, links)
        self._assert_reaches_a_page(links[0], '/recovery/guardian-approve')
        self.assertEqual(urlsplit(links[0]).fragment, self.approval.approval_token)

        self.assertTrue(NotificationService().send_guardian_approval_email(
            self.approval.guardian, self.approval))
        links = self._links(mail.outbox[-1])
        self.assertTrue(links)
        for link in links:
            self._assert_reaches_a_page(link, '/recovery/guardian-approve')
            self.assertEqual(urlsplit(link).fragment, self.approval.approval_token)

    def test_the_guardian_invitation_links_to_the_invitation_page(self):
        guardian = self.approval.guardian
        guardian.status = 'pending'
        guardian.invitation_token = 'an-invitation-token'
        guardian.invitation_expires_at = timezone.now() + timedelta(days=1)
        guardian.save()
        send_guardian_invitation.apply(args=[str(guardian.id)])
        links = self._links(mail.outbox[-1])
        self.assertEqual(len(links), 1, links)
        self._assert_reaches_a_page(links[0], '/recovery/guardian-invite')

    def test_the_owners_recovery_email_links_reach_their_pages(self):
        RecoveryAttempt.objects.filter(pk=self.attempt.pk).update(status='cancelled')
        attempt, _ = self._start()
        message = mail.outbox[-1]
        links = sorted(LINK.findall(message.body))
        self.assertEqual(len(links), 2, links)
        self._assert_reaches_a_page(links[0], '/recovery/cancel')
        self._assert_reaches_a_page(links[1], '/recovery/guardian-attempt')
        self.assertIn(str(attempt.id), links[1])


class NoStaleLinkInTheSourceTests(TestCase):
    def test_no_recovery_email_uses_the_old_host_or_a_page_that_never_existed(self):
        package = Path(settings.BASE_DIR)
        sources = [*(package / 'auth_module').rglob('*.py'),
                   *(package / 'templates' / 'recovery').iterdir()]
        stale = re.compile(r'https?://securevault\.com|/recovery/cancel/|/recovery/challenge/')
        found = [str(path) for path in sources
                 if '__pycache__' not in path.parts and path != Path(__file__)
                 and stale.search(path.read_text(encoding='utf-8'))]
        self.assertEqual(found, [])

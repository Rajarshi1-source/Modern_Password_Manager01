"""
Tests for zero-knowledge duress signalling.

These cover the half of "Plausible Deniability Vault" that lives on the server.
The other half -- deciding WHICH vault to open -- is deliberately absent from
the backend entirely: it happens client-side via `hiddenVaultEnvelope.decode()`
so the master password never reaches this process. The most important
assertions here are therefore negative ones: that the endpoint reveals nothing,
and that no password is involved anywhere in the flow.
"""

import base64
import secrets

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from security.models import DuressCode, DuressEvent, DuressSignal
from security.services.duress_code_service import get_duress_code_service


def make_token():
    """A well-formed signal token: base64 of 32 random bytes (44 chars)."""
    return base64.b64encode(secrets.token_bytes(32)).decode('ascii')


class DuressSignalModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )

    def test_hash_token_is_stable_and_not_reversible(self):
        token = make_token()

        self.assertEqual(
            DuressSignal.hash_token(token),
            DuressSignal.hash_token(token),
        )
        self.assertNotIn(token, DuressSignal.hash_token(token))
        self.assertEqual(len(DuressSignal.hash_token(token)), 64)

    def test_str_does_not_leak_the_hash(self):
        """__str__ lands in admin pages, logs and error reports."""
        token = make_token()
        signal = DuressSignal.objects.create(
            user=self.user, token_hash=DuressSignal.hash_token(token),
        )

        self.assertNotIn(signal.token_hash, str(signal))


class DuressSignalServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )
        self.service = get_duress_code_service()
        self.context = {'ip_address': '203.0.113.10', 'user_agent': 'test-agent'}

    def test_register_stores_only_the_hash(self):
        token = make_token()

        signal = self.service.register_signal_token(self.user, token)

        self.assertEqual(signal.token_hash, DuressSignal.hash_token(token))
        # The raw token must appear in no column.
        self.assertFalse(
            DuressSignal.objects.filter(token_hash=token).exists()
        )

    def test_registering_again_deactivates_the_previous_token(self):
        """A user re-running duress setup must not leave a live stale token."""
        first = self.service.register_signal_token(self.user, make_token())
        second = self.service.register_signal_token(self.user, make_token())

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_matching_signal_fires_and_counts(self):
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        fired = self.service.consume_unlock_signal(
            self.user, token, self.context,
        )

        signal.refresh_from_db()
        self.assertTrue(fired)
        self.assertEqual(signal.trigger_count, 1)
        self.assertIsNotNone(signal.last_triggered_at)

    def test_non_matching_signal_does_nothing(self):
        self.service.register_signal_token(self.user, make_token())

        fired = self.service.consume_unlock_signal(
            self.user, make_token(), self.context,
        )

        self.assertFalse(fired)
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_signal_does_not_deactivate_after_firing(self):
        """Sustained coercion means repeated unlocks; silently disarming the
        alarm after the first would defeat the feature."""
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        self.service.consume_unlock_signal(self.user, token, self.context)
        self.service.consume_unlock_signal(self.user, token, self.context)

        signal.refresh_from_db()
        self.assertTrue(signal.is_active)
        self.assertEqual(signal.trigger_count, 2)

    def test_another_users_token_never_matches(self):
        token = make_token()
        self.service.register_signal_token(self.user, token)
        other = User.objects.create_user(
            username='other-user',
            email='other@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )

        fired = self.service.consume_unlock_signal(other, token, self.context)

        self.assertFalse(fired)

    def test_signal_with_no_configured_code_still_records_an_event(self):
        """The alarm must not be silently swallowed."""
        token = make_token()
        self.service.register_signal_token(self.user, token)

        fired = self.service.consume_unlock_signal(
            self.user, token, self.context,
        )

        self.assertTrue(fired)
        event = DuressEvent.objects.get(user=self.user)
        self.assertEqual(event.event_type, 'code_activated')
        self.assertEqual(event.ip_address, '203.0.113.10')

    def test_fallback_picks_highest_severity_code_not_alphabetical(self):
        """`order_by('-threat_level')` on a CharField would rank
        medium > low > high > critical -- the mildest response for the worst
        situation. Severity must be ranked explicitly."""
        token = make_token()
        self.service.register_signal_token(self.user, token)
        for level in ('low', 'medium', 'critical', 'high'):
            DuressCode.objects.create(
                user=self.user,
                code_hash=f'hash-{level}',
                threat_level=level,
                is_active=True,
            )

        self.service.consume_unlock_signal(self.user, token, self.context)

        event = DuressEvent.objects.filter(user=self.user).first()
        self.assertEqual(event.threat_level, 'critical')


class DuressSignalAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.register_url = reverse('duress-signal-register')
        self.report_url = reverse('duress-signal-report')

    def test_register_accepts_well_formed_token(self):
        response = self.client.post(
            self.register_url, {'token': make_token()}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(DuressSignal.objects.filter(user=self.user).exists())

    def test_register_rejects_wrong_length_token(self):
        response = self.client.post(
            self.register_url, {'token': 'too-short'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_returns_204_on_match(self):
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        response = self.client.post(
            self.report_url, {'signal': token}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_report_returns_identical_response_whether_or_not_it_matches(self):
        """The core indistinguishability property.

        A coercer holding the user's session can call this endpoint at will.
        Match, no-match, malformed, and no-signal-configured must be
        byte-identical, or they gain an oracle for whether the password they
        extracted was the real one.
        """
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        matching = self.client.post(
            self.report_url, {'signal': token}, format='json',
        )
        non_matching = self.client.post(
            self.report_url, {'signal': make_token()}, format='json',
        )
        malformed = self.client.post(
            self.report_url, {'signal': 'nope'}, format='json',
        )
        missing = self.client.post(self.report_url, {}, format='json')

        for response in (matching, non_matching, malformed, missing):
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(response.content, b'')

    def test_report_is_204_even_for_user_with_no_signal_configured(self):
        """Must not reveal that duress is unconfigured."""
        response = self.client.post(
            self.report_url, {'signal': make_token()}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b'')

    def test_endpoints_require_authentication(self):
        anon = APIClient()

        self.assertIn(
            anon.post(self.report_url, {'signal': make_token()}, format='json').status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            anon.post(self.register_url, {'token': make_token()}, format='json').status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_no_password_field_is_accepted_anywhere_in_this_flow(self):
        """ZK contract guard.

        Neither endpoint may grow a password/master_password parameter. If one
        ever does, the decision has moved server-side and the invariant in
        docs/adaptive-password-zk-remediation-plan.md §1 is broken.
        """
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        response = self.client.post(
            self.report_url,
            {'signal': make_token(), 'password': 'MyR3alP@ss'},
            format='json',
        )

        # The extra field is ignored, not honoured: no alarm, no error.
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DuressEvent.objects.count(), 0)

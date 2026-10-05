"""
HTTP contract for the endpoints BreachAlertsDashboard calls (Greptile, PR #515).

The dashboard must list ``vault.BreachAlert`` records and mark *those* read.
Listing ``MLBreachMatch`` rows (which have no ``is_read``) and "marking read"
through ``resolve_match`` left every alert unread again after a reload.

Literal paths are used on purpose: they are the contract the frontend hard-codes.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from ml_dark_web.models import (
    BreachSource, MLBreachData, MLBreachMatch, UserCredentialMonitoring,
)
from vault.models import BreachAlert

User = get_user_model()

LIST_URL = '/api/ml-darkweb/breach-alerts/'


def _mark_read_url(alert_id):
    return f'/api/ml-darkweb/mark-alert-read/{alert_id}/'


class BreachAlertsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alerts_owner', email='owner@example.com', password='x'
        )
        self.other = User.objects.create_user(
            username='alerts_other', email='other@example.com', password='x'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.alert = BreachAlert.objects.create(
            user=self.user,
            breach_name='Acme breach',
            breach_description='Acme leaked credentials',
            identifier='acme.example',
            exposed_data={'types': ['email'], 'confidence': 0.87},
            severity='high',
        )

    def test_list_carries_what_the_dashboard_renders(self):
        res = self.client.get(LIST_URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)
        item = res.data['alerts'][0]
        self.assertEqual(item['id'], self.alert.id)
        self.assertFalse(item['is_read'])
        self.assertFalse(item['resolved'])
        self.assertEqual(item['identifier'], 'acme.example')
        self.assertEqual(item['exposed_data']['confidence'], 0.87)

    def test_list_excludes_other_users_alerts(self):
        BreachAlert.objects.create(
            user=self.other, breach_name='Not yours', identifier='x.example'
        )

        res = self.client.get(LIST_URL)

        self.assertEqual([a['id'] for a in res.data['alerts']], [self.alert.id])

    @mock.patch('ml_dark_web.tasks.broadcast_alert_update.delay')
    def test_mark_read_persists_across_a_reload(self, broadcast):
        res = self.client.post(_mark_read_url(self.alert.id))

        self.assertEqual(res.status_code, 200)
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_read)
        self.assertIsNotNone(self.alert.read_at)
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.kwargs['alert_id'], self.alert.id)
        self.assertEqual(broadcast.call_args.kwargs['update_type'], 'marked_read')

        # "Reload": the next list must still report it read.
        reloaded = self.client.get(LIST_URL).data['alerts'][0]
        self.assertTrue(reloaded['is_read'])

    @mock.patch('ml_dark_web.tasks.broadcast_alert_update.delay')
    def test_mark_read_rejects_other_users_alert(self, broadcast):
        foreign = BreachAlert.objects.create(
            user=self.other, breach_name='Not yours', identifier='x.example'
        )

        res = self.client.post(_mark_read_url(foreign.id))

        self.assertEqual(res.status_code, 404)
        foreign.refresh_from_db()
        self.assertFalse(foreign.is_read)
        broadcast.assert_not_called()

    def test_list_pages_through_every_alert_without_overlap(self):
        # Same detected_at on purpose: `-id` must keep the pages stable.
        for i in range(4):
            BreachAlert.objects.create(
                user=self.user, breach_name=f'extra {i}', identifier='x.example',
                detected_at=self.alert.detected_at,
            )  # 5 alerts in total with setUp's

        first = self.client.get(LIST_URL, {'limit': 2}).data
        second = self.client.get(LIST_URL, {'limit': 2, 'offset': 2}).data
        third = self.client.get(LIST_URL, {'limit': 2, 'offset': 4}).data

        self.assertEqual([first['count'], second['count'], third['count']], [2, 2, 1])
        self.assertEqual(
            [first['has_more'], second['has_more'], third['has_more']], [True, True, False]
        )
        ids = [a['id'] for page in (first, second, third) for a in page['alerts']]
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_list_rejects_non_integer_pagination_with_400(self):
        for params in ({'offset': 'abc'}, {'limit': 'abc'}, {'offset': ''}):
            res = self.client.get(LIST_URL, params)

            self.assertEqual(res.status_code, 400, params)
            self.assertEqual(res.data, {'error': 'invalid_pagination'})

    def test_list_reports_data_type_so_scan_alerts_can_be_labelled(self):
        scan = BreachAlert.objects.create(
            user=self.user, breach_name='Scan hit', identifier='person@example.net',
            data_type='email',
        )

        by_id = {a['id']: a for a in self.client.get(LIST_URL).data['alerts']}

        self.assertEqual(by_id[scan.id]['data_type'], 'email')
        self.assertEqual(by_id[scan.id]['identifier'], 'person@example.net')

    def test_list_caps_limit_and_ignores_negative_offset(self):
        res = self.client.get(LIST_URL, {'limit': 100000, 'offset': -5})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)
        self.assertFalse(res.data['has_more'])

    # breach_matches / resolve_match share the mount with the alert endpoints
    # and must stay scoped to request.user too.
    def _create_match(self, user):
        source = BreachSource.objects.create(
            name='Test source', url='https://example.com', source_type='forum',
        )
        breach = MLBreachData.objects.create(
            breach_id=f'test-{user.pk}', title='Test breach',
            description='Test description', source=source, severity='HIGH',
            confidence_score=0.9, raw_content='Test content',
        )
        credential = UserCredentialMonitoring.objects.create(
            user=user, email_hash=f'{user.pk:064x}', domain=f'{user.username}.example',
        )
        return MLBreachMatch.objects.create(
            user=user, breach=breach, monitored_credential=credential,
            similarity_score=0.9, confidence_score=0.9,
        )

    def test_breach_matches_excludes_other_users_matches(self):
        own = self._create_match(self.user)
        self._create_match(self.other)

        res = self.client.get('/api/ml-darkweb/breach_matches/')

        self.assertEqual(res.status_code, 200)
        self.assertEqual([m['id'] for m in res.data], [own.id])

    def test_resolve_match_rejects_other_users_match(self):
        foreign = self._create_match(self.other)

        res = self.client.post('/api/ml-darkweb/resolve_match/', {'match_id': foreign.id})

        self.assertEqual(res.status_code, 404)
        foreign.refresh_from_db()
        self.assertFalse(foreign.resolved)

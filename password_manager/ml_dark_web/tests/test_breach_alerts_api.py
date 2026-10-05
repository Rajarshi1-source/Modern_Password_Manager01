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

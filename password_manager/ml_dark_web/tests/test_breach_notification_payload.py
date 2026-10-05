"""
The real-time `breach_alert` payload must match what the frontend reads.

BreachAlertsDashboard.handleNewAlert and BreachToast (and the test_breach_alert
management command) use `title`, UPPERCASE `severity`, and `confidence` /
`domain`; the producer used to send `breach_name` and lowercase `severity` only,
so live alerts showed a generic title and fell back to MEDIUM styling.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from ml_dark_web.tasks import send_breach_notification
from vault.models import BreachAlert

User = get_user_model()


class _FakeChannelLayer:
    def __init__(self):
        self.sent = []

    async def group_send(self, group, event):
        self.sent.append((group, event))


class BreachNotificationPayloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='notify_owner', email='notify@example.com', password='x'
        )
        self.layer = _FakeChannelLayer()

    def _send(self, alert):
        with mock.patch('channels.layers.get_channel_layer', return_value=self.layer):
            result = send_breach_notification(alert.id)
        self.assertTrue(result['success'], result)
        ((group, event),) = self.layer.sent
        self.assertEqual(group, f'user_{self.user.id}')
        self.assertEqual(event['type'], 'breach_alert')
        return event['message']

    def test_ml_alert_payload_carries_what_the_frontend_reads(self):
        alert = BreachAlert.objects.create(
            user=self.user, breach_name='Acme breach', breach_description='Leaked',
            identifier='acme.example', severity='high',
            exposed_data={'types': ['email'], 'confidence': 0.87},
        )

        message = self._send(alert)

        self.assertEqual(message['alert_id'], alert.id)
        self.assertEqual(message['title'], 'Acme breach')
        self.assertEqual(message['breach_name'], 'Acme breach')  # kept for existing readers
        self.assertEqual(message['severity'], 'HIGH')
        self.assertEqual(message['confidence'], 0.87)
        self.assertEqual(message['domain'], 'acme.example')

    def test_scan_alert_payload_omits_confidence_and_domain(self):
        # Breach-scan alerts store an email / vault item id in `identifier`.
        alert = BreachAlert.objects.create(
            user=self.user, breach_name='Scan hit', identifier='person@example.net',
            data_type='email', severity='medium',
        )

        message = self._send(alert)

        self.assertEqual(message['title'], 'Scan hit')
        self.assertEqual(message['severity'], 'MEDIUM')
        self.assertNotIn('confidence', message)
        self.assertNotIn('domain', message)

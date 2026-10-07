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
    """Minimal channel layer that records group_send calls."""
    def __init__(self):
        """Start with no recorded sends."""
        self.sent = []

    async def group_send(self, group, event):
        """Record the group and event instead of delivering them."""
        self.sent.append((group, event))


class BreachNotificationPayloadTests(TestCase):
    """The real-time payload carries what the frontend reads."""
    def setUp(self):
        """Create the alert owner and a fake channel layer."""
        self.user = User.objects.create_user(
            username='notify_owner', email='notify@example.com', password='x'
        )
        self.layer = _FakeChannelLayer()

    def _send(self, alert):
        """Run the task for ``alert`` and return the single message it sent."""
        with mock.patch('channels.layers.get_channel_layer', return_value=self.layer):
            result = send_breach_notification(alert.id)
        self.assertTrue(result['success'], result)
        ((group, event),) = self.layer.sent
        self.assertEqual(group, f'user_{self.user.id}')
        self.assertEqual(event['type'], 'breach_alert')
        return event['message']

    def test_ml_alert_payload_carries_what_the_frontend_reads(self):
        """An ML alert sends title, uppercase severity, confidence and domain."""
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

    def test_non_object_exposed_data_still_sends_the_alert(self):
        """A list-valued exposed_data must not stop the notification being sent."""
        alert = BreachAlert.objects.create(
            user=self.user, breach_name='Odd data', identifier='odd.example',
            severity='low', exposed_data=['email'],
        )

        message = self._send(alert)

        self.assertEqual(message['title'], 'Odd data')
        self.assertNotIn('confidence', message)
        alert.refresh_from_db()
        self.assertTrue(alert.notified)

    def test_scan_alert_payload_omits_confidence_and_domain(self):
        """A breach-scan alert sends no confidence or domain."""
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

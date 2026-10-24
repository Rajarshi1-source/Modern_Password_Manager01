"""
Predictive-intent audit records are actually written.

vault's AuditLog has action (max_length=20), item_type and status; it has no
`details` field. These four writes passed `details=` and over-length actions,
so every one raised (TypeError, or a Postgres DataError for the length) into
an `except` that swallowed it, and nothing was ever recorded.
"""
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ml_security.services.predictive_intent_service import PredictiveIntentService
from vault.models import AuditLog


class PredictiveIntentAuditLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        self.service = PredictiveIntentService.__new__(PredictiveIntentService)

    def _actions(self):
        return list(AuditLog.objects.filter(user=self.user).values_list('action', flat=True))

    def test_preload_and_access_events_are_recorded(self):
        self.service._log_preload_event(
            self.user, SimpleNamespace(item_id='i'),
            SimpleNamespace(id='p', confidence_score=0.9, prediction_reason='r'))
        self.service._log_credential_access(
            self.user, SimpleNamespace(id='x', vault_item_id='i', delivery_count=1))
        self.assertEqual(sorted(self._actions()), ['credential_preload', 'preload_access'])

    def test_every_action_fits_the_column(self):
        max_length = AuditLog._meta.get_field('action').max_length
        for action in ('predictive_export', 'predictive_delete', 'credential_preload', 'preload_access'):
            self.assertLessEqual(len(action), max_length, action)

    def test_export_and_delete_are_recorded(self):
        client = APIClient()
        client.force_authenticate(self.user)
        exported = client.get(reverse('ml_security:intent_export'))
        deleted = client.delete(reverse('ml_security:intent_delete_data') + '?confirm=true')
        self.assertLess(exported.status_code, 500, exported.content[:300])
        self.assertLess(deleted.status_code, 500, deleted.content[:300])
        self.assertIn('predictive_export', self._actions())
        self.assertIn('predictive_delete', self._actions())

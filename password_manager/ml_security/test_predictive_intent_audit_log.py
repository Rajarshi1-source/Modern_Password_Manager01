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

    def _preload(self, create):
        """Run preload_credentials over one prediction with the given create."""
        from unittest.mock import MagicMock, patch
        from ml_security.services import predictive_intent_service as module
        prediction = SimpleNamespace(
            predicted_vault_item=SimpleNamespace(item_id='i', encrypted_data='x'),
            prediction_reason='r', confidence_score=0.95)
        predictions = MagicMock()
        predictions.select_related.return_value.order_by.return_value.__getitem__.return_value = [prediction]
        service = PredictiveIntentService()
        with patch.object(module.IntentPrediction.objects, 'filter', return_value=predictions), \
                patch.object(module.PreloadedCredential.objects, 'filter') as existing, \
                patch.object(module.PreloadedCredential.objects, 'create', side_effect=create):
            existing.return_value.exists.return_value = False
            return service.preload_credentials(self.user, b'k' * 32, 'session-key-id')

    def test_a_failed_preload_records_no_success(self):
        self.assertEqual(self._preload(RuntimeError('insert failed')), [])
        self.assertNotIn('credential_preload', self._actions())

        stored = object()
        self.assertEqual(self._preload(lambda **kwargs: stored), [stored])
        self.assertEqual(self._actions(), ['credential_preload'])

    def test_every_action_fits_the_column_and_is_a_choice(self):
        field = AuditLog._meta.get_field('action')
        choices = dict(field.choices)
        for action in ('predictive_export', 'predictive_delete', 'credential_preload', 'preload_access',
                       'password_reset', 'password_reset_req'):
            self.assertLessEqual(len(action), field.max_length, action)
            self.assertIn(action, choices)

    def test_export_and_delete_are_recorded(self):
        client = APIClient()
        client.force_authenticate(self.user)
        exported = client.get(reverse('ml_security:intent_export'))
        deleted = client.delete(reverse('ml_security:intent_delete_data') + '?confirm=true')
        self.assertLess(exported.status_code, 500, exported.content[:300])
        self.assertLess(deleted.status_code, 500, deleted.content[:300])
        self.assertIn('predictive_export', self._actions())
        self.assertIn('predictive_delete', self._actions())

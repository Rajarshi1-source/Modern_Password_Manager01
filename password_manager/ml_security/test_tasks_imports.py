"""
Regression test: the ml_security Celery tasks must get past their imports.

``ml_security`` is a top-level app, so inside ``ml_security/tasks.py`` a
double-dot import (``from ..predictive_intent_models import ...``) points above
the top-level package and raises ``ImportError: attempted relative import beyond
top-level package``. The imports sit at the top of each task body, before the
``try:``, so the module imports fine and Celery registers the tasks, but every
run raised instead of returning a handled result.

Each task is run for real against the (empty) test database rather than mocked:
the tasks swallow query errors into ``{'status': 'error'}``, so asserting on the
returned status also proves the queries beneath the imports are valid.
``CleanupExpiredPredictionsTests`` additionally runs against populated tables so
the deletion itself is covered, not just "returns success".
"""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ml_security import tasks
from ml_security.predictive_intent_models import (
    ContextSignal, IntentPrediction, PreloadedCredential,
)
from vault.models import EncryptedVaultItem

User = get_user_model()


class MlSecurityTaskImportTests(TestCase):
    """Every task gets past its imports and returns a handled result."""

    def _assert_ran(self, result, expected):
        """Assert a task returned a dict with the expected status."""
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('status'), expected, result)

    def test_train_intent_model_gets_past_its_imports(self):
        """With no training data the task skips instead of raising."""
        self._assert_ran(tasks.train_intent_model(), 'skipped')

    def test_cleanup_expired_predictions_gets_past_its_imports(self):
        """The cleanup task runs cleanly on empty tables."""
        self._assert_ran(tasks.cleanup_expired_predictions(), 'success')

    def test_cleanup_old_patterns_gets_past_its_imports(self):
        """The retention cleanup runs cleanly on empty tables."""
        self._assert_ran(tasks.cleanup_old_patterns(), 'success')

    def test_preload_morning_credentials_gets_past_its_imports(self):
        """The morning preload runs cleanly with no active users."""
        self._assert_ran(tasks.preload_morning_credentials(), 'success')

    def test_analyze_usage_patterns_gets_past_its_imports(self):
        """The usage analysis runs cleanly on empty tables."""
        self._assert_ran(tasks.analyze_usage_patterns(), 'success')


class CleanupExpiredPredictionsTests(TestCase):
    """cleanup_expired_predictions deletes what it should and keeps the rest."""

    def setUp(self):
        """Create a user and the vault item every prediction points at."""
        self.user = User.objects.create_user(
            username='cleanup_owner', email='cleanup@example.com', password='x'
        )
        self.item = EncryptedVaultItem.objects.create(
            user=self.user, item_id=f'item-{uuid.uuid4().hex[:8]}',
            item_type='password', encrypted_data='ciphertext',
        )
        self.now = timezone.now()

    def _prediction(self, expires_in, was_used=None):
        """Create a prediction expiring ``expires_in`` from now."""
        return IntentPrediction.objects.create(
            user=self.user, predicted_vault_item=self.item, confidence_score=0.9,
            prediction_reason='time_pattern', expires_at=self.now + expires_in,
            was_used=was_used,
        )

    def test_deletes_expired_data_and_keeps_live_data(self):
        """Expired rows go; live and recently-used rows stay (7-day analytics window)."""
        expired_unused = self._prediction(-timedelta(hours=1))
        old_used = self._prediction(-timedelta(days=8), was_used=True)
        live = self._prediction(timedelta(hours=1))
        recently_used = self._prediction(-timedelta(days=1), was_used=True)

        def preload(prediction, expires_in):
            """Create a preloaded credential tied to ``prediction``."""
            return PreloadedCredential.objects.create(
                user=self.user, vault_item=self.item, prediction=prediction,
                encrypted_credential=b'x', encryption_iv=b'iv', session_key_id='sk',
                preload_reason='time_pattern', confidence_at_preload=0.9,
                expires_at=self.now + expires_in,
            )

        expired_preload = preload(live, -timedelta(minutes=5))
        live_preload = preload(live, timedelta(hours=1))

        stale_signal = ContextSignal.objects.create(user=self.user, current_domain='a.example')
        live_signal = ContextSignal.objects.create(user=self.user, current_domain='b.example')
        # `timestamp` is auto_now_add, so age the stale row with an update.
        ContextSignal.objects.filter(pk=stale_signal.pk).update(
            timestamp=self.now - timedelta(hours=25)
        )

        result = tasks.cleanup_expired_predictions()

        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(result['deleted'], {
            'unused_predictions': 1, 'old_predictions': 1,
            'preloaded_credentials': 1, 'context_signals': 1,
        })
        remaining = set(IntentPrediction.objects.values_list('pk', flat=True))
        self.assertEqual(remaining, {live.pk, recently_used.pk})
        self.assertFalse(IntentPrediction.objects.filter(pk__in=[expired_unused.pk, old_used.pk]).exists())
        # No stale credential may survive; the live one must.
        self.assertFalse(PreloadedCredential.objects.filter(pk=expired_preload.pk).exists())
        self.assertTrue(PreloadedCredential.objects.filter(pk=live_preload.pk).exists())
        self.assertFalse(ContextSignal.objects.filter(pk=stale_signal.pk).exists())
        self.assertTrue(ContextSignal.objects.filter(pk=live_signal.pk).exists())

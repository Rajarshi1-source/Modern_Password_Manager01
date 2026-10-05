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
"""
from django.test import TestCase

from ml_security import tasks


class MlSecurityTaskImportTests(TestCase):
    def _assert_ran(self, result, expected):
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('status'), expected, result)

    def test_train_intent_model_gets_past_its_imports(self):
        # No training data -> a handled skip, not an ImportError or an error.
        self._assert_ran(tasks.train_intent_model(), 'skipped')

    def test_cleanup_expired_predictions_gets_past_its_imports(self):
        self._assert_ran(tasks.cleanup_expired_predictions(), 'success')

    def test_cleanup_old_patterns_gets_past_its_imports(self):
        self._assert_ran(tasks.cleanup_old_patterns(), 'success')

    def test_preload_morning_credentials_gets_past_its_imports(self):
        self._assert_ran(tasks.preload_morning_credentials(), 'success')

    def test_analyze_usage_patterns_gets_past_its_imports(self):
        self._assert_ran(tasks.analyze_usage_patterns(), 'success')

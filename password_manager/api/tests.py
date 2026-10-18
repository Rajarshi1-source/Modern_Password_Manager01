from unittest.mock import patch

from django.test import RequestFactory, TestCase

from api.health import health_check


class HealthCheckErrorDisclosureTests(TestCase):
    """/health/ is unauthenticated: failures must not echo exception text."""

    SECRET = 'could not connect to server db-internal.example:5432 as pm_user'

    def test_database_error_text_not_in_response(self):
        with patch('api.health.connection.cursor', side_effect=Exception(self.SECRET)):
            response = health_check(RequestFactory().get('/health/'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'db-internal', response.content)
        self.assertIn(b'"database": "error"', response.content)

    def test_cache_error_text_not_in_response(self):
        with patch('api.health.cache.set', side_effect=Exception(self.SECRET)):
            response = health_check(RequestFactory().get('/health/'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'db-internal', response.content)
        self.assertIn(b'"cache": "error"', response.content)

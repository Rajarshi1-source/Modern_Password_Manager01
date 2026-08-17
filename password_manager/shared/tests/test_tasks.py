"""
Tests for shared/tasks.py.

`cleanup-expired-sessions` in celery.py scheduled `shared.tasks.cleanup_expired_sessions`
against an app that had no `tasks.py` at all -- this is coverage for the task
added to fill that gap.
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class CleanupExpiredSessionsTaskTests(TestCase):
    def test_deletes_only_expired_sessions(self):
        from shared.tasks import cleanup_expired_sessions

        expired = SessionStore()
        expired['probe'] = 'expired'
        expired.set_expiry(-1)  # already in the past
        expired.save()

        live = SessionStore()
        live['probe'] = 'live'
        live.set_expiry(3600)
        live.save()

        result = cleanup_expired_sessions()

        self.assertEqual(result['expired_sessions_deleted'], 1)
        self.assertFalse(SessionStore().exists(expired.session_key))
        self.assertTrue(SessionStore().exists(live.session_key))

    def test_noop_when_nothing_expired(self):
        from shared.tasks import cleanup_expired_sessions

        live = SessionStore()
        live['probe'] = 'live'
        live.set_expiry(3600)
        live.save()

        result = cleanup_expired_sessions()

        self.assertEqual(result['expired_sessions_deleted'], 0)
        self.assertTrue(SessionStore().exists(live.session_key))

"""
Tests for `check_expired_deaddrops`.

This task was never scheduled in production until
docs/privacy-features-gap-remediation-plan.md §21 -- see
`password_manager/celery.py`'s beat_schedule merge. Its first activation (or
any future beat/worker outage lasting past several ticks) could otherwise
find an unbounded backlog and process the entire thing in one task
invocation: one DB write plus one notification-task publish per row. These
tests exist to pin the batch cap that bounds that, and the filter boundaries
`check_deaddrop_backlog` (the pre-deploy report) mirrors and must stay in
sync with.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from mesh_deaddrop.models import DeadDrop
from mesh_deaddrop.tasks.deaddrop_tasks import (
    EXPIRE_BATCH_SIZE,
    check_expired_deaddrops,
)


class CheckExpiredDeaddropsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='deaddrop-owner',
            email='owner@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

    def _make_drop(self, **overrides):
        defaults = dict(
            owner=self.user,
            title='drop',
            latitude='51.500000',
            longitude='-0.120000',
            encrypted_secret=b'x',
            secret_hash='hash',
            status='active',
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1),
        )
        defaults.update(overrides)
        return DeadDrop.objects.create(**defaults)

    def test_marks_expired_and_notifies(self):
        drop = self._make_drop()

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            result = check_expired_deaddrops()

        drop.refresh_from_db()
        self.assertEqual(drop.status, 'expired')
        self.assertFalse(drop.is_active)
        mock_notify.assert_called_once_with(str(drop.id))
        self.assertEqual(result, {'expired_count': 1, 'deferred_count': 0})

    def test_caps_batch_size_and_defers_the_rest(self):
        """The behaviour this task exists to add: a backlog bigger than
        EXPIRE_BATCH_SIZE must not all be processed -- and be mailed -- in
        one tick. Rows past the cap stay exactly as they were, so the same
        query catches them on the next tick rather than silently skipping
        them."""
        overflow = 3
        drops = [self._make_drop() for _ in range(EXPIRE_BATCH_SIZE + overflow)]

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            result = check_expired_deaddrops()

        self.assertEqual(result, {
            'expired_count': EXPIRE_BATCH_SIZE,
            'deferred_count': overflow,
        })
        self.assertEqual(mock_notify.call_count, EXPIRE_BATCH_SIZE)

        expired_ids = {d.id for d in DeadDrop.objects.filter(status='expired')}
        still_active_ids = {d.id for d in DeadDrop.objects.filter(status='active')}
        self.assertEqual(len(expired_ids), EXPIRE_BATCH_SIZE)
        self.assertEqual(len(still_active_ids), overflow)
        self.assertEqual(expired_ids | still_active_ids, {d.id for d in drops})

    def test_batch_takes_the_oldest_overdue_first(self):
        """Ordering matters once a backlog exceeds the cap: the drop overdue
        the LONGEST must not be the one perpetually pushed to "next tick" by
        a steady stream of newer arrivals every hour. Exceeds the cap by
        exactly one so there is a single, unambiguous drop that must be the
        one deferred: whichever expired most recently."""
        oldest_first = [
            self._make_drop(expires_at=timezone.now() - timedelta(days=10, minutes=-i))
            for i in range(EXPIRE_BATCH_SIZE)
        ]
        newest = self._make_drop(expires_at=timezone.now() - timedelta(minutes=1))

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ):
            check_expired_deaddrops()

        for drop in oldest_first:
            drop.refresh_from_db()
            self.assertEqual(drop.status, 'expired')
        newest.refresh_from_db()
        self.assertEqual(newest.status, 'active')

    def test_future_expiry_is_not_touched(self):
        drop = self._make_drop(expires_at=timezone.now() + timedelta(days=1))

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            result = check_expired_deaddrops()

        drop.refresh_from_db()
        self.assertEqual(drop.status, 'active')
        mock_notify.assert_not_called()
        self.assertEqual(result, {'expired_count': 0, 'deferred_count': 0})

    def test_already_expired_status_is_not_touched_again(self):
        """status__in=[pending, distributed, active] -- a drop already
        marked 'expired' must not be re-processed or re-mailed."""
        drop = self._make_drop(status='expired')

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            check_expired_deaddrops()

        mock_notify.assert_not_called()
        drop.refresh_from_db()
        self.assertEqual(drop.status, 'expired')

    def test_inactive_drop_is_not_touched(self):
        drop = self._make_drop(is_active=False)

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            check_expired_deaddrops()

        mock_notify.assert_not_called()
        drop.refresh_from_db()
        self.assertFalse(drop.is_active)

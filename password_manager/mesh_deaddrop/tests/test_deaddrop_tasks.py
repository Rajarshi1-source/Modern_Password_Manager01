"""
Tests for `check_expired_deaddrops` and `notify_owner_deaddrop_expired`.

`check_expired_deaddrops` was never scheduled in production until
docs/privacy-features-gap-remediation-plan.md §21 -- see
`password_manager/celery.py`'s beat_schedule merge. Its first activation (or
any future beat/worker outage lasting past several ticks) could otherwise
find an unbounded backlog and process the entire thing in one task
invocation: one DB write plus one notification-task publish per row.
`CheckExpiredDeaddropsTests` pins the batch cap that bounds that, the
publish-before-save ordering that keeps a broker hiccup from silently and
permanently losing a row's notification, and the filter boundaries
`check_deaddrop_backlog` (the pre-deploy report) mirrors and must stay in
sync with.

`NotifyOwnerDeaddropExpiredTests` covers the companion fix: `send_mail`
failures used to be caught and logged with no way to ever recover them --
now they propagate into the task's own `autoretry_for`.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from mesh_deaddrop.models import DeadDrop
from mesh_deaddrop.tasks.deaddrop_tasks import (
    EXPIRE_BATCH_SIZE,
    check_expired_deaddrops,
    notify_owner_deaddrop_expired,
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
            secret_hash='hash',  # noqa: S106 -- fixture data, not a credential
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

    def test_publish_failure_leaves_the_drop_unmarked_for_retry(self):
        """Publish happens BEFORE the status write, not after. If it were the
        other way around, a .delay() failure right after a successful
        .save() would leave the row 'expired' -- which drops it out of this
        task's own filter -- with no notification ever queued for it and no
        future tick able to find it again. Publishing first means a failure
        here instead leaves the row exactly as it was, so the same query
        matches it again next tick. Also confirms a failure on one row
        doesn't abort the rest of the batch."""
        failing = self._make_drop()
        healthy = self._make_drop()

        def delay_side_effect(dead_drop_id):
            if dead_drop_id == str(failing.id):
                raise ConnectionError('broker unreachable')

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay',
            side_effect=delay_side_effect,
        ) as mock_notify:
            result = check_expired_deaddrops()

        failing.refresh_from_db()
        healthy.refresh_from_db()
        self.assertEqual(failing.status, 'active')
        self.assertTrue(failing.is_active)
        self.assertEqual(healthy.status, 'expired')
        self.assertFalse(healthy.is_active)
        self.assertEqual(mock_notify.call_count, 2)
        self.assertEqual(result, {'expired_count': 1, 'deferred_count': 1})

    def test_concurrent_collection_is_not_overwritten_back_to_expired(self):
        """`batch` is read once, upfront -- a snapshot. If a drop is
        successfully collected (DeadDropCollectView has no expiry check of
        its own, so a collection already in flight can still complete after
        the drop technically crosses expires_at) in the window between that
        snapshot and this row's own turn in the loop, the task must notice
        and back off, not blindly overwrite the real 'collected' status
        back to 'expired' and send a wrong "expired unclaimed" email for a
        secret the owner actually received.

        Simulates the race deterministically rather than with real threads:
        `processed_first` (the more-overdue of the two, so it sorts first
        in the batch) has a .delay() side effect that marks the OTHER drop
        collected via a direct DB update -- standing in for a concurrent
        request finishing in the window before `collected`'s own turn comes
        up. `collected`'s per-row select_for_update().get() re-fetch must
        see that write (a fresh DB read, not the stale snapshot object) and
        back off."""
        processed_first = self._make_drop(expires_at=timezone.now() - timedelta(days=5))
        collected = self._make_drop(expires_at=timezone.now() - timedelta(days=1))

        def delay_side_effect(dead_drop_id):
            if dead_drop_id == str(processed_first.id):
                DeadDrop.objects.filter(pk=collected.pk).update(
                    status='collected', collected_at=timezone.now(), is_active=False,
                )

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay',
            side_effect=delay_side_effect,
        ) as mock_notify:
            result = check_expired_deaddrops()

        processed_first.refresh_from_db()
        collected.refresh_from_db()
        self.assertEqual(processed_first.status, 'expired')
        self.assertEqual(collected.status, 'collected')
        # Exactly one notify call -- collected's own recheck caught the
        # race and skipped it entirely, not just skipped the final save.
        mock_notify.assert_called_once_with(str(processed_first.id))
        self.assertEqual(result, {'expired_count': 1, 'deferred_count': 1})

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


class NotifyOwnerDeaddropExpiredTests(TestCase):
    """`.run()`, not `.delay()`/`.apply()`: this project's TESTING settings
    point the Celery broker at `'memory://'` specifically so `.delay()`
    never executes a task body in tests (see the settings comment on
    CELERY_BROKER_URL) -- `.run()` is the standard way to exercise a
    `@shared_task`'s own logic directly, bypassing that entirely along with
    the `autoretry_for` dispatch wrapper this task now carries.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='deaddrop-owner',
            email='owner@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        self.drop = DeadDrop.objects.create(
            owner=self.user,
            title='drop',
            latitude='51.500000',
            longitude='-0.120000',
            encrypted_secret=b'x',
            secret_hash='hash',  # noqa: S106 -- fixture data, not a credential
            status='expired',
            is_active=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

    def test_sends_the_email(self):
        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.send_mail'
        ) as mock_send:
            notify_owner_deaddrop_expired.run(str(self.drop.id))

        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args.kwargs['recipient_list'], [self.user.email],
        )

    def test_send_mail_failure_is_no_longer_silently_swallowed(self):
        """The bug this fixes: send_mail's exception used to be caught and
        logged with no way to ever recover it. It must now propagate, so
        the task-level autoretry_for=(Exception,) (see the @shared_task
        decorator) actually gets a chance to retry it."""
        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.send_mail',
            side_effect=ConnectionError('smtp relay unreachable'),
        ):
            with self.assertRaises(ConnectionError):
                notify_owner_deaddrop_expired.run(str(self.drop.id))

    def test_missing_drop_does_not_raise(self):
        """Not a transient failure -- retrying would never fix it, so this
        must still return quietly rather than propagate into autoretry."""
        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.send_mail'
        ) as mock_send:
            notify_owner_deaddrop_expired.run('00000000-0000-0000-0000-000000000000')

        mock_send.assert_not_called()

    def test_owner_with_no_email_does_not_raise(self):
        self.user.email = ''
        self.user.save()

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.send_mail'
        ) as mock_send:
            notify_owner_deaddrop_expired.run(str(self.drop.id))

        mock_send.assert_not_called()


class CheckExpiredDeaddropsRealConcurrencyTests(TransactionTestCase):
    """The mocked-side-effect race in `CheckExpiredDeaddropsTests` pins the
    per-row recheck's LOGIC (a fresh fetch sees a change made in between),
    but that test runs everything on one connection/transaction, so it
    cannot demonstrate the select_for_update() LOCK doing anything -- a
    connection never blocks against its own held lock. This class uses a
    second real thread and a real, separate connection, mirroring
    security/tests/test_duress_signal.py::RegisterSignalTokenConcurrencyTests
    (same reasoning: TransactionTestCase + threads, not TestCase + mocks,
    is what actually exercises row-level MVCC locking)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='deaddrop-owner-race',
            email='owner@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        self.drop = DeadDrop.objects.create(
            owner=self.user,
            title='drop',
            latitude='51.500000',
            longitude='-0.120000',
            encrypted_secret=b'x',
            secret_hash='hash',  # noqa: S106 -- fixture data, not a credential
            status='active',
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1),
        )

    def test_real_concurrent_collection_wins_the_lock_and_is_not_overwritten(self):
        import threading

        from django.db import connection, connections

        if connection.vendor == 'sqlite':
            # Same reasoning as RegisterSignalTokenConcurrencyTests
            # (test_duress_signal.py): SQLite serializes writers at the file
            # level rather than row-locking, so this can't distinguish a
            # correct select_for_update() from a missing one. Runs against
            # Postgres in CI.
            self.skipTest(
                "select_for_update() row-locking needs real MVCC. SQLite "
                "serializes writers at the file level instead. Runs against "
                "Postgres in CI."
            )

        collector_has_locked = threading.Event()
        collector_may_commit = threading.Event()
        errors = []
        errors_lock = threading.Lock()

        def collector():
            """Holds its own row lock open (via an unsaved manual
            transaction) until the expiry task has had a chance to try --
            and block -- on the same row, then commits the collection."""
            from django.db import transaction as txn

            try:
                with txn.atomic():
                    row = DeadDrop.objects.select_for_update().get(pk=self.drop.pk)
                    collector_has_locked.set()
                    if not collector_may_commit.wait(timeout=5):
                        raise RuntimeError('expiry task never blocked on the lock')
                    row.status = 'collected'
                    row.collected_at = timezone.now()
                    row.is_active = False
                    row.save()
            except Exception as exc:  # noqa: BLE001 - surfaced on the main thread below
                with errors_lock:
                    errors.append(exc)
            finally:
                connections.close_all()

        collector_thread = threading.Thread(target=collector)
        collector_thread.start()
        self.assertTrue(
            collector_has_locked.wait(timeout=5),
            'collector thread never acquired its lock',
        )

        # The expiry task's own select_for_update() on the same row must now
        # block behind the collector's open transaction. Signal it to
        # commit shortly after the main thread's call is issued, so the
        # task's lock acquisition genuinely waits rather than racing a
        # collector that finished before check_expired_deaddrops even
        # started.
        def release_soon():
            collector_may_commit.set()

        threading.Timer(0.3, release_soon).start()

        with mock.patch(
            'mesh_deaddrop.tasks.deaddrop_tasks.notify_owner_deaddrop_expired.delay'
        ) as mock_notify:
            result = check_expired_deaddrops()

        collector_thread.join(timeout=5)
        self.assertEqual(errors, [], f"collector thread failed: {errors}")

        self.drop.refresh_from_db()
        self.assertEqual(self.drop.status, 'collected')
        mock_notify.assert_not_called()
        self.assertEqual(result, {'expired_count': 0, 'deferred_count': 1})

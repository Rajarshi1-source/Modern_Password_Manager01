"""
Tests for security/tasks/time_lock_tasks.py -- the Celery task layer for the
Password Will / Dead Man's Switch / Escrow feature.

Before this test module, none of these six task functions had ever been
invoked under test: test_time_lock.py covers the API and model layers only.
celery.py never merged time_lock_tasks.CELERY_BEAT_SCHEDULE into its own
beat_schedule, so `check_capsule_unlocks`, `check_dead_mans_switches`,
`check_expired_capsules`, and `check_escrow_deadlines` had never run in
production either -- these tests are the first real exercise of this code.

`send_mail` is mocked throughout. These tests must never attempt a real SMTP
connection -- EMAIL_BACKEND defaults to django.core.mail.backends.smtp.EmailBackend.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from security.models import (
    TimeLockCapsule,
    PasswordWill,
    CapsuleBeneficiary,
    EscrowAgreement,
)


def make_capsule(owner, capsule_type='general', **overrides):
    defaults = dict(
        owner=owner,
        title='Test Capsule',
        encrypted_data=b'data',
        encryption_key_encrypted=b'key',
        unlock_at=timezone.now() + timedelta(hours=1),
        delay_seconds=3600,
        mode='server',
        status='locked',
        capsule_type=capsule_type,
    )
    defaults.update(overrides)
    return TimeLockCapsule.objects.create(**defaults)


class CheckCapsuleUnlocksTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pass123!')

    @patch('security.tasks.time_lock_tasks.notify_beneficiary')
    def test_unlocks_ready_capsule_and_fans_out_notifications(self, mock_notify):
        from security.tasks.time_lock_tasks import check_capsule_unlocks

        capsule = make_capsule(
            self.owner,
            unlock_at=timezone.now() - timedelta(minutes=1),
        )
        beneficiary = CapsuleBeneficiary.objects.create(
            capsule=capsule, email='ben@example.com', name='Ben',
        )

        result = check_capsule_unlocks()

        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'unlocked')
        self.assertIsNotNone(capsule.opened_at)
        self.assertEqual(result['unlocked'], 1)
        mock_notify.delay.assert_called_once_with(
            capsule_id=str(capsule.id),
            beneficiary_id=str(beneficiary.id),
        )

    @patch('security.tasks.time_lock_tasks.notify_beneficiary')
    def test_leaves_not_yet_due_capsule_locked(self, mock_notify):
        from security.tasks.time_lock_tasks import check_capsule_unlocks

        capsule = make_capsule(
            self.owner,
            unlock_at=timezone.now() + timedelta(hours=2),
        )

        result = check_capsule_unlocks()

        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'locked')
        self.assertEqual(result['unlocked'], 0)
        mock_notify.delay.assert_not_called()

    @patch('security.tasks.time_lock_tasks.notify_beneficiary')
    def test_does_not_renotify_already_notified_beneficiary(self, mock_notify):
        from security.tasks.time_lock_tasks import check_capsule_unlocks

        capsule = make_capsule(
            self.owner,
            unlock_at=timezone.now() - timedelta(minutes=1),
        )
        CapsuleBeneficiary.objects.create(
            capsule=capsule, email='ben@example.com', name='Ben',
            notified_at=timezone.now(),
        )

        check_capsule_unlocks()

        mock_notify.delay.assert_not_called()


class CheckExpiredCapsulesTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner2', 'owner2@example.com', 'pass123!')

    def test_marks_old_unlocked_capsule_expired(self):
        from security.tasks.time_lock_tasks import check_expired_capsules

        capsule = make_capsule(
            self.owner,
            status='unlocked',
            opened_at=timezone.now() - timedelta(days=31),
        )

        result = check_expired_capsules()

        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'expired')
        self.assertEqual(result['expired'], 1)

    def test_leaves_recently_unlocked_capsule_alone(self):
        from security.tasks.time_lock_tasks import check_expired_capsules

        capsule = make_capsule(
            self.owner,
            status='unlocked',
            opened_at=timezone.now() - timedelta(days=1),
        )

        result = check_expired_capsules()

        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'unlocked')
        self.assertEqual(result['expired'], 0)


class CheckDeadMansSwitchesTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('willowner', 'will@example.com', 'pass123!')
        self.capsule = make_capsule(self.owner, capsule_type='will')

    @patch('security.tasks.time_lock_tasks.trigger_password_will')
    @patch('security.tasks.time_lock_tasks.send_will_reminder')
    def test_triggers_will_past_inactivity_deadline(self, mock_reminder, mock_trigger):
        from security.tasks.time_lock_tasks import check_dead_mans_switches

        will = PasswordWill.objects.create(
            owner=self.owner,
            capsule=self.capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            last_check_in=timezone.now() - timedelta(days=31),
            is_active=True,
        )

        result = check_dead_mans_switches()

        mock_trigger.delay.assert_called_once_with(str(will.id))
        mock_reminder.delay.assert_not_called()
        self.assertEqual(result['wills_triggered'], 1)

    @patch('security.tasks.time_lock_tasks.trigger_password_will')
    @patch('security.tasks.time_lock_tasks.send_will_reminder')
    def test_sends_reminder_within_reminder_window(self, mock_reminder, mock_trigger):
        from security.tasks.time_lock_tasks import check_dead_mans_switches

        will = PasswordWill.objects.create(
            owner=self.owner,
            capsule=self.capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            check_in_reminder_days=7,
            last_check_in=timezone.now() - timedelta(days=24),  # 6 days from deadline
            is_active=True,
        )

        result = check_dead_mans_switches()

        mock_reminder.delay.assert_called_once_with(str(will.id))
        mock_trigger.delay.assert_not_called()
        self.assertEqual(result['reminders_sent'], 1)

    @patch('security.tasks.time_lock_tasks.trigger_password_will')
    @patch('security.tasks.time_lock_tasks.send_will_reminder')
    def test_does_nothing_for_will_with_time_remaining(self, mock_reminder, mock_trigger):
        from security.tasks.time_lock_tasks import check_dead_mans_switches

        PasswordWill.objects.create(
            owner=self.owner,
            capsule=self.capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            check_in_reminder_days=7,
            last_check_in=timezone.now(),
            is_active=True,
        )

        check_dead_mans_switches()

        mock_trigger.delay.assert_not_called()
        mock_reminder.delay.assert_not_called()

    @patch('security.tasks.time_lock_tasks.trigger_password_will')
    def test_triggers_date_based_will_past_target_date(self, mock_trigger):
        from security.tasks.time_lock_tasks import check_dead_mans_switches

        will = PasswordWill.objects.create(
            owner=self.owner,
            capsule=self.capsule,
            trigger_type='date',
            target_date=timezone.now() - timedelta(days=1),
            is_active=True,
        )

        result = check_dead_mans_switches()

        mock_trigger.delay.assert_called_once_with(str(will.id))
        self.assertEqual(result['wills_triggered'], 1)

    @patch('security.tasks.time_lock_tasks.trigger_password_will')
    def test_ignores_inactive_and_already_triggered_wills(self, mock_trigger):
        from security.tasks.time_lock_tasks import check_dead_mans_switches

        PasswordWill.objects.create(
            owner=self.owner, capsule=self.capsule, trigger_type='date',
            target_date=timezone.now() - timedelta(days=1), is_active=False,
        )
        already = make_capsule(self.owner, capsule_type='will')
        PasswordWill.objects.create(
            owner=self.owner, capsule=already, trigger_type='date',
            target_date=timezone.now() - timedelta(days=1),
            is_active=True, is_triggered=True,
        )

        check_dead_mans_switches()

        mock_trigger.delay.assert_not_called()


class TriggerPasswordWillTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('triggerowner', 'trig@example.com', 'pass123!')
        self.capsule = make_capsule(self.owner, capsule_type='will')
        self.will = PasswordWill.objects.create(
            owner=self.owner,
            capsule=self.capsule,
            trigger_type='manual',
            is_active=True,
        )
        self.beneficiary = CapsuleBeneficiary.objects.create(
            capsule=self.capsule, email='ben@example.com', name='Ben',
        )

    @patch('security.tasks.time_lock_tasks.notify_beneficiary')
    def test_triggers_will_unlocks_capsule_and_notifies_beneficiaries(self, mock_notify):
        from security.tasks.time_lock_tasks import trigger_password_will

        result = trigger_password_will(str(self.will.id))

        self.will.refresh_from_db()
        self.capsule.refresh_from_db()
        self.assertTrue(self.will.is_triggered)
        self.assertIsNotNone(self.will.triggered_at)
        self.assertEqual(self.capsule.status, 'unlocked')
        self.assertTrue(self.will.beneficiaries_notified)
        mock_notify.delay.assert_called_once_with(
            capsule_id=str(self.capsule.id),
            beneficiary_id=str(self.beneficiary.id),
            is_will=True,
            personal_message=self.will.notes,
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['beneficiaries_notified'], 1)

    @patch('security.tasks.time_lock_tasks.notify_beneficiary')
    def test_already_triggered_will_is_not_retriggered(self, mock_notify):
        from security.tasks.time_lock_tasks import trigger_password_will

        self.will.is_triggered = True
        self.will.save()

        trigger_password_will(str(self.will.id))

        mock_notify.delay.assert_not_called()

    def test_unknown_will_id_returns_failure(self):
        from security.tasks.time_lock_tasks import trigger_password_will
        import uuid

        result = trigger_password_will(str(uuid.uuid4()))

        self.assertFalse(result['success'])


class CheckEscrowDeadlinesTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('escrowowner', 'escrow@example.com', 'pass123!')
        self.capsule = make_capsule(self.owner, capsule_type='escrow')
        self.party = User.objects.create_user('party2', 'party2@example.com', 'pass123!')

    @patch('security.tasks.time_lock_tasks.send_mail')
    def test_auto_releases_escrow_past_deadline_when_releasable(self, mock_send_mail):
        from security.tasks.time_lock_tasks import check_escrow_deadlines

        escrow = EscrowAgreement.objects.create(
            capsule=self.capsule,
            title='Auto-release test',
            release_condition='date',
            approval_deadline=timezone.now() - timedelta(hours=1),
        )
        escrow.parties.add(self.owner, self.party)
        # release_condition='date': can_release checks capsule.unlock_at, not
        # the escrow's own approval_deadline -- put the capsule's own unlock
        # time in the past too so `can_release` is actually True.
        self.capsule.unlock_at = timezone.now() - timedelta(minutes=1)
        self.capsule.save()

        result = check_escrow_deadlines()

        escrow.refresh_from_db()
        self.assertTrue(escrow.is_released)
        self.assertEqual(result['auto_released'], 1)
        self.assertEqual(mock_send_mail.call_count, 2)  # one per party

    @patch('security.tasks.time_lock_tasks.send_mail')
    def test_disputed_escrow_is_not_released(self, mock_send_mail):
        from security.tasks.time_lock_tasks import check_escrow_deadlines

        escrow = EscrowAgreement.objects.create(
            capsule=self.capsule,
            title='Disputed',
            release_condition='date',
            approval_deadline=timezone.now() - timedelta(hours=1),
            is_disputed=True,
        )
        escrow.parties.add(self.owner)

        result = check_escrow_deadlines()

        escrow.refresh_from_db()
        self.assertFalse(escrow.is_released)
        self.assertEqual(result['auto_released'], 0)
        mock_send_mail.assert_not_called()

    @patch('security.tasks.time_lock_tasks.send_mail')
    def test_escrow_before_deadline_is_left_alone(self, mock_send_mail):
        from security.tasks.time_lock_tasks import check_escrow_deadlines

        escrow = EscrowAgreement.objects.create(
            capsule=self.capsule,
            title='Not due yet',
            release_condition='date',
            approval_deadline=timezone.now() + timedelta(hours=1),
        )
        escrow.parties.add(self.owner)

        result = check_escrow_deadlines()

        escrow.refresh_from_db()
        self.assertFalse(escrow.is_released)
        self.assertEqual(result['auto_released'], 0)


class TimeLockBeatScheduleRegistryTests(TestCase):
    """The actual regression this whole fix is about: celery.py must
    schedule these 4 tasks, and each name must resolve.

    `time_lock_tasks.py` is unconditionally imported by
    `security/tasks/__init__.py` (no lazy/conditional import, unlike Dark
    Protocol before PR #482), so unlike that case, checking the in-process
    `app.tasks` registry here is not subject to the cross-test-file
    pollution PR #482 had to guard against with a subprocess snapshot --
    this module's tasks are already registered by the time Django's test
    runner has loaded the app.
    """

    def test_time_lock_beat_schedule_merged_and_resolves(self):
        from password_manager.celery import app

        app.autodiscover_tasks(force=True)
        import security.tasks  # noqa: F401
        app.finalize()

        expected = {
            'check-capsule-unlocks': 'time_lock.check_capsule_unlocks',
            'check-dead-mans-switches': 'time_lock.check_dead_mans_switches',
            'check-expired-capsules': 'time_lock.check_expired_capsules',
            'check-escrow-deadlines': 'time_lock.check_escrow_deadlines',
        }

        for entry, task_name in expected.items():
            with self.subTest(entry=entry):
                self.assertIn(entry, app.conf.beat_schedule)
                self.assertEqual(app.conf.beat_schedule[entry]['task'], task_name)
                self.assertIn(task_name, app.tasks)

"""
Tests for the `check_time_lock_backlog` management command.

This command is the pre-deploy safety check for PR #483
(fix/time-lock-beat-schedule-not-merged) -- it must correctly identify
PasswordWill/EscrowAgreement rows that are already overdue, since those are
exactly what would fire in a single batch on the first beat tick after that
PR deploys.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from security.models import TimeLockCapsule, PasswordWill, EscrowAgreement


def make_capsule(owner, capsule_type, **overrides):
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


class CheckTimeLockBacklogCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            'backlogtest', 'bt@example.com', 'pass123!',
        )

    def test_no_backlog_exits_cleanly(self):
        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

    def test_reports_overdue_inactivity_will(self):
        capsule = make_capsule(self.owner, 'will')
        will = PasswordWill.objects.create(
            owner=self.owner,
            capsule=capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            last_check_in=timezone.now() - timedelta(days=40),
            is_active=True,
        )

        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command('check_time_lock_backlog', stdout=out)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn('BACKLOG FOUND', out.getvalue())
        self.assertIn('1 PasswordWill row(s)', out.getvalue())
        self.assertIn('0 EscrowAgreement row(s)', out.getvalue())
        # Row is identified by ID only in routine output -- no owner
        # username or capsule title (CodeRabbit, PR #483: that PII has no
        # business in a daily CronJob's stdout).
        self.assertIn(str(will.id), out.getvalue())
        self.assertNotIn(self.owner.username, out.getvalue())
        self.assertNotIn(capsule.title, out.getvalue())

    def test_reports_overdue_date_based_will(self):
        capsule = make_capsule(self.owner, 'will')
        PasswordWill.objects.create(
            owner=self.owner,
            capsule=capsule,
            trigger_type='date',
            target_date=timezone.now() - timedelta(days=1),
            is_active=True,
        )

        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command('check_time_lock_backlog', stdout=out)

        self.assertIn('1 PasswordWill row(s)', out.getvalue())

    def test_does_not_report_will_not_yet_due(self):
        capsule = make_capsule(self.owner, 'will')
        PasswordWill.objects.create(
            owner=self.owner,
            capsule=capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            last_check_in=timezone.now(),
            is_active=True,
        )

        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

    def test_does_not_report_inactive_or_already_triggered_wills(self):
        capsule1 = make_capsule(self.owner, 'will')
        PasswordWill.objects.create(
            owner=self.owner, capsule=capsule1, trigger_type='date',
            target_date=timezone.now() - timedelta(days=1), is_active=False,
        )
        capsule2 = make_capsule(self.owner, 'will')
        PasswordWill.objects.create(
            owner=self.owner, capsule=capsule2, trigger_type='date',
            target_date=timezone.now() - timedelta(days=1),
            is_active=True, is_triggered=True,
        )

        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

    def test_reports_overdue_escrow(self):
        # `release_condition='date'` gates `can_release` on
        # `capsule.unlock_at`, not on `approval_deadline` -- both need to be
        # in the past for this escrow to actually be releasable (CodeRabbit,
        # PR #483: the command now checks `can_release`, matching what
        # check_escrow_deadlines itself gates the real release on).
        capsule = make_capsule(
            self.owner, 'escrow', unlock_at=timezone.now() - timedelta(hours=1),
        )
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Overdue Escrow',
            release_condition='date',
            approval_deadline=timezone.now() - timedelta(hours=2),
        )
        escrow.parties.add(self.owner)

        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command('check_time_lock_backlog', stdout=out)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn('0 PasswordWill row(s)', out.getvalue())
        self.assertIn('1 EscrowAgreement row(s)', out.getvalue())
        self.assertIn(str(escrow.id), out.getvalue())
        self.assertNotIn(escrow.title, out.getvalue())

    def test_does_not_report_escrow_with_unmet_approval_condition(self):
        """Deadline elapsed but `can_release` is False -- must not be
        reported. This is the exact gap CodeRabbit caught: the query alone
        (`approval_deadline__lte=now`) does not mean the escrow is actually
        releasable, and check_escrow_deadlines would skip this row too.
        """
        capsule = make_capsule(self.owner, 'escrow')
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Needs more approvals',
            release_condition='all_approve',
            approval_deadline=timezone.now() - timedelta(hours=2),
        )
        other_party = User.objects.create_user(
            'otherparty', 'other@example.com', 'pass123!',
        )
        escrow.parties.add(self.owner, other_party)
        # Only one of two parties approved -- can_release is False.
        escrow.approve(self.owner.id)

        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

    def test_does_not_report_disputed_escrow(self):
        # unlock_at in the past too, so `is_disputed` is the ONLY reason
        # this escrow is excluded -- with the default future unlock_at, a
        # regression that dropped the query's `is_disputed=False` filter
        # would still pass this test, since `can_release` would separately
        # return False from the still-future unlock_at (CodeRabbit, PR #483
        # round 2: same masking pattern already fixed for
        # test_reports_overdue_escrow in round 1, missed here).
        capsule = make_capsule(
            self.owner, 'escrow', unlock_at=timezone.now() - timedelta(hours=1),
        )
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Disputed',
            release_condition='date',
            approval_deadline=timezone.now() - timedelta(hours=2),
            is_disputed=True,
        )
        escrow.parties.add(self.owner)

        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

    def test_does_not_report_already_released_escrow(self):
        # Same fix as test_does_not_report_disputed_escrow above, same
        # reason: unlock_at in the past so `is_released` is the only thing
        # excluding this row, not an accidental assist from can_release's
        # separate future-unlock_at check.
        capsule = make_capsule(
            self.owner, 'escrow', unlock_at=timezone.now() - timedelta(hours=1),
        )
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Released',
            release_condition='date',
            approval_deadline=timezone.now() - timedelta(hours=2),
            is_released=True,
        )
        escrow.parties.add(self.owner)

        out = StringIO()
        call_command('check_time_lock_backlog', stdout=out)
        self.assertIn('No backlog', out.getvalue())

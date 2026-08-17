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
        PasswordWill.objects.create(
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
        self.assertIn(self.owner.username, out.getvalue())

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
        capsule = make_capsule(self.owner, 'escrow')
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

    def test_does_not_report_disputed_escrow(self):
        capsule = make_capsule(self.owner, 'escrow')
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
        capsule = make_capsule(self.owner, 'escrow')
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

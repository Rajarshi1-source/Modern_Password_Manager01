"""
Pre-deploy safety check for PR #483 (fix/time-lock-beat-schedule-not-merged).

`check-dead-mans-switches` and `check-escrow-deadlines` have never run in
production -- their beat entries didn't exist until that PR. The moment they
start running, ANY PasswordWill or EscrowAgreement already past its deadline
fires immediately, in a single batch, on the very first tick -- rather than
each having fired individually at its own due date as the feature intends.
`trigger_password_will` unlocks a capsule and emails real beneficiaries;
`check_escrow_deadlines` can auto-release an escrow and email all parties.

Read-only. Run this against production BEFORE deploying PR #483, so a batch
trigger is a decision, not a surprise.

Usage:
    python manage.py check_time_lock_backlog

Exit code is 1 if a backlog exists, 0 otherwise -- safe to gate a deploy
script on.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Read-only pre-deploy check: reports PasswordWill and "
        "EscrowAgreement rows already past their trigger/release deadline, "
        "which will fire in a single batch on the first beat tick after "
        "PR #483 deploys."
    )

    def handle(self, *args, **options):
        from security.models import PasswordWill, EscrowAgreement

        now = timezone.now()

        # Mirrors check_dead_mans_switches' own trigger logic exactly
        # (security/tasks/time_lock_tasks.py): inactivity-based wills are
        # overdue once last_check_in + inactivity_days has passed;
        # date-based wills are overdue once target_date has passed. Can't
        # express "last_check_in + inactivity_days" as a single field
        # comparison in the ORM, so it's evaluated in Python per candidate
        # row -- fine at this table's expected scale (a per-user opt-in
        # feature, not bulk data).
        candidates = PasswordWill.objects.filter(
            is_active=True, is_triggered=False,
        ).select_related('owner', 'capsule')

        overdue_wills = []
        for will in candidates:
            if will.trigger_type == 'inactivity' and will.inactivity_days is not None:
                deadline = will.last_check_in + timedelta(days=will.inactivity_days)
                if now >= deadline:
                    overdue_wills.append((will, deadline))
            elif will.trigger_type == 'date' and will.target_date is not None:
                if now >= will.target_date:
                    overdue_wills.append((will, will.target_date))

        # An elapsed `approval_deadline` alone does not make an escrow
        # releasable: `check_escrow_deadlines` (time_lock_tasks.py) queries
        # this same broad filter, then gates the actual `.release()` call on
        # `escrow.can_release` -- e.g. an 'all_approve' escrow past its
        # deadline but still short of approvals stays locked. Filtering
        # through `can_release` here mirrors that gate exactly, so this
        # report matches what the production task would actually trigger
        # rather than over-reporting rows the task would just skip.
        overdue_escrows = [
            escrow
            for escrow in EscrowAgreement.objects.filter(
                is_released=False, is_disputed=False, approval_deadline__lte=now,
            ).select_related('capsule')
            if escrow.can_release
        ]

        if not overdue_wills and not overdue_escrows:
            self.stdout.write(self.style.SUCCESS(
                'No backlog: 0 overdue PasswordWill rows, 0 overdue '
                'EscrowAgreement rows. Safe to deploy PR #483 -- the first '
                'beat tick will find nothing to trigger.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'BACKLOG FOUND: {len(overdue_wills)} PasswordWill row(s) and '
            f'{len(overdue_escrows)} EscrowAgreement row(s) already past '
            f'their deadline. Deploying PR #483 as-is will trigger ALL of '
            f'them in a single batch on the first beat tick, rather than '
            f'each individually at its own due date.'
        ))

        # IDs and non-identifying metadata only -- this is a daily CronJob's
        # routine stdout, which ends up in whatever log aggregation the
        # cluster uses, visible to a broader audience than a "look up this
        # specific will" operator action should be. Owner usernames and
        # capsule/escrow titles are left out; look a row up by ID
        # (`PasswordWill.objects.get(id=...)` / `EscrowAgreement.objects.get(id=...)`)
        # when actually acting on a finding.
        for will, deadline in overdue_wills:
            overdue_by = now - deadline
            self.stdout.write(
                f'  PasswordWill {will.id} -- '
                f'trigger_type={will.trigger_type!r} '
                f'overdue_by={overdue_by}'
            )

        for escrow in overdue_escrows:
            overdue_by = now - escrow.approval_deadline
            party_count = escrow.parties.count()
            self.stdout.write(
                f'  EscrowAgreement {escrow.id} -- '
                f'release_condition={escrow.release_condition!r} '
                f'overdue_by={overdue_by} parties={party_count}'
            )

        self.stdout.write(self.style.WARNING(
            '\nOptions before deploying: (a) accept the batch trigger if '
            'that outcome is fine for these specific rows, (b) manually '
            'check in / extend affected wills first '
            '(PasswordWill.check_in()), or (c) hold this deploy until '
            'each has been reviewed individually.'
        ))

        raise SystemExit(1)

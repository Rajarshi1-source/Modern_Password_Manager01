"""
Pre-deploy safety check for the honeypot-email (breach canary) beat schedule.

The `honeypot-*` beat entries have never run in production: honeypot_tasks.py
was neither imported (so its `@shared_task`s were unregistered) nor scheduled.
The moment they start running, work that accumulated over that entire window is
processed in a single batch on the first tick rather than at each item's own
due time.

Two of the six scheduled tasks have externally-visible effects:

  * `process_pending_rotations` sends a reminder EMAIL for every
    CredentialRotationLog that is pending, unconfirmed, and older than 24h.
    The query has no lower bound, so the whole backlog mails out at once.
    (It sends reminders only -- it does not itself rotate any credential.)
  * `scan_all_honeypots` calls the alias provider once per active honeypot.
    A large first scan can trip provider rate limits and can raise many
    HoneypotBreachEvent rows simultaneously.

`send_breach_digest` is self-bounding (last 24h only) and
`cleanup_expired_honeypots` is idempotent, so neither is reported here.

Read-only. Run this against production BEFORE deploying, so a batch send is a
decision, not a surprise.

Usage:
    python manage.py check_honeypot_backlog

Exit code is 1 if a backlog exists, 0 otherwise -- safe to gate a deploy
script on.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Read-only pre-deploy check: reports the CredentialRotationLog "
        "reminder backlog and the unscanned-honeypot backlog that will be "
        "processed in a single batch on the first honeypot beat tick."
    )

    def handle(self, *args, **options):
        from security.models import CredentialRotationLog, HoneypotEmail

        now = timezone.now()

        # Mirrors process_pending_rotations' own filter exactly
        # (security/tasks/honeypot_tasks.py): pending, initiated more than 24h
        # ago, and not yet confirmed by the user. Every row this matches gets
        # one reminder email on the first tick.
        rotation_cutoff = now - timedelta(hours=24)
        stale_rotations = list(
            CredentialRotationLog.objects.filter(
                status='pending',
                initiated_at__lt=rotation_cutoff,
                user_confirmed=False,
            ).select_related('user')
        )

        # Mirrors scan_all_honeypots' filter exactly. Each of these triggers
        # one outbound provider API call on the first tick.
        active_honeypots = HoneypotEmail.objects.filter(
            is_active=True,
            status__in=['active', 'triggered'],
        ).count()

        if not stale_rotations and not active_honeypots:
            self.stdout.write(self.style.SUCCESS(
                'No backlog: 0 stale CredentialRotationLog rows, 0 active '
                'honeypots to scan. Safe to deploy -- the first beat tick '
                'will find nothing to send or scan.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'BACKLOG FOUND: {len(stale_rotations)} CredentialRotationLog '
            f'row(s) will each receive a reminder email, and '
            f'{active_honeypots} active honeypot(s) will be scanned against '
            f'their provider, all on the first beat tick.'
        ))

        # IDs and non-identifying metadata only. This is a scheduled check
        # whose stdout lands in cluster log aggregation, visible to a broader
        # audience than a targeted operator lookup should be -- so no
        # usernames, no email addresses, and no service names (a service name
        # paired with a user is exactly the credential-mapping this product
        # exists to protect). Look a row up by ID when acting on a finding.
        for rotation in stale_rotations:
            pending_for = now - rotation.initiated_at
            self.stdout.write(
                f'  CredentialRotationLog {rotation.id} -- '
                f'pending_for={pending_for}'
            )

        if active_honeypots:
            self.stdout.write(
                f'  HoneypotEmail -- {active_honeypots} active alias(es) '
                f'queued for first scan'
            )

        self.stdout.write(self.style.WARNING(
            '\nOptions before deploying: (a) accept the batch -- reminder '
            'emails are benign if the volume is acceptable, (b) confirm or '
            'close stale rotations first so they fall out of the query, or '
            '(c) stagger the first scan by deploying with '
            "'honeypot-scan-all' temporarily removed if the provider's rate "
            'limit is a concern at this alias count.'
        ))

        raise SystemExit(1)

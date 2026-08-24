"""
Pre-deploy safety check for the mesh dead-drop beat schedule.

Four of `mesh_deaddrop`'s five schedulable tasks have never run in production:
`deaddrop_tasks.py` defines its own CELERY_BEAT_SCHEDULE, but nothing merged it
into the app's `beat_schedule` until the block in `password_manager/celery.py`
was added. (Only `flush-pending-sync` ran, because that one entry was also
written into the static schedule by hand.) The moment the other four start
running, work that accumulated over that entire window is processed in a single
batch on the first tick rather than at each item's own due time.

Two of the four have effects worth seeing in advance:

  * `check_expired_deaddrops` marks every past-expiry dead drop expired AND
    fires `notify_owner_deaddrop_expired` for each -- one real EMAIL per drop.
    The query has no lower bound, so the whole backlog mails out at once. This
    is the direct analogue of `process_pending_rotations` in
    `check_honeypot_backlog`, and the reason this command exists.
  * `cleanup_old_access_logs` hard-deletes DeadDropAccess and FragmentTransfer
    rows older than 90 days. Not user-visible, but the first tick deletes the
    entire accumulated backlog in one transaction -- on a large table that is a
    long-running DELETE worth scheduling deliberately rather than discovering.

`check_mesh_node_health` is reported too, as context rather than a hazard: it
sends nothing and its effect (marking genuinely-stale nodes offline) is
corrective, but it is the one task whose first tick changes state a human might
be watching. `cleanup_location_cache` is self-bounding and idempotent against a
small cache table, so it is not reported.

Read-only. Run this against production BEFORE deploying, so a batch send is a
decision, not a surprise.

Usage:
    python manage.py check_deaddrop_backlog

Exit code is 1 if a mailing/deleting backlog exists, 0 otherwise -- safe to
gate a deploy script on. `check_mesh_node_health`'s count alone does not set
the exit code, since it neither mails nor deletes.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

# Cap on how many individual rows this command prints. The summary counts
# above the list are always the TRUE totals (a cheap .count(), never len() of
# a loaded list) -- only the per-row detail section is capped, so a very large
# backlog is reported accurately without loading every row into memory or
# flooding whatever log aggregation this stdout lands in. Mirrors
# MAX_ROTATION_SAMPLES in security/.../check_honeypot_backlog.py, and exists
# for the same reason: this query has no historical lower bound of its own.
MAX_DEADDROP_SAMPLES = 100


class Command(BaseCommand):
    help = (
        "Read-only pre-deploy check: reports the expired-dead-drop email "
        "backlog and the old-log deletion backlog that will be processed in a "
        "single batch on the first mesh_deaddrop beat tick."
    )

    def handle(self, *args, **options):
        from mesh_deaddrop.models import (
            DeadDrop,
            DeadDropAccess,
            FragmentTransfer,
            MeshNode,
        )

        now = timezone.now()

        # Mirrors check_expired_deaddrops' own filter exactly
        # (mesh_deaddrop/tasks/deaddrop_tasks.py). Every row this matches is
        # marked expired AND gets one notification email on the first tick.
        expired_query = DeadDrop.objects.filter(
            status__in=['pending', 'distributed', 'active'],
            expires_at__lt=now,
            is_active=True,
        )
        expired_count = expired_query.count()
        expired_samples = list(
            expired_query.order_by('expires_at')[:MAX_DEADDROP_SAMPLES]
        )

        # Mirrors cleanup_old_access_logs' 90-day cutoff. These are deleted,
        # not mailed -- reported so the size of the first DELETE is known.
        log_cutoff = now - timedelta(days=90)
        stale_access_logs = DeadDropAccess.objects.filter(
            access_time__lt=log_cutoff
        ).count()
        stale_transfers = FragmentTransfer.objects.filter(
            transfer_time__lt=log_cutoff
        ).count()

        # Mirrors check_mesh_node_health's 10-minute staleness window.
        # Context only: no mail, no deletion.
        node_cutoff = now - timedelta(minutes=10)
        stale_nodes = MeshNode.objects.filter(
            is_online=True, last_seen__lt=node_cutoff
        ).count()

        mailing_or_deleting = bool(
            expired_count or stale_access_logs or stale_transfers
        )

        if not mailing_or_deleting:
            self.stdout.write(self.style.SUCCESS(
                'No backlog: 0 past-expiry dead drops to mail, 0 access/'
                'transfer log rows past the 90-day cutoff. Safe to deploy -- '
                'the first beat tick will find nothing to send or delete.'
            ))
            if stale_nodes:
                self.stdout.write(
                    f'  (FYI: {stale_nodes} mesh node(s) will be marked '
                    f'offline on the first health tick. No mail, no deletion.)'
                )
            return

        self.stdout.write(self.style.WARNING(
            f'BACKLOG FOUND: {expired_count} dead drop(s) will each be marked '
            f'expired and send their owner one email, and '
            f'{stale_access_logs + stale_transfers} log row(s) '
            f'({stale_access_logs} access + {stale_transfers} transfer) will '
            f'be deleted, all on the first beat tick.'
        ))

        # IDs and non-identifying metadata only. This is a pre-deploy check
        # whose stdout lands in cluster log aggregation, visible to a broader
        # audience than a targeted operator lookup should be -- so no
        # usernames, no recipient addresses, and no dead-drop labels. Look a
        # row up by ID when acting on a finding. Same rule, and the same
        # reason, as check_honeypot_backlog's own detail loop.
        for drop in expired_samples:
            overdue_by = now - drop.expires_at
            self.stdout.write(
                f'  DeadDrop {drop.id} -- overdue_by={overdue_by}'
            )

        if expired_count > len(expired_samples):
            self.stdout.write(
                f'  ... and {expired_count - len(expired_samples)} more '
                f'(showing the {len(expired_samples)} longest-overdue rows; '
                f'the count above is the true total).'
            )

        if stale_nodes:
            self.stdout.write(
                f'  MeshNode -- {stale_nodes} node(s) queued to be marked '
                f'offline (no mail, no deletion)'
            )

        self.stdout.write(self.style.WARNING(
            '\nOptions before deploying: (a) accept the batch -- expiry '
            'notifications are benign if the volume is acceptable, (b) close '
            'or extend genuinely-stale dead drops first so they fall out of '
            "the query, or (c) deploy with 'check-expired-deaddrops' "
            'temporarily removed and run it manually off-peak if the email '
            'volume or the first DELETE is large.'
        ))

        raise SystemExit(1)

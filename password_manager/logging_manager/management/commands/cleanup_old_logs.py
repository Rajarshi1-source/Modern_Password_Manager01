"""Management command to purge SystemLog rows older than a retention window.

Can be invoked by Celery beat *or* a K8s CronJob:
    python manage.py cleanup_old_logs          # default 90 days
    python manage.py cleanup_old_logs --days 30
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete SystemLog entries older than --days (default: ERROR_LOG_RETENTION_DAYS or 90)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Retention window in days (overrides ERROR_LOG_RETENTION_DAYS setting)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Number of rows deleted per batch to avoid long locks",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from logging_manager.models import SystemLog

        days = options["days"] or getattr(settings, "ERROR_LOG_RETENTION_DAYS", 90)
        batch_size = options["batch_size"]
        cutoff = timezone.now() - timedelta(days=days)

        total_deleted = 0
        while True:
            pks = list(
                SystemLog.objects.filter(timestamp__lt=cutoff)
                .values_list("pk", flat=True)[:batch_size]
            )
            if not pks:
                break
            deleted, _ = SystemLog.objects.filter(pk__in=pks).delete()
            total_deleted += deleted

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {total_deleted} log entries older than {days} days."
            )
        )

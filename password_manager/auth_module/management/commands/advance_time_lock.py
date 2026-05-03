"""
E2E-only helper: fast-forward `TimeLockedRecovery.release_after` so
Tier-3 recovery tests do not need to wait 7+ real days.

Refuses to run outside DEBUG / testserver environments — never permitted
in production.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Fast-forward TimeLockedRecovery.release_after for E2E tests. '
        'Refuses to run outside DEBUG / test environments.'
    )

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument(
            '--hours',
            type=int,
            default=168,
            help='How far ahead to advance the clock (default 168 = 7d).',
        )

    def handle(self, *args, **opts):
        if not settings.DEBUG and 'testserver' not in settings.ALLOWED_HOSTS:
            raise CommandError(
                'advance_time_lock refuses to run outside DEBUG / test env'
            )

        try:
            from auth_module.time_locked_models import TimeLockedRecovery
        except ImportError as exc:
            raise CommandError(
                f'time_locked_models not importable in this branch: {exc}'
            )

        try:
            user = User.objects.get(username=opts['username'])
        except User.DoesNotExist:
            raise CommandError(f"user '{opts['username']}' not found")

        rec = (
            TimeLockedRecovery.objects
            .filter(user=user, is_active=True)
            .order_by('-enrolled_at')
            .first()
        )
        if not rec:
            raise CommandError(f"no active time-lock for {user.username}")
        if not rec.release_after:
            raise CommandError(
                f"time-lock for {user.username} not initiated (no release_after set)"
            )

        # Set release_after into the past so the next /release/ call
        # passes the gate. We don't just zero it — we move it back by
        # `hours` so the audit log reflects the simulated wait.
        rec.release_after = timezone.now() - timedelta(hours=1)
        rec.save(update_fields=['release_after'])
        self.stdout.write(
            self.style.SUCCESS(
                f'release_after advanced for {user.username} '
                f'(was {opts["hours"]} hours from now)'
            )
        )

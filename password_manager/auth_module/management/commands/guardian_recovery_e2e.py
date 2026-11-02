"""
E2E-only helper for frontend/e2e/guardian_recovery.spec.js: prints what the
guardian recovery emails would link to, and with --open-windows or --end-wait
fast-forwards the hours the flow normally takes.

Refuses to run outside DEBUG / testserver environments, like advance_time_lock.
"""
import json
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auth_module.quantum_recovery_models import GuardianApproval, RecoveryAttempt
from shared import sealed_shares


class Command(BaseCommand):
    help = 'Read and fast-forward a guardian recovery in E2E tests.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('--open-windows', action='store_true')
        parser.add_argument('--end-wait', action='store_true')

    def handle(self, *args, **opts):
        if not settings.DEBUG and 'testserver' not in settings.ALLOWED_HOSTS:
            raise CommandError('guardian_recovery_e2e refuses to run outside DEBUG / test env')

        attempt = RecoveryAttempt.objects.filter(
            recovery_setup__user__username=opts['username'],
        ).order_by('-initiated_at').first()
        if attempt is None:
            self.stdout.write(json.dumps({}))
            return

        now = timezone.now()
        if opts['open_windows']:
            GuardianApproval.objects.filter(recovery_attempt=attempt).update(
                approval_window_start=now - timedelta(minutes=1),
                approval_window_end=now + timedelta(hours=1))
        if opts['end_wait']:
            # Moves the alert back, and must not stand in for one never sent:
            # nothing is released without it.
            if attempt.canary_alert_sent_at is None:
                raise CommandError('no owner alert on record for this attempt')
            hours = attempt.recovery_setup.canary_alert_window_hours
            RecoveryAttempt.objects.filter(pk=attempt.pk).update(
                canary_alert_sent_at=now - timedelta(hours=hours, minutes=1))

        self.stdout.write(json.dumps({
            'attempt_path': (f'/recovery/guardian-attempt?attempt={attempt.id}&key='
                             f'{sealed_shares.key_fingerprint(bytes(attempt.requester_public_key))}'),
            'alert_sent': attempt.canary_alert_sent_at is not None,
            # By guardian email: a guardian's browser opens only its own share
            'approval_tokens': {
                a.guardian.encrypted_guardian_info.decode('utf-8'): a.approval_token
                for a in attempt.guardian_approvals.select_related('guardian')
            },
        }))

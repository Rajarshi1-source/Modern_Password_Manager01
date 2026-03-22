"""
Dead Man's Switch Service
===========================

Monitors inheritance plans and triggers notifications/releases
when owners fail to check in within their configured intervals.
"""

import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from smart_contracts.models.vault import SmartContractVault, VaultStatus, ConditionType
from smart_contracts.models.escrow import InheritancePlan

logger = logging.getLogger(__name__)


class DeadMansSwitchService:
    """
    Background service that monitors all active dead man's switch vaults
    and triggers grace period notifications / auto-release.
    """

    def check_all_switches(self) -> dict:
        """
        Check all active dead man's switch vaults.
        Called periodically by Celery beat.

        Returns summary of actions taken.
        """
        stats = {
            'checked': 0,
            'grace_period_started': 0,
            'released': 0,
            'errors': 0,
        }

        active_plans = InheritancePlan.objects.filter(
            status__in=[
                InheritancePlan.InheritanceStatus.ACTIVE,
                InheritancePlan.InheritanceStatus.GRACE_PERIOD,
            ],
            vault__status=VaultStatus.ACTIVE,
        ).select_related('vault', 'owner', 'beneficiary_user')

        for plan in active_plans:
            stats['checked'] += 1
            try:
                self._process_plan(plan, stats)
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing inheritance plan {plan.id}: {e}")

        logger.info(
            f"Dead man's switch check complete: {stats['checked']} checked, "
            f"{stats['grace_period_started']} grace periods started, "
            f"{stats['released']} released, {stats['errors']} errors"
        )
        return stats

    def _process_plan(self, plan: InheritancePlan, stats: dict):
        """Process a single inheritance plan."""
        now = timezone.now()

        if plan.status == InheritancePlan.InheritanceStatus.ACTIVE:
            # Check if inactivity period has elapsed
            if plan.is_overdue:
                self._start_grace_period(plan)
                stats['grace_period_started'] += 1

        elif plan.status == InheritancePlan.InheritanceStatus.GRACE_PERIOD:
            # Check if grace period has also elapsed
            if plan.is_release_due:
                self._trigger_release(plan)
                stats['released'] += 1

    def _start_grace_period(self, plan: InheritancePlan):
        """Start the grace period — notify the owner."""
        plan.status = InheritancePlan.InheritanceStatus.GRACE_PERIOD
        plan.grace_period_started_at = timezone.now()
        plan.save(update_fields=['status', 'grace_period_started_at', 'updated_at'])

        # Notify vault owner
        if not plan.notification_sent:
            try:
                send_mail(
                    subject='⚠️ Dead Man\'s Switch — Grace Period Started',
                    message=(
                        f'Your vault "{plan.vault.title}" has entered its grace period.\n\n'
                        f'You have {plan.grace_period_days} days to check in before '
                        f'the password is automatically released to your beneficiary.\n\n'
                        f'Log in to your account and check in to prevent release.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[plan.owner.email],
                    fail_silently=True,
                )
                plan.notification_sent = True
                plan.save(update_fields=['notification_sent'])
                logger.info(f"Grace period notification sent to {plan.owner.email}")
            except Exception as e:
                logger.error(f"Failed to send grace notification: {e}")

        # Notify beneficiary
        if not plan.beneficiary_notified and plan.beneficiary_email:
            try:
                send_mail(
                    subject='🔔 You are the beneficiary of a password vault',
                    message=(
                        f'A password vault is in its grace period and may be released to you.\n\n'
                        f'The vault owner has {plan.grace_period_days} days to check in. '
                        f'If they do not, you will receive access to the vault contents.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[plan.beneficiary_email],
                    fail_silently=True,
                )
                plan.beneficiary_notified = True
                plan.save(update_fields=['beneficiary_notified'])
                logger.info(f"Beneficiary notification sent to {plan.beneficiary_email}")
            except Exception as e:
                logger.error(f"Failed to send beneficiary notification: {e}")

    def _trigger_release(self, plan: InheritancePlan):
        """Release the vault to the beneficiary."""
        plan.status = InheritancePlan.InheritanceStatus.TRIGGERED
        plan.triggered_at = timezone.now()
        plan.save(update_fields=['status', 'triggered_at', 'updated_at'])

        vault = plan.vault
        vault.status = VaultStatus.UNLOCKED
        vault.unlocked_at = timezone.now()
        vault.save(update_fields=['status', 'unlocked_at', 'updated_at'])

        # Notify beneficiary of release
        if plan.beneficiary_email:
            try:
                send_mail(
                    subject='🔓 Password Vault Released to You',
                    message=(
                        f'A password vault has been released to you.\n\n'
                        f'The vault owner did not check in within the configured period, '
                        f'and the dead man\'s switch has been triggered.\n\n'
                        f'Log in to access the vault contents.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[plan.beneficiary_email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send release notification: {e}")

        logger.info(f"Dead man's switch triggered: vault {vault.id} released to {plan.beneficiary_email}")

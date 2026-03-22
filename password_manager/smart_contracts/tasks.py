"""
Celery Tasks for Smart Contract Automation
============================================

Periodic tasks for dead man's switch monitoring, condition evaluation,
and on-chain state synchronization.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='smart_contracts.tasks.check_dead_mans_switches')
def check_dead_mans_switches():
    """
    Periodic task: Check all active dead man's switch vaults.
    Triggers grace period notifications and auto-release.
    Runs every hour via Celery beat.
    """
    from smart_contracts.services.dead_mans_switch import DeadMansSwitchService

    service = DeadMansSwitchService()
    stats = service.check_all_switches()

    logger.info(f"Dead man's switch check: {stats}")
    return stats


@shared_task(name='smart_contracts.tasks.evaluate_pending_conditions')
def evaluate_pending_conditions():
    """
    Periodic task: Evaluate conditions for all active vaults.
    Updates condition status in the database.
    Runs every 15 minutes via Celery beat.
    """
    from smart_contracts.models.vault import SmartContractVault, VaultStatus
    from smart_contracts.services.condition_engine import ConditionEngine

    engine = ConditionEngine()
    active_vaults = SmartContractVault.objects.filter(status=VaultStatus.ACTIVE)

    stats = {'evaluated': 0, 'conditions_met': 0, 'errors': 0}

    for vault in active_vaults:
        try:
            result = engine.evaluate(vault)
            stats['evaluated'] += 1

            if result['met']:
                stats['conditions_met'] += 1

                # Update vault conditions
                for condition in vault.conditions.all():
                    if not condition.is_met:
                        from django.utils import timezone
                        condition.is_met = result['met']
                        condition.evaluated_at = timezone.now()
                        condition.save()

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Condition evaluation error for vault {vault.id}: {e}")

    logger.info(f"Condition evaluation: {stats}")
    return stats


@shared_task(name='smart_contracts.tasks.sync_onchain_state')
def sync_onchain_state():
    """
    Periodic task: Sync vault state from on-chain contract.
    Ensures local state matches blockchain state.
    Runs every 30 minutes via Celery beat.
    """
    from smart_contracts.models.vault import SmartContractVault, VaultStatus
    from smart_contracts.services.web3_bridge import SmartContractWeb3Bridge

    bridge = SmartContractWeb3Bridge()
    if not bridge.is_available():
        logger.debug("Web3 bridge not available, skipping on-chain sync")
        return {'synced': 0, 'reason': 'bridge_unavailable'}

    stats = {'synced': 0, 'status_changes': 0, 'errors': 0}

    # Only sync vaults that have on-chain IDs
    vaults = SmartContractVault.objects.filter(
        status=VaultStatus.ACTIVE,
        vault_id_onchain__isnull=False
    )

    for vault in vaults:
        try:
            onchain_data = bridge.get_vault_onchain(vault.vault_id_onchain)
            if onchain_data:
                stats['synced'] += 1

                # Check if status changed on-chain
                onchain_status = onchain_data.get('status', 0)
                if onchain_status == 1 and vault.status == VaultStatus.ACTIVE:
                    # Vault was unlocked on-chain
                    from django.utils import timezone
                    vault.status = VaultStatus.UNLOCKED
                    vault.unlocked_at = timezone.now()
                    vault.save(update_fields=['status', 'unlocked_at', 'updated_at'])
                    stats['status_changes'] += 1
                    logger.info(f"Vault {vault.id} synced as UNLOCKED from on-chain")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"On-chain sync error for vault {vault.id}: {e}")

    logger.info(f"On-chain state sync: {stats}")
    return stats

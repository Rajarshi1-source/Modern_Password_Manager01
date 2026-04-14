"""
__init__.py for security tasks package

This module re-exports tasks from both the legacy tasks.py file
and the modular task files.
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Breach Checking Tasks (real implementation with HIBP integration)
# ============================================================================

from .breach_tasks import (
    check_for_breaches,
    scan_user_vault,
    daily_breach_scan,
)


# ============================================================================
# Genetic Password Tasks (from breach_tasks module)
# ============================================================================

from .breach_tasks import (
    check_genetic_evolution,
    daily_genetic_evolution_check,
    sync_epigenetic_data,
    cleanup_expired_genetic_trials,
    refresh_dna_tokens,
)


# ============================================================================
# Adaptive Password Tasks
# ============================================================================

try:
    from .adaptive_tasks import *
    ADAPTIVE_TASKS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import adaptive tasks: {e}")
    ADAPTIVE_TASKS_AVAILABLE = False


# ============================================================================
# Time-Lock Tasks
# ============================================================================

try:
    from .time_lock_tasks import (
        check_capsule_unlocks,
        check_dead_mans_switches,
        check_expired_capsules,
        check_escrow_deadlines,
        trigger_password_will,
        send_will_reminder,
        notify_beneficiary,
        process_vdf_computation,
        CELERY_BEAT_SCHEDULE as TIME_LOCK_BEAT_SCHEDULE,
    )
    TIME_LOCK_TASKS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import time-lock tasks: {e}")
    TIME_LOCK_TASKS_AVAILABLE = False


__all__ = [
    'check_for_breaches',
    'scan_user_vault',
    'daily_breach_scan',
    'check_genetic_evolution',
    'daily_genetic_evolution_check',
    'sync_epigenetic_data',
    'cleanup_expired_genetic_trials',
    'refresh_dna_tokens',
]

if ADAPTIVE_TASKS_AVAILABLE:
    pass  # adaptive_tasks uses wildcard import

if TIME_LOCK_TASKS_AVAILABLE:
    __all__.extend([
        'check_capsule_unlocks',
        'check_dead_mans_switches',
        'check_expired_capsules',
        'check_escrow_deadlines',
        'trigger_password_will',
        'send_will_reminder',
        'notify_beneficiary',
        'process_vdf_computation',
    ])


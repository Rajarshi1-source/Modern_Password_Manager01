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
# Predictive Expiration / Threat Intelligence tasks (re-exported from
# breach_tasks for test imports: `from security.tasks import ...`)
# ============================================================================

try:
    from .breach_tasks import (
        analyze_user_password_patterns,
        evaluate_password_expiration_risk,
        process_forced_rotation,
        update_threat_intelligence,
        daily_predictive_scan,
        send_expiration_notifications,
    )
except ImportError as e:  # pragma: no cover
    # Do NOT silently no-op: these are production beat-scheduled tasks. A stub
    # that returns success would keep beat green while the daily re-score and
    # risk-alert fan-out never run. Register fallbacks under the real
    # security.tasks.* names that fail loudly so the breakage is visible.
    logger.exception(f"Could not import predictive tasks from .breach_tasks: {e}")
    _IMPORT_ERROR = e

    def _unavailable(task_name):
        raise RuntimeError(
            f"{task_name} is unavailable: security.tasks.breach_tasks failed "
            f"to import ({_IMPORT_ERROR})"
        )

    @shared_task(name='security.tasks.analyze_user_password_patterns')
    def analyze_user_password_patterns(user_id=None):
        _unavailable('analyze_user_password_patterns')

    @shared_task(name='security.tasks.evaluate_password_expiration_risk')
    def evaluate_password_expiration_risk(credential_id=None, user_id=None):
        _unavailable('evaluate_password_expiration_risk')

    @shared_task(name='security.tasks.process_forced_rotation')
    def process_forced_rotation(credential_id=None, user_id=None, reason=''):
        _unavailable('process_forced_rotation')

    @shared_task(name='security.tasks.update_threat_intelligence')
    def update_threat_intelligence():
        _unavailable('update_threat_intelligence')

    @shared_task(name='security.tasks.daily_predictive_scan')
    def daily_predictive_scan():
        _unavailable('daily_predictive_scan')

    @shared_task(name='security.tasks.send_expiration_notifications')
    def send_expiration_notifications():
        _unavailable('send_expiration_notifications')


@shared_task(name='security.daily_credential_scan')
def daily_credential_scan():
    """Daily sweep that evaluates all active credentials for expiration risk.

    Minimal shim so tests that mock this task can import it. The real
    implementation can iterate users and call ``analyze_user_password_patterns``.
    """
    return {'status': 'ok', 'scanned': 0}


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


# ============================================================================
# Dark Protocol Tasks
# ============================================================================
#
# Each `@shared_task` in dark_protocol_tasks.py carries an explicit
# `name='dark_protocol.<func>'` that already matches what celery.py's beat
# schedule expects -- but `@shared_task` only registers a task once its
# defining module is imported, and nothing imported this one. The
# `dark-protocol-*` beat entries had never run as a result. Importing here
# (mirroring the try/except pattern above) is the fix.
#
# NOTE: importing a name here makes it *registered* (a worker can look it
# up and run it if asked, e.g. `test_dark_protocol.py`'s direct task-level
# tests) -- it does NOT make it *scheduled*. Whether a task actually runs
# unattended is decided entirely by celery.py's beat_schedule, which this
# import list has no control over. `health_check_nodes` is imported here
# like its four siblings (all five are equally real, safe-to-call Python
# functions), but celery.py deliberately does not schedule it (CodeRabbit,
# PR #482 round 4: it mutates real node status based on simulated
# `random.random()` data with no config gate) -- see the comment above
# `dark-protocol-rotate-paths` in celery.py for the full reasoning.

try:
    from .dark_protocol_tasks import (
        rotate_network_paths,
        generate_cover_traffic,
        health_check_nodes,
        cleanup_expired_sessions as cleanup_expired_dark_protocol_sessions,
        analyze_traffic_patterns,
        register_node,
    )
    DARK_PROTOCOL_TASKS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import dark protocol tasks: {e}")
    DARK_PROTOCOL_TASKS_AVAILABLE = False


try:
    from ..services.pattern_analysis_engine import PatternAnalysisEngine
    from ..services.predictive_expiration_service import PredictiveExpirationService
    from ..services.threat_intelligence_service import ThreatIntelligenceService
    from ..models import PredictiveExpirationRule
except ImportError as e:
    logger.warning(f"Could not import predictive expiration symbols: {e}")
    PatternAnalysisEngine = None
    PredictiveExpirationService = None
    ThreatIntelligenceService = None
    PredictiveExpirationRule = None


__all__ = [
    'check_for_breaches',
    'scan_user_vault',
    'daily_breach_scan',
    'check_genetic_evolution',
    'daily_genetic_evolution_check',
    'sync_epigenetic_data',
    'cleanup_expired_genetic_trials',
    'refresh_dna_tokens',
    'analyze_user_password_patterns',
    'evaluate_password_expiration_risk',
    'process_forced_rotation',
    'update_threat_intelligence',
    'daily_predictive_scan',
    'send_expiration_notifications',
    'daily_credential_scan',
    'PatternAnalysisEngine',
    'PredictiveExpirationService',
    'ThreatIntelligenceService',
    'PredictiveExpirationRule',
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

if DARK_PROTOCOL_TASKS_AVAILABLE:
    __all__.extend([
        'rotate_network_paths',
        'generate_cover_traffic',
        'health_check_nodes',
        'cleanup_expired_dark_protocol_sessions',
        'analyze_traffic_patterns',
        'register_node',
    ])


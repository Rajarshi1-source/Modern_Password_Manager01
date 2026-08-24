"""
Celery Configuration for Password Manager

This module configures Celery for asynchronous task processing.
Supports: background tasks, scheduled tasks, blockchain anchoring, ML operations, FHE operations

Usage:
    celery -A password_manager worker -l info
    celery -A password_manager beat -l info
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

app = Celery('password_manager')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure Celery settings
app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    # NOTE: @shared_task auto-generates names as '<app>.tasks.<func_name>'.
    # fnmatch '*' does NOT match dots, so 'blockchain.*' would never match
    # 'blockchain.tasks.anchor_pending_commitments'.  Use '<app>.tasks.*'.
    task_routes={
        'blockchain.tasks.*': {'queue': 'blockchain'},
        'smart_contracts.tasks.*': {'queue': 'blockchain'},
        'ml_security.tasks.*': {'queue': 'ml'},
        'ml_dark_web.tasks.*': {'queue': 'ml'},
        'fhe_service.tasks.*': {'queue': 'fhe'},
        'adversarial_ai.tasks.*': {'queue': 'adversarial'},
        'analytics.tasks.*': {'queue': 'analytics'},
        'heartbeat_auth.tasks.*': {'queue': 'ml'},
        'ultrasonic_pairing.tasks.*': {'queue': 'default'},
    },
    
    # Task priority support (RabbitMQ / Redis with sorted sets)
    task_queue_max_priority=10,
    task_default_priority=5,
    
    # Task time limits (prevent hanging tasks)
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    
    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching for long-running tasks
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    
    # Retry settings
    task_acks_late=True,  # Acknowledge task after it completes
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # `analyze-password-strength-daily` (-> ml_security.tasks.analyze_all_passwords)
        # deliberately removed rather than fixed. No such task exists anywhere
        # under any name, and the only thing in the codebase that scores
        # password strength (`PasswordStrengthPredictor` in
        # `ml_security/ml_models/password_strength.py`) is wired into the
        # adversarial-AI red-team feature, not a per-user vault sweep.
        # Writing one would mean the server decrypting every user's stored
        # passwords, which conflicts with the zero-knowledge design already
        # established elsewhere in this file: `daily_predictive_scan` below
        # explicitly documents "the server never decrypts the vault". This
        # entry reads as a leftover from a pre-zero-knowledge prototype;
        # `predictive-daily-scan` (-> security.tasks.daily_predictive_scan)
        # is the live, zero-knowledge-compatible daily risk analysis that
        # supersedes it.

        # Breach monitoring (every 6 hours)
        'check-data-breaches': {
            'task': 'ml_dark_web.tasks.check_compromised_passwords',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        },

        # Bug Bounty: continuous vault self-pentest (daily, fans out per user)
        'bug-bounty-self-pentest-daily': {
            'task': 'bug_bounty.tasks.run_scheduled_self_tests',
            'schedule': crontab(hour=3, minute=30),  # 3:30 AM daily
        },
        
        # Blockchain anchoring (if enabled, hourly)
        'anchor-vault-to-blockchain': {
            'task': 'blockchain.tasks.anchor_pending_commitments',
            'schedule': crontab(minute=0),  # Every hour
        },

        # Phase C / C6: daily spot-check of a random sample of MerkleProof
        # rows against the on-chain ``verifyCommitment`` view. Confirms
        # the anchored Merkle roots still match the proofs we hand out
        # — a mismatch fires a logger.error → Sentry alert.
        'verify-random-merkle-proofs': {
            'task': 'blockchain.tasks.verify_random_proofs',
            'schedule': crontab(hour=4, minute=15),  # 4:15 AM daily
        },

        # Phase 2b: flush pending reputation events into Merkle-rooted anchor
        # batches (every 15 minutes). If the adapter is "null" this is
        # effectively a cheap bookkeeping sweep; with "arbitrum" it submits
        # to the CommitmentRegistry contract.
        'flush-reputation-anchor-batches': {
            'task': 'password_reputation.tasks.flush_pending_reputation_batches',
            'schedule': crontab(minute='*/15'),
        },

        # Ambient Biometric Fusion: nightly reliability-weight recompute
        # per user (cheap heuristic, bounded 500 obs/user). Keeps per-signal
        # weights in sync with what actually discriminates trusted contexts.
        'recompute-ambient-signal-reliability': {
            'task': 'ambient_auth.tasks.recompute_signal_reliability',
            'schedule': crontab(hour=3, minute=30),  # 3:30 AM daily
        },
        
        # Clean up expired Django sessions (daily). `shared` had no
        # `tasks.py` at all, so this named a task that could not exist; added
        # `shared/tasks.py` with the standard `Session.objects.filter(
        # expire_date__lt=now).delete()` sweep Django's own `clearsessions`
        # management command runs (SESSION_ENGINE is the DB-backed default).
        'cleanup-expired-sessions': {
            'task': 'shared.tasks.cleanup_expired_sessions',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
        },

        # Clean up old logs (weekly)
        'cleanup-old-logs': {
            'task': 'logging_manager.tasks.cleanup_old_logs',
            'schedule': crontab(day_of_week=0, hour=4, minute=0),  # Sunday 4:00 AM
        },

        # Update threat intelligence (daily). Was scheduled under
        # `ml_security.tasks.update_threat_intelligence`; the task is
        # registered as `security.tasks.update_threat_intelligence`
        # (breach_tasks.py, explicit `name=`). Not new capability: this same
        # call already runs once a day as the first step of
        # `daily_predictive_scan` below (`predictive-daily-scan`), so fixing
        # this entry means the threat-feed refresh now runs twice daily
        # (1:30 AM here, plus whenever the predictive scan's chord fires)
        # instead of once -- redundant but harmless; `update_threat_intelligence`
        # only upserts ThreatIntelFeed sync status and aggregates
        # IndustryThreatLevel, no unbounded side effects from a second run.
        'update-threat-intel': {
            'task': 'security.tasks.update_threat_intelligence',
            'schedule': crontab(hour=1, minute=30),  # 1:30 AM daily
        },
        
        # =================================================================
        # Genetic Password Evolution Tasks
        # =================================================================
        
        # These three entries named `security.tasks.<func>`, which is not what
        # these tasks are registered as: they are defined in `breach_tasks.py`
        # under a bare `@shared_task`, and `@shared_task` derives the name from
        # the DEFINING module -- so the real names carry a `breach_tasks`
        # segment. Beat still published the message (the scheduler falls back to
        # `send_task` for a name it cannot resolve locally), but the worker
        # rejected every one as `NotRegistered`, so all three jobs had never run.
        #
        # Corrected the entries rather than pinning `name='security.tasks.<func>'`
        # on the decorators: nothing outside this file referred to the short
        # names (the task package and tests import the Python symbols, which are
        # unaffected either way), renaming a registered task would leave workers
        # on older code unable to resolve it mid-rollout, and a name that
        # disagrees with its defining module is exactly what kept this bug
        # invisible. Same call made for the adaptive tasks below.
        #
        # The four siblings in `breach_tasks.py` that DO carry an explicit
        # `name='security.tasks.<func>'` are deliberately left alone -- they
        # resolve correctly today and have live beat entries.

        # Daily genetic evolution check (for premium users).
        # Inert until an epigenetic provider is configured: the fan-out selects
        # only connections that already carry a biological age.
        'check-genetic-evolution-daily': {
            'task': 'security.tasks.breach_tasks.daily_genetic_evolution_check',
            'schedule': crontab(hour=5, minute=0),  # 5:00 AM daily
        },

        # Cleanup expired genetic trials (daily)
        'cleanup-genetic-trials': {
            'task': 'security.tasks.breach_tasks.cleanup_expired_genetic_trials',
            'schedule': crontab(hour=4, minute=30),  # 4:30 AM daily
        },

        # Refresh DNA provider OAuth tokens (weekly).
        # The provider refresh call itself is still unimplemented; the task
        # reports `implemented: False` rather than claiming a refresh it did not
        # perform. See `refresh_dna_tokens` in breach_tasks.py.
        'refresh-dna-tokens-weekly': {
            'task': 'security.tasks.breach_tasks.refresh_dna_tokens',
            'schedule': crontab(day_of_week=6, hour=3, minute=0),  # Saturday 3:00 AM
        },
        
        # =================================================================
        # Adaptive (Epigenetic) Password Tasks — plan §5.4 / gap D3
        # =================================================================
        #
        # These three tasks have existed and been importable since the
        # feature's first version with NO beat entry, so the learning loop
        # never actually closed in production: profiles were never
        # re-aggregated, expired suggestions were never swept, and the bandit
        # posteriors (Phase 3) were persisted but never fed.
        #
        # Task NAMES verified against the live registry rather than taken from
        # the plan text, which named them `security.tasks.<func>`. `@shared_task`
        # with no explicit `name=` derives the name from the DEFINING module, so
        # the real names carry the `adaptive_tasks` segment. An entry using the
        # plan's names would raise NotRegistered on every beat tick.
        #
        # Left on the default queue deliberately. There is no `security.tasks.*`
        # entry in `task_routes` above, so every security task runs on default
        # today; adding one for these three would also relocate the breach,
        # genetic and predictive-expiration tasks to a queue no deployed worker
        # currently consumes.
        #
        # `adaptive-cleanup-expired-adaptations` moved off the plan's 4:15
        # (taken by `verify-random-merkle-proofs` above) to 4:45.
        # `adaptive-update-rl-model-from-feedback` moved off the plan's Mon
        # 4:45 to Mon 5:15 -- not because of `cleanup-genetic-trials`
        # (4:30, a different time; an earlier comment here wrongly named
        # it), but because `adaptive-cleanup-expired-adaptations` itself
        # now also lands on 4:45 every Monday.
        # `adaptive-aggregate-typing-profiles`'s hourly `:15` schedule was
        # left alone: it still coincides with `verify-random-merkle-proofs`
        # once a day, at 4:15. Harmless and consistent with this file's own
        # existing pattern -- `anchor-vault-to-blockchain` (hourly `:00`)
        # already coincides daily with `analyze-password-strength-daily`
        # (2:00 AM) the same way, and `bug-bounty-self-pentest-daily` /
        # `recompute-ambient-signal-reliability` already share 3:30 AM --
        # because the two tasks route to different queues (`blockchain` vs
        # this app's default) and touch disjoint tables.

        # Re-aggregate typing profiles for users with recent sessions (hourly).
        # `expires` matches the schedule interval: a tick queued during a
        # broker/worker outage and still unconsumed an hour later is stale by
        # the time it would run (the next tick already supersedes it), so it
        # is dropped rather than piling up and firing a backlog of redundant
        # runs once a worker recovers.
        'adaptive-aggregate-typing-profiles': {
            'task': 'security.tasks.adaptive_tasks.aggregate_typing_profiles',
            'schedule': crontab(minute=15),  # Every hour at :15
            'options': {'expires': 3600},
        },

        # Expire stale adaptation suggestions (daily)
        'adaptive-cleanup-expired-adaptations': {
            'task': 'security.tasks.adaptive_tasks.cleanup_expired_adaptations',
            'schedule': crontab(hour=4, minute=45),  # 4:45 AM daily
        },

        # Fold user feedback into the Beta-Bernoulli bandit posteriors and
        # rebuild the DP-noised cross-user cold-start priors (weekly).
        # Matches ADAPTIVE_PASSWORD['RL_MODEL_UPDATE_INTERVAL_DAYS'] = 7.
        'adaptive-update-rl-model-from-feedback': {
            'task': 'security.tasks.adaptive_tasks.update_rl_model_from_feedback',
            'schedule': crontab(day_of_week=1, hour=5, minute=15),  # Mon 5:15 AM
        },

        # =================================================================
        # 🌑 Dark Protocol Network Tasks
        # =================================================================
        #
        # These task names below were already correct -- each `@shared_task`
        # in security/tasks/dark_protocol_tasks.py carries an explicit
        # `name='dark_protocol.<func>'` matching exactly what these entries
        # schedule. The bug was that `security/tasks/__init__.py` never
        # imported that module, so those decorators never ran and nothing
        # registered the names beat was asking for. Fixed by adding the
        # missing import there, mirroring the existing try/except pattern
        # already used for `time_lock_tasks` and `adaptive_tasks`; no changes
        # needed here.
        #
        # Verified safe to turn on: none of these task bodies (nor the
        # service/generator code they call) perform outbound network I/O --
        # all pure DB reads/writes over DarkProtocolConfig/GarlicSession/
        # RoutingPath/etc. Every query below is gated on `is_enabled` / an
        # active session existing, so each is a cheap no-op until Dark
        # Protocol is actually in use by a real user.
        #
        # `dark-protocol-health-check` (-> dark_protocol.health_check_nodes)
        # is deliberately NOT among the entries below (CodeRabbit, PR #482
        # round 4). That task is NOT a cheap no-op and is NOT gated on any
        # `is_enabled`-style config -- correcting the claim above, which
        # used to say otherwise. It queries every `status='active'`
        # DarkProtocolNode unconditionally, decides reachability via
        # `random.random() > 0.05` (an explicit simulation stub, not a real
        # ping -- see the function's own comment), and marks a node
        # `status='inactive'` -- a real, persistent mutation -- after 3
        # simulated failures in a rolling 5-minute window. Scheduled every
        # minute, a real node WILL eventually rack up 3 unlucky coin flips
        # purely by chance and get taken offline for a reason unrelated to
        # its actual reachability. The task stays registered (and callable
        # directly, e.g. by `test_dark_protocol.py`) but is not beat-scheduled
        # until it performs a real check or gets a config gate on the
        # mutation -- see `test_health_check_nodes_entry_stays_removed` in
        # `test_celery_beat_registry.py`.

        # Rotate anonymous routing paths (every 5 minutes)
        'dark-protocol-rotate-paths': {
            'task': 'dark_protocol.rotate_network_paths',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },

        # Generate cover traffic for active sessions (every 2 minutes)
        'dark-protocol-cover-traffic': {
            'task': 'dark_protocol.generate_cover_traffic',
            'schedule': crontab(minute='*/2'),  # Every 2 minutes
        },
        
        # Cleanup expired sessions and bundles (every 15 minutes)
        'dark-protocol-cleanup': {
            'task': 'dark_protocol.cleanup_expired_sessions',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        
        # Analyze traffic patterns for cover traffic learning (hourly)
        'dark-protocol-traffic-analysis': {
            'task': 'dark_protocol.analyze_traffic_patterns',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # =================================================================
        # 🔮 Predictive Intent Tasks
        # =================================================================
        
        # Train intent prediction model (daily at 2 AM)
        'predictive-intent-train-model': {
            'task': 'ml_security.train_intent_model',
            'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
        },
        
        # Cleanup expired predictions and preloaded credentials (hourly)
        'predictive-intent-cleanup': {
            'task': 'ml_security.cleanup_expired_predictions',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # Cleanup old patterns based on retention settings (daily at 3 AM)
        'predictive-intent-pattern-cleanup': {
            'task': 'ml_security.cleanup_old_patterns',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
        },
        
        # Preload morning credentials (daily at 6 AM)
        'predictive-intent-morning-preload': {
            'task': 'ml_security.preload_morning_credentials',
            'schedule': crontab(hour=6, minute=0),  # 6:00 AM daily
        },
        
        # Analyze usage patterns for statistics (daily at 4 AM)
        'predictive-intent-analyze-patterns': {
            'task': 'ml_security.analyze_usage_patterns',
            'schedule': crontab(hour=4, minute=0),  # 4:00 AM daily
        },
        
        # =================================================================
        # Smart Contract Automation Tasks
        # =================================================================
        
        # Check dead man's switch vaults (hourly)
        'check-dead-mans-switches': {
            'task': 'smart_contracts.tasks.check_dead_mans_switches',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # Evaluate pending vault conditions (every 15 minutes)
        'evaluate-pending-conditions': {
            'task': 'smart_contracts.tasks.evaluate_pending_conditions',
            'schedule': crontab(minute='*/15'),
        },

        # Reconcile VaultAuditLog anchors + drift vs on-chain status
        # (every 30 minutes). Picks up reveals whose broadcast landed but
        # whose receipt we didn't see in the request cycle.
        'smart-contracts-sync-onchain-state': {
            'task': 'smart_contracts.tasks.sync_onchain_state',
            'schedule': crontab(minute='*/30'),
        },

        # Self-destructing passwords: flip expired policies every 5 min
        # and hard-purge ciphertext once an hour.
        'self-destruct-expire-stale-policies': {
            'task': 'self_destruct.tasks.expire_stale_policies',
            'schedule': crontab(minute='*/5'),
        },
        'self-destruct-purge-expired-ciphertext': {
            'task': 'self_destruct.tasks.purge_expired_ciphertext',
            'schedule': crontab(minute=0),
        },

        # Ultrasonic pairing: expire TTL-past sessions every 2 minutes
        # so replay windows don't grow; hourly purge wipes ciphertext
        # from delivered/expired sessions beyond grace.
        'ultrasonic-pairing-expire-stale-sessions': {
            'task': 'ultrasonic_pairing.tasks.expire_stale_sessions',
            'schedule': crontab(minute='*/2'),
        },
        'ultrasonic-pairing-purge-delivered-payloads': {
            'task': 'ultrasonic_pairing.tasks.purge_delivered_payloads',
            'schedule': crontab(minute=15),  # every hour at :15
        },

        # Heartbeat/HRV baselines: nightly re-smoothing of per-user
        # mean+covariance to absorb slow drift without replay.
        'heartbeat-auth-recompute-baselines': {
            'task': 'heartbeat_auth.tasks.recompute_baselines',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
        },

        
        # =================================================================
        # FeatureFlagUsage Batch Flush
        # =================================================================
        
        # Flush buffered feature flag usage records to DB (every 60 seconds)
        'flush-feature-flag-usage': {
            'task': 'ab_testing.tasks.flush_feature_flag_usage',
            'schedule': 60.0,  # Every 60 seconds
        },

        # =================================================================
        # Mesh Dead Drop Password Sharing
        # =================================================================
        #
        # This is the ONLY one of `mesh_deaddrop`'s five schedulable tasks that
        # has ever run: the other four live in that module's own
        # CELERY_BEAT_SCHEDULE, which nothing merged until the
        # MESH_DEADDROP_BEAT_SCHEDULE block below the beat_schedule was added.
        #
        # Deliberately left here STATICALLY as well, rather than deleted in
        # favour of the merge. The merged dict defines `flush-pending-sync`
        # identically (same task name, same 60.0 schedule -- asserted by
        # `test_mesh_deaddrop_static_and_merged_entries_agree`, so the two
        # cannot silently drift), so the merge overwrites this with an equal
        # value and the duplication is a no-op. What it buys: this entry keeps
        # ticking even if the merge's import fails, which matters more for a
        # once-a-minute delivery drain than for the four daily/hourly sweeps.
        # Same reasoning the Honeypot block in security/tasks/__init__.py gives
        # for why Dark Protocol's entries are static and its own are not.
        'flush-pending-sync': {
            'task': 'mesh_deaddrop.flush_pending_sync',
            'schedule': 60.0,
        },

        # =================================================================
        # Social Proof-Based Recovery
        # =================================================================

        # Expire invitations and recovery requests on a cadence (every 10 min)
        'social-recovery-expire-stale-requests': {
            'task': 'social_recovery.expire_stale_requests',
            'schedule': crontab(minute='*/10'),
        },

        # Settle voucher stakes after successful recoveries (hourly).
        'social-recovery-settle-stakes': {
            'task': 'social_recovery.settle_stakes',
            'schedule': crontab(minute=30),
        },

        # =================================================================
        # Personality-Based Security Questions
        # =================================================================

        # Nightly inference refresh for opted-in profiles (once a day).
        'personality-nightly-inference': {
            'task': 'personality_auth.nightly_inference_refresh',
            'schedule': crontab(hour=2, minute=45),
        },

        # Hourly prune of expired questions and stale challenges.
        'personality-prune-expired-questions': {
            'task': 'personality_auth.prune_expired_questions',
            'schedule': crontab(minute=10),
        },

        # =================================================================
        # Biometric Liveness
        # =================================================================

        # Drain the last-resort persist outbox: verdicts whose inline DB write
        # AND broker retry path both failed. Idempotent re-apply; rows are
        # deleted on success, so a healthy system sweeps an empty table.
        'biometric-liveness-drain-persist-outbox': {
            'task': 'biometric_liveness.tasks.drain_liveness_persist_outbox',
            'schedule': crontab(minute='*/5'),
        },

        # =================================================================
        # Predictive Password Expiration (zero-knowledge)
        # =================================================================

        # Single daily pipeline (2:15 AM): the scan first refreshes threat
        # intel in-process (so it always re-scores on fresh data), then
        # dispatches a chord that runs send_expiration_notifications only after
        # every re-score completes — so notifications never fire on stale or
        # not-yet-drained risk state. No separate fixed-offset beats.
        'predictive-daily-scan': {
            'task': 'security.tasks.daily_predictive_scan',
            'schedule': crontab(hour=2, minute=15),
        },

    },
)

# =============================================================================
# Time-Lock: Password Will / Dead Man's Switch / Escrow
# =============================================================================
#
# `time_lock_tasks.py` defines its own CELERY_BEAT_SCHEDULE dict (4 entries:
# check_capsule_unlocks, check_dead_mans_switches, check_expired_capsules,
# check_escrow_deadlines), already correctly named (`time_lock.<func>`,
# matching each task's own `@shared_task(name=...)` exactly) and already
# imported by security/tasks/__init__.py as TIME_LOCK_BEAT_SCHEDULE -- but
# nothing had ever merged it into this file's beat_schedule above, so none of
# the four were ever actually scheduled despite being fully implemented.
#
# Merged via `on_after_finalize` rather than a plain import above: this
# module is imported eagerly as a side effect of `password_manager/__init__.py`
# (`from .celery import app as celery_app`), which itself runs the moment
# ANYTHING imports the `password_manager` package -- including Django's own
# `django.setup()`, which imports `password_manager.settings` as one of its
# first steps, before `apps.populate()` has finished. An eager
# `from security.tasks import ...` here (even placed after
# `app.autodiscover_tasks()`, which does NOT block on that promise -- it's
# deliberately lazy for exactly this reason) hits
# `django.core.exceptions.AppRegistryNotReady` at import time, because
# `security.tasks` pulls in `breach_tasks.py`, which does
# `from django.contrib.auth.models import User` at module level. Confirmed
# empirically: an eager version of this import crashed startup.
# `on_after_finalize` is Celery's own mechanism for exactly this kind of
# deferred setup -- it only fires once the app is finalized (first real task
# lookup, well after django.setup() has completed in normal boot), the same
# safe point `autodiscover_tasks()`'s own deferred imports rely on.
#
# SAFETY NOTE FOR DEPLOYMENT (not something this merge can fix from the code
# alone): `check-dead-mans-switches` and `check-escrow-deadlines` have real,
# externally-visible effects the first time they run --
# `trigger_password_will` unlocks a capsule and emails beneficiaries;
# `check_escrow_deadlines` can auto-release an escrow and email all parties.
# Because this beat entry has never existed, ANY PasswordWill
# (is_active=True, is_triggered=False, deadline already elapsed) or
# EscrowAgreement (is_released=False, approval_deadline already elapsed)
# sitting in production today will all fire in a single batch on the first
# tick after this deploys, rather than each having fired individually at its
# own due date. Check for a backlog before deploying -- see
# docs/time-lock-beat-schedule-plan.md §3 for the query.


# =============================================================================
# Honeypot Emails: breach canary
# =============================================================================
#
# `honeypot_tasks.py` implements the full canary loop -- poll each alias with
# its provider (SimpleLogin / AnonAddy), raise a HoneypotBreachEvent when one
# receives mail, rotate the real credential for the breached service, and email
# the user a digest. None of it had ever run: the module was never imported (so
# its nine `@shared_task`s were never registered) AND had no beat entries. See
# the block in security/tasks/__init__.py for why both halves were needed.
#
# SAFETY NOTE FOR DEPLOYMENT -- same hazard as the Time-Lock merge above, and
# for the same reason: entries that have never existed do not fire "from now
# on", they fire the WHOLE accumulated backlog on the first tick. Two entries
# carry real externally-visible effects, and they are NOT equally risky:
#
#   * `process_pending_rotations` -- the actual hazard. Its query
#     (`status='pending', initiated_at__lt=now-24h, user_confirmed=False`) has
#     no lower bound, so EVERY stale CredentialRotationLog ever accumulated
#     gets a reminder email in a single batch on the first tick. Note it sends
#     reminders; it does not itself rotate anything.
#   * `scan_all_honeypots` -- calls the alias provider (SimpleLogin/AnonAddy)
#     once per active honeypot. The first tick scans the entire backlog of
#     never-scanned aliases at once, which can trip provider rate limits and
#     can raise many HoneypotBreachEvents simultaneously.
#
# `send_breach_digest` is self-bounding (`detected_at__gte=now-24h`) and
# `cleanup_expired_honeypots` is idempotent, so neither needs pre-deploy care.
#
# Run `python manage.py check_honeypot_backlog` before deploying -- it reports
# the backlog without mutating anything. A non-zero backlog is not necessarily
# a blocker, but it must be a decision, not a surprise.


# =============================================================================
# Mesh Dead Drop: the third instance of the orphaned-schedule defect
# =============================================================================
#
# `mesh_deaddrop/tasks/deaddrop_tasks.py` defines its own CELERY_BEAT_SCHEDULE
# (5 entries) that nothing ever merged -- flagged as a follow-up in
# docs/privacy-features-gap-remediation-plan.md §4.4 with "unverified blast
# radius", now verified and fixed here.
#
# UNLIKE Time-Lock and Honeypot, only the SCHEDULING half was broken, not
# registration: `mesh_deaddrop/tasks/__init__.py` does `from .deaddrop_tasks
# import *`, and `autodiscover_tasks()` imports each installed app's `tasks`
# package, so all nine `@shared_task(name='mesh_deaddrop.*')` decorators have
# always run. Proof it registers fine today: `flush-pending-sync` is in the
# static beat_schedule above and works. So four fully-implemented tasks were
# simply never enqueued:
#
#   * check_expired_deaddrops      (hourly)
#   * check_mesh_node_health       (every 5 min)
#   * cleanup_old_access_logs      (daily)
#   * cleanup_location_cache       (every 6 hours)
#
# `rebalance_orphaned_fragments` is registered and zero-argument but is NOT in
# that module's schedule dict and is not added here -- it is a fan-out target,
# invoked by `check_mesh_node_health` only when that task actually marks nodes
# offline. The three `notify_*` tasks take a required id and must likewise stay
# unscheduled (a no-argument beat call would raise TypeError every tick).
#
# SAFETY NOTE FOR DEPLOYMENT -- same hazard as the Time-Lock and Honeypot
# merges above, and for the same reason: an entry that has never existed does
# not start firing "from now on", it fires the WHOLE accumulated backlog on the
# first tick. Verified per task rather than assumed:
#
#   * `check_expired_deaddrops` -- THE hazard. Its query
#     (`status__in=['pending','distributed','active'], expires_at__lt=now,
#     is_active=True`) has no lower bound, so EVERY dead drop that has silently
#     sat past its expiry is marked expired at once AND fires
#     `notify_owner_deaddrop_expired.delay()` -- one real email per drop, in a
#     single batch. Directly analogous to `process_pending_rotations`.
#   * `cleanup_old_access_logs` -- deletes DeadDropAccess/FragmentTransfer rows
#     older than 90 days. Not user-visible, but the first tick deletes the
#     entire accumulated backlog in one transaction; on a large table that is a
#     long-running DELETE worth scheduling deliberately.
#   * `check_mesh_node_health` -- bounded and arguably corrective: nodes unseen
#     for 10 minutes are currently left marked online forever. The first tick
#     flips all genuinely-stale nodes offline and triggers ONE
#     `rebalance_orphaned_fragments`. No notifications.
#   * `cleanup_location_cache` -- deletes cache rows older than 24h. Same shape
#     as the log cleanup but a smaller, self-bounding table. Low risk.
#
# Run `python manage.py check_deaddrop_backlog` before deploying -- it reports
# the backlog without mutating anything, mirroring `check_honeypot_backlog`.
#
# `personality_auth/tasks.py` also defines a module-level CELERY_BEAT_SCHEDULE
# and §4.4 named it as the same bug, but that turned out to be only half right:
# both of its entries (`personality-nightly-inference`,
# `personality-prune-expired-questions`) are already present in the static
# beat_schedule above, so they DO run. It is a duplicate-definition drift
# hazard rather than an orphan, and is deliberately NOT merged here -- doing so
# would silently let the module's copy override the reviewed static one. It is
# covered instead by `test_every_module_beat_schedule_is_merged`, which asserts
# every module-level dict's entries reach the live schedule by SOME route.


@app.on_after_finalize.connect
def _merge_feature_beat_schedules(sender, **kwargs):
    """Merge beat schedules that live in their own feature modules.

    Deferred to on_after_finalize rather than imported at module scope: see the
    Time-Lock comment block above for the AppRegistryNotReady failure an eager
    `from security.tasks import ...` causes here.
    """
    from mesh_deaddrop.tasks import CELERY_BEAT_SCHEDULE as MESH_DEADDROP_BEAT_SCHEDULE
    from security.tasks import HONEYPOT_BEAT_SCHEDULE, TIME_LOCK_BEAT_SCHEDULE

    sender.conf.beat_schedule.update(TIME_LOCK_BEAT_SCHEDULE)
    sender.conf.beat_schedule.update(HONEYPOT_BEAT_SCHEDULE)
    sender.conf.beat_schedule.update(MESH_DEADDROP_BEAT_SCHEDULE)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'


@app.task(bind=True)
def test_task(self):
    """Test task for health checks."""
    return {
        'status': 'success',
        'message': 'Celery worker is healthy',
        'task_id': self.request.id
    }


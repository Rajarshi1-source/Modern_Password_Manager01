"""
Celery Tasks for ML-Powered Dark Web Monitoring
Handles async processing of breach detection, credential matching, and alerts
"""

from celery import shared_task, group, chord
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
import logging
import json
import os
from typing import List, Dict

from .models import (
    BreachSource, MLBreachData, UserCredentialMonitoring,
    MLBreachMatch, DarkWebScrapeLog, BreachPatternAnalysis
)
# NOTE: `.ml_services` is intentionally NOT imported at module level.
# It pulls in `torch` and `transformers` at import time, which in turn
# imports `triton` via `torch._dynamo`. On CI runners without CUDA,
# triton's native library can segfault during initialization. Because
# `password_manager/__init__.py` always loads Celery and Celery's
# `autodiscover_tasks()` walks every INSTALLED_APPS' `tasks.py`, an
# eager import here would crash pytest before a single test ran.
# Import inside the task bodies instead — that path only fires when
# the task actually executes (in a Celery worker, not under pytest).
from vault.models import BreachAlert
from .ml_config import MLDarkWebConfig

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def process_scraped_content(self, content: str, source_id: int, content_metadata: dict = None):
    """
    Process scraped dark web content with ML classifier
    
    Args:
        content: Raw scraped content
        source_id: ID of the BreachSource
        content_metadata: Additional metadata about the content
    """
    try:
        logger.info(f"Processing content from source {source_id}")

        # Deferred — see the module-level comment above explaining why
        # `.ml_services` is not imported at the top of this file.
        from .ml_services import get_breach_classifier

        # Get the breach classifier
        classifier = get_breach_classifier()
        
        # Classify the content
        result = classifier.classify_breach(content)
        
        # Extract indicators
        indicators = classifier.extract_breach_indicators(content)
        
        if result['is_breach']:
            # Get source
            source = BreachSource.objects.get(id=source_id)
            
            # Create breach record
            breach_id = f"BREACH_{timezone.now().timestamp():.0f}_{source.id}"
            
            breach = MLBreachData.objects.create(
                breach_id=breach_id,
                title=content[:500].strip(),
                description=content[:2000].strip(),
                source=source,
                severity=result['severity'],
                confidence_score=result['confidence'],
                ml_model_version=MLDarkWebConfig.CURRENT_MODEL_VERSION,
                raw_content=content,
                processed_content=content[:5000],
                processing_status='analyzing',
                extracted_emails=indicators.get('emails', []),
                extracted_domains=indicators.get('domains', []),
                extracted_credentials=indicators.get('credentials', [])
            )
            
            logger.info(f"Breach detected: {breach.breach_id} (confidence: {result['confidence']:.2f})")
            
            # Trigger credential matching async
            match_credentials_against_breach.delay(breach.id)
            
            # Update source reliability
            update_source_reliability.delay(source_id, success=True)
            
            return {
                'success': True,
                'breach_id': breach.id,
                'severity': result['severity'],
                'confidence': result['confidence']
            }
        else:
            logger.info(f"No breach detected in content from source {source_id}")
            return {
                'success': True,
                'breach_id': None,
                'message': 'No breach detected'
            }
    
    except BreachSource.DoesNotExist:
        logger.error(f"BreachSource {source_id} not found")
        return {'success': False, 'error': 'Source not found'}
    
    except Exception as e:
        logger.error(f"Error processing content: {e}", exc_info=True)
        # Retry with exponential backoff
        self.retry(exc=e, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True)
def match_credentials_against_breach(self, breach_id: int):
    """
    Match user credentials against detected breach
    Uses Siamese network for similarity matching
    
    Args:
        breach_id: ID of the MLBreachData record
    """
    try:
        logger.info(f"Matching credentials against breach {breach_id}")
        
        # Get breach
        breach = MLBreachData.objects.get(id=breach_id)
        
        # Extract credentials from breach
        breach_credentials = breach.extracted_credentials or []
        breach_emails = breach.extracted_emails or []
        
        # Combine for matching
        all_breach_identifiers = list(set(breach_credentials + breach_emails))
        
        if not all_breach_identifiers:
            logger.warning(f"No identifiers found in breach {breach_id}")
            breach.processing_status = 'completed'
            breach.processed_at = timezone.now()
            breach.save()
            return {'success': True, 'matches': 0}
        
        # Deferred — see the module-level comment above explaining why
        # `.ml_services` is not imported at the top of this file.
        from .ml_services import get_credential_matcher

        # Get credential matcher
        matcher = get_credential_matcher()

        # Get all active monitored credentials
        monitored_credentials = UserCredentialMonitoring.objects.filter(is_active=True)
        
        matches_found = 0
        
        # Process in batches to avoid memory issues
        batch_size = MLDarkWebConfig.MATCH_BATCH_SIZE
        
        for i in range(0, monitored_credentials.count(), batch_size):
            batch = monitored_credentials[i:i + batch_size]
            batch_cred_ids = []
            
            for cred in batch:
                batch_cred_ids.append(cred.id)
                
                # Find matches
                credential_matches = matcher.find_matches(
                    cred.email_hash,
                    all_breach_identifiers
                )
                
                if credential_matches:
                    # Get best match
                    best_match = credential_matches[0]
                    similarity_score = best_match[1]
                    
                    # Create match record
                    match, created = MLBreachMatch.objects.get_or_create(
                        user=cred.user,
                        breach=breach,
                        monitored_credential=cred,
                        defaults={
                            'similarity_score': similarity_score,
                            'confidence_score': similarity_score * breach.confidence_score,
                            'match_type': 'email' if '@' in best_match[0] else 'credential',
                            'matched_data': {
                                'matched_identifier': best_match[0][:50],  # Truncate for privacy
                                'num_matches': len(credential_matches)
                            }
                        }
                    )
                    
                    if created:
                        matches_found += 1
                        logger.info(f"Match found: User {cred.user.id} - Breach {breach_id} (similarity: {similarity_score:.2f})")
                        
                        # Create alert async
                        create_breach_alert.delay(match.id)
            
            # Batch update last_checked for all credentials in this batch (single UPDATE)
            if batch_cred_ids:
                UserCredentialMonitoring.objects.filter(
                    id__in=batch_cred_ids
                ).update(last_checked=timezone.now())
        
        # Close-out the breach record. Two race-safety properties that
        # the previous in-memory `breach.processing_status` check
        # didn't give us (Codex P1 + CodeRabbit major on PR #244):
        #
        # 1. The status decision is made via an atomic SQL UPDATE with
        #    a WHERE-clause precondition, not a Python-level if/else
        #    against an object loaded at task start. That closes the
        #    "task A loads breach as 'analyzing'; task B finishes and
        #    sets 'matched'; task A's stale in-memory view thinks
        #    it's still 'analyzing' and overwrites with 'completed'"
        #    interleaving.
        #
        # 2. `affected_records` is the TRUE TOTAL across all runs, not
        #    this run's per-run delta. `matches_found` only counts
        #    rows we created via `get_or_create`; if another run
        #    already populated MLBreachMatch we'd shrink the recorded
        #    total. Re-derive the count from the DB.
        #
        # Once a breach is in 'matched' it stays there — `matched` is
        # monotonic. The exclude(processing_status='matched') below is
        # what makes "completed" race-safe: if another writer set
        # 'matched' between our load and our write, the WHERE clause
        # filters us out and we no-op on the status flip (still bump
        # processed_at + affected_records to true_total).
        true_total = MLBreachMatch.objects.filter(breach=breach).count()
        now = timezone.now()

        if true_total > 0:
            # There ARE matches for this breach (this run, or a prior
            # run that completed during ours). Always 'matched'; record
            # the true total. Single unconditional UPDATE — `matched`
            # is monotonic so concurrent writes converge.
            MLBreachData.objects.filter(pk=breach.pk).update(
                processing_status='matched',
                affected_records=true_total,
                processed_at=now,
            )
        else:
            # No matches at all. Mark 'completed' ONLY if a concurrent
            # writer hasn't already set 'matched'. The exclude() makes
            # the UPDATE atomic relative to other writers — if their
            # 'matched' write landed first, our row count is 0 and the
            # decision matrix is a no-op (still safe to bump processed_at
            # in a second UPDATE if we wanted, but skip it to keep the
            # losing-the-race path a clean no-op).
            MLBreachData.objects.filter(pk=breach.pk).exclude(
                processing_status='matched',
            ).update(
                processing_status='completed',
                affected_records=0,
                processed_at=now,
            )
        
        logger.info(f"Credential matching completed for breach {breach_id}. {matches_found} matches found.")
        
        return {
            'success': True,
            'breach_id': breach_id,
            'matches': matches_found
        }
    
    except MLBreachData.DoesNotExist:
        logger.error(f"Breach {breach_id} not found")
        return {'success': False, 'error': 'Breach not found'}
    
    except Exception as e:
        logger.error(f"Error matching credentials: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def check_compromised_passwords(stale_analyzing_minutes: int = 30, max_dispatch: int = 200):
    """
    Periodic sweep that re-drives credential matching for breaches the
    inline pipeline didn't finish.

    This task is the target of the Celery beat schedule entry
    ``check-data-breaches`` (every 6 hours; see
    ``password_manager/celery.py``). Without a matching function on
    the module, beat would silently ``KeyError`` on each fire — which
    is exactly the dead-entry CodeRabbit flagged in the review of
    PR #241. Adding the function here makes the schedule actually
    work and gives us an observable sweep loop in production.

    What it does
    ------------
    Finds ``MLBreachData`` rows in a non-terminal processing state and
    dispatches :func:`match_credentials_against_breach` for each. Two
    sources of work:

      * ``processing_status='pending'`` — breach detected but no
        matching pass started yet (e.g. inline classifier landed but
        the matcher worker was offline at the time).
      * ``processing_status='analyzing'`` rows whose ``detected_at`` is
        older than ``stale_analyzing_minutes`` — worker likely crashed
        mid-pass; rematching is safe because the matcher path is
        idempotent (``MLBreachMatch.get_or_create``).

    Bounded dispatch
    ----------------
    The query is capped at ``max_dispatch`` rows so a sudden flood of
    pending breaches can't generate a multi-thousand-task storm in one
    beat tick. Unprocessed rows roll over to the next 6-hour tick.

    Idempotence
    -----------
    Re-dispatching ``match_credentials_against_breach`` for the same
    ``breach_id`` is safe: the matcher uses
    ``MLBreachMatch.objects.get_or_create`` keyed by
    ``(user, breach, monitored_credential)`` and only counts newly-
    created rows in its ``matches_found`` return value.

    Args:
        stale_analyzing_minutes: How old an ``analyzing`` row must be
            before we treat it as stuck and rematch it.
        max_dispatch: Per-tick safety cap on dispatched matching tasks.

    Returns:
        ``{'success': bool, 'dispatched': int, 'pending': int,
        'stuck': int}`` so the beat log line is observable. Failure
        modes set ``success=False`` and an ``error`` key.
    """
    # Reject obviously-malformed input (CodeRabbit major on PR #244):
    # negative `max_dispatch` makes a queryset slice `[:negative]` skip
    # the safety cap entirely on some ORMs; negative
    # `stale_analyzing_minutes` would make the cutoff point in the
    # future and silently re-dispatch every analyzing row. Fail closed
    # with a clear error instead of producing weird behaviour.
    if not isinstance(stale_analyzing_minutes, int) or stale_analyzing_minutes < 0:
        return {'success': False, 'error': 'stale_analyzing_minutes must be a non-negative int'}
    if not isinstance(max_dispatch, int) or max_dispatch < 0:
        return {'success': False, 'error': 'max_dispatch must be a non-negative int'}
    if max_dispatch == 0:
        # Caller explicitly disabled this tick. Return a clean zero.
        return {'success': True, 'dispatched': 0, 'pending': 0, 'stuck': 0}

    try:
        stuck_cutoff = timezone.now() - timezone.timedelta(minutes=stale_analyzing_minutes)
        # An ``analyzing`` row is "stuck" when the last time the matcher
        # pipeline touched it (either by claim or by completion) is
        # older than the staleness cutoff. We use ``processed_at`` for
        # this when set (claim writes it, completion writes it) and
        # fall back to ``detected_at`` when ``processed_at`` is NULL
        # — that's the case for rows that were created in the
        # ``analyzing`` state but never reached either path. Codex P2
        # on PR #244 caught the earlier version where a stuck-row
        # claim wrote ``analyzing`` over ``analyzing`` without moving
        # any timestamp out of the stale window, so the same row
        # stayed eligible for every subsequent tick.
        stuck_filter = (
            Q(processing_status='analyzing')
            & (
                Q(processed_at__isnull=True, detected_at__lt=stuck_cutoff)
                | Q(processed_at__lt=stuck_cutoff)
            )
        )

        # Build the candidate set as a single query so we keep the
        # ordering deterministic (oldest-first) for both halves —
        # important so the same backlog isn't repeatedly partial-
        # processed on every tick.
        candidates = (
            MLBreachData.objects
            .filter(Q(processing_status='pending') | stuck_filter)
            .order_by('detected_at')
            .values_list('id', 'processing_status')[:max_dispatch]
        )
        candidates = list(candidates)

        pending = sum(1 for _id, status in candidates if status == 'pending')
        stuck = sum(1 for _id, status in candidates if status == 'analyzing')

        # Atomically CLAIM each candidate before dispatching the match
        # task. Codex P1 on PR #244 caught a real race: between the
        # candidate-select above and the dispatch below, another worker
        # (or a previous still-queued copy of this sweep) could already
        # be processing the same row. Without a claim step we'd
        # double-dispatch — and the matcher's "find zero NEW matches"
        # path used to regress 'matched' rows back to 'completed' with
        # affected_records=0. The matcher fix (above) closes the
        # regression hole; the claim step also closes the duplicate-
        # work hole that the matcher's get_or_create makes harmless
        # but still wasteful.
        #
        # The claim semantics:
        #   * pending row: atomic transition pending → analyzing.
        #     UPDATE returns 1 only if the row is STILL pending. If a
        #     racing worker already flipped it to analyzing, we get
        #     zero and skip dispatch.
        #   * stuck-analyzing row: re-claim with an explicit
        #     stuck-window precondition (same WHERE we used in the
        #     candidate select). The status stays 'analyzing'; the
        #     WHERE clause is what makes the UPDATE atomic.
        #
        # Both branches also write `processed_at = now` so a
        # subsequent sweep tick sees the row as "freshly touched"
        # and excludes it from the stuck candidate set. Without this
        # bump, a slow-running matcher pass (>= stale_analyzing_minutes)
        # would let the next tick re-dispatch the same row.
        #
        # Broker-publish failure handling: if `.delay()` raises (e.g.
        # Redis down), we revert the claim so the next sweep can pick
        # the row back up without waiting for staleness recapture.
        # CodeRabbit major on PR #244.
        now = timezone.now()
        dispatched = 0
        for breach_id, original_status in candidates:
            # Snapshot the pre-claim processed_at so a broker-publish
            # failure can fully revert the claim (status + timestamp).
            # Codex P2 on PR #244 follow-up: without this, a stuck-row
            # claim that failed to dispatch left processed_at freshened
            # to "now", hiding the row from the next sweep's stuck
            # filter until staleness recapture (~30 min).
            prior_processed_at = (
                MLBreachData.objects
                .filter(id=breach_id)
                .values_list('processed_at', flat=True)
                .first()
            )
            if original_status == 'pending':
                claim_qs = MLBreachData.objects.filter(
                    id=breach_id, processing_status='pending',
                )
                claimed = claim_qs.update(
                    processing_status='analyzing',
                    processed_at=now,
                )
            else:
                # Stuck-analyzing: re-confirm the stuck-window
                # precondition at UPDATE time so a worker that just
                # started won't lose its claim to us. WHERE clause
                # mirrors the `stuck_filter` used in the candidate
                # select. The UPDATE writes the same `analyzing`
                # status back (no-op data-wise), but moves
                # `processed_at` out of the stale window — that's
                # the real claim signal.
                claim_qs = MLBreachData.objects.filter(
                    id=breach_id,
                    processing_status='analyzing',
                ).filter(
                    Q(processed_at__isnull=True, detected_at__lt=stuck_cutoff)
                    | Q(processed_at__lt=stuck_cutoff)
                )
                claimed = claim_qs.update(
                    processing_status='analyzing',
                    processed_at=now,
                )
            if claimed:
                try:
                    match_credentials_against_breach.delay(breach_id)
                    dispatched += 1
                except Exception:
                    # Broker publish failed. Revert the claim so the
                    # row is available to the next sweep tick rather
                    # than waiting for staleness recapture (~30 min).
                    #
                    # We revert BOTH dimensions of the claim:
                    #   * status (pending → analyzing flip, when the
                    #     original was 'pending')
                    #   * processed_at (we bumped it to `now`; restore
                    #     the pre-claim value so the next sweep's
                    #     stuck filter sees the row as eligible again
                    #     instead of hidden for stale_analyzing_minutes)
                    revert_fields = {'processed_at': prior_processed_at}
                    if original_status == 'pending':
                        revert_fields['processing_status'] = 'pending'
                    MLBreachData.objects.filter(id=breach_id).update(**revert_fields)
                    # Re-raise so the outer try/except logs the
                    # broker error and returns success=False.
                    raise

        # NOTE on the count semantics (CodeRabbit nit on PR #244):
        # `pending` and `stuck` are the counts from the candidate
        # SELECT BEFORE the per-row claim races. `dispatched` is the
        # count of rows that ACTUALLY won their claim and got
        # forwarded to the matcher. After a lost race, `dispatched`
        # is strictly less than `pending + stuck`. The log line and
        # return shape preserve both numbers so the gap between
        # "candidates seen" and "dispatched" is observable in
        # production.
        logger.info(
            'check_compromised_passwords dispatched=%d '
            '(candidates_pending=%d, candidates_stuck=%d, candidates_total=%d)',
            dispatched, pending, stuck, len(candidates),
        )
        return {
            'success': True,
            'dispatched': dispatched,
            'pending': pending,
            'stuck': stuck,
        }
    except Exception as e:  # noqa: BLE001 — sweep must never crash beat
        # Use logger.exception with a static message so Semgrep's
        # `python-logger-credential-disclosure` rule (which scans the
        # format-string argument for secret-looking literals) doesn't
        # false-positive on the task name. The traceback carries the
        # diagnostic context; the exception's str() goes into the
        # response payload, not the log message.
        logger.exception('check_compromised_passwords sweep failed')  # nosemgrep
        return {'success': False, 'error': str(e)}


@shared_task
def create_breach_alert(match_id: int):
    """
    Create and send breach alert to user
    
    Args:
        match_id: ID of the MLBreachMatch record
    """
    try:
        match = MLBreachMatch.objects.select_related('user', 'breach', 'monitored_credential').get(id=match_id)
        
        # Check if alert already created
        if match.alert_created:
            logger.warning(f"Alert already created for match {match_id}")
            return {'success': True, 'message': 'Alert already exists'}
        
        # Create BreachAlert
        alert = BreachAlert.objects.create(
            user=match.user,
            breach_name=match.breach.title[:255],
            breach_date=match.breach.breach_date.date() if match.breach.breach_date else timezone.now().date(),
            breach_description=match.breach.description[:1000],
            data_type='email',  # or determine from match_type
            identifier=match.monitored_credential.domain,
            exposed_data={
                'types': match.breach.exposed_data_types,
                'severity': match.breach.severity,
                'confidence': match.confidence_score
            },
            severity=match.breach.severity.lower(),
            detected_at=match.detected_at,
            notified=False
        )
        
        # Update match record
        match.alert_created = True
        match.alert_id = alert.id
        match.save()
        
        logger.info(f"Alert created: {alert.id} for user {match.user.id}")
        
        # Send notification
        send_breach_notification.delay(alert.id)
        
        return {
            'success': True,
            'alert_id': alert.id
        }
    
    except MLBreachMatch.DoesNotExist:
        logger.error(f"Match {match_id} not found")
        return {'success': False, 'error': 'Match not found'}
    
    except Exception as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def send_breach_notification(alert_id: int):
    """
    Send real-time notification to user via WebSocket
    
    Args:
        alert_id: ID of the BreachAlert
    """
    try:
        alert = BreachAlert.objects.select_related('user').get(id=alert_id)
        
        # Send via Django Channels WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{alert.user.id}",
                {
                    'type': 'breach_alert',
                    'message': {
                        'alert_id': alert.id,
                        'breach_name': alert.breach_name,
                        'severity': alert.severity,
                        'detected_at': alert.detected_at.isoformat(),
                        'description': alert.breach_description[:200]
                    }
                }
            )
            
            logger.info(f"WebSocket notification sent to user {alert.user.id}")
        else:
            logger.warning("Channel layer not configured. Notification not sent.")
        
        # Mark as notified
        alert.notified = True
        alert.notification_sent_at = timezone.now()
        alert.save()
        
        # Optional: Send email notification
        # send_email_notification.delay(alert_id)
        
        return {'success': True}
    
    except BreachAlert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")
        return {'success': False, 'error': 'Alert not found'}
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def broadcast_alert_update(user_id: int, alert_id: int, update_type: str, additional_data: dict = None):
    """
    Broadcast real-time alert status updates to user via WebSocket
    
    Args:
        user_id: ID of the User
        alert_id: ID of the BreachAlert
        update_type: Type of update ('marked_read', 'resolved', 'dismissed', etc.)
        additional_data: Optional additional data to send
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        if not channel_layer:
            logger.warning("Channel layer not configured. Alert update not broadcast.")
            return {'success': False, 'error': 'Channel layer not configured'}
        
        # Prepare message
        message = {
            'alert_id': alert_id,
            'update_type': update_type,
            'timestamp': timezone.now().isoformat()
        }
        
        if additional_data:
            message.update(additional_data)
        
        # Send via WebSocket
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                'type': 'alert_update',
                'message': message
            }
        )
        
        logger.info(f"Alert update broadcast to user {user_id}: {update_type}")
        
        return {'success': True}
    
    except Exception as e:
        logger.error(f"Error broadcasting alert update: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def scrape_dark_web_source(self, source_id: int):
    """
    Scrape a dark web source for breach data using Scrapy.

    Runs the spider in a subprocess so the Twisted reactor never blocks the
    Celery worker thread.  The subprocess writes JSON to a temp file which
    this task reads after completion.
    """
    import glob
    import os
    import subprocess
    import sys
    import tempfile

    SCRAPE_TIMEOUT = int(os.environ.get('SCRAPE_TIMEOUT_SECONDS', 3600))

    spider_map = {
        'forum': 'BreachForumSpider',
        'pastebin': 'PastebinSpider',
        'marketplace': 'GenericDarkWebSpider',
        'telegram': 'GenericDarkWebSpider',
        'other': 'GenericDarkWebSpider',
    }

    try:
        source = BreachSource.objects.get(id=source_id, is_active=True)

        scrape_log = DarkWebScrapeLog.objects.create(
            source=source,
            status='running',
        )

        logger.info(f"Starting scrape of {source.name}")

        spider_name = spider_map.get(source.source_type, 'GenericDarkWebSpider')
        fd, output_file = tempfile.mkstemp(
            prefix=f'scrape_{source_id}_',
            suffix='.json',
        )
        os.close(fd)

        cmd = [
            sys.executable, '-m', 'scrapy', 'crawl', spider_name,
            '-a', f'url={source.url}',
            '-a', 'use_tor=True',
            '-a', f'source_id={source_id}',
            '-o', output_file,
            '-t', 'json',
        ]

        scrapy_env = os.environ.copy()
        scrapy_env.setdefault('SCRAPY_SETTINGS_MODULE', 'ml_dark_web.scrapers.dark_web_spider')

        logger.info(f"Launching spider subprocess for {source.name}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=scrapy_env,
        )

        try:
            stdout, stderr = proc.communicate(timeout=SCRAPE_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(
                f"Spider for source {source_id} timed out after {SCRAPE_TIMEOUT}s"
            )

        if proc.returncode != 0:
            err_msg = stderr.decode('utf-8', errors='replace')[-2000:]
            logger.error(f"Spider exited {proc.returncode}: {err_msg}")
            raise RuntimeError(f"Spider exited with code {proc.returncode}")

        scraped_content = []
        breaches_detected = 0

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, 'r') as f:
                scraped_items = json.load(f)
                scraped_content = scraped_items if isinstance(scraped_items, list) else [scraped_items]

                for item in scraped_content:
                    process_scraped_content.delay(
                        content=item.get('content', ''),
                        source_id=source_id,
                        content_metadata=item,
                    )

                    indicators = item.get('indicators', {})
                    if indicators.get('has_breach_keyword') or indicators.get('has_password_keyword'):
                        breaches_detected += 1

            os.remove(output_file)
            logger.info(f"Processed {len(scraped_content)} items from {source.name}")
        else:
            logger.warning(f"No output file found for scrape {source_id}")
            if os.path.exists(output_file):
                os.remove(output_file)

        scrape_log.items_found = len(scraped_content)
        scrape_log.breaches_detected = breaches_detected
        scrape_log.status = 'completed'
        scrape_log.completed_at = timezone.now()
        scrape_log.processing_time_seconds = (
            scrape_log.completed_at - scrape_log.started_at
        ).total_seconds()
        scrape_log.save()

        source.last_scraped = timezone.now()
        source.save()

        logger.info(f"Scrape completed: {source.name}. {breaches_detected} breaches detected.")

        return {
            'success': True,
            'source_id': source_id,
            'items_found': len(scraped_content),
            'breaches_detected': breaches_detected,
        }

    except BreachSource.DoesNotExist:
        logger.error(f"Source {source_id} not found or inactive")
        return {'success': False, 'error': 'Source not found'}

    except Exception as e:
        logger.error(f"Error scraping source: {e}", exc_info=True)

        if 'scrape_log' in locals():
            scrape_log.status = 'failed'
            scrape_log.error_message = str(e)[:500]
            scrape_log.completed_at = timezone.now()
            scrape_log.save()

        raise self.retry(exc=e)


@shared_task
def scrape_all_active_sources():
    """
    Scrape all active dark web sources
    Called periodically by Celery beat
    """
    logger.info("Starting scheduled scrape of all active sources")
    
    active_sources = BreachSource.objects.filter(is_active=True)
    
    # Create a group of scraping tasks
    job = group(scrape_dark_web_source.s(source.id) for source in active_sources)
    result = job.apply_async()
    
    logger.info(f"Initiated scraping for {active_sources.count()} sources")
    
    return {
        'success': True,
        'sources_count': active_sources.count(),
        'task_id': result.id
    }


@shared_task
def update_source_reliability(source_id: int, success: bool = True):
    """
    Update source reliability score based on scraping results
    
    Args:
        source_id: ID of the BreachSource
        success: Whether the scrape was successful
    """
    try:
        source = BreachSource.objects.get(id=source_id)
        
        # Update reliability score (exponential moving average)
        alpha = 0.1  # Weight for new observation
        new_observation = 1.0 if success else 0.0
        source.reliability_score = (alpha * new_observation) + ((1 - alpha) * source.reliability_score)
        source.save(update_fields=['reliability_score'])
        
        logger.info(f"Updated reliability for {source.name}: {source.reliability_score:.2f}")
        
        return {'success': True, 'reliability': source.reliability_score}
    
    except BreachSource.DoesNotExist:
        logger.error(f"Source {source_id} not found")
        return {'success': False, 'error': 'Source not found'}


@shared_task
def analyze_breach_patterns():
    """
    Analyze breach patterns using LSTM
    Detect temporal patterns, threat actors, etc.
    """
    # TODO: Implement LSTM pattern detection
    # This would analyze sequences of breaches over time
    # to detect patterns and predict future breaches
    
    logger.info("Breach pattern analysis started")
    
    try:
        # Get recent breaches
        recent_breaches = MLBreachData.objects.filter(
            detected_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).order_by('detected_at')
        
        if recent_breaches.count() < 10:
            logger.info("Not enough data for pattern analysis")
            return {'success': True, 'message': 'Insufficient data'}
        
        # TODO: Implement LSTM model for pattern detection
        # For now, return placeholder
        
        logger.info(f"Analyzed {recent_breaches.count()} recent breaches")
        
        return {
            'success': True,
            'breaches_analyzed': recent_breaches.count()
        }
    
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_breach_data(days_to_keep: int = 365):
    """
    Clean up old breach data to maintain database performance
    
    Args:
        days_to_keep: Number of days of data to keep
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        # Delete old breach data (keep alerts)
        deleted_breaches = MLBreachData.objects.filter(
            detected_at__lt=cutoff_date,
            processing_status='completed'
        ).delete()
        
        # Delete old scrape logs
        deleted_logs = DarkWebScrapeLog.objects.filter(
            started_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleanup completed: {deleted_breaches[0]} breaches, {deleted_logs[0]} logs deleted")
        
        return {
            'success': True,
            'breaches_deleted': deleted_breaches[0],
            'logs_deleted': deleted_logs[0]
        }
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def monitor_user_credentials(user_id: int, credentials: List[str]):
    """
    Add user credentials to monitoring system
    
    Args:
        user_id: ID of the user
        credentials: List of credentials (emails) to monitor
    """
    try:
        # Deferred — see the module-level comment above explaining why
        # `.ml_services` is not imported at the top of this file.
        from .ml_services import get_credential_matcher

        user = User.objects.get(id=user_id)
        matcher = get_credential_matcher()
        
        added_count = 0
        
        for credential in credentials:
            # Hash credential
            email_hash = matcher.hash_credential(credential)
            
            # Extract domain
            domain = credential.split('@')[-1] if '@' in credential else 'unknown'
            
            # Get embedding
            embedding = matcher.get_embedding(email_hash)
            
            # Create or update monitoring record
            monitoring, created = UserCredentialMonitoring.objects.get_or_create(
                user=user,
                email_hash=email_hash,
                defaults={
                    'domain': domain,
                    'email_embedding': embedding.tobytes(),
                    'is_active': True
                }
            )
            
            if created:
                added_count += 1
        
        logger.info(f"Added {added_count} credentials for monitoring (user: {user_id})")
        
        # Trigger immediate check against existing breaches
        check_user_against_all_breaches.delay(user_id)
        
        return {
            'success': True,
            'added': added_count
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    
    except Exception as e:
        logger.error(f"Error monitoring credentials: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def check_user_against_all_breaches(user_id: int):
    """
    Check a user's credentials against all existing breaches
    Used when adding new monitoring or for periodic checks
    
    Args:
        user_id: ID of the user
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Get user's monitored credentials
        monitored_creds = UserCredentialMonitoring.objects.filter(
            user=user,
            is_active=True
        )
        
        if not monitored_creds.exists():
            logger.info(f"No monitored credentials for user {user_id}")
            return {'success': True, 'message': 'No credentials to check'}
        
        # Get all unprocessed breaches
        breaches = MLBreachData.objects.filter(
            processing_status__in=['matched', 'completed']
        )
        
        matches_found = 0
        
        # Check against each breach
        for breach in breaches:
            result = match_credentials_against_breach.delay(breach.id)
            # The task will handle individual user matching
        
        logger.info(f"Initiated breach checks for user {user_id} against {breaches.count()} breaches")
        
        return {
            'success': True,
            'breaches_checked': breaches.count()
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    
    except Exception as e:
        logger.error(f"Error checking breaches: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


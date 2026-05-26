import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from vault.models import BreachAlert
from security.services.breach_monitor import HIBPService
from security.tasks import scan_user_vault
from password_manager.throttling import PasswordCheckRateThrottle, SecurityOperationThrottle

logger = logging.getLogger(__name__)


class DarkWebViewSet(viewsets.ViewSet):
    """API endpoints for dark web monitoring and breach alerts"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordCheckRateThrottle]
    
    @action(detail=False, methods=['post'])
    def check_password(self, request):
        """
        Check if a password hash prefix appears in breached data
        Using k-anonymity model to protect the full hash
        """
        hash_prefix = request.data.get('hash_prefix')
        if not hash_prefix or len(hash_prefix) != 5:
            return Response(
                {'error': 'Valid hash prefix required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Call HIBP API to get hash suffixes
            response = HIBPService.check_password_prefix(hash_prefix)
            return Response(response)
        except Exception as e:
            logger.exception("Handled Exception in view")
            return Response(
                {'error': 'internal_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_breaches(self, request):
        """Get all breach alerts for the current user"""
        alerts = BreachAlert.objects.filter(user=request.user)
        
        # Serialize alerts
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'breach_name': alert.breach_name,
                'breach_date': alert.breach_date,
                'breach_description': alert.breach_description,
                'data_type': alert.data_type,
                'identifier': alert.identifier,
                'exposed_data': alert.exposed_data,
                'severity': alert.severity,
                'detected_at': alert.detected_at,
                'resolved': alert.resolved,
                'resolved_at': alert.resolved_at,
                'notified': alert.notified,
                'notification_sent_at': alert.notification_sent_at
            })
            
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def mark_resolved(self, request):
        """Mark a breach alert as resolved"""
        alert_id = request.data.get('alert_id')
        if not alert_id:
            return Response(
                {'error': 'Alert ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            alert = BreachAlert.objects.get(id=alert_id, user=request.user)
            alert.resolved = True
            alert.resolved_at = timezone.now()
            alert.save()
            
            return Response({'status': 'success'})
            
        except BreachAlert.DoesNotExist:
            return Response(
                {'error': 'Alert not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Phase E / E2 (2026-05): cache key prefix for vault-scan task
    # ownership. The TTL is derived from Celery's ``result_expires``
    # setting so the cache entry expires together with the underlying
    # task result — there's no point remembering the owner of a task
    # whose result has been purged from the Celery backend. Default
    # is 3600s (1h) matching the project's celery.py.
    #
    # PR #276 review (Codex P1): the cache here is Django's default
    # ``django.core.cache.cache``. In a multi-worker deployment this
    # MUST be a shared backend (Redis, Memcached) — the per-process
    # ``LocMemCache`` default would route writes in scan_vault to one
    # worker's memory and reads in scan_status to another's, producing
    # spurious 404s for the rightful owner. This codebase's production
    # CACHES config sets ``USE_REDIS_CACHE=True`` which switches the
    # default to Redis; the same env var also gates the rate-limiting
    # cache (see settings/base.py:328-393). Local dev with a single
    # Daphne process is fine on LocMemCache.
    _SCAN_OWNER_CACHE_PREFIX = 'scan_task_owner:'

    @classmethod
    def _scan_owner_cache_ttl(cls):
        # Read from Celery config so the two values can't drift.
        # Falls back to 3600s matching the celery.py default.
        from django.conf import settings as _s
        return int(getattr(_s, 'CELERY_RESULT_EXPIRES', 3600) or 3600)

    @action(detail=False, methods=['post'])
    def scan_vault(self, request):
        """Trigger a scan of the user's vault for breached credentials.

        Phase E / E2 (2026-05): records ``cache['scan_task_owner:<id>']
        = user.id`` so ``scan_status`` can verify the caller is the
        task's owner before returning the result. Without this, an
        authenticated user with a leaked task_id (logs, browser
        history, frontend telemetry) could read another user's scan
        result — a classic IDOR.

        See the class-level docstring on _SCAN_OWNER_CACHE_PREFIX for
        the multi-worker cache-backend requirement.
        """
        from django.core.cache import cache

        task = scan_user_vault.delay(request.user.id)
        cache.set(
            self._SCAN_OWNER_CACHE_PREFIX + task.id,
            request.user.id,
            timeout=self._scan_owner_cache_ttl(),
        )

        return Response({
            'status': 'started',
            'task_id': task.id
        })

    @action(detail=False, methods=['get'])
    def scan_status(self, request):
        """Get the status of a vault scan task.

        Phase E / E2 (2026-05): verifies task ownership against the
        cache before reading from Celery's result backend. Returns
        404 (not 403) for "not yours" so an attacker can't enumerate
        valid task_ids by treating 404 vs 403 as a side channel.
        """
        from django.core.cache import cache

        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {'error': 'Task ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Phase E / E2: ownership check. Same response shape for
        # "task not found in cache" and "task belongs to a different
        # user" — both return 404 so an attacker can't distinguish
        # via the response.
        cached_owner_id = cache.get(self._SCAN_OWNER_CACHE_PREFIX + task_id)
        if cached_owner_id is None or cached_owner_id != request.user.id:
            return Response(
                {'error': 'not_found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Check celery task status
            task = scan_user_vault.AsyncResult(task_id)
            
            if task.state == 'PENDING':
                response = {
                    'status': 'pending',
                    'progress': 0
                }
            elif task.state == 'SUCCESS':
                response = {
                    'status': 'completed',
                    'result': task.result
                }
            elif task.state == 'FAILURE':
                # Celery's `task.result` for FAILURE is the exception
                # repr/traceback. Log it server-side and return only the
                # sanitized constant to the client (CodeQL #1133-#1303
                # family, completing the codemod's coverage manually).
                logger.error(
                    "Vault scan task failed",
                    extra={'task_id': task_id, 'task_result': str(task.result)},
                )
                response = {
                    'status': 'failed',
                    'error': 'internal_error',
                }
            else:
                response = {
                    'status': task.state,
                    'progress': task.info.get('progress', 0) if task.info else 0
                }
                
            return Response(response)
            
        except Exception as e:
            logger.exception("Handled Exception in view")
            return Response(
                {'error': 'internal_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

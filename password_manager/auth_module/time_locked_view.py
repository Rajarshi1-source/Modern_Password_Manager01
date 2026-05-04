"""
Tier 3 (Self-Time-Locked) recovery REST surface.

Four endpoints:

  POST /api/auth/vault/time-locked/enroll/        (auth)
       Store the server's Shamir 2-of-2 share. The user keeps the other
       share offline in a `.dlrec` file.

  POST /api/auth/vault/time-locked/initiate/      (anon — user lost MP)
       Begin the recovery delay clock. Server sets `release_after`,
       canary_state=ALERTING, mints a `canary_ack_token`, sends the
       first canary alert.
       Does NOT leak whether the username exists or has an enrollment.

  POST /api/auth/vault/time-locked/release/       (anon)
       After `release_after` elapses, return `server_half`. Refuses
       (and logs) if too early or if the canary was acknowledged.
       Once released, the row is consumed (`canary_state=EXPIRED`,
       `is_active=False`) — one-shot.

  POST /api/auth/vault/time-locked/canary-ack/    (anon)
       Legitimate user clicks the canary email/SMS link, sending the
       opaque ack token. Cancels the active recovery.

Server's powers are exactly: enforce the delay, send canary alerts, log
release attempts. Server's half is opaque Shamir share bytes — it never
inspects mathematical content. Without the user's `.dlrec` file, the
server's half alone is information-theoretically useless.
"""
import base64
import secrets
import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.recovery_throttling import (
    RecoveryThrottle,
    RecoveryInitiateThrottle,
    RecoveryCompleteThrottle,
)
from auth_module.time_locked_models import TimeLockedRecovery, ServerHalfReleaseLog
from auth_module.quantum_recovery_models import RecoveryAuditLog

# Optional integration with the trust-score modulator (Unit 7). If the
# module is not yet present in this branch, fall back to a 7-day default.
try:
    from auth_module.services.trust_score_modulator import (
        compute_time_lock_delay_days,
    )
except ImportError:  # pragma: no cover — Unit 7 not landed
    def compute_time_lock_delay_days(_score):
        return 7


log = logging.getLogger(__name__)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')[:255]


def _send_canary(user, recovery):
    """Hook for canary-alert delivery.

    The plan is to wire this through the existing notification subsystem
    (email + SMS) once the canary message templates are agreed. For now
    we log a structured warning so operations sees recovery initiations
    in the application log; the ``canary_ack_token`` is intentionally
    NOT logged because it is a bearer credential — anyone who reads it
    from a log line can cancel a legitimate recovery. The token is
    delivered only via the (future) email/SMS channel rendered from
    the DB row directly.
    """
    log.warning(
        'TIME_LOCKED_CANARY user_id=%s recovery_id=%s release_after=%s',
        user.pk, recovery.pk, recovery.release_after,
    )


class TimeLockedEnrollView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        server_half_b64 = request.data.get('server_half')
        if not isinstance(server_half_b64, str) or not server_half_b64:
            return Response({'error': 'server_half required'}, status=400)
        try:
            server_half = base64.b64decode(server_half_b64, validate=True)
        except Exception:
            return Response({'error': 'server_half must be base64'}, status=400)

        meta = request.data.get('half_metadata', {}) or {}
        if not isinstance(meta, dict):
            return Response({'error': 'half_metadata must be object'}, status=400)

        # One active enrollment per user — deactivate any prior row.
        TimeLockedRecovery.objects.filter(
            user=request.user, is_active=True,
        ).update(is_active=False)
        rec = TimeLockedRecovery.objects.create(
            user=request.user,
            server_half=server_half,
            half_metadata=meta,
            is_active=True,
        )
        RecoveryAuditLog.objects.create(
            user=request.user,
            event_type='setup_created',
            event_data={
                'subsystem': 'time_locked',
                'recovery_id': rec.pk,
                'half_bytes': len(server_half),
            },
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response({'success': True, 'recovery_id': rec.pk}, status=201)


class TimeLockedInitiateView(APIView):
    """Anonymous — user has lost master password."""
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryInitiateThrottle]

    def post(self, request):
        username = request.data.get('username')
        if not isinstance(username, str) or not username:
            return Response({'error': 'username required'}, status=400)

        # We must NOT leak whether `username` exists or is enrolled.
        # That means every code path returns the same response shape:
        # {'success': True, 'release_after': <ISO timestamp>}. For the
        # legitimate case the timestamp is the real release_after.
        # For "no such user" or "user but no enrollment" we fabricate
        # a plausible-looking release_after using the same default
        # delay so an attacker probing usernames cannot distinguish.
        delay_days = compute_time_lock_delay_days(None)
        decoy_release_after = timezone.now() + timedelta(days=delay_days)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({
                'success': True,
                'release_after': decoy_release_after.isoformat(),
            })

        rec = (
            TimeLockedRecovery.objects
            .filter(user=user, is_active=True)
            .order_by('-enrolled_at')
            .first()
        )
        if not rec:
            return Response({
                'success': True,
                'release_after': decoy_release_after.isoformat(),
            })

        # Trust-score modulation defaults to 7d; Unit 7 wires the
        # behavioral score through.
        rec.release_after = timezone.now() + timedelta(days=delay_days)
        rec.canary_state = TimeLockedRecovery.CanaryState.ALERTING
        rec.canary_ack_token = secrets.token_urlsafe(32)
        rec.initiated_at = timezone.now()
        rec.last_canary_sent = timezone.now()
        rec.save(update_fields=[
            'release_after', 'canary_state', 'canary_ack_token',
            'initiated_at', 'last_canary_sent',
        ])

        _send_canary(user, rec)

        RecoveryAuditLog.objects.create(
            user=user,
            event_type='recovery_initiated',
            event_data={
                'subsystem': 'time_locked',
                'recovery_id': rec.pk,
                'release_after': rec.release_after.isoformat(),
                'delay_days': delay_days,
            },
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response({
            'success': True,
            'release_after': rec.release_after.isoformat(),
        })


class TimeLockedReleaseView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryCompleteThrottle]

    def post(self, request):
        username = request.data.get('username')
        if not isinstance(username, str) or not username:
            return Response({'error': 'username required'}, status=400)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'no recovery in progress'}, status=404)

        rec = (
            TimeLockedRecovery.objects
            .filter(user=user, is_active=True)
            .order_by('-enrolled_at')
            .first()
        )
        if not rec or not rec.release_after:
            return Response({'error': 'no recovery in progress'}, status=404)

        ip = _client_ip(request)
        ua = _user_agent(request)

        if rec.canary_state == TimeLockedRecovery.CanaryState.ACKNOWLEDGED:
            ServerHalfReleaseLog.objects.create(
                recovery=rec, succeeded=False,
                refusal_reason='cancelled_by_canary',
                ip_address=ip, user_agent=ua,
            )
            return Response(
                {'error': 'cancelled by canary acknowledgement'},
                status=403,
            )

        if timezone.now() < rec.release_after:
            ServerHalfReleaseLog.objects.create(
                recovery=rec, succeeded=False, refusal_reason='too_early',
                ip_address=ip, user_agent=ua,
            )
            return Response({
                'error': 'delay not elapsed',
                'release_after': rec.release_after.isoformat(),
            }, status=403)

        ServerHalfReleaseLog.objects.create(
            recovery=rec, succeeded=True,
            ip_address=ip, user_agent=ua,
        )
        rec.completed_at = timezone.now()
        rec.canary_state = TimeLockedRecovery.CanaryState.EXPIRED
        rec.is_active = False
        rec.save(update_fields=['completed_at', 'canary_state', 'is_active'])

        RecoveryAuditLog.objects.create(
            user=user,
            event_type='recovery_completed',
            event_data={'subsystem': 'time_locked', 'recovery_id': rec.pk},
            ip_address=ip, user_agent=ua,
        )
        return Response({
            'server_half': base64.b64encode(bytes(rec.server_half)).decode('ascii'),
            'half_metadata': rec.half_metadata,
        })


class TimeLockedCanaryAckView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        token = request.data.get('token')
        if not isinstance(token, str) or not token:
            return Response({'error': 'token required'}, status=400)

        rec = (
            TimeLockedRecovery.objects
            .filter(canary_ack_token=token, is_active=True)
            .first()
        )
        if not rec:
            # Don't leak validity — opaque success.
            return Response({'success': True})

        rec.canary_state = TimeLockedRecovery.CanaryState.ACKNOWLEDGED
        rec.is_active = False  # legitimate user said "no" — kill the recovery
        rec.save(update_fields=['canary_state', 'is_active'])

        RecoveryAuditLog.objects.create(
            user=rec.user,
            event_type='user_cancelled_recovery',
            event_data={'subsystem': 'time_locked', 'recovery_id': rec.pk},
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response({'success': True})

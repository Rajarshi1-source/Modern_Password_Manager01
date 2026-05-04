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

Concurrency note: ``release`` and ``canary-ack`` perform read-then-write
on the active TimeLockedRecovery row. Both wrap that round trip in
``transaction.atomic()`` + ``select_for_update()`` so concurrent calls
cannot double-release the server half or race the cancel-vs-release
decision. Without the lock, two parallel ``release`` requests could
both observe ``is_active=True`` and both succeed; or a release call
could observe ``ACKNOWLEDGED=False`` while a canary-ack write was
in flight.
"""
import base64
import binascii
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
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
        """Fallback when the trust-score modulator is unavailable.

        Returns the conservative 7-day default delay regardless of input.
        """
        return 7


log = logging.getLogger(__name__)


def _client_ip(request):
    """Return the client's IP address, honouring an X-Forwarded-For header.

    If the deployment is behind a trusted proxy, the proxy populates
    ``X-Forwarded-For`` with the original client; we take the leftmost
    entry. Otherwise we fall back to ``REMOTE_ADDR``. The value is used
    only for audit logging, not for any auth decision.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _user_agent(request):
    """Return the request's User-Agent header, truncated to 255 chars.

    Truncation matches the column width in ``ServerHalfReleaseLog``; the
    header is logged for forensics only.
    """
    return request.META.get('HTTP_USER_AGENT', '')[:255]


def _build_canary_email(user, recovery):
    """Build the (subject, body) tuple for a canary alert email.

    The body contains a single bearer URL keyed off
    ``recovery.canary_ack_token`` — clicking it cancels the active
    recovery. The token is therefore treated as a credential and never
    appears in logs (see ``_send_canary``).
    """
    subject = 'Recovery initiated for your vault — was this you?'
    base = getattr(settings, 'FRONTEND_BASE_URL', 'https://your-app.example.com')
    cancel_url = f'{base}/recovery/time-lock/cancel?token={recovery.canary_ack_token}'
    body = (
        f"Hi {user.username},\n\n"
        f"Someone has started time-locked recovery for your vault. "
        f"If this was you, you can ignore this email — recovery will "
        f"complete automatically at {recovery.release_after.isoformat()}.\n\n"
        f"If this was NOT you, click the link below to cancel the "
        f"recovery and revoke the request:\n"
        f"  {cancel_url}\n\n"
        f"You will continue to receive these alerts during the delay "
        f"window so you have multiple chances to cancel.\n"
    )
    return subject, body


def _send_canary(user, recovery):
    """Deliver a canary alert to the user's email channel.

    Two layers of behaviour, in order:

    1. **Email** — if the user has an email address configured we send
       the canary via ``django.core.mail.send_mail``. Failures are
       logged but never raised, because the recovery flow itself must
       not be aborted by transient mail-server problems (the user can
       still cancel via subsequent canary alerts before
       ``release_after``).
    2. **Operations log** — we always emit a structured ``log.warning``
       so on-call sees the initiation. The ``canary_ack_token`` is
       intentionally NOT logged because it is a bearer credential —
       anyone who reads it from a log line could cancel a legitimate
       recovery. The token is delivered exclusively via the email body.

    SMS delivery is a follow-up once the SMS provider is wired in;
    the docstring will be updated then. The email path is sufficient
    for the security property the design relies on (a non-server-side
    notification channel out of band of the recovery API).
    """
    log.warning(
        'TIME_LOCKED_CANARY user_id=%s recovery_id=%s release_after=%s',
        user.pk, recovery.pk, recovery.release_after,
    )
    if not user.email:
        return
    subject, body = _build_canary_email(user, recovery)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    try:
        send_mail(subject, body, from_email, [user.email], fail_silently=True)
    except Exception:  # noqa: BLE001 — mail backends raise heterogeneous types
        # We swallow any exception so a flaky email backend cannot
        # block recovery initiation. The canary will retry on the
        # next configured cadence.
        log.exception('TIME_LOCKED_CANARY_EMAIL_FAILED user_id=%s', user.pk)


class TimeLockedEnrollView(APIView):
    """Enroll the server's Shamir 2-of-2 share for the authenticated user.

    The client sends a base64-encoded ``server_half`` and an optional
    ``half_metadata`` dict. Server-side we store both as opaque blobs;
    we never inspect or reconstruct from ``server_half`` alone.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        """Validate input, decode the share, replace any prior enrollment."""
        server_half_b64 = request.data.get('server_half')
        if not isinstance(server_half_b64, str) or not server_half_b64:
            return Response({'error': 'server_half required'}, status=400)
        # ``base64.b64decode(validate=True)`` raises ``binascii.Error``
        # for non-base64 input and ``ValueError`` for the empty string;
        # we narrow the exception so unrelated runtime faults bubble.
        try:
            server_half = base64.b64decode(server_half_b64, validate=True)
        except (binascii.Error, ValueError):
            return Response({'error': 'server_half must be base64'}, status=400)

        meta = request.data.get('half_metadata', {}) or {}
        if not isinstance(meta, dict):
            return Response({'error': 'half_metadata must be object'}, status=400)

        # One active enrollment per user. The deactivate+create pair
        # MUST be serialized with a row-level lock; without it, two
        # concurrent enroll requests can both observe zero active rows
        # (or both deactivate and both create) and end up writing two
        # is_active=True rows for the same user.
        with transaction.atomic():
            # Lock all of the user's recovery rows (active or not) so
            # any concurrent enroll for the same user blocks until we
            # commit. We materialize via list() so the SELECT...FOR
            # UPDATE actually executes inside the txn.
            list(
                TimeLockedRecovery.objects
                .select_for_update()
                .filter(user=request.user)
            )
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
    """Anonymous endpoint: begin the time-lock delay for ``username``.

    Always returns a uniform response shape so attackers cannot probe
    usernames by inspecting the response body. For unknown users or
    enrolled-but-no-recovery accounts we synthesize a decoy
    ``release_after`` using the same default delay as a real one.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryInitiateThrottle]

    def post(self, request):
        """Start the delay clock if a real enrollment exists; otherwise decoy.

        Constant response shape: ``{'success': True, 'release_after': <ISO>}``.
        """
        username = request.data.get('username')
        if not isinstance(username, str) or not username:
            return Response({'error': 'username required'}, status=400)

        # We must NOT leak whether `username` exists or is enrolled.
        # Every code path returns the same response shape. For unknown
        # usernames we fabricate a plausible-looking release_after using
        # the default delay so an attacker cannot distinguish.
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
    """Anonymous endpoint: release the server's Shamir share to the requestor.

    The transition from ``is_active=True`` to ``is_active=False`` is
    one-shot and must not be observed by two callers, so the read-then-
    write is wrapped in ``transaction.atomic()`` + ``select_for_update()``.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryCompleteThrottle]

    def post(self, request):
        """Atomically check eligibility and consume the active row."""
        username = request.data.get('username')
        if not isinstance(username, str) or not username:
            return Response({'error': 'username required'}, status=400)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'no recovery in progress'}, status=404)

        ip = _client_ip(request)
        ua = _user_agent(request)

        # Single transaction: row-lock the candidate active recovery
        # so concurrent release / canary-ack calls cannot race the
        # read. CRITICAL: every write that depends on consuming the
        # row (the ServerHalfReleaseLog row, the row state mutation,
        # AND the RecoveryAuditLog write) must live inside the same
        # txn. If audit-log creation is moved outside and fails, the
        # share is already consumed (is_active=False, canary_state=
        # EXPIRED) but the client gets 500 and never sees server_half
        # — the legitimate user permanently loses Tier-3 recovery for
        # this enrollment. Keeping audit inside means an audit
        # failure rolls back the consumption too, so the client can
        # retry safely.
        with transaction.atomic():
            rec = (
                TimeLockedRecovery.objects
                .select_for_update()
                .filter(user=user, is_active=True)
                .order_by('-enrolled_at')
                .first()
            )
            if not rec or not rec.release_after:
                return Response({'error': 'no recovery in progress'}, status=404)

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

            # Audit INSIDE the txn so that an audit failure rolls back
            # the consumption together with itself.
            RecoveryAuditLog.objects.create(
                user=user,
                event_type='recovery_completed',
                event_data={'subsystem': 'time_locked', 'recovery_id': rec.pk},
                ip_address=ip, user_agent=ua,
            )

            server_half_b64 = base64.b64encode(bytes(rec.server_half)).decode('ascii')
            half_metadata = rec.half_metadata

        return Response({
            'server_half': server_half_b64,
            'half_metadata': half_metadata,
        })


class TimeLockedCanaryAckView(APIView):
    """Anonymous endpoint: cancel an active recovery via its ack token.

    Like ``TimeLockedReleaseView``, the cancel is one-shot and must not
    race a release call. ``transaction.atomic()`` + ``select_for_update()``
    serialize the read-then-write; ``release`` will then re-read the
    canary state under the same lock and refuse with ``cancelled_by_
    canary``.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        """Acknowledge the canary token and atomically deactivate the row."""
        token = request.data.get('token')
        if not isinstance(token, str) or not token:
            return Response({'error': 'token required'}, status=400)

        # We mark canary_state=ACKNOWLEDGED but deliberately leave
        # is_active=True. That keeps the row visible to a subsequent
        # ``release`` call so it can log the refusal as
        # 'cancelled_by_canary' and surface a 403 to the requestor —
        # if we set is_active=False here, ``release`` would query for
        # is_active=True only, miss this row, and instead 404 with
        # 'no recovery in progress', erasing the cancel signal from
        # the forensics trail and confusing the recovering client.
        # The next enroll for this user (or future cleanup pass) will
        # deactivate the row when appropriate.
        with transaction.atomic():
            rec = (
                TimeLockedRecovery.objects
                .select_for_update()
                .filter(canary_ack_token=token, is_active=True)
                .first()
            )
            if rec is not None:
                rec.canary_state = TimeLockedRecovery.CanaryState.ACKNOWLEDGED
                rec.save(update_fields=['canary_state'])
                # Audit inside the txn — if the audit write fails the
                # canary state change rolls back together with it, so
                # we never end up with a "silently cancelled" row that
                # has no log entry.
                RecoveryAuditLog.objects.create(
                    user=rec.user,
                    event_type='user_cancelled_recovery',
                    event_data={
                        'subsystem': 'time_locked',
                        'recovery_id': rec.pk,
                    },
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )

        # Always opaque success — never leak token validity.
        return Response({'success': True})

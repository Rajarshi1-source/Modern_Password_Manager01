"""
VaultWrappedDEKView — REST surface for the user's wrapped vault DEK.

Zero-knowledge boundary: the server stores the `blob` field as opaque
ciphertext. It is never decrypted server-side. This view validates only
the envelope shape (`v`, `kdf`, `kdf_params`, `salt`, `iv`, `wrapped`)
and never inspects the `wrapped` payload itself.

PUT semantics:
  - First PUT (no row exists): create the wrapped DEK, mint a stable
    `dek_id` (UUID).
  - Subsequent PUT (master-password rotation): client MUST send the
    existing `dek_id`. Refusing to clobber the DEK identity is what
    protects existing recovery factors (each row in
    `RecoveryWrappedDEK` references the same `dek_id`) from being
    silently orphaned.
"""
import json
import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.recovery_throttling import (
    RecoveryThrottle,
    RecoveryCompleteThrottle,
    VaultKeySweepThrottle,
)
from auth_module.auth_hash import make_auth_hash_record
from auth_module.recovery_notice import notify as notify_recovery, unacknowledged_exposure
from auth_module.models import UserSalt
from auth_module.recovery_models_v2 import VaultWrappedDEK, RecoveryWrappedDEK
from auth_module.quantum_recovery_models import RecoveryAttempt, RecoveryAuditLog
from auth_module.time_locked_models import TimeLockedRecovery
from auth_module.login_verifier import (
    is_login_verifier,
    revoke_sessions,
    set_login_verifier,
)
from shared import sealed_shares
from shared.client_ip import get_client_ip
from vault.models.vault_models import EncryptedVaultItem


# Wrapped-DEK envelope versioning. The client (sessionVaultCryptoV3.js)
# produces this exact shape; bumping the version requires both ends to
# agree.
ENVELOPE_VERSION = 'wdek-1'
_REQUIRED_FIELDS = ('kdf', 'kdf_params', 'salt', 'iv', 'wrapped')
# A replaced DEK, encrypted under the DEK that replaced it (sessionVaultCryptoV3.js).
RETIRED_KEY_VERSION = 'rdek-1'
# The item envelope of sessionVaultCryptoV3.encryptItem.
ITEM_VERSION = 'svc-gcm-2'
STALE_ITEMS_PAGE = 50


def _valid_envelope(blob):
    """Validate the wrapped-DEK envelope shape WITHOUT decrypting it.

    Server never inspects `blob['wrapped']`. We check only that the
    envelope is the version we know how to store and round-trip.
    """
    if not isinstance(blob, dict) or blob.get('v') != ENVELOPE_VERSION:
        return False
    return all(k in blob for k in _REQUIRED_FIELDS)


def _valid_retired_key(entry, dek_id):
    """The shape of a retired-key entry for ``dek_id``, without opening it."""
    return (
        isinstance(entry, dict)
        and set(entry) == {'v', 'dek_id', 'iv', 'wrapped'}
        and entry['v'] == RETIRED_KEY_VERSION
        and entry['dek_id'] == str(dek_id)
        and isinstance(entry['iv'], str) and 0 < len(entry['iv']) <= 64
        and isinstance(entry['wrapped'], str) and 0 < len(entry['wrapped']) <= 128
    )


def _item_envelope(encrypted_data):
    """The parsed v3 item envelope, or None if ``encrypted_data`` is not one.
    Reads only the public fields; ``ct`` stays opaque."""
    try:
        parsed = json.loads(encrypted_data)
    except (TypeError, ValueError):
        return None
    if (
        not isinstance(parsed, dict)
        or parsed.get('v') != ITEM_VERSION
        or not isinstance(parsed.get('iv'), str)
        or not isinstance(parsed.get('ct'), str)
    ):
        return None
    return parsed


_client_ip = get_client_ip


def _decode_master_auth_hash(value):
    """The client's PBKDF2-SHA256 master-password check (32 bytes, base64),
    or None if ``value`` is not one."""
    import base64
    import binascii
    if not isinstance(value, str):
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == 32 else None


def _finished_guardian_attempt(user, request):
    """The user's finished guardian recovery named in the request, locked, if
    the device that asked for it is calling and it has not set a password yet."""
    try:
        attempt_id = uuid.UUID(str(request.data.get('attempt_id')))
    except ValueError:
        return None
    attempt = RecoveryAttempt.objects.select_for_update(of=('self',)).filter(
        id=attempt_id,
        recovery_setup__user=user,
        status='completed',
        password_rotated_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if attempt is None or not sealed_shares.share_proof_matches(
            request.data.get('requester_token'), attempt.requester_token_hash):
        return None
    return None if attempt.recovery_setup.is_travel_locked() else attempt


class VaultWrappedDEKView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def get(self, request):
        try:
            row = VaultWrappedDEK.objects.get(user=request.user)
        except VaultWrappedDEK.DoesNotExist:
            return Response({'enrolled': False})
        return Response({
            'enrolled': True,
            'blob': row.blob,
            'dek_id': str(row.dek_id),
            'retired_keys': row.retired_keys,
        })

    def put(self, request):
        blob = request.data.get('blob')
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        with transaction.atomic():
            row, created = (
                VaultWrappedDEK.objects
                .select_for_update()
                .get_or_create(user=request.user, defaults={'blob': blob})
            )
            if not created:
                # Master-password rotation. Same DEK, new KEK; client
                # MUST send the existing dek_id to prove DEK possession.
                if str(row.dek_id) != str(request.data.get('dek_id') or ''):
                    return Response({'error': 'dek_id mismatch'}, status=409)
                row.blob = blob
                row.rotated_at = timezone.now()
                row.save(update_fields=['blob', 'rotated_at', 'updated_at'])

        # Audit log: re-use existing event_types from RecoveryAuditLog.
        # `setup_created` / `setup_updated` semantically match enrollment
        # vs rotation; specifics live in event_data. (Adding new event
        # type values would only require updating the choices tuple,
        # not a DB migration, since EVENT_TYPES is form-level only.)
        RecoveryAuditLog.objects.create(
            user=request.user,
            event_type='setup_created' if created else 'setup_updated',
            event_data={
                'subsystem': 'wrapped_dek',
                'dek_id': str(row.dek_id),
                'action': 'enrolled' if created else 'rotated',
            },
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
        )
        return Response({'success': True, 'dek_id': str(row.dek_id)})


class VaultKeyReplaceView(APIView):
    """Replace the vault DEK after a recovery compromise.

    Whoever completed the recovery may hold the DEK. The browser generates a new
    one and sends it wrapped under the master password, with the old one
    encrypted under the new one (``retired_key``). This writes them as one row:
    there is no state in which the vault has no working key, and rows still
    sealed under the old DEK stay readable until ``VaultStaleItemsView`` has
    moved them. The server sees only ciphertext.

    Every recovery factor wraps the old DEK, so all are revoked, and the sessions
    end because any other device holds the old DEK in memory.

    Only while a support unlock's exposure warning is open. That unlock has
    already removed the credentials of whoever caused the lock. Before it, they
    may hold the master password they set, and replacing the key would cut the
    owner's factors off from the vault for good.

    Request: ``{dek_id, blob, retired_key, login_verifier}``. The verifier proves
    the master password, so a stolen session alone cannot do this.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        user = request.user
        blob = request.data.get('blob')
        retired_key = request.data.get('retired_key')
        login_verifier = request.data.get('login_verifier')
        if not _valid_envelope(blob) or not is_login_verifier(login_verifier):
            return Response({'error': 'invalid request'}, status=400)
        if not user.check_password(login_verifier):
            return Response({'error': 'Incorrect master password.'}, status=403)

        with transaction.atomic():
            row = VaultWrappedDEK.objects.select_for_update().filter(user=user).first()
            if row is None:
                return Response({'error': 'vault key not found'}, status=404)
            old_dek_id = str(row.dek_id)
            if old_dek_id != str(request.data.get('dek_id') or ''):
                return Response({'error': 'dek_id mismatch'}, status=409)
            if not _valid_retired_key(retired_key, old_dek_id):
                return Response({'error': 'invalid request'}, status=400)
            exposed_since = unacknowledged_exposure(user)
            if exposed_since is None:
                return Response(
                    {'error': 'The vault key can only be replaced after support '
                              'unlocks the account.'},
                    status=403,
                )
            if row.key_replaced_at and row.key_replaced_at >= exposed_since:
                return Response({'error': 'The vault key was already replaced.'}, status=409)

            now = timezone.now()
            row.blob = blob
            row.dek_id = uuid.uuid4()
            row.retired_keys = [*row.retired_keys, retired_key]
            row.rotated_at = row.key_replaced_at = now
            row.save(update_fields=['blob', 'dek_id', 'retired_keys', 'rotated_at',
                                    'key_replaced_at', 'updated_at'])
            RecoveryWrappedDEK.objects.filter(
                user=user, status=RecoveryWrappedDEK.Status.ACTIVE,
            ).update(status=RecoveryWrappedDEK.Status.REVOKED, revoked_at=now)
            TimeLockedRecovery.objects.filter(user=user, is_active=True).update(is_active=False)
            revoke_sessions(user)
            notify_recovery(user, 'vault_key_replaced', request)
            RecoveryAuditLog.objects.create(
                user=user,
                event_type='setup_updated',
                event_data={
                    'subsystem': 'wrapped_dek',
                    'action': 'key_replaced',
                    'old_dek_id': old_dek_id,
                    'dek_id': str(row.dek_id),
                },
                ip_address=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
            )
        return Response({'success': True, 'dek_id': str(row.dek_id)})


class VaultStaleItemsView(APIView):
    """Rows still sealed under a replaced DEK, and their re-encrypted versions.

    Rows reach this state after a key replacement, and later from a restored
    backup or a device's offline queue. The browser reads them through
    ``retired_keys`` at each sign-in and writes them back under the current DEK
    (``legacyVaultMigration``). Includes soft-deleted rows, which the vault list
    does not. Other envelopes (v2, decoy) are not this key's to touch.

    The write keeps ``updated_at``: nothing changed for the user, and a row
    edited since it was read fails the match and is left for the next pass.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [VaultKeySweepThrottle]

    def get(self, request):
        row = VaultWrappedDEK.objects.filter(user=request.user).first()
        if row is None:
            return Response({'items': [], 'next': None})
        stale = (
            EncryptedVaultItem.objects
            .filter(user=request.user, encrypted_data__contains=f'"v":"{ITEM_VERSION}"')
            .exclude(encrypted_data__contains=f'"dek_id":"{row.dek_id}"')
            .order_by('id')
        )
        after = request.query_params.get('after')
        if after:
            try:
                stale = stale.filter(id__gt=uuid.UUID(after))
            except ValueError:
                return Response({'error': 'invalid cursor'}, status=400)
        page = list(stale[:STALE_ITEMS_PAGE])
        return Response({
            'items': [
                {
                    'id': str(item.id),
                    'encrypted_data': item.encrypted_data,
                    'updated_at': item.updated_at.isoformat(),
                }
                for item in page if _item_envelope(item.encrypted_data) is not None
            ],
            # By page, not by what is left: a row the browser cannot read stays
            # stale, and must not bring it back to the same page for ever.
            'next': str(page[-1].id) if len(page) == STALE_ITEMS_PAGE else None,
        })

    def post(self, request):
        items = request.data.get('items')
        if not isinstance(items, list) or len(items) > STALE_ITEMS_PAGE:
            return Response({'error': 'invalid items'}, status=400)
        row = VaultWrappedDEK.objects.filter(user=request.user).first()
        if row is None:
            return Response({'error': 'vault key not found'}, status=404)
        parsed = []
        for item in items:
            if not isinstance(item, dict):
                return Response({'error': 'invalid items'}, status=400)
            try:
                item_id = uuid.UUID(str(item.get('id')))
                updated_at = parse_datetime(str(item.get('updated_at')))
            except ValueError:
                return Response({'error': 'invalid items'}, status=400)
            envelope = _item_envelope(item.get('encrypted_data'))
            # Only forward: a stale device must not move a row back under an old key.
            if updated_at is None or envelope is None or envelope.get('dek_id') != str(row.dek_id):
                return Response({'error': 'invalid items'}, status=400)
            parsed.append((item_id, updated_at, item['encrypted_data']))
        rewritten = 0
        with transaction.atomic():
            for item_id, updated_at, encrypted_data in parsed:
                rewritten += EncryptedVaultItem.objects.filter(
                    id=item_id, user=request.user, updated_at=updated_at,
                ).update(encrypted_data=encrypted_data)
        return Response({'rewritten': rewritten})


class WrappedDEKRecoveryRotateView(APIView):
    """Anonymous rotation of the master-wrapped DEK after a recovery.

    Why this exists: ``VaultWrappedDEKView.put`` is `IsAuthenticated`,
    but the recovery pages (``/recovery/key/use-v2``,
    ``/recovery/time-lock/recover``, etc.) run BEFORE the user is
    authenticated — they can't authenticate normally because they
    forgot the master password. They have just unwrapped the DEK
    locally using a recovery secret, re-wrapped it under a new
    master-password KEK, and now need to PUT the new envelope to the
    server. Without this anonymous endpoint, the rotation would 401
    and the user would still be locked out on next login.

    Request: ``{username, factor_type, dek_id, blob, auth_hash,
    login_verifier, new_auth_hash}``

    The new master password replaces three things, all written in one
    transaction behind the same ``auth_hash`` proof: the master-wrapped DEK
    (``blob``), the credential sign-in checks (``login_verifier``, derived
    in the browser from the new master password, see
    ``auth_module/login_verifier.py``), and the master-password check in
    ``UserSalt.auth_hash`` (``new_auth_hash``) that verify_master and
    change_master compare against. Rotating only the
    envelope left sign-in on the forgotten password, so the user was
    locked out at the next sign-in. A successful rotation also ends the
    account's existing sessions.

    Authorization model:

      - The endpoint requires the caller to know the user's CURRENT
        ``dek_id``, which is only obtainable via a successful
        ``recovery-factors/lookup/`` (or for an unknown user, via
        coincidence with a decoy — but the decoy ``dek_id`` would
        never match an existing ``VaultWrappedDEK.dek_id``, so the
        write here would be rejected).
      - The caller must also reference an enrolled ``factor_type``
        which actually exists for the user.
      - The throttle (``RecoveryCompleteThrottle``) and the audit log
        cover abuse.
      - A ``social_mesh`` rotation also needs ``attempt_id`` and
        ``requester_token`` of a finished recovery, used once. Guardians who
        pool the shares they opened when accepting know the seed, and so
        ``auth_hash``; this keeps them behind the owner's emailed link and
        wait, which only the attempt goes through.

    Trade-off: an attacker who knows ``username`` AND can call lookup
    AND has gotten a real (not decoy) blob can submit a malformed
    new envelope and DESTROY the user's vault by replacing the
    master-wrapped row with one that wraps no actual DEK. They
    cannot EXFILTRATE anything — the wrapped envelope is opaque on
    both old and new sides — so the worst case is temporary DoS,
    which the user can remediate by performing recovery again
    (recovery factors are unaffected by master-row writes). ZK is
    preserved either way.
    """

    authentication_classes = []  # a stale bearer token must not turn this into a 401
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryCompleteThrottle]

    def post(self, request):
        import hmac as _hmac

        username = request.data.get('username')
        factor_type = request.data.get('factor_type')
        dek_id_in = request.data.get('dek_id')
        blob = request.data.get('blob')
        # auth_hash is the proof-of-secret-knowledge: SHA-256 of
        # "rotation-auth-v1:" || recovery_secret, set at enrollment
        # and stored on the factor row. The lookup endpoint does NOT
        # disclose this value, so an attacker who only hit lookup has
        # everything *except* this hash and cannot rotate.
        auth_hash_in = request.data.get('auth_hash')
        login_verifier = request.data.get('login_verifier')
        new_auth_hash = _decode_master_auth_hash(request.data.get('new_auth_hash'))

        if (
            not isinstance(username, str)
            or not username
            or factor_type not in RecoveryWrappedDEK.FactorType.values
            or not isinstance(dek_id_in, str)
            or not dek_id_in
            or not isinstance(auth_hash_in, str)
            or len(auth_hash_in) != 64
            or not is_login_verifier(login_verifier)
            or new_auth_hash is None
        ):
            return Response(
                {'error': 'username, factor_type, dek_id, auth_hash, login_verifier, '
                          'and new_auth_hash required'},
                status=400,
            )
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        # Look up the user. We do NOT leak existence here either —
        # the same generic 'recovery target not found' covers both
        # 'no such user' and 'user exists but no matching factor /
        # mismatched dek_id'. An attacker probing usernames sees a
        # uniform error. A locked account answers the same: a recovery factor
        # must not re-key it behind the "this wasn't me" lock.
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return Response({'error': 'recovery target not found'}, status=404)

        with transaction.atomic():
            try:
                wrapped_row = (
                    VaultWrappedDEK.objects
                    .select_for_update()
                    .get(user=user)
                )
            except VaultWrappedDEK.DoesNotExist:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Caller must know the EXISTING dek_id. Only a successful
            # recovery-factors/lookup/ surfaces that value to a non-
            # authenticated client, and the server-side decoy path
            # synthesizes a UUIDv4 that won't match any real wrapped
            # DEK row. So this check ties the rotation to a real
            # factor enrollment.
            if str(wrapped_row.dek_id) != dek_id_in:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Caller must reference a factor_type that the user
            # actually has enrolled AND must demonstrate possession
            # of the recovery secret via auth_hash. Without the
            # auth_hash check, the rotation endpoint trusts only
            # dek_id, which is freely obtainable from the anonymous
            # lookup endpoint — an attacker could then DoS any
            # vault by submitting a garbage envelope. The auth_hash
            # is computed client-side from the recovery secret, has
            # ≥130 bits of preimage resistance for tier-1 secrets
            # (32^26 alphabet) and ≥256 for tier 2/3, so it cannot
            # be brute-forced offline even on full DB exfiltration.
            #
            # The row is locked with select_for_update() inside the
            # outer transaction so a concurrent revoke / re-enroll
            # cannot race past this read and let an old recovery
            # secret authorize one last rotation.
            factor = (
                RecoveryWrappedDEK.objects
                .select_for_update()
                .filter(
                    user=user,
                    factor_type=factor_type,
                    status=RecoveryWrappedDEK.Status.ACTIVE,
                )
                .order_by('-created_at')
                .first()
            )
            if factor is None:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Empty stored auth_hash means the row was created
            # before this field existed (i.e. on a deployment that
            # ran an earlier version of the layered-recovery code).
            # The server has nothing to compare against, so we cannot
            # safely accept the rotation: trusting any submitted
            # auth_hash on a legacy row would let an attacker who
            # only hit lookup take ownership of the rotation by
            # being the first to submit a hash. Instead, surface a
            # distinguishable status so the client can show an
            # actionable message — the user must re-enroll the
            # factor (which writes a real auth_hash) before recovery
            # via this endpoint will work.
            if not factor.auth_hash:
                return Response(
                    {
                        'error': 'recovery factor pre-dates auth_hash',
                        're_enroll_required': True,
                        'detail': (
                            'This recovery factor was enrolled before the '
                            'rotation auth_hash existed. Sign in with your '
                            'master password (or another active recovery '
                            'factor) and re-enroll this factor to refresh it.'
                        ),
                    },
                    status=409,
                )

            # Constant-time comparison so a partial match doesn't
            # leak timing information.
            if not _hmac.compare_digest(
                factor.auth_hash.lower(), auth_hash_in.lower(),
            ):
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # After auth_hash, so only a holder of the secret sees this answer.
            attempt = None
            if factor_type == RecoveryWrappedDEK.FactorType.SOCIAL_MESH:
                attempt = _finished_guardian_attempt(user, request)
                if attempt is None:
                    return Response(
                        {'error': 'This recovery cannot set a master password: it has '
                                  'not finished, it is paused on this account, or it '
                                  'already set one. Try signing in with the new one, or '
                                  'start recovery again.'},
                        status=403,
                    )

            wrapped_row.blob = blob
            wrapped_row.rotated_at = timezone.now()
            wrapped_row.save(
                update_fields=['blob', 'rotated_at', 'updated_at'],
            )
            if attempt is not None:
                attempt.password_rotated_at = wrapped_row.rotated_at
                attempt.save(update_fields=['password_rotated_at'])
            set_login_verifier(user, login_verifier)
            UserSalt.objects.filter(user=user).update(
                auth_hash=make_auth_hash_record(new_auth_hash))
            revoke_sessions(user)
            notify_recovery(user, 'recovery_completed', request, recovery_factor_id=factor.pk)

            RecoveryAuditLog.objects.create(
                user=user,
                event_type='setup_updated',
                event_data={
                    'subsystem': 'wrapped_dek',
                    'dek_id': str(wrapped_row.dek_id),
                    'action': 'recovery_rotation',
                    'factor_type': factor_type,
                    'login_verifier_rotated': True,
                },
                ip_address=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
            )

        return Response({'success': True, 'dek_id': str(wrapped_row.dek_id)})

"""Voucher-side flows: invitation acceptance, attestation, recovery requests."""
from __future__ import annotations

import hashlib
import secrets as _secrets
import uuid
from datetime import timedelta
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.db import transaction
from django.utils import timezone

from zk_proofs.crypto import secp256k1 as ec
from zk_proofs.crypto import schnorr

from ..models import (
    RecoveryCircle,
    RelationshipCommitment,
    SocialRecoveryRequest,
    VouchAttestation,
    Voucher,
)
from .audit_service import record_event
from .stake_service import commit_stake
from .web_of_trust_service import evaluate_quorum


DEFAULT_REQUEST_TTL = timedelta(hours=72)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_multibase_ed25519(mb: str) -> bytes:
    """Decode a ``z...`` Ed25519 multibase public key to 32 raw bytes."""
    if not mb or not mb.startswith("z"):
        raise ValueError("public key must be a 'z'-prefixed multibase")
    from decentralized_identity.services.did_service import multibase_decode

    pub = multibase_decode(mb)
    if len(pub) != 32:
        raise ValueError("decoded ed25519 key must be 32 bytes")
    return pub


def _verify_ed25519(public_key_multibase: str, message: bytes, signature: bytes) -> bool:
    try:
        pub = _decode_multibase_ed25519(public_key_multibase)
        Ed25519PublicKey.from_public_bytes(pub).verify(bytes(signature), bytes(message))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _scalar_from_bytes(blob: bytes) -> int:
    if not blob:
        return 1
    return int.from_bytes(hashlib.sha256(blob).digest(), "big") % ec.N or 1


# ---------------------------------------------------------------------------
# Voucher invitation lifecycle
# ---------------------------------------------------------------------------


@transaction.atomic
def accept_invitation(
    *, invitation_token: str, signature: bytes, extra_data: Optional[dict] = None
) -> Voucher:
    """Voucher accepts their invitation by signing ``invitation_token``."""
    voucher = (
        Voucher.objects.select_for_update()
        .filter(invitation_token=invitation_token)
        .select_related("circle")
        .first()
    )
    if voucher is None:
        raise ValueError("unknown invitation token")
    if not voucher.invitation_is_valid:
        raise ValueError("invitation is not valid (expired or already used)")
    if not _verify_ed25519(
        voucher.ed25519_public_key, invitation_token.encode("utf-8"), signature
    ):
        raise ValueError("signature does not match voucher public key")

    voucher.status = "accepted"
    voucher.accepted_at = timezone.now()
    voucher.save(update_fields=["status", "accepted_at"])

    circle = voucher.circle
    record_event(
        event_type="voucher_accepted",
        user=voucher.user,
        circle=circle,
        event_data={"voucher_id": str(voucher.voucher_id)},
    )

    # Flip the circle to ``active`` if this was the last outstanding invite.
    circle.activate_if_ready()

    return voucher


# ---------------------------------------------------------------------------
# Recovery request lifecycle
# ---------------------------------------------------------------------------


@transaction.atomic
def initiate_request(
    *,
    circle: RecoveryCircle,
    initiator_email: str = "",
    initiator_ip: Optional[str] = None,
    device_fingerprint: str = "",
    geo: Optional[dict] = None,
    expires_in: Optional[timedelta] = None,
    risk_score: float = 0.0,
) -> SocialRecoveryRequest:
    if circle.status != "active":
        raise ValueError("circle must be active to initiate recovery")

    last_request = (
        SocialRecoveryRequest.objects.filter(circle=circle)
        .order_by("-created_at")
        .first()
    )
    if last_request is not None and circle.cooldown_hours:
        cutoff = last_request.created_at + timedelta(hours=circle.cooldown_hours)
        if timezone.now() < cutoff and last_request.status in (
            "pending",
            "approved",
            "completed",
        ):
            raise ValueError("circle is in cooldown from a previous request")

    ttl = expires_in or DEFAULT_REQUEST_TTL
    request = SocialRecoveryRequest.objects.create(
        circle=circle,
        initiator_email=initiator_email,
        initiator_ip=initiator_ip,
        device_fingerprint=device_fingerprint or "",
        geo=geo or {},
        required_approvals=circle.threshold,
        challenge_nonce=_secrets.token_hex(32),
        risk_score=float(risk_score or 0.0),
        expires_at=timezone.now() + ttl,
    )

    record_event(
        event_type="request_initiated",
        user=circle.user,
        circle=circle,
        event_data={
            "request_id": str(request.request_id),
            "initiator_email": initiator_email,
            "risk_score": risk_score,
        },
        ip_address=initiator_ip,
    )

    return request


@transaction.atomic
def submit_attestation(
    *,
    request: SocialRecoveryRequest,
    voucher: Voucher,
    decision: str,
    signature: bytes,
    fresh_commitment: Optional[bytes] = None,
    proof_T: Optional[bytes] = None,
    proof_s: Optional[bytes] = None,
    stake_amount: int = 0,
    ip_address: Optional[str] = None,
    user_agent: str = "",
) -> VouchAttestation:
    """Record a voucher's attestation on a live recovery request."""
    if request.circle_id != voucher.circle_id:
        raise ValueError("voucher does not belong to this request's circle")
    if decision not in ("approve", "deny"):
        raise ValueError("decision must be 'approve' or 'deny'")
    if voucher.status not in ("accepted", "active"):
        raise ValueError("voucher is not accepted/active")
    if request.status != "pending":
        raise ValueError("request is not pending")
    if request.is_expired:
        request.status = "expired"
        request.save(update_fields=["status"])
        raise ValueError("request has expired")

    signed_message = (
        f"pwm-social-recovery-v1|{request.request_id}|{decision}|{request.challenge_nonce}"
    ).encode("utf-8")

    if not _verify_ed25519(voucher.ed25519_public_key, signed_message, signature):
        record_event(
            event_type="attestation_rejected",
            user=voucher.user,
            circle=request.circle,
            event_data={
                "voucher_id": str(voucher.voucher_id),
                "request_id": str(request.request_id),
                "reason": "bad_signature",
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise ValueError("bad ed25519 signature")

    # Verify Schnorr equality proof (if provided). Approvals MUST ship a proof;
    # denials MAY skip it.
    if decision == "approve":
        rc = RelationshipCommitment.objects.filter(voucher=voucher).first()
        if rc is None:
            raise ValueError("missing relationship commitment for voucher")
        if not (fresh_commitment and proof_T and proof_s):
            raise ValueError("approval must include a Schnorr equality proof")
        stored_commit = bytes(rc.pedersen_commitment)
        if not schnorr.verify_equality(
            bytes(fresh_commitment), stored_commit, bytes(proof_T), bytes(proof_s)
        ):
            record_event(
                event_type="attestation_rejected",
                user=voucher.user,
                circle=request.circle,
                event_data={
                    "voucher_id": str(voucher.voucher_id),
                    "request_id": str(request.request_id),
                    "reason": "bad_zk_proof",
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("bad Schnorr equality proof")

    attestation, created = VouchAttestation.objects.update_or_create(
        request=request,
        voucher=voucher,
        defaults=dict(
            ed25519_signature=bytes(signature),
            signed_message=signed_message,
            zk_proof_T=bytes(proof_T) if proof_T else None,
            zk_proof_s=bytes(proof_s) if proof_s else None,
            fresh_commitment=bytes(fresh_commitment) if fresh_commitment else None,
            decision=decision,
            stake_committed=int(stake_amount or 0),
            ip_address=ip_address,
            user_agent=user_agent,
        ),
    )

    # Stake only committed once on approve + only if voucher.user is known.
    if decision == "approve" and stake_amount and voucher.user is not None:
        commit_stake(user=voucher.user, amount=int(stake_amount), request_id=str(request.request_id))

    record_event(
        event_type="attestation_recorded",
        user=voucher.user,
        circle=request.circle,
        event_data={
            "voucher_id": str(voucher.voucher_id),
            "request_id": str(request.request_id),
            "decision": decision,
            "stake": int(stake_amount or 0),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Recompute running tallies + status transition.
    q = evaluate_quorum(request)
    request.received_approvals = q.approve_count
    request.total_weight = q.total_weight
    request.total_stake_committed = q.total_stake
    if q.quorum_met:
        request.status = "approved"
    elif q.deny_count > (voucher.circle.total_vouchers - voucher.circle.threshold):
        request.status = "denied"
    request.save(
        update_fields=[
            "received_approvals",
            "total_weight",
            "total_stake_committed",
            "status",
        ]
    )

    return attestation

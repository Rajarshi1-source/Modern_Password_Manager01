"""RecoveryCircle management.

The owner's device splits the recovery seed with Shamir and seals each share
to a voucher's hybrid X25519 + ML-KEM-768 public key
(``frontend/src/services/recovery/sealedShareRecovery.js``); ``create_circle``
stores those sealed shares and the seed check. The server never sees the seed
or a share. Individual Voucher rows are created in ``pending`` status; the
circle flips to ``active`` once every voucher accepts their invitation.
"""
from __future__ import annotations

import hashlib
import secrets as _secrets
import uuid
from datetime import timedelta
from typing import Iterable, List, Mapping, Optional

from django.db import transaction
from django.utils import timezone

from shared import sealed_shares
from zk_proofs.crypto import secp256k1 as ec
from zk_proofs.crypto import schnorr

from ..models import (
    RecoveryCircle,
    RelationshipCommitment,
    Voucher,
)
from .audit_service import record_event


DEFAULT_INVITATION_TTL = timedelta(days=7)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_from_bytes(blob: bytes) -> int:
    """Return a secp256k1 scalar derived from an arbitrary byte string."""
    if not blob:
        return 1  # never return 0 - commitments would be trivially openable
    return int.from_bytes(hashlib.sha256(blob).digest(), "big") % ec.N or 1


def _relationship_commitment(voucher_public_key: str, circle_id: uuid.UUID):
    """Return ``(commit_point_bytes, blinding_int, salt_bytes, salt_hash_hex)``.

    The *message* component of the Pedersen commitment is the SHA-256 digest
    of the voucher's public key combined with the circle id, which is the
    anti-Sybil fingerprint the voucher will later re-prove. The raw ``salt``
    is returned so the caller can persist it on the ``RelationshipCommitment``
    row; without it the voucher has no way to reconstruct ``r1`` when building
    the Schnorr equality proof at attestation time.
    """
    m_bytes = f"{voucher_public_key}|{circle_id}".encode("utf-8")
    m_scalar = _scalar_from_bytes(m_bytes)

    salt = _secrets.token_bytes(32)
    r_scalar = _scalar_from_bytes(salt) or 1
    point = schnorr.commit(m_scalar, r_scalar)
    commit_bytes = ec.encode_point(point)
    salt_hash = hashlib.sha256(salt).hexdigest()
    return commit_bytes, r_scalar, salt, salt_hash


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@transaction.atomic
def create_circle(
    *,
    user,
    secret_check: bytes,
    threshold: int,
    vouchers: Iterable[Mapping],
    min_voucher_reputation: int = 0,
    min_total_stake: int = 0,
    cooldown_hours: int = 24,
    invitation_ttl: Optional[timedelta] = None,
) -> RecoveryCircle:
    """Create a new recovery circle.

    ``vouchers`` is an iterable of dicts with at minimum:

        ``{"ed25519_public_key": "z...", "hybrid_public_key": bytes,
        "share_index": int, "sealed_share": bytes, "share_proof_hash": bytes}``

    (the last four already decoded and checked by
    ``shared.sealed_shares``). ``secret_check`` is the owner's seed check.

    Additional optional keys:

        ``user`` (existing User FK), ``did_string``, ``email``,
        ``display_name``, ``vouch_weight`` (1-10), ``stake_amount``.
    """
    voucher_list: List[Mapping] = list(vouchers)
    total = len(voucher_list)
    if threshold < 2 or threshold > total:
        raise ValueError("threshold must be in [2, total_vouchers]")
    if total < 2:
        raise ValueError("at least two vouchers required")

    if len({v["share_index"] for v in voucher_list}) != total:
        raise ValueError("share_index values must be distinct")
    # One key on two vouchers lets its holder open both shares.
    if len({bytes(v["hybrid_public_key"]) for v in voucher_list}) != total:
        raise ValueError("each voucher needs its own guardian key")

    circle = RecoveryCircle.objects.create(
        user=user,
        threshold=threshold,
        total_vouchers=total,
        secret_check=bytes(secret_check),
        status="draft",
        min_voucher_reputation=min_voucher_reputation,
        min_total_stake=min_total_stake,
        cooldown_hours=cooldown_hours,
    )

    ttl = invitation_ttl or DEFAULT_INVITATION_TTL
    now = timezone.now()

    for voucher_spec in voucher_list:
        ed_pub = voucher_spec["ed25519_public_key"]

        voucher = Voucher.objects.create(
            circle=circle,
            user=voucher_spec.get("user"),
            did_string=voucher_spec.get("did_string", "") or "",
            email=voucher_spec.get("email", "") or "",
            display_name=voucher_spec.get("display_name", "") or "",
            ed25519_public_key=ed_pub,
            relationship_label=voucher_spec.get("relationship_label", "") or "",
            vouch_weight=int(voucher_spec.get("vouch_weight", 1)),
            share_index=voucher_spec["share_index"],
            encrypted_shard_data=voucher_spec["sealed_share"],
            hybrid_public_key=voucher_spec["hybrid_public_key"],
            share_proof_hash=voucher_spec["share_proof_hash"],
            encryption_metadata={
                "algorithm": sealed_shares.HYBRID_KEM_ALGORITHM,
                "share_format": sealed_shares.SHARE_FORMAT,
            },
            stake_amount=int(voucher_spec.get("stake_amount", 0)),
            status="pending",
            invitation_expires_at=now + ttl,
        )

        commit_bytes, _r, salt, salt_hash = _relationship_commitment(
            ed_pub, circle.circle_id
        )
        RelationshipCommitment.objects.create(
            circle=circle,
            voucher=voucher,
            pedersen_commitment=commit_bytes,
            salt=salt,
            salt_hash=salt_hash,
        )

    record_event(
        event_type="circle_created",
        user=user,
        circle=circle,
        event_data={
            "threshold": threshold,
            "total_vouchers": total,
            "invitation_ttl_hours": int(ttl.total_seconds() // 3600),
        },
    )

    return circle


@transaction.atomic
def revoke_voucher(*, voucher: Voucher, reason: str = "") -> None:
    voucher.status = "revoked"
    voucher.revoked_at = timezone.now()
    voucher.save(update_fields=["status", "revoked_at"])
    record_event(
        event_type="voucher_revoked",
        user=voucher.circle.user,
        circle=voucher.circle,
        event_data={"voucher_id": str(voucher.voucher_id), "reason": reason[:128]},
    )

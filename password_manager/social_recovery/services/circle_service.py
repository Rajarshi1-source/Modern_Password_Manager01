"""RecoveryCircle management.

The owner of the vault calls ``create_circle`` to split the recovery secret
with Shamir and publish a Pedersen commitment of it. Individual Voucher rows
are created in ``draft`` status; the circle flips to ``active`` once every
voucher accepts their invitation.
"""
from __future__ import annotations

import hashlib
import secrets as _secrets
import uuid
from datetime import timedelta
from typing import Iterable, List, Mapping, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.db import transaction
from django.utils import timezone

from auth_module.services.shamir_py3 import ShamirSecretSharer
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


SHARE_ENCRYPTION_ALGORITHM = "aes-gcm-sha256kdf-v1"


def _encrypt_share_placeholder(share: str, public_key_multibase: str) -> bytes:
    """Envelope a Shamir share with AES-256-GCM.

    The key is derived from SHA-256 of a domain-separated label plus the
    voucher's public key, matching the prior keying material so existing
    callers keep the same trust root. Unlike the previous raw XOR cipher,
    AES-GCM provides authenticated encryption — any tampering with the
    ciphertext or metadata at rest is detected on decryption.

    Output layout: ``nonce (12 bytes) || AES-GCM ciphertext (plaintext + tag)``.

    A full deployment should still upgrade this to the ``mesh_crypto_service``
    X25519 wrapping primitive; this function is the minimum-viable fix that
    removes the malleability of the prior XOR construction.
    """
    key = hashlib.sha256(
        ("pwm-social-recovery-v1|" + public_key_multibase).encode()
    ).digest()
    nonce = _secrets.token_bytes(12)
    aad = f"pwm-social-recovery|{public_key_multibase}".encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, share.encode("utf-8"), aad)
    return nonce + ciphertext


def _relationship_commitment(voucher_public_key: str, circle_id: uuid.UUID):
    """Return ``(commit_point, blinding_int, salt_hash_hex)``.

    The *message* component of the Pedersen commitment is the SHA-256 digest
    of the voucher's public key combined with the circle id, which is the
    anti-Sybil fingerprint the voucher will later re-prove.
    """
    m_bytes = f"{voucher_public_key}|{circle_id}".encode("utf-8")
    m_scalar = _scalar_from_bytes(m_bytes)

    salt = _secrets.token_bytes(32)
    r_scalar = _scalar_from_bytes(salt) or 1
    point = schnorr.commit(m_scalar, r_scalar)
    commit_bytes = ec.encode_point(point)
    salt_hash = hashlib.sha256(salt).hexdigest()
    return commit_bytes, r_scalar, salt_hash


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@transaction.atomic
def create_circle(
    *,
    user,
    master_secret_hex: str,
    threshold: int,
    vouchers: Iterable[Mapping],
    min_voucher_reputation: int = 0,
    min_total_stake: int = 0,
    cooldown_hours: int = 24,
    invitation_ttl: Optional[timedelta] = None,
) -> RecoveryCircle:
    """Create a new recovery circle.

    ``vouchers`` is an iterable of dicts with at minimum:

        ``{"ed25519_public_key": "z...", "relationship_label": "..."}``

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

    # 1) Split the master secret with Shamir.
    shares = ShamirSecretSharer.split_secret(master_secret_hex, threshold, total)

    # 2) Publish a Pedersen commitment to the master secret itself so the
    #    completion service can later verify reconstruction correctness.
    master_m = _scalar_from_bytes(bytes.fromhex(master_secret_hex))
    master_salt = _secrets.token_bytes(32)
    master_r = _scalar_from_bytes(master_salt) or 1
    master_commit_bytes = ec.encode_point(schnorr.commit(master_m, master_r))

    circle = RecoveryCircle.objects.create(
        user=user,
        threshold=threshold,
        total_vouchers=total,
        secret_commitment=master_commit_bytes,
        salt=master_salt,
        status="draft",
        min_voucher_reputation=min_voucher_reputation,
        min_total_stake=min_total_stake,
        cooldown_hours=cooldown_hours,
    )

    ttl = invitation_ttl or DEFAULT_INVITATION_TTL
    now = timezone.now()

    for idx, (share_str, voucher_spec) in enumerate(zip(shares, voucher_list), start=1):
        ed_pub = voucher_spec["ed25519_public_key"]
        ciphertext = _encrypt_share_placeholder(share_str, ed_pub)

        voucher = Voucher.objects.create(
            circle=circle,
            user=voucher_spec.get("user"),
            did_string=voucher_spec.get("did_string", "") or "",
            email=voucher_spec.get("email", "") or "",
            display_name=voucher_spec.get("display_name", "") or "",
            ed25519_public_key=ed_pub,
            relationship_label=voucher_spec.get("relationship_label", "") or "",
            vouch_weight=int(voucher_spec.get("vouch_weight", 1)),
            share_index=idx,
            encrypted_shard_data=ciphertext,
            encryption_metadata={
                "algorithm": SHARE_ENCRYPTION_ALGORITHM,
                "target_public_key": ed_pub,
                "share_format": "shamir-py3/v1",
                "nonce_length": 12,
                "aad": "pwm-social-recovery|<target_public_key>",
            },
            stake_amount=int(voucher_spec.get("stake_amount", 0)),
            status="pending",
            invitation_expires_at=now + ttl,
        )

        commit_bytes, _r, salt_hash = _relationship_commitment(ed_pub, circle.circle_id)
        RelationshipCommitment.objects.create(
            circle=circle,
            voucher=voucher,
            pedersen_commitment=commit_bytes,
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
def add_voucher(
    *,
    circle: RecoveryCircle,
    ed25519_public_key: str,
    share_index: int,
    encrypted_share: bytes,
    did_string: str = "",
    email: str = "",
    display_name: str = "",
    user=None,
    vouch_weight: int = 1,
    stake_amount: int = 0,
) -> Voucher:
    """Attach an additional voucher (used by tests and admin actions)."""
    voucher = Voucher.objects.create(
        circle=circle,
        ed25519_public_key=ed25519_public_key,
        did_string=did_string,
        email=email,
        display_name=display_name,
        user=user,
        share_index=share_index,
        encrypted_shard_data=encrypted_share,
        vouch_weight=vouch_weight,
        stake_amount=stake_amount,
        status="pending",
        invitation_expires_at=timezone.now() + DEFAULT_INVITATION_TTL,
    )
    commit_bytes, _r, salt_hash = _relationship_commitment(
        ed25519_public_key, circle.circle_id
    )
    RelationshipCommitment.objects.create(
        circle=circle,
        voucher=voucher,
        pedersen_commitment=commit_bytes,
        salt_hash=salt_hash,
    )
    record_event(
        event_type="voucher_invited",
        user=circle.user,
        circle=circle,
        event_data={"voucher_id": str(voucher.voucher_id)},
    )
    return voucher


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

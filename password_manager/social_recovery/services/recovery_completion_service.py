"""Complete an approved recovery request by reconstructing the secret."""
from __future__ import annotations

import hashlib
from typing import Iterable, List, Mapping

from django.db import transaction
from django.utils import timezone

from auth_module.services.shamir_py3 import ShamirSecretSharer
from zk_proofs.crypto import secp256k1 as ec
from zk_proofs.crypto import schnorr

from ..models import SocialRecoveryRequest, VouchAttestation, Voucher
from .audit_service import record_event
from .stake_service import release_stake, slash_stake
from .web_of_trust_service import evaluate_quorum


def _scalar_from_bytes(blob: bytes) -> int:
    """Mirror the scalar derivation used when the commitment was built."""
    if not blob:
        return 1
    return int.from_bytes(hashlib.sha256(blob).digest(), "big") % ec.N or 1


def _verify_secret_commitment(circle, recovered_secret_hex: str) -> bool:
    """Recompute the Pedersen commitment from the recovered secret + circle salt
    and compare against the stored one.

    Returns True if, and only if, the Pedersen commitment opens to the
    reconstructed secret. A mismatch indicates at least one corrupted or
    forged share in the recovery set and the result MUST be rejected.
    """
    stored = bytes(circle.secret_commitment or b"")
    salt = bytes(circle.salt or b"")
    if not stored or not salt:
        # If we have no commitment to check against (legacy rows) we cannot
        # prove correctness — treat as a verification failure rather than a
        # silent pass.
        return False
    try:
        m_scalar = _scalar_from_bytes(bytes.fromhex(recovered_secret_hex))
    except ValueError:
        return False
    r_scalar = _scalar_from_bytes(salt) or 1
    recomputed = ec.encode_point(schnorr.commit(m_scalar, r_scalar))
    return hashlib.compare_digest(stored, recomputed)


@transaction.atomic
def complete_request(
    *,
    request: SocialRecoveryRequest,
    decrypted_shares: Iterable[Mapping],
) -> str:
    """Reconstruct the master secret using voucher-supplied decrypted shares.

    ``decrypted_shares`` is an iterable of ``{"voucher_id": ..., "share": ...}``
    mappings. The caller (API view) is responsible for only accepting shares
    that arrive inside a signed envelope from the voucher's device; the
    service then ensures the submitting voucher actually approved the request.
    """
    if request.status not in ("approved", "completed"):
        raise ValueError("request must be approved before completion")

    approved_voucher_ids = set(
        VouchAttestation.objects.filter(
            request=request, decision="approve"
        ).values_list("voucher_id", flat=True)
    )

    supplied: List[str] = []
    used_voucher_ids = []
    for entry in decrypted_shares:
        vid = entry["voucher_id"]
        share = entry["share"]
        if vid not in approved_voucher_ids:
            raise ValueError(f"voucher {vid} did not approve this request")
        if vid in used_voucher_ids:
            continue  # idempotent; duplicates are ignored
        supplied.append(share)
        used_voucher_ids.append(vid)

    if len(supplied) < request.circle.threshold:
        raise ValueError(
            f"need >= {request.circle.threshold} shares, got {len(supplied)}"
        )

    secret_hex = ShamirSecretSharer.recover_secret(supplied[: request.circle.threshold])

    # Verify the recovered secret against the Pedersen commitment published at
    # circle-creation time. A mismatch means at least one share was corrupted
    # or forged — we must not return a wrong secret to the caller.
    if not _verify_secret_commitment(request.circle, secret_hex):
        record_event(
            event_type="request_commitment_mismatch",
            user=request.circle.user,
            circle=request.circle,
            event_data={"request_id": str(request.request_id)},
        )
        raise ValueError(
            "reconstructed secret failed Pedersen commitment verification"
        )

    request.status = "completed"
    request.completed_at = timezone.now()
    request.save(update_fields=["status", "completed_at"])

    # Release stake for approving vouchers, on the assumption that a
    # successful recovery implies those vouchers behaved honestly. Vouchers
    # that denied or failed their proof path are left untouched.
    q = evaluate_quorum(request)
    for att in VouchAttestation.objects.filter(request=request, decision="approve").select_related("voucher__user"):
        if att.voucher.user and att.stake_committed:
            release_stake(
                user=att.voucher.user,
                amount=int(att.stake_committed),
                request_id=str(request.request_id),
            )

    record_event(
        event_type="request_completed",
        user=request.circle.user,
        circle=request.circle,
        event_data={
            "request_id": str(request.request_id),
            "approvals": q.approve_count,
            "total_weight": q.total_weight,
            "total_stake": q.total_stake,
        },
    )

    return secret_hex


@transaction.atomic
def cancel_request(*, request: SocialRecoveryRequest, slash_denies: bool = False) -> None:
    """Owner cancels a request; optionally slash any approvers."""
    if request.status not in ("pending", "approved"):
        raise ValueError("only pending/approved requests can be cancelled")
    request.status = "cancelled"
    request.completed_at = timezone.now()
    request.save(update_fields=["status", "completed_at"])

    if slash_denies:
        for att in VouchAttestation.objects.filter(
            request=request, decision="approve"
        ).select_related("voucher__user"):
            if att.voucher.user and att.stake_committed:
                slash_stake(
                    user=att.voucher.user,
                    amount=int(att.stake_committed),
                    request_id=str(request.request_id),
                    reason="owner_cancelled_slash",
                )

    record_event(
        event_type="request_cancelled",
        user=request.circle.user,
        circle=request.circle,
        event_data={
            "request_id": str(request.request_id),
            "slashed": slash_denies,
        },
    )


def reject_fraudulent_attestation(*, voucher: Voucher, request: SocialRecoveryRequest, reason: str = "fraud") -> None:
    """Slash a voucher when an attestation is later shown to be fraudulent."""
    att = VouchAttestation.objects.filter(request=request, voucher=voucher).first()
    if att is None or voucher.user is None or not att.stake_committed:
        return
    slash_stake(
        user=voucher.user,
        amount=int(att.stake_committed),
        request_id=str(request.request_id),
        reason=reason,
    )
    record_event(
        event_type="stake_slashed",
        user=voucher.user,
        circle=request.circle,
        event_data={
            "voucher_id": str(voucher.voucher_id),
            "request_id": str(request.request_id),
            "reason": reason,
        },
    )

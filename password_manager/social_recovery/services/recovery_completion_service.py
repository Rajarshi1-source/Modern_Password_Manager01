"""Complete an approved recovery request by releasing the re-sealed shares."""
from __future__ import annotations

import hashlib
import hmac

from django.db import transaction
from django.utils import timezone

from shared import sealed_shares

from ..models import SocialRecoveryRequest, VouchAttestation, Voucher
from .audit_service import record_event
from .stake_service import slash_stake
from .web_of_trust_service import evaluate_quorum


@transaction.atomic
def complete_request(*, request: SocialRecoveryRequest) -> dict:
    """Return the approving vouchers' shares, re-sealed to the requester.

    The requester's device opens them with its one-time private key,
    recombines the seed and checks it against ``secret_check``. The server
    never sees a share or the seed, so it cannot check the result itself.
    """
    if request.status not in ("approved", "completed"):
        raise ValueError("request must be approved before completion")
    circle = request.circle
    if not bytes(circle.secret_check or b"") or not bytes(request.requester_public_key or b""):
        raise ValueError("circle predates client-side sealing; create it again")

    approvals = (
        VouchAttestation.objects.filter(request=request, decision="approve")
        .exclude(resealed_share=None)
        .select_related("voucher__user")
        .order_by("voucher__share_index")
    )
    shares = [
        {
            "voucher_id": str(att.voucher.voucher_id),
            "share_index": att.voucher.share_index,
            "sealed_share": sealed_shares.b64(att.resealed_share),
        }
        for att in approvals
    ]
    if len(shares) < circle.threshold:
        raise ValueError(f"need >= {circle.threshold} shares, got {len(shares)}")

    if request.status != "completed":
        request.status = "completed"
        request.completed_at = timezone.now()
        request.save(update_fields=["status", "completed_at"])

        # Approvers' stakes stay committed: the server cannot tell whether a
        # re-sealed share is genuine (only the requester's device can, with
        # the seed check), so completing is no evidence of honest vouching,
        # and a fraudulent approval can still be slashed afterwards
        # (reject_fraudulent_attestation).
        q = evaluate_quorum(request)

        record_event(
            event_type="request_completed",
            user=circle.user,
            circle=circle,
            event_data={
                "request_id": str(request.request_id),
                "approvals": q.approve_count,
                "total_weight": q.total_weight,
                "total_stake": q.total_stake,
            },
        )

    return {
        "threshold": circle.threshold,
        "secret_check": sealed_shares.b64(circle.secret_check),
        "sealed_shares": shares,
        "algorithm": sealed_shares.HYBRID_KEM_ALGORITHM,
    }


@transaction.atomic
def abandon_request(*, request: SocialRecoveryRequest, abandon_token: bytes) -> None:
    """The requester's device reports that the released shares did not
    recombine (a guardian sent a bad share). The request becomes ``failed``,
    which the cooldown does not count, so the requester can start again.

    Only the device holding the request's one-time key can derive the token
    whose SHA-256 it sent at initiation. The token says nothing about the
    key, a share or the seed.
    """
    request = SocialRecoveryRequest.objects.select_for_update().get(pk=request.pk)
    stored = bytes(request.abandon_token_hash or b"")
    if (request.status != "completed" or not stored
            or not hmac.compare_digest(hashlib.sha256(abandon_token).digest(), stored)):
        raise ValueError("request cannot be abandoned")
    request.status = "failed"
    request.save(update_fields=["status"])
    record_event(
        event_type="request_failed",
        user=request.circle.user,
        circle=request.circle,
        event_data={"request_id": str(request.request_id)},
    )


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

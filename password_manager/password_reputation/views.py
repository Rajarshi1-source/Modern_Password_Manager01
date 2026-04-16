"""HTTP views for password_reputation (mounted under /api/reputation/)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .anchors import available_adapters, configured_adapter_name
from .providers import available_schemes
from .serializers import (
    AnchorBatchSerializer,
    LeaderboardEntrySerializer,
    ReputationAccountSerializer,
    ReputationEventSerializer,
    ReputationProofSerializer,
    ReputationProofSubmitSerializer,
)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_proof(request):
    """Accept a reputation proof and (if valid) mint score + tokens."""
    serializer = ReputationProofSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    result = services.submit_proof(
        user=request.user,
        scope_id=payload["scope_id"],
        commitment=payload["commitment"],
        claimed_entropy_bits=payload["claimed_entropy_bits"],
        binding_hash=payload["binding_hash"],
        scheme=payload["scheme"],
    )

    response_body = {
        "accepted": result.accepted,
        "error": result.error,
        "proof": ReputationProofSerializer(result.proof).data,
        "event": ReputationEventSerializer(result.event).data if result.event else None,
        "account": ReputationAccountSerializer(result.account).data,
    }
    http_status = status.HTTP_200_OK if result.accepted else status.HTTP_202_ACCEPTED
    return Response(response_body, status=http_status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the caller's reputation account."""
    account = services.account_for(request.user)
    return Response(ReputationAccountSerializer(account).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_events(request):
    """Append-only log of the caller's reputation events."""
    limit = int(request.query_params.get("limit", 50))
    limit = max(1, min(limit, 200))
    events = services.recent_events(request.user, limit=limit)
    return Response(ReputationEventSerializer(events, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_proofs(request):
    """Latest proof submission per scope for the caller."""
    from .models import ReputationProof

    qs = ReputationProof.objects.filter(user=request.user).order_by("-created_at")[:100]
    return Response(ReputationProofSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leaderboard(request):
    """Top-N leaderboard. Authenticated-only so we don't leak usernames publicly."""
    limit = int(request.query_params.get("limit", 20))
    limit = max(1, min(limit, 100))
    rows = services.leaderboard(limit=limit)
    payload = []
    for rank, account in enumerate(rows, start=1):
        payload.append({
            "rank": rank,
            "user_id": account.user_id,
            "username": getattr(account.user, "username", "") or "",
            "score": account.score,
            "tokens": account.tokens,
            "proofs_accepted": account.proofs_accepted,
        })
    return Response(LeaderboardEntrySerializer(payload, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def config(request):
    """Public (authenticated) config surface so the frontend can inspect the active adapter."""
    return Response({
        "schemes": available_schemes(),
        "adapter": configured_adapter_name(),
        "available_adapters": available_adapters(),
        "stats": services.stats(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_batches(request):
    """Recent anchor batches (visible to all authenticated users — they're public on-chain)."""
    from .models import AnchorBatch

    qs = AnchorBatch.objects.all().order_by("-created_at")[:25]
    return Response(AnchorBatchSerializer(qs, many=True).data)

"""HTTP views for ambient_auth (mounted under /api/ambient/)."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SIGNAL_KEYS, SURFACE_CHOICES
from . import services
from .serializers import (
    AmbientContextSerializer,
    AmbientIngestSerializer,
    AmbientObservationSerializer,
    AmbientProfileSerializer,
    AmbientSignalConfigSerializer,
    PromoteContextSerializer,
    RenameContextSerializer,
)

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ingest(request):
    """Accept an ambient observation and return trust + MFA recommendation."""
    serializer = AmbientIngestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = services.ingest(request.user, serializer.validated_data)
    except RuntimeError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("ambient_auth.ingest failed")
        return Response(
            {"error": "Ambient ingest failed. See server logs."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "trust_score": result.trust_score,
            "novelty_score": result.novelty_score,
            "mfa_recommendation": result.mfa_recommendation,
            "matched_context": (
                AmbientContextSerializer(result.matched_context).data
                if result.matched_context is not None
                else None
            ),
            "observation": AmbientObservationSerializer(result.observation).data,
            "reasons": result.reasons,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_contexts(request):
    qs = services.list_contexts(request.user)
    return Response(AmbientContextSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def promote_context(request):
    serializer = PromoteContextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        ctx = services.promote_context(
            request.user,
            serializer.validated_data["observation_id"],
            serializer.validated_data["label"],
        )
    except LookupError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(AmbientContextSerializer(ctx).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def context_detail(request, context_id):
    if request.method == "DELETE":
        try:
            services.delete_context(request.user, context_id)
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = RenameContextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        ctx = services.rename_context(
            request.user,
            context_id,
            serializer.validated_data["label"],
        )
    except LookupError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(AmbientContextSerializer(ctx).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_observations(request):
    limit = int(request.query_params.get("limit", 50))
    qs = services.recent_observations(request.user, limit=limit)
    return Response(AmbientObservationSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    profiles = request.user.ambient_profiles.order_by("-updated_at")[:5]
    return Response(AmbientProfileSerializer(profiles, many=True).data)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def signal_config(request):
    if request.method == "GET":
        cfg = services.get_signal_configs(request.user)
        return Response(cfg)

    updates = request.data
    if not isinstance(updates, dict):
        return Response(
            {"error": "Body must be an object: {signal_key: {enabled, enabled_on_surfaces}}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    for signal_key, patch in updates.items():
        if signal_key not in SIGNAL_KEYS:
            return Response(
                {"error": f"Unknown signal_key: {signal_key}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(patch, dict):
            continue
        try:
            services.set_signal_config(
                request.user,
                signal_key,
                enabled=patch.get("enabled"),
                enabled_on_surfaces=patch.get("enabled_on_surfaces"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(services.get_signal_configs(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reset_baseline(request):
    services.reset_baseline(request.user)
    return Response({"reset": True}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def config(request):
    """Public-to-authenticated config surface so the client can self-discover."""
    from django.conf import settings as _django_settings

    ambient_cfg = getattr(_django_settings, "AMBIENT_AUTH", {}) or {}
    signals = services.get_signal_configs(request.user)
    user_opted_in = any(c.get("enabled") for c in signals.values()) if signals else True
    return Response(
        {
            "enabled": services.enabled(),
            "enforcement_stage": str(ambient_cfg.get("ENFORCEMENT_STAGE", "collect")).lower(),
            "signals": list(SIGNAL_KEYS),
            "surfaces": [s for s, _ in SURFACE_CHOICES],
            "schema_version": 1,
            "user_opted_in": user_opted_in,
        }
    )

"""
API views for :mod:`stegano_vault`.

Endpoints (mounted at ``/api/stego/``):

* ``POST   /embed/``   cover image + opaque blob -> stego PNG bytes.
* ``POST   /extract/`` stego PNG -> opaque blob bytes.
* ``POST   /store/``   persist a pre-made stego PNG + metadata.
* ``GET    /``         list this user's stego vaults.
* ``GET    /<id>/``    download stored stego PNG.
* ``DELETE /<id>/``    delete a stored stego vault.
* ``GET    /events/``  access-event audit log for this user.
* ``GET    /config/``  feature flag + tier info for clients.

The server never sees vault plaintext. It only:

* copies the already-encrypted blob into PNG pixel LSBs, or
* pulls it back out, or
* serves it back byte-for-byte for later cross-device use.
"""

from __future__ import annotations

import logging

from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from stegano_vault import services
from stegano_vault.models import StegoAccessEvent, StegoVault
from stegano_vault.serializers import (
    StegoAccessEventSerializer,
    StegoVaultSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT", "") or "")[:240]


def _feature_enabled_response():
    if not services.enabled():
        return Response(
            {"detail": "Steganographic vault is disabled."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ---------------------------------------------------------------------------
# Embed / extract (stateless helpers)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stego_embed(request):
    """
    Multipart request: ``cover`` (image/png) + ``blob`` (bytes).
    Returns image/png bytes with the blob LSB-embedded.
    """
    guard = _feature_enabled_response()
    if guard is not None:
        return guard

    cover_file = request.FILES.get("cover")
    blob_file = request.FILES.get("blob")
    if cover_file is None or blob_file is None:
        return Response(
            {"detail": "Both 'cover' and 'blob' multipart fields are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if cover_file.size > services.max_image_bytes():
        return Response(
            {"detail": "Cover image too large."},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    cover_bytes = cover_file.read()
    blob_bytes = blob_file.read()
    try:
        stego_bytes = services.embed_blob_in_png(cover_bytes, blob_bytes)
    except services.PngLsbError as exc:
        return Response(
            {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )
    services.log_event(
        user=request.user,
        kind=StegoAccessEvent.Kind.EMBED,
        surface=request.data.get("surface", "web"),
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        details={"blob_len": len(blob_bytes), "cover_len": len(cover_bytes)},
    )
    resp = HttpResponse(stego_bytes, content_type="image/png")
    resp["Content-Disposition"] = 'attachment; filename="stego.png"'
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stego_extract(request):
    """
    Multipart request: ``image`` (stego PNG). Returns ``application/octet-stream``
    with the recovered blob bytes.
    """
    guard = _feature_enabled_response()
    if guard is not None:
        return guard

    img_file = request.FILES.get("image")
    if img_file is None:
        return Response(
            {"detail": "'image' multipart field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    img_bytes = img_file.read()
    try:
        blob = services.extract_blob_from_png(img_bytes)
    except services.PngLsbError as exc:
        return Response(
            {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )
    services.log_event(
        user=request.user,
        kind=StegoAccessEvent.Kind.EXTRACT,
        surface=request.data.get("surface", "web"),
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        details={"img_len": len(img_bytes), "blob_len": len(blob)},
    )
    return HttpResponse(blob, content_type="application/octet-stream")


# ---------------------------------------------------------------------------
# CRUD on StegoVault rows
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def stego_vault_collection(request):
    """GET list this user's vaults; POST to ``/store/`` to upload."""
    guard = _feature_enabled_response()
    if guard is not None:
        return guard

    if request.method == "GET":
        qs = StegoVault.objects.filter(user=request.user).order_by("-updated_at")
        return Response(StegoVaultSerializer(qs, many=True).data)

    # POST = store
    return stego_store(request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stego_store(request):
    """
    Multipart: ``image`` (stego PNG already embedded client-side),
    ``label`` (str), ``tier`` (int), ``cover_hash`` (hex str).
    """
    guard = _feature_enabled_response()
    if guard is not None:
        return guard

    img_file = request.FILES.get("image")
    if img_file is None:
        return Response(
            {"detail": "'image' multipart field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    label = (request.data.get("label") or "Default")[:120]
    try:
        tier = int(request.data.get("tier", 0))
    except (TypeError, ValueError):
        return Response(
            {"detail": "'tier' must be an integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cover_hash = (request.data.get("cover_hash") or "")[:64]
    if img_file.size > services.max_image_bytes():
        return Response(
            {"detail": "Stego image too large."},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    try:
        sv = services.store_stego_vault(
            user=request.user,
            image_bytes=img_file.read(),
            label=label,
            tier=tier,
            cover_hash=cover_hash,
            surface=request.data.get("surface", "web"),
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(StegoVaultSerializer(sv).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def stego_vault_detail(request, vault_id):
    guard = _feature_enabled_response()
    if guard is not None:
        return guard

    sv = services.get_stego_vault_for_user(request.user, vault_id)
    if sv is None:
        return Response(
            {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if request.method == "DELETE":
        services.delete_stego_vault(
            user=request.user,
            vault_id=sv.id,
            surface=request.query_params.get("surface", "web"),
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # GET -> download the stego PNG bytes
    services.log_event(
        user=request.user,
        kind=StegoAccessEvent.Kind.DOWNLOAD,
        stego_vault=sv,
        surface=request.query_params.get("surface", "web"),
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        details={"label": sv.label},
    )
    try:
        sv.last_accessed_at = sv.last_accessed_at or None
        sv.save(update_fields=["last_accessed_at"])
    except Exception:  # pragma: no cover
        pass

    try:
        return FileResponse(
            sv.image.open("rb"), content_type=sv.image_mime or "image/png"
        )
    except Exception as exc:
        logger.warning("Unable to serve stego image %s: %s", sv.id, exc)
        return Response(
            {"detail": "Unable to open stored image."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stego_events(request):
    guard = _feature_enabled_response()
    if guard is not None:
        return guard
    qs = StegoAccessEvent.objects.filter(user=request.user).order_by("-created_at")[:200]
    return Response(StegoAccessEventSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stego_config(request):
    from django.conf import settings

    cfg = getattr(settings, "STEGO_VAULT", {}) or {}
    return Response(
        {
            "enabled": services.enabled(),
            "max_image_bytes": services.max_image_bytes(),
            "tiers_bytes": list(cfg.get("TIERS_BYTES", [32768, 131072, 1048576])),
            "format": "PNG LSB + HiddenVaultBlob v1",
            "schema_version": 1,
        }
    )

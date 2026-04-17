"""HTTP views for decentralized_identity (mounted at /api/did/)."""

from __future__ import annotations

import base64
import logging
from typing import Optional

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    RevocationList,
    SignInChallenge,
    UserDID,
    VCPresentation,
    VerifiableCredential,
)
from .serializers import (
    ChallengeSerializer,
    IssueVCSerializer,
    RegisterDIDSerializer,
    SignInVerifySerializer,
    UserDIDSerializer,
    VCSerializer,
    VCSummarySerializer,
    VerifyVPSerializer,
)
from .services import (
    create_challenge,
    did_service,
    issue_credential,
    resolve_did,
    register_user_did,
    verify_presentation,
    verify_sign_in_presentation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DID lifecycle
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_did(request):
    serializer = RegisterDIDSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        obj = register_user_did(
            request.user,
            serializer.validated_data["did_string"],
            serializer.validated_data["public_key_multibase"],
            make_primary=serializer.validated_data.get("make_primary", True),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(UserDIDSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_user_dids(request):
    return Response(
        UserDIDSerializer(UserDID.objects.filter(user=request.user), many=True).data
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def resolve(request, did):
    try:
        doc = resolve_did(did)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(doc)


# ---------------------------------------------------------------------------
# Credential issuance + listing
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue(request):
    if not request.user.is_staff:
        return Response(
            {"error": "Only staff users can issue credentials in v1"},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = IssueVCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        vc = issue_credential(
            subject_did=serializer.validated_data["subject_did"],
            schema_id=serializer.validated_data["schema_id"],
            credential_subject=serializer.validated_data["credential_subject"],
            validity_days=serializer.validated_data.get("validity_days", 365),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # Best-effort fanout to storage backends.
    try:
        from .tasks import fanout_vc_storage

        fanout_vc_storage.delay(str(vc.id))
    except Exception:
        logger.debug("Celery not running; skipping storage fanout", exc_info=True)
    return Response(VCSerializer(vc).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_my_credentials(request):
    dids = list(
        UserDID.objects.filter(user=request.user).values_list("did_string", flat=True)
    )
    qs = VerifiableCredential.objects.filter(subject_did__in=dids)
    return Response(VCSummarySerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# Presentation verification (public)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_vp(request):
    serializer = VerifyVPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ok, payload, errors = verify_presentation(
        vp_jwt=serializer.validated_data["vp_jwt"],
        expected_nonce=serializer.validated_data.get("nonce") or None,
        expected_audience=serializer.validated_data.get("audience") or None,
    )
    # Best-effort audit log.
    try:
        VCPresentation.objects.create(
            holder_did=payload.get("iss", "") if isinstance(payload, dict) else "",
            presented_to=serializer.validated_data.get("audience", ""),
            vp_jwt=serializer.validated_data["vp_jwt"][:4096],
            verified=ok,
            verification_errors=errors,
        )
    except Exception:
        logger.debug("VP audit log failed", exc_info=True)
    return Response({"verified": ok, "errors": errors, "payload": payload})


# ---------------------------------------------------------------------------
# Sign-in with DID
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
def sign_in_challenge(request):
    serializer = ChallengeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ch = create_challenge(serializer.validated_data["did_string"])
    return Response(
        {"nonce": ch.nonce, "expires_at": ch.expires_at.isoformat()}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def sign_in_verify(request):
    serializer = SignInVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ok, user, errors = verify_sign_in_presentation(
        did_string=serializer.validated_data["did_string"],
        vp_jwt=serializer.validated_data["vp_jwt"],
        expected_nonce=serializer.validated_data["nonce"],
    )
    if not ok or user is None:
        return Response(
            {"verified": False, "errors": errors},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "verified": True,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {"id": user.id, "username": user.username, "email": user.email},
        }
    )


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def status_list(request, list_id: str):
    rl = get_object_or_404(RevocationList, list_id=list_id)
    return Response(
        {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://w3id.org/vc/status-list/2021/v1",
            ],
            "id": f"{request.build_absolute_uri()}",
            "type": ["VerifiableCredential", "StatusList2021Credential"],
            "issuer": getattr(settings, "DID_ISSUER_DID", ""),
            "credentialSubject": {
                "id": f"{request.build_absolute_uri()}#list",
                "type": "StatusList2021",
                "statusPurpose": "revocation",
                "encodedList": rl.encoded_list,
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_credential(request, vc_id):
    if not request.user.is_staff:
        return Response(
            {"error": "Only staff users can revoke credentials"},
            status=status.HTTP_403_FORBIDDEN,
        )
    vc = get_object_or_404(VerifiableCredential, id=vc_id)
    vc.status = "revoked"
    vc.save(update_fields=["status"])
    return Response(VCSerializer(vc).data)


# ---------------------------------------------------------------------------
# .well-known/did.json for did:web
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def well_known_did_json(request):
    key = did_service.ensure_issuer_key()
    return Response(did_service.did_document_for_did_web(key))

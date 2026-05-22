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
        logger.exception("Handled ValueError in view")
        return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
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
        logger.exception("Handled ValueError in view")
        return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
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
        logger.exception("Handled ValueError in view")
        return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)

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
    """Issue a nonce + binding cookie for the Sign-in-with-DID flow.

    Audit-fix C9 (2026-05): the challenge response now sets a
    ``did_signin_binding`` cookie that the verify endpoint MUST observe.
    This binds an otherwise-replayable VP to the holder's browser.
    """
    from .services.sign_in_service import (
        CHALLENGE_TTL_SECONDS,
        SIGNIN_BINDING_COOKIE,
    )

    serializer = ChallengeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ch, binding_token = create_challenge(serializer.validated_data["did_string"])
    resp = Response(
        {"nonce": ch.nonce, "expires_at": ch.expires_at.isoformat()}
    )
    # Cookie scope intentionally narrow: HttpOnly so JS can't read it,
    # Secure so it never leaves TLS, SameSite=Strict so cross-site CSRF
    # cannot replay it. Reuse the single source-of-truth TTL constant so
    # the cookie's max_age can't drift from `ch.expires_at` if the TTL
    # is ever retuned. Refined per CodeRabbit review.
    resp.set_cookie(
        SIGNIN_BINDING_COOKIE,
        binding_token,
        max_age=CHALLENGE_TTL_SECONDS,
        httponly=True,
        secure=not getattr(settings, 'DEBUG', False),
        samesite='Strict',
        path='/',
    )
    return resp


@api_view(["POST"])
@permission_classes([AllowAny])
def sign_in_verify(request):
    """Verify a Verifiable Presentation and mint JWTs.

    Reads the ``did_signin_binding`` cookie set at challenge time and
    passes it through to the service so the atomic nonce-consume UPDATE
    can require it in the WHERE clause (audit fix C9).
    """
    from .services.sign_in_service import SIGNIN_BINDING_COOKIE

    serializer = SignInVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    client_binding = request.COOKIES.get(SIGNIN_BINDING_COOKIE)
    ok, user, errors = verify_sign_in_presentation(
        did_string=serializer.validated_data["did_string"],
        vp_jwt=serializer.validated_data["vp_jwt"],
        expected_nonce=serializer.validated_data["nonce"],
        client_binding=client_binding,
    )
    if not ok or user is None:
        return Response(
            {"verified": False, "errors": errors},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    refresh = RefreshToken.for_user(user)
    resp = Response(
        {
            "verified": True,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {"id": user.id, "username": user.username, "email": user.email},
        }
    )
    # Burn the binding cookie now that it has fulfilled its purpose.
    resp.delete_cookie(SIGNIN_BINDING_COOKIE, path='/')
    return resp


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

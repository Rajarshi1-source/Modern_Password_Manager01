"""DRF views for social_recovery."""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from password_manager.throttling import VouchAttestationThrottle

from .models import RecoveryCircle, SocialRecoveryRequest, Voucher
from .serializers import (
    AcceptInvitationSerializer,
    AttestationSerializer,
    AuditLogSerializer,
    CircleSerializer,
    CreateCircleSerializer,
    InitiateRequestSerializer,
    RequestSerializer,
)
from .services import (
    accept_invitation,
    complete_request,
    create_circle,
    initiate_request,
    submit_attestation,
)
from .services.recovery_completion_service import abandon_request, cancel_request
from shared import sealed_shares
from shared.client_ip import get_client_ip


User = get_user_model()

logger = logging.getLogger(__name__)


_client_ip = get_client_ip


# ---------------------------------------------------------------------------
# Circle endpoints
# ---------------------------------------------------------------------------


class CircleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        circles = RecoveryCircle.objects.filter(user=request.user).prefetch_related("vouchers")
        return Response(CircleSerializer(circles, many=True).data)

    def post(self, request):
        serializer = CreateCircleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        voucher_specs = []
        for v in data["vouchers"]:
            spec = dict(v)
            uid = spec.pop("user_id", None)
            spec["user"] = User.objects.filter(id=uid).first() if uid else None
            voucher_specs.append(spec)

        try:
            circle = create_circle(
                user=request.user,
                secret_check=data["secret_check"],
                threshold=data["threshold"],
                vouchers=voucher_specs,
                min_voucher_reputation=data.get("min_voucher_reputation", 0),
                min_total_stake=data.get("min_total_stake", 0),
                cooldown_hours=data.get("cooldown_hours", 24),
            )
        except ValueError as exc:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            CircleSerializer(circle).data, status=status.HTTP_201_CREATED
        )


class CircleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, circle_id):
        circle = get_object_or_404(
            RecoveryCircle, circle_id=circle_id, user=request.user
        )
        return Response(CircleSerializer(circle).data)


# ---------------------------------------------------------------------------
# Voucher endpoints
# ---------------------------------------------------------------------------


class AcceptInvitationView(APIView):
    """Public endpoint: voucher signs the invitation token.

    GET returns the voucher's sealed share so its device can compute the
    share proof that POST requires.
    """

    permission_classes = [AllowAny]

    def get(self, request, invitation_token):
        voucher = Voucher.objects.filter(invitation_token=invitation_token).first()
        if voucher is None or not voucher.invitation_is_valid:
            return Response({"error": "invalid_request"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "voucher_id": str(voucher.voucher_id),
            "share_index": voucher.share_index,
            "sealed_share": sealed_shares.b64(voucher.encrypted_shard_data),
        })

    def post(self, request, invitation_token):
        payload = dict(request.data)
        payload.setdefault("invitation_token", invitation_token)
        serializer = AcceptInvitationSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            voucher = accept_invitation(
                invitation_token=data["invitation_token"],
                signature=data["signature"],
                share_proof=data["share_proof"],
            )
        except ValueError as exc:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "voucher_id": str(voucher.voucher_id),
                "status": voucher.status,
                "circle_id": str(voucher.circle_id),
            }
        )


# ---------------------------------------------------------------------------
# Recovery request endpoints
# ---------------------------------------------------------------------------


class InitiateRecoveryView(APIView):
    # Unauthenticated: anyone in possession of a circle_id can start a
    # request. Combined with the throttle below this is fine — quorum
    # still requires voucher signatures — but without rate limiting a
    # discoverer of any circle_id could pin the cooldown timer.
    permission_classes = [AllowAny]
    throttle_classes = [VouchAttestationThrottle]

    def post(self, request):
        serializer = InitiateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        circle = get_object_or_404(RecoveryCircle, circle_id=data["circle_id"])
        try:
            recovery_request = initiate_request(
                circle=circle,
                requester_public_key=data["requester_public_key"],
                abandon_token_hash=data.get("abandon_token_hash", b""),
                initiator_email=data.get("initiator_email", ""),
                initiator_ip=_client_ip(request),
                device_fingerprint=data.get("device_fingerprint", ""),
                geo=data.get("geo", {}),
            )
        except ValueError as exc:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            RequestSerializer(recovery_request).data, status=status.HTTP_201_CREATED
        )


class RequestDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        return Response(RequestSerializer(recovery_request).data)


class AttestRequestView(APIView):
    # The attestation endpoint is the spam target: a leaked voucher key
    # could otherwise be POSTed at full line-rate until quorum flips.
    # ``VouchAttestationThrottle`` caps both per-voucher (10/min default)
    # and per-IP (50/hour default) — both buckets must allow the request.
    permission_classes = [AllowAny]
    throttle_classes = [VouchAttestationThrottle]

    def post(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        serializer = AttestationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        voucher = get_object_or_404(
            Voucher, voucher_id=data["voucher_id"], circle=recovery_request.circle
        )
        try:
            attestation = submit_attestation(
                request=recovery_request,
                voucher=voucher,
                decision=data["decision"],
                signature=data["signature"],
                fresh_commitment=data.get("fresh_commitment"),
                proof_T=data.get("proof_T"),
                proof_s=data.get("proof_s"),
                resealed_share=data.get("resealed_share"),
                stake_amount=data.get("stake_amount", 0),
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ValueError as exc:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "attestation_id": str(attestation.attestation_id),
                "request_status": recovery_request.status,
                "received_approvals": recovery_request.received_approvals,
            },
            status=status.HTTP_201_CREATED,
        )


class CompleteRequestView(APIView):
    # Returns only shares re-sealed to the requester's one-time key, which
    # nobody else can open; the throttle limits polling.
    permission_classes = [AllowAny]
    throttle_classes = [VouchAttestationThrottle]

    def post(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        try:
            result = complete_request(request=recovery_request)
        except ValueError:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**result, "status": recovery_request.status})


class AbandonRequestView(APIView):
    # Authorised by the token only the requester's device can derive.
    permission_classes = [AllowAny]
    throttle_classes = [VouchAttestationThrottle]

    def post(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        token = sealed_shares.decode_digest(request.data.get("abandon_token", ""))
        try:
            if token is None:
                raise ValueError("abandon_token must be a base64 32-byte value")
            abandon_request(request=recovery_request, abandon_token=token)
        except ValueError:
            logger.exception("Handled ValueError in view")
            return Response({"error": "invalid_request"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "failed"})


class CancelRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        recovery_request = get_object_or_404(
            SocialRecoveryRequest, request_id=request_id
        )
        if recovery_request.circle.user_id != request.user.id:
            return Response({"error": "not the circle owner"}, status=status.HTTP_403_FORBIDDEN)
        try:
            cancel_request(
                request=recovery_request,
                slash_denies=bool(request.data.get("slash_approvers", False)),
            )
        except ValueError as exc:
            logger.exception("Handled ValueError in view")
            return Response({"error": 'invalid_request'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": recovery_request.status})


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_view(request):
    from .models import SocialRecoveryAuditLog

    qs = (
        SocialRecoveryAuditLog.objects.filter(user=request.user)
        .order_by("-created_at")[:200]
    )
    return Response(AuditLogSerializer(qs, many=True).data)

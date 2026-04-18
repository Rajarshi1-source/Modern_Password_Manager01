"""DRF views for social_recovery."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RecoveryCircle, SocialRecoveryRequest, Voucher
from .serializers import (
    AcceptInvitationSerializer,
    AttestationSerializer,
    AuditLogSerializer,
    CircleSerializer,
    CompleteRequestSerializer,
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
from .services.recovery_completion_service import cancel_request


User = get_user_model()


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
                master_secret_hex=data["master_secret_hex"],
                threshold=data["threshold"],
                vouchers=voucher_specs,
                min_voucher_reputation=data.get("min_voucher_reputation", 0),
                min_total_stake=data.get("min_total_stake", 0),
                cooldown_hours=data.get("cooldown_hours", 24),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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
    """Public endpoint: voucher signs the invitation token."""

    permission_classes = [AllowAny]

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
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitiateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        circle = get_object_or_404(RecoveryCircle, circle_id=data["circle_id"])
        try:
            recovery_request = initiate_request(
                circle=circle,
                initiator_email=data.get("initiator_email", ""),
                initiator_ip=_client_ip(request),
                device_fingerprint=data.get("device_fingerprint", ""),
                geo=data.get("geo", {}),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            RequestSerializer(recovery_request).data, status=status.HTTP_201_CREATED
        )


class RequestDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        return Response(RequestSerializer(recovery_request).data)


class AttestRequestView(APIView):
    permission_classes = [AllowAny]

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
                stake_amount=data.get("stake_amount", 0),
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "attestation_id": str(attestation.attestation_id),
                "request_status": recovery_request.status,
                "received_approvals": recovery_request.received_approvals,
            },
            status=status.HTTP_201_CREATED,
        )


class CompleteRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, request_id):
        recovery_request = get_object_or_404(SocialRecoveryRequest, request_id=request_id)
        serializer = CompleteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            secret_hex = complete_request(
                request=recovery_request,
                decrypted_shares=serializer.validated_data["decrypted_shares"],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"secret_hex": secret_hex, "status": recovery_request.status})


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
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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

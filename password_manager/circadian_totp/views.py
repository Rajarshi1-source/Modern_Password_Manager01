"""HTTP views for circadian_totp (mounted under /api/circadian/).

All endpoints require an authenticated user via the project-wide JWT
authentication class (see REST_FRAMEWORK settings). The public
/verify/ endpoint is still JWT-gated because it is used for step-up MFA
after a primary login has produced a JWT.
"""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import CircadianTOTPDevice, WearableLink
from .serializers import (
    CircadianProfileSerializer,
    CircadianTOTPDeviceSerializer,
    SleepIngestSerializer,
    WearableLinkSerializer,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile(request):
    """Return the caller's circadian profile + linked wearables."""
    prof = services.get_or_create_profile(request.user)
    links = WearableLink.objects.filter(user=request.user)
    devices = CircadianTOTPDevice.objects.filter(user=request.user)
    return Response(
        {
            "profile": CircadianProfileSerializer(prof).data,
            "wearables": WearableLinkSerializer(links, many=True).data,
            "devices": CircadianTOTPDeviceSerializer(devices, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recompute_calibration(request):
    """Re-run phase estimation from stored SleepObservation rows."""
    prof = services.recompute_profile(request.user)
    return Response(CircadianProfileSerializer(prof).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wearable_connect(request, provider: str):
    """Initiate OAuth linking for a wearable provider."""
    try:
        url, state = services.wearable_authorize_url(request.user, provider)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except NotImplementedError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
    return Response({"authorize_url": url, "state": state})


@api_view(["POST", "GET"])
@permission_classes([IsAuthenticated])
def wearable_callback(request, provider: str):
    """Complete OAuth for a provider with the authorization `code`.

    Accepts both POST (body) and GET (query string) for flexibility with
    browser redirect flows.
    """
    code = request.data.get("code") or request.query_params.get("code")
    state = request.data.get("state") or request.query_params.get("state", "")
    if not code:
        return Response(
            {"error": "authorization code is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        link = services.wearable_exchange_code(request.user, provider, code, state)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WearableLinkSerializer(link).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wearable_ingest(request, provider: str):
    """Ingest sleep observations pushed by a mobile client.

    The payload is a list under ``observations``. Each observation must contain
    ``sleep_start`` and ``sleep_end`` ISO-8601 timestamps; ``efficiency_score``
    is optional.
    """
    serializer = SleepIngestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        created = services.ingest_sleep_observations(
            request.user, provider, serializer.validated_data["observations"]
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    prof = services.recompute_profile(request.user)
    return Response(
        {
            "created": created,
            "profile": CircadianProfileSerializer(prof).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wearable_unlink(request, provider: str):
    """Remove stored OAuth credentials for a provider."""
    deleted, _ = WearableLink.objects.filter(
        user=request.user, provider=provider
    ).delete()
    return Response({"deleted": deleted})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def device_setup(request):
    """Provision a new CircadianTOTPDevice and return a QR provisioning URI."""
    name = request.data.get("name") or "Circadian Authenticator"
    device, provisioning_uri = services.provision_device(request.user, name)
    return Response(
        {
            "device": CircadianTOTPDeviceSerializer(device).data,
            "provisioning_uri": provisioning_uri,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def device_verify(request):
    """Confirm a freshly-provisioned device using a code.

    Request:  {"device_id": uuid, "code": "123456"}
    """
    device_id = request.data.get("device_id")
    code = request.data.get("code", "")
    if not device_id or not code:
        return Response(
            {"error": "device_id and code are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    device = get_object_or_404(
        CircadianTOTPDevice, id=device_id, user=request.user
    )
    ok = services.confirm_device(device, code)
    return Response(
        {"confirmed": ok, "device": CircadianTOTPDeviceSerializer(device).data},
        status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def device_list(request):
    devices = CircadianTOTPDevice.objects.filter(user=request.user)
    return Response(CircadianTOTPDeviceSerializer(devices, many=True).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    device = get_object_or_404(
        CircadianTOTPDevice, id=device_id, user=request.user
    )
    device.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_verify(request):
    """Runtime MFA verification used by auth_module and step-up flows.

    Request: {"code": "123456", "device_id": (optional) uuid}
    """
    code = request.data.get("code", "")
    device_id = request.data.get("device_id")
    if not code:
        return Response(
            {"error": "code is required"}, status=status.HTTP_400_BAD_REQUEST
        )
    verified = services.verify_code_for_user(
        request.user, code, device_id=device_id
    )
    return Response(
        {"verified": verified},
        status=status.HTTP_200_OK if verified else status.HTTP_401_UNAUTHORIZED,
    )

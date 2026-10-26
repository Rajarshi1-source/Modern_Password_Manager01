"""
Recovery notices (auth_module/recovery_notice.py).

GET  /api/auth/recovery-notices/          the account's recent notices (in-app)
POST /api/auth/recovery-notices/cancel/   {"token": ...} "this wasn't me"
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .recovery_throttling import RecoveryThrottle

from .models import RecoveryNotice
from .recovery_notice import cancel_from_notice

CANCEL_ANSWER = (
    'If that link was valid and not expired, the recovery it reported has been stopped. '
    'Nothing else changes if it was not.'
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_recovery_notices(request):
    notices = RecoveryNotice.objects.filter(user=request.user)[:50]
    return Response({'notices': [{
        'id': str(n.id),
        'event': n.event,
        'description': n.get_event_display(),
        'created_at': n.created_at,
        'cancel_until': n.cancel_until,
        'cancelled_at': n.cancelled_at,
        'ip_address': n.ip_address,
        'user_agent': n.user_agent,
    } for n in notices]})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RecoveryThrottle])
def cancel_recovery_notice(request):
    """The same answer whether or not the token was valid, so the endpoint
    cannot be used to test tokens."""
    cancel_from_notice(request.data.get('token'))
    return Response({'message': CANCEL_ANSWER}, status=status.HTTP_200_OK)

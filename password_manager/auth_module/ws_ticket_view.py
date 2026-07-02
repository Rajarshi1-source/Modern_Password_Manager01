"""
WebSocket authentication ticket endpoint.

``POST /api/auth/ws-ticket/`` issues a short-lived, single-use ticket that the
browser uses to open a WebSocket without putting its long-lived auth token in
the URL. The request itself is authenticated the normal way (token/JWT in the
``Authorization`` header), so the token never appears in a ``ws://`` URL, access
log, or browser history.
"""

from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from ml_dark_web.ws_ticket import TTL_SECONDS, issue_ticket


# The DRF default is JWT-only, but the SPA's api client sends
# "Authorization: Token <key>" (legacy AuthContext stores DRF tokens under the
# localStorage 'token' key). Accept both — mirroring CurrentUserView — so ticket
# minting works for JWT and DRF-token sessions alike.
@api_view(['POST'])
@authentication_classes([JWTAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def ws_ticket_view(request):
    """Issue a short-lived, single-use WebSocket auth ticket for the caller.

    The ticket is consumed on first use by the shared WS auth middleware and
    expires after ``TTL_SECONDS``.
    """
    ticket = issue_ticket(request.user.id)
    return Response({'ticket': ticket, 'expires_in': TTL_SECONDS})

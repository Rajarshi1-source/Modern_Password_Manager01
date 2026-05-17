"""
GET /api/auth/me/ — return the authenticated user's profile.

Provides bootstrap-time user hydration so the SPA doesn't have to
persist the profile to `localStorage`. Accepts both SimpleJWT bearer
tokens and the legacy DRF authtoken — same endpoint serves both
coexisting auth providers (see `hooks/useAuth.jsx` and
`contexts/AuthContext.jsx`).

NOTE on cross-PR coordination: this same view also lands in PR #245
(the CodeQL #1048 follow-up). Both PRs define an identical view at
the same URL path. Whichever merges first wins; the second will
need a trivial conflict resolution (accept the identical file).
The contents intentionally match between the two PRs so the
resolution is mechanical.

The whitelist mirrors the SPA's `SAFE_USER_FIELDS`. A custom
Profile model (when present on `request.user.profile`) extends the
response with `display_name`, `avatar`, etc. via getattr-fallback
so deployments without one surface null rather than erroring.
"""
from __future__ import annotations

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication


class CurrentUserView(APIView):
    """GET /api/auth/me/ — minimal profile of the authenticated user."""

    # Tuples so Ruff RUF012 (mutable class-attr) doesn't flag, and so
    # a stray `+=` on the class can't mutate the shared default.
    authentication_classes = (JWTAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = request.user
        body = {
            'id': user.pk,
            'username': user.get_username(),
            'email': getattr(user, 'email', '') or '',
            'first_name': getattr(user, 'first_name', '') or '',
            'last_name': getattr(user, 'last_name', '') or '',
            'date_joined': (
                user.date_joined.isoformat()
                if getattr(user, 'date_joined', None) is not None
                else None
            ),
            'is_staff': bool(getattr(user, 'is_staff', False)),
            'is_superuser': bool(getattr(user, 'is_superuser', False)),
        }
        profile = getattr(user, 'profile', None)
        if profile is not None:
            body.update({
                'display_name': getattr(profile, 'display_name', None),
                'avatar': getattr(profile, 'avatar', None),
                'avatar_url': getattr(profile, 'avatar_url', None),
                'locale': getattr(profile, 'locale', None),
                'preferred_language': getattr(profile, 'preferred_language', None),
                'timezone': getattr(profile, 'timezone', None),
            })
        return Response(body)

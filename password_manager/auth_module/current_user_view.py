"""
GET /api/auth/me/ — return the authenticated user's profile.

Why this exists
---------------
CodeQL alert #1048 (`js/clear-text-storage-of-sensitive-data`) led
us to stop persisting the user profile to `localStorage`. The
trade-off: on page reload, the SPA has a valid auth token but no
cached user object, so anything that renders `user.email` or
`user.username` would show empty values until the user navigated
to a route that happened to fetch the profile.

CodeRabbit + Codex flagged this as a UX regression on PR #245.
The right fix is for the SPA bootstrap to hydrate the user via an
API call. The existing `/api/users/{user_id}/` endpoint requires
knowing `user_id` up-front — which we don't have on a token-only
bootstrap (the legacy DRF TokenAuth flow uses opaque tokens and
the SimpleJWT flow would require client-side JWT parsing).

This view solves both: it identifies the user from `request.user`
(populated by whichever authentication class accepted the token)
and returns a minimal, display-safe profile. Both auth flows can
call the same endpoint with no client-side identity bookkeeping.

The response shape mirrors the field whitelist in
`frontend/src/utils/userStorage.js::SAFE_USER_FIELDS` so a
component that previously read from cached `localStorage.user`
sees the same field set.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class CurrentUserView(APIView):
    """GET /api/auth/me/ — minimal profile of the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        # Whitelist — mirrors the SPA's SAFE_USER_FIELDS so the response
        # shape is the one consumers of `useAuth().user` already expect.
        # Adding a new field here is a deliberate decision and should be
        # paired with adding it to SAFE_USER_FIELDS on the frontend.
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
        return Response(body)

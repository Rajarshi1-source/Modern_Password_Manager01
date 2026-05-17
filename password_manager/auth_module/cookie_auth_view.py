"""
HttpOnly-cookie-based refresh-token endpoints.

Why this exists
---------------
The existing ``/api/auth/token/`` and ``/api/auth/token/refresh/``
endpoints return the refresh token in the JSON response. The web
client then writes it to ``localStorage``, which means any XSS in
the SPA (or a compromised third-party script) can exfiltrate the
refresh token and impersonate the user for the entire refresh-token
lifetime (currently 7 days, see ``settings.SIMPLE_JWT``).

The hardened pattern, recommended for browser-based SPAs, is:

  * The refresh token lives in an **HttpOnly, Secure, SameSite=Strict
    cookie** scoped to ``/api/auth/``. JavaScript cannot read or
    enumerate it; only the browser's network stack sends it back on
    matching requests.
  * The access token is **kept in memory only** in the SPA (a closure
    or module-level variable, never persisted to ``localStorage`` /
    ``sessionStorage``). On page reload the SPA calls the
    cookie-refresh endpoint to mint a fresh access token from the
    cookie. The 15-minute access-token TTL means the in-memory copy
    is short-lived even if it is briefly exposed in a heap dump.
  * Refresh-on-use rotation is preserved (``ROTATE_REFRESH_TOKENS``
    + ``BLACKLIST_AFTER_ROTATION`` from ``SIMPLE_JWT``). Every
    refresh issues a new cookie and blacklists the old one.

Scope of this PR
----------------
This module provides the foundation alongside the existing endpoints.
It does NOT remove or change the legacy ``/token/`` and
``/token/refresh/`` paths — those keep working so existing logged-in
users keep their sessions. New code can opt into the cookie flow via
a frontend feature flag; once that flag is fully rolled out the
legacy endpoints can be retired in a follow-up.

Three views:

  ``CookieTokenObtainView``
      POST username + password → issues access token in JSON body,
      sets refresh token as HttpOnly cookie.

  ``CookieTokenRefreshView``
      POST with the HttpOnly refresh cookie → returns a new access
      token in JSON, rotates the refresh cookie. No body required.

  ``CookieTokenLogoutView``
      POST → blacklists the refresh token (if SimpleJWT blacklist
      app is installed), clears the cookie.

CSRF
----
``SameSite=Strict`` is the primary defense against cross-site request
forgery for these endpoints — a malicious origin cannot cause the
browser to send the cookie on a cross-site request. We additionally
require the SPA's ``X-Requested-With: XMLHttpRequest`` header on the
refresh endpoint as a belt-and-suspenders check: a legitimate
``fetch()``/``axios`` call from the SPA sets it; an HTML form GET
from another origin would not. CSRF token exchange is unnecessary
for these specific endpoints because the cookie itself is the
authenticator, and same-site enforcement plus the header check
covers the relevant attack surface.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken


# ---------------------------------------------------------------------------
# Cookie shape — single source of truth.
#
# All cookie settings are derived from environment / Django settings so a
# test environment (HTTP localhost, dev) can relax ``secure`` and ``samesite``
# while production deployments keep them strict. Defaults match the
# OWASP recommendation for refresh tokens.
# ---------------------------------------------------------------------------

REFRESH_COOKIE_NAME = getattr(settings, "AUTH_REFRESH_COOKIE_NAME", "auth_refresh")
REFRESH_COOKIE_PATH = getattr(settings, "AUTH_REFRESH_COOKIE_PATH", "/api/auth/")
REFRESH_COOKIE_DOMAIN = getattr(settings, "AUTH_REFRESH_COOKIE_DOMAIN", None)
# `secure=True` requires HTTPS. In local dev (DEBUG=True) we relax this so
# the cookie still flows over http://localhost:8000. NEVER set this to
# False in production — an HTTP refresh-token cookie is an open lobby for
# network attackers.
REFRESH_COOKIE_SECURE = getattr(
    settings, "AUTH_REFRESH_COOKIE_SECURE", not settings.DEBUG
)
# `Strict` is the right answer for an SPA-only refresh endpoint: the
# cookie should never travel cross-site under any circumstance. If a
# future use-case needs OAuth-style cross-site redirects we can downgrade
# to `Lax` per endpoint, but the refresh cookie itself must stay Strict.
REFRESH_COOKIE_SAMESITE = getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", "Strict")


def _refresh_cookie_max_age_seconds() -> int:
    """Pull the configured refresh-token TTL and convert to seconds."""
    lifetime: timedelta = settings.SIMPLE_JWT.get(
        "REFRESH_TOKEN_LIFETIME", timedelta(days=7)
    )
    return int(lifetime.total_seconds())


def _set_refresh_cookie(response: Response, token_value: str) -> None:
    """Write the refresh-token cookie with the hardened attribute set."""
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token_value,
        max_age=_refresh_cookie_max_age_seconds(),
        path=REFRESH_COOKIE_PATH,
        domain=REFRESH_COOKIE_DOMAIN,
        secure=REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Delete the refresh cookie. Must mirror path/domain/samesite from
    ``_set_refresh_cookie`` or the browser will keep the original."""
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=REFRESH_COOKIE_DOMAIN,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def _read_refresh_cookie(request: Request) -> Optional[str]:
    """Return the cookie value or None if absent."""
    raw = request.COOKIES.get(REFRESH_COOKIE_NAME)
    return raw if isinstance(raw, str) and raw else None


class CookieTokenObtainView(APIView):
    """POST username + password → access token in body, refresh in cookie.

    Mirrors ``TokenObtainPairView`` but the response body contains only
    the access token. The refresh token is set in an HttpOnly cookie so
    the SPA never has direct access to it.
    """

    # Disable bearer authentication: this endpoint identifies the user
    # from username/password in the request body, not from any
    # Authorization header. The SPA may have a stale bearer attached
    # from a previous session (the request interceptor attaches it
    # to every outgoing call); DRF authenticates before checking
    # permissions, so JWTAuthentication on an expired token would
    # 401 the login attempt. Same fix pattern as CookieTokenRefreshView
    # below.
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        """Resolve the configured token-obtain serializer dynamically.

        Hard-coding ``TokenObtainPairSerializer`` here bypasses the
        project setting ``SIMPLE_JWT['TOKEN_OBTAIN_SERIALIZER']``,
        which on this codebase points at
        ``auth_module.token_family.FamilyLimitedTokenObtainPairSerializer``.
        Without going through that subclass the cookie login path
        wouldn't enforce the concurrent-device cap that the legacy
        JSON /token/ flow already enforces — a real regression
        on the opt-in flow.

        Falls back to the SimpleJWT default if the project hasn't
        configured the setting.
        """
        configured = settings.SIMPLE_JWT.get(
            "TOKEN_OBTAIN_SERIALIZER",
            "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
        )
        return import_string(configured)

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer_class()(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        validated = serializer.validated_data
        access = validated.get("access")
        refresh = validated.get("refresh")

        body = {"access": access, "token_type": "Bearer"}
        # Surface the same useful claims the legacy endpoint did, minus
        # the refresh token itself — that lives in the cookie now.
        if "user" in validated:
            body["user"] = validated["user"]

        response = Response(body, status=status.HTTP_200_OK)
        if refresh is not None:
            _set_refresh_cookie(response, str(refresh))
        return response


class CookieTokenRefreshView(APIView):
    """POST (cookie-only) → returns a new access token, rotates the refresh cookie."""

    # Disable bearer authentication on this endpoint. The SPA's request
    # interceptor attaches `Authorization: Bearer <access>` to every
    # outgoing request, but by the time the SPA decides to refresh,
    # that access token is by definition expired. DRF authenticates
    # BEFORE checking permissions, so the global JWTAuthentication
    # would reject the expired bearer with 401 before our `post()`
    # ever reads the refresh cookie — turning an otherwise-valid
    # cookie session into a forced logout on every refresh cycle.
    # Codex P2 on PR #246 follow-up. Setting authentication_classes
    # to an empty list bypasses authentication entirely; AllowAny on
    # permissions still applies and our `post()` does its own cookie-
    # based identification.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        # Belt-and-suspenders on top of SameSite=Strict: refuse refreshes
        # that don't carry the SPA's XHR header. A cross-site HTML form
        # POST cannot set this header. This isn't a security boundary on
        # its own (a same-origin XSS could forge it trivially) but it
        # closes a class of mistakes where a malformed third-party page
        # accidentally triggers a refresh.
        if request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest":
            return Response(
                {"detail": "refresh requires X-Requested-With: XMLHttpRequest"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_refresh = _read_refresh_cookie(request)
        if not raw_refresh:
            return Response(
                {"detail": "refresh cookie missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError as token_err:
            # Treat any decode/validation failure as "not authenticated"
            # and respond 401. We DO NOT clear the cookie on a
            # blacklisted-token error because that is the symptom of a
            # rotation race (Codex P2 on PR #246 follow-up):
            #
            #   * Tab A and Tab B both have the same refresh cookie.
            #   * Both fire /refresh/ concurrently.
            #   * Tab A's request lands first, blacklists the old
            #     token, sets a fresh cookie on Tab A's response.
            #   * Tab B's request lands next. Decoding raises
            #     TokenError("Token is blacklisted").
            #   * If we clear the cookie here, Tab B's Set-Cookie:
            #     deletion arrives at the browser AFTER Tab A's
            #     rotated cookie and overwrites it — kicking the
            #     whole session out for a benign concurrent refresh.
            #
            # For any other TokenError (truly malformed cookie,
            # expired-and-not-rotatable, etc.) we still clear so the
            # client doesn't keep presenting a bad value on every
            # retry. Matching on the message string is fragile but
            # SimpleJWT raises a consistent "blacklisted" wording.
            err_text = str(token_err).lower()
            is_rotation_race = 'blacklist' in err_text
            response = Response(
                {"detail": "refresh token invalid or expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            if not is_rotation_race:
                _clear_refresh_cookie(response)
            return response

        new_access = str(refresh.access_token)

        # Honour SIMPLE_JWT.ROTATE_REFRESH_TOKENS — the project sets this
        # to True. We always rotate when called via this endpoint: a
        # successful refresh issues a fresh refresh-token cookie and
        # blacklists the old one (if the blacklist app is installed).
        #
        # ``new_refresh_value`` stays None when we did NOT rotate. We
        # only ever re-write the cookie on actual rotation; this both
        # (a) avoids the CodeQL "cookie constructed from user-supplied
        # input" warning that fires when we'd re-set the same user-
        # supplied token value verbatim, and (b) is a true reflection
        # of the contract — if there's no rotation, there's no new
        # cookie to set.
        new_refresh_value: Optional[str] = None
        if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
            try:
                if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION", False):
                    try:
                        refresh.blacklist()
                    except AttributeError:
                        # blacklist() is only available when the
                        # token_blacklist app is installed. The project
                        # installs it; fall through gracefully if a test
                        # environment doesn't.
                        pass
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
                # Register the rotated token in the OutstandingToken
                # table so ``enforce_token_family_limit`` (from
                # auth_module.token_family) can count it. Without
                # ``.outstand()`` SimpleJWT's family-limit enforcement
                # would silently miss every refresh-rotated token
                # issued through this endpoint and the device cap
                # would drift relative to the JSON /token/refresh/
                # path. Wrapped in AttributeError because the method
                # only exists when the token_blacklist app is
                # installed; the project installs it.
                try:
                    refresh.outstand()
                except AttributeError:
                    pass
                new_refresh_value = str(refresh)
            except TokenError:
                # If rotation fails (e.g. the existing token is exactly
                # at expiry mid-rotation), respond as unauthenticated
                # rather than silently leaving a half-rotated cookie.
                response = Response(
                    {"detail": "refresh rotation failed"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                _clear_refresh_cookie(response)
                return response

        response = Response(
            {"access": new_access, "token_type": "Bearer"},
            status=status.HTTP_200_OK,
        )
        if new_refresh_value is not None:
            _set_refresh_cookie(response, new_refresh_value)
        return response


class CookieTokenLogoutView(APIView):
    """POST → blacklists the refresh token (if installed) and clears the cookie.

    Idempotent: calling logout with no cookie returns 200. Calling it
    with a malformed cookie still clears the cookie and returns 200 —
    the user wanted to log out and the cookie is gone, which is the
    user-visible contract.
    """

    # Same reasoning as CookieTokenRefreshView — the SPA will be sending
    # this with an expired Authorization: Bearer header in tow. We
    # don't want DRF's global JWTAuthentication to 401 before the
    # cookie-based logout runs.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        raw_refresh = _read_refresh_cookie(request)
        if raw_refresh:
            try:
                refresh = RefreshToken(raw_refresh)
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass  # blacklist app not installed
            except TokenError:
                # Malformed cookie — just clear it.
                pass
        response = Response({"detail": "logged out"}, status=status.HTTP_200_OK)
        _clear_refresh_cookie(response)
        return response

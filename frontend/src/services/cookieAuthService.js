/**
 * cookieAuthService.js — client for the HttpOnly-cookie refresh-token
 * endpoints (`/api/auth/cookie/token/`, `.../refresh/`, `.../logout/`).
 *
 * Pairs with:
 *   * Backend:  auth_module/cookie_auth_view.py
 *   * Frontend: services/tokenStore.js (in-memory access token)
 *
 * The functions here are the ONLY places that know how to mint or
 * destroy an access token in the cookie-based flow. UI code calls
 * `loginWithCookie()` / `logoutWithCookie()`; the axios interceptor
 * calls `refreshAccessTokenViaCookie()` on 401 (or proactively when
 * the in-memory token is near expiry).
 *
 * `withCredentials: true` is required so the browser actually
 * includes the HttpOnly refresh cookie on these requests — axios
 * does NOT do this by default. We set it explicitly per call instead
 * of mutating `axios.defaults` so other API surfaces (vault,
 * social-recovery, etc.) are unaffected.
 *
 * `X-Requested-With: XMLHttpRequest` is required by the refresh
 * endpoint as a belt-and-suspenders check on top of SameSite=Strict.
 * See cookie_auth_view.py for the rationale.
 */
import axios from 'axios';

import {
  setAccessToken,
  clearAccessToken,
  getAccessToken,
} from './tokenStore';

const COOKIE_LOGIN_URL = '/api/auth/cookie/token/';
const COOKIE_REFRESH_URL = '/api/auth/cookie/token/refresh/';
const COOKIE_LOGOUT_URL = '/api/auth/cookie/token/logout/';

// SimpleJWT default access lifetime is 15 minutes; cookieAuth_view.py
// inherits that. We pass the hint to tokenStore so the interceptor can
// pre-emptively refresh before the next request.
const ACCESS_TOKEN_LIFETIME_SECONDS = 15 * 60;

const _commonHeaders = {
  // Marks the request as same-origin XHR. The backend's refresh
  // endpoint refuses calls without this header on top of the
  // SameSite=Strict cookie check.
  'X-Requested-With': 'XMLHttpRequest',
};

/**
 * Log in via the cookie endpoint. On success the backend sets the
 * HttpOnly refresh cookie and returns the access token in the JSON
 * body; we store the access token in memory.
 *
 * @param {{username: string, password: string}} credentials
 * @returns {Promise<{access: string, user?: object}>}
 */
export async function loginWithCookie({ username, password }) {
  const resp = await axios.post(
    COOKIE_LOGIN_URL,
    { username, password },
    {
      // Include the (initially empty) cookie jar so the response
      // Set-Cookie is accepted by the browser.
      withCredentials: true,
      headers: _commonHeaders,
    },
  );
  const { access, user } = resp.data || {};
  if (!access) {
    throw new Error('cookie login: backend response missing access token');
  }
  setAccessToken(access, ACCESS_TOKEN_LIFETIME_SECONDS);
  return { access, user };
}

/**
 * Ask the backend to mint a new access token from the refresh
 * cookie. The cookie is rotated in place (Set-Cookie on the
 * response) and the new access token is stored in memory.
 *
 * Returns `null` if the refresh cookie is missing or expired —
 * the caller should treat that as "logged out". Does not throw on
 * 401 (the expected unauthenticated path).
 *
 * @returns {Promise<string | null>} the new access token, or null
 */
export async function refreshAccessTokenViaCookie() {
  try {
    const resp = await axios.post(
      COOKIE_REFRESH_URL,
      null,
      {
        withCredentials: true,
        headers: _commonHeaders,
        // Don't let an interceptor recursively trigger a refresh on
        // the refresh call itself. Callers that wire up an axios
        // interceptor should skip `config.url === COOKIE_REFRESH_URL`.
      },
    );
    const { access } = resp.data || {};
    if (!access) {
      clearAccessToken();
      return null;
    }
    setAccessToken(access, ACCESS_TOKEN_LIFETIME_SECONDS);
    return access;
  } catch (err) {
    const status = err?.response?.status;
    if (status === 401) {
      // Backend already cleared the cookie if it was malformed; the
      // user is logged out.
      clearAccessToken();
      return null;
    }
    // Network errors / 5xx bubble — these aren't an
    // "unauthenticated" signal, the caller may want to retry.
    throw err;
  }
}

/**
 * Log out via the cookie endpoint. Blacklists the refresh token
 * server-side (if the blacklist app is installed) and clears the
 * cookie. Always clears the in-memory access token, even on network
 * failure — the user wanted to log out and that intent is honoured
 * locally regardless of whether the backend round-trip succeeds.
 */
export async function logoutWithCookie() {
  try {
    await axios.post(
      COOKIE_LOGOUT_URL,
      null,
      { withCredentials: true, headers: _commonHeaders },
    );
  } catch {
    /* swallow — local cleanup must always run */
  } finally {
    clearAccessToken();
  }
}

/**
 * Re-export for the axios interceptor convenience — keeps the
 * "access token lives here" invariant searchable from one spot.
 */
export { getAccessToken };

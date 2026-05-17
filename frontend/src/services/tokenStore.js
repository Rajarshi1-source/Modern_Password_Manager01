/**
 * tokenStore.js — in-memory access-token store.
 *
 * Why this exists
 * ---------------
 * The legacy auth flow persists both the JWT access token AND the
 * refresh token in `localStorage`. That is XSS-exfiltratable: a
 * single compromised third-party script gets a full refresh-token
 * lifetime of access to the user's vault (7 days; see
 * `SIMPLE_JWT.REFRESH_TOKEN_LIFETIME` on the backend).
 *
 * The hardened pattern this module implements:
 *
 *   * The refresh token lives in an HttpOnly+Secure+SameSite=Strict
 *     cookie scoped to `/api/auth/`. JavaScript cannot read it; only
 *     the browser's network stack sends it back to the matching
 *     endpoints (see `auth_module/cookie_auth_view.py` on the
 *     backend).
 *
 *   * The short-lived access token (15 min TTL) is kept ONLY in
 *     this module's closure. It is never written to `localStorage`,
 *     `sessionStorage`, `IndexedDB`, or any other persistent store.
 *     On page reload it disappears, and the SPA must call
 *     `/api/auth/cookie/token/refresh/` to get a fresh one from the
 *     refresh cookie.
 *
 * Trade-off vs. localStorage
 * --------------------------
 * Reload latency: one extra round-trip to mint a new access token.
 * That cost is paid by every session that survives a page reload,
 * but it closes the XSS-exfiltration window for the long-lived
 * refresh token entirely. The trade is intentional — we accept
 * the latency in exchange for the harder security property.
 *
 * Module-scope vs. React state
 * ----------------------------
 * The token deliberately lives in module scope rather than React
 * state. React state would be reset on unmount of the auth
 * provider, which can happen during route transitions or HMR.
 * A module-scope closure persists across those without leaking
 * the value into a persistent store.
 *
 * Migration discipline
 * --------------------
 * If you find yourself wanting to read the access token from
 * outside the axios interceptor / login flow — stop. The contract
 * is that the access token is held by axios, never inspected by
 * UI code. UI code asks `tokenStore.isAuthenticated()` (which
 * just checks "do we have a token at all"), not for the token
 * value. Leaking the value into a React component or a logging
 * helper is how the in-memory invariant gets quietly violated.
 */

let _accessToken = null;
let _accessTokenExpiresAtMs = null;

// Listeners notified when the token transitions from absent → present
// or present → absent. Used by the auth provider to flip
// `isAuthenticated` without exposing the token value to components.
const _listeners = new Set();

function _notify() {
  for (const fn of _listeners) {
    try {
      fn(_accessToken !== null);
    } catch {
      /* listener exceptions must not corrupt the store */
    }
  }
}

/**
 * Store a freshly-issued access token. Pass `null` to clear.
 *
 * @param {string | null} token  raw JWT access token, or null on logout
 * @param {number} [expiresInSeconds]  optional TTL hint from the
 *   backend; the store records `expiresAt` so callers can decide
 *   whether to pre-emptively refresh.
 */
export function setAccessToken(token, expiresInSeconds) {
  if (token === null || token === undefined) {
    _accessToken = null;
    _accessTokenExpiresAtMs = null;
  } else {
    _accessToken = String(token);
    _accessTokenExpiresAtMs =
      typeof expiresInSeconds === 'number' && Number.isFinite(expiresInSeconds)
        ? Date.now() + expiresInSeconds * 1000
        : null;
  }
  _notify();
}

/**
 * Return the current access token, or null if unauthenticated.
 *
 * Intended ONLY for the axios interceptor that injects the
 * `Authorization: Bearer ...` header. UI code should never call this.
 */
export function getAccessToken() {
  return _accessToken;
}

/** Boolean projection — safe for React components. */
export function isAuthenticated() {
  return _accessToken !== null;
}

/**
 * Whether the token is past (or within `graceSeconds` of) its expiry.
 * Used by the axios interceptor to decide whether to refresh before
 * the next request. Returns `false` when expiry is unknown — we
 * fall back to reactive 401 refresh in that case.
 */
export function isAccessTokenExpired(graceSeconds = 30) {
  if (_accessToken === null) return true;
  if (_accessTokenExpiresAtMs === null) return false;
  return Date.now() >= _accessTokenExpiresAtMs - graceSeconds * 1000;
}

/** Drop the in-memory token. Does NOT touch the refresh cookie —
 *  call the cookie-logout endpoint for that. */
export function clearAccessToken() {
  setAccessToken(null);
}

/**
 * Subscribe to authenticated-state transitions.
 * Returns an unsubscribe function.
 *
 * @param {(isAuthenticated: boolean) => void} listener
 * @returns {() => void}
 */
export function subscribe(listener) {
  if (typeof listener !== 'function') {
    throw new TypeError('tokenStore.subscribe expects a function');
  }
  _listeners.add(listener);
  return () => _listeners.delete(listener);
}

/**
 * Test-only escape hatch: reset the entire store state. Tests that
 * import this module repeatedly under jsdom should call this in
 * `afterEach` to avoid carrying state across tests.
 */
export function __resetForTests() {
  _accessToken = null;
  _accessTokenExpiresAtMs = null;
  _listeners.clear();
}

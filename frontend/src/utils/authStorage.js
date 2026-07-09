/**
 * authStorage.js — single source of truth for the JWT access token's
 * localStorage placement.
 *
 * The problem
 * -----------
 * Historically two localStorage keys have held the JWT access token,
 * written by different login flows:
 *   * `accessToken` — useAuth email/password login + App.jsx OAuth handleLogin
 *   * `token`       — OAuthCallback, SignInWithDID, PasskeyAuth
 *
 * `authHeader()` (utils/authHeader.js) prefers `accessToken` over `token`, so
 * if a session ends up with BOTH keys set — e.g. a user authenticates via one
 * flow and later via the other WITHOUT a clean logout in between — the reader
 * can surface the STALE `accessToken` and mask the newer `token`.
 *
 * The fix
 * -------
 * Every login write goes through `setSessionToken()`, which removes the
 * ALTERNATE key so at most one of the two is ever set. Every logout / auth-error
 * path goes through `clearStoredTokens()`, which wipes both localStorage keys,
 * the refresh token, and the in-memory cookie-flow token so no credential
 * authHeader() can read survives the transition.
 *
 * This intentionally preserves which key each flow writes (some direct readers
 * still look up `token` specifically, e.g. useBreachWebSocket / preferencesService);
 * the invariant it enforces is "exactly one access-token key set", not "always
 * accessToken".
 */
import { clearAccessToken } from '../services/tokenStore';

export const ACCESS_TOKEN_KEY = 'accessToken';
export const LEGACY_TOKEN_KEY = 'token';
const REFRESH_TOKEN_KEY = 'refreshToken';

/**
 * Persist the JWT access token under exactly one localStorage key, clearing the
 * alternate so `authHeader()` can never resolve a stale credential.
 *
 * @param {'accessToken' | 'token'} key  which key this login flow writes
 * @param {string} value  raw JWT access token
 */
export function setSessionToken(key, value) {
  const alternate = key === ACCESS_TOKEN_KEY ? LEGACY_TOKEN_KEY : ACCESS_TOKEN_KEY;
  localStorage.setItem(key, value);
  localStorage.removeItem(alternate);
}

/**
 * Wipe every JWT credential surface `authHeader()` reads: both localStorage
 * access-token keys, the refresh token, and the in-memory cookie-flow token.
 * Safe (idempotent) to call on any logout / auth-error path.
 */
export function clearStoredTokens() {
  clearAccessToken();
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

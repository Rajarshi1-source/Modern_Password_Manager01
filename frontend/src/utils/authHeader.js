/**
 * authHeader — build the Authorization header for the JWT-only backend.
 *
 * Resolves the access token the same way useAuth's axios request interceptor
 * does, so hand-rolled fetch/axios calls stay consistent with the shared client
 * across BOTH auth flows:
 *   1. the in-memory `tokenStore` — cookie-flow sessions keep the short-lived
 *      access token out of localStorage entirely;
 *   2. localStorage `accessToken` (useAuth email/password login);
 *   3. localStorage `token` (OAuth-callback / DID login).
 * When none is present (unauthenticated / post-logout) the header is omitted
 * entirely rather than sending a literal `Bearer null`.
 *
 * This is an auth-injection helper (the same role as the interceptor): it only
 * reads the token to place it on an outgoing request and never persists or logs
 * it, so tokenStore's in-memory invariant is preserved.
 *
 * NOTE: preferring `accessToken` can surface a stale credential if a session
 * ends up with BOTH localStorage keys set (the two are written/cleared by
 * different flows). The durable fix is to clear the alternate key on every
 * login/logout transition; centralising the lookup here makes that a one-file
 * change. (The cleaner long-term move is routing these callers through the
 * shared authenticated axios client instead of hand-rolling headers.)
 *
 * @returns {{ Authorization: string } | {}} object to spread into request headers
 */
import { getAccessToken as getInMemoryAccessToken } from '../services/tokenStore';

export function authHeader() {
  const token =
    getInMemoryAccessToken() ||
    localStorage.getItem('accessToken') ||
    localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default authHeader;

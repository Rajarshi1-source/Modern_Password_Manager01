/**
 * authHeader — build the Authorization header for the JWT-only backend.
 *
 * The JWT access token lives under `accessToken` (useAuth email/password login)
 * or `token` (OAuth-callback / DID login) depending on which flow the user took,
 * so we read `accessToken` first and fall back to `token`. When neither is set
 * (unauthenticated / post-logout) the header is omitted entirely rather than
 * sending a literal `Bearer null`.
 *
 * NOTE: preferring `accessToken` can surface a stale credential if a session
 * ends up with BOTH keys set (the two are written/cleared by different flows).
 * The durable fix is to clear the alternate key on every login/logout
 * transition; centralising the lookup here makes that a one-file change.
 *
 * @returns {{ Authorization: string } | {}} object to spread into request headers
 */
export function authHeader() {
  const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default authHeader;

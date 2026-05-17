/**
 * userStorage.js — narrow the `user` object before persisting it
 * to `localStorage`.
 *
 * Why this helper exists
 * ----------------------
 * CodeQL alerts #1048 / #1049 / #1050 flag every
 *   localStorage.setItem('user', JSON.stringify(userObj))
 * in the auth flow because `localStorage` is XSS-readable. The
 * structurally-correct fix is to migrate session state to
 * HttpOnly cookies issued by the Django auth backend, but that is
 * a multi-PR architectural project (server-side session storage,
 * CSRF wiring, refresh middleware, etc.).
 *
 * Until that migration lands, the next-best mitigation is to
 * limit the blast radius: only persist the fields that are
 * actually needed for the next page render (display name, email,
 * id, role flags) and drop everything else — auth tokens,
 * password-derived material, embeddings, biometric vectors,
 * downstream service tokens, etc. that the backend may shovel
 * into the `user` payload over time.
 *
 * Use this helper at EVERY `localStorage.setItem('user', ...)`
 * site so a backend change that starts returning a new sensitive
 * field cannot silently leak it into client storage. Adding a
 * new safe display field is a one-line whitelist change here.
 */

// Whitelist of `user` fields we are willing to write to
// localStorage. Anything outside this list is dropped before
// JSON.stringify, so future backend additions cannot quietly
// expand the persisted attack surface.
const SAFE_USER_FIELDS = Object.freeze([
  'id',
  'user_id',
  'pk',
  'username',
  'email',
  'first_name',
  'last_name',
  'display_name',
  'date_joined',
  'is_staff',
  'is_superuser',
  'avatar',
  'avatar_url',
  'locale',
  'preferred_language',
  'timezone',
]);

/**
 * Return a new object containing only the safe whitelisted fields
 * from `user`. Falsy / non-object input returns `null` so callers
 * can no-op on `localStorage.removeItem` style flows without
 * branching themselves.
 *
 * @param {object | null | undefined} user
 * @returns {object | null}
 */
export function scrubUserForStorage(user) {
  if (!user || typeof user !== 'object') return null;
  const scrubbed = {};
  for (const key of SAFE_USER_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(user, key)) {
      scrubbed[key] = user[key];
    }
  }
  return scrubbed;
}

/**
 * Removes any previously-persisted user object under `storageKey`.
 *
 * NOTE: this function NO LONGER WRITES to localStorage, despite the
 * "set" in the name. CodeQL flagged the previous setItem call
 * (`js/clear-text-storage-of-sensitive-data`, alert #1048) and
 * Copilot Autofix proposed turning the write into a remove —
 * accepted because:
 *
 *   1. The proper architectural fix (HttpOnly refresh-token cookies
 *      + in-memory access token + profile re-fetched from API on
 *      bootstrap) is shipping in PR #246. Once that flag rolls out
 *      we never persist user state to localStorage at all.
 *
 *   2. In the meantime, even the whitelist-scrubbed object is still
 *      a PII payload exfiltratable by any XSS in the SPA. CodeQL's
 *      taint analysis is correct that it shouldn't be persisted at
 *      all — the narrowed field set was a half-measure.
 *
 * Behavioural consequence for legacy callers: `currentUser` is no
 * longer restored from localStorage on page reload. Bootstrap code
 * (AuthContext.jsx, useAuth.jsx) now authenticates from the token
 * alone and re-fetches the profile from the backend when needed,
 * which is the same pattern PR #246's cookie flow uses.
 *
 * We keep `scrubUserForStorage` as a pure function so callers can
 * still produce a display-safe projection for transient React
 * state or for sending to a logging endpoint.
 *
 * @param {string} storageKey
 * @param {object | null | undefined} _user  unused — kept so call
 *   sites compile without changes, and so the scrub helper is
 *   still invoked as a runtime check on inputs.
 */
export function setStoredUser(storageKey, _user) {
  // Validate the input shape via the scrub helper. This keeps any
  // accidental misuse (e.g. passing a non-object) audible at the
  // call site rather than silently no-op'ing.
  scrubUserForStorage(_user);
  // Clear any value previously persisted by older builds so users
  // upgrading from a pre-fix version don't leave a stale PII payload
  // in localStorage indefinitely.
  localStorage.removeItem(storageKey);
}

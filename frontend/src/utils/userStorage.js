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

// Whitelist of `user` fields the scrub helper retains. Originally
// designed for "fields safe to persist to localStorage"; since this
// module no longer writes to localStorage at all, the list now
// governs which fields callers may project into transient React
// state (e.g. via `scrubUserForStorage` for input validation).
//
// Each field is here because UI code legitimately renders it.
// Adding a new field is a deliberate decision; it should NOT be
// done casually to silence a runtime warning.
//
// Note: `email`, `first_name`, `last_name`, and `date_joined` are
// PII (GDPR-relevant). `is_staff` / `is_superuser` reveal privilege
// level which could help target spear-phishing. We accept them
// here because they are needed for UI rendering and because the
// scrubbed object now lives only in React state (per-session) —
// not in any persistent store. CodeRabbit nit on PR #245.
const SAFE_USER_FIELDS = Object.freeze([
  // ----- identifiers (needed by API calls that take user_id) -----
  'id',
  'user_id',
  'pk',
  // ----- display name fields (rendered in header / nav) -----
  'username',
  'first_name',
  'last_name',
  'display_name',
  // ----- PII used in UI (GDPR-relevant) -----
  'email',
  'date_joined',
  // ----- privilege flags (toggle admin UI affordances) -----
  // Reveal privilege level if exfiltrated. Acceptable because the
  // UI legitimately gates affordances on them; they're also
  // re-asserted by the backend on every authenticated request.
  'is_staff',
  'is_superuser',
  // ----- visual / preference -----
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
 * Remove any previously-persisted user object under `storageKey`.
 *
 * The name is "clear", not "set", because this function does NOT
 * write to localStorage — it only ensures the slot is empty. CodeQL
 * #1048 (`js/clear-text-storage-of-sensitive-data`) led us to stop
 * persisting the user profile to client storage entirely; the
 * underlying issue is that even a whitelist-scrubbed object is still
 * a PII payload exfiltratable by any XSS in the SPA.
 *
 * Bootstrap code (AuthContext.jsx, useAuth.jsx) now hydrates the
 * user from `GET /api/auth/me/` on page reload instead of from
 * cached localStorage. The profile lives only in React state.
 *
 * Validation behaviour:
 *   * `scrubUserForStorage` is run as an input check — non-object
 *     input produces a `console.warn` so call-site misuse is
 *     audible during development. (Doesn't throw; we don't want a
 *     stray bad call to take down the login flow.)
 *   * The legacy `storageKey` slot is removed regardless, so users
 *     upgrading from a pre-fix build don't leave a stale PII
 *     payload in localStorage indefinitely.
 *
 * `scrubUserForStorage` is kept as a pure function so callers can
 * project a display-safe view into transient React state (e.g.
 * for sending to a logging endpoint) without re-importing this
 * whole concern.
 *
 * @param {string} storageKey
 * @param {object | null | undefined} user  passed for input
 *   validation; the value itself is never written anywhere.
 */
export function clearStoredUser(storageKey, user) {
  if (user !== undefined && user !== null) {
    const scrubbed = scrubUserForStorage(user);
    if (scrubbed === null) {
      // Non-null input that the scrub rejected (i.e. not an object)
      // means the caller passed something this helper can't validate.
      // Audible so a regression that starts passing the wrong shape
      // gets noticed in dev rather than silently no-op'ing.
      // eslint-disable-next-line no-console
      console.warn(
        '[userStorage] clearStoredUser received a non-object user; ignoring.',
        { type: typeof user },
      );
    }
  }
  localStorage.removeItem(storageKey);
}

/**
 * @deprecated Use {@link clearStoredUser}. The name `setStoredUser`
 * is a maintainability hazard — it no longer writes anything; it
 * only clears the slot. Kept as a backward-compat alias so existing
 * call sites continue to compile while migration to the new name
 * progresses. CodeRabbit major nit on PR #245.
 *
 * Equivalent to `clearStoredUser(storageKey, user)`.
 */
export const setStoredUser = clearStoredUser;

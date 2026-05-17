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
 * Convenience: write the scrubbed user object to localStorage
 * under the given key. No-ops when given falsy input rather than
 * writing `null` over a previously-good value.
 *
 * @param {string} storageKey
 * @param {object | null | undefined} user
 */
export function setStoredUser(storageKey, user) {
  const safe = scrubUserForStorage(user);
  if (safe === null) return;
  localStorage.setItem(storageKey, JSON.stringify(safe));
}

/**
 * Decoy vault contents store.
 *
 * Closes the limitation `VaultDuressSetup` states in its own copy and that
 * docs/vault-unlock-envelope-integration-plan.md §7.3 deferred: a decoy
 * unlock rendered an EMPTY vault, which beats the real list failing to
 * decrypt row by row but is still not a BELIEVABLE vault. See
 * docs/decoy-vault-contents-plan.md.
 *
 * WHY THIS IS CLIENT-SIDE AND DEVICE-LOCAL
 * ----------------------------------------
 * `/api/vault/` returns one item list per account and takes no slot
 * parameter, and it must stay that way: the ZK invariant
 * (docs/adaptive-password-zk-remediation-plan.md §1-2) forbids the server
 * learning which slot unlocked a session, which rules out every server-side
 * decoy design. So the decoy's contents live where the envelope itself
 * already lives -- `localStorage`, device-local, no server copy, no
 * cross-device sync (`unlockEnvelopeStore.js` "STORAGE").
 *
 * WHAT A ROW IS
 * -------------
 * Deliberately a NORMAL vault row: `encrypted_data` is a standard
 * `sessionVaultCrypto` v2 envelope (`{v,iv,ct,salt}`) sealed under the DECOY
 * DEK, carrying the same salt the decoy slot stamps. That is a second layer
 * of encryption inside an already-encrypted container, and it is worth the
 * bytes: every consumer above this module -- `VaultItemsSection`,
 * `VaultDashboard`, `vaultEnvelope.decryptEnvelope`, `keyForSalt`'s
 * matching-salt fast path -- handles a decoy row unmodified, so no display
 * code has to learn that decoy rows exist. One shape, one code path.
 *
 * INDISTINGUISHABILITY -- the part that is easy to get wrong
 * ----------------------------------------------------------
 * A storage key that appears ONLY when a decoy is configured IS the oracle
 * this feature exists to remove: a coercer with devtools reads the feature's
 * existence off the key list and no ciphertext strength helps. Two rules,
 * both load-bearing:
 *
 *   1. `writeUnconfigured()` is called from `unlockEnvelopeStore.provision()`
 *      for EVERY account, decoy or not, filling the blob with random bytes
 *      under a throwaway key that is never stored. This mirrors what
 *      `hiddenVaultEnvelope.encode()` already does for an unconfigured decoy
 *      SLOT (see `keyFor`, quoted in `provision`'s docstring) -- the
 *      precedent and its reasoning are already in this codebase.
 *   2. The plaintext is padded to exactly `PLAINTEXT_LEN` before encryption,
 *      so the stored value is a CONSTANT length. Neither the number of decoy
 *      items nor whether there are any can be read off the blob.
 *
 * The storage key is deliberately not `vaultDecoyItems`. It is a local cache;
 * that is a true description and it names nothing.
 */

import sessionVaultCrypto, { PAYLOAD_VERSION } from '../sessionVaultCrypto';
import { HiddenVaultError } from './hiddenVaultEnvelope';

// Deliberately does NOT import `unlockEnvelopeStore`, which imports this
// module: the dependency runs one way only. Opening the decoy slot to reach
// its DEK is `unlockEnvelopeStore.seedDecoyContents`'s job, and it hands the
// key straight to `seedWithKey` below -- so no component ever holds decoy key
// material, and neither module has to reason about a cycle.

const STORAGE_KEY = 'vaultLocalCache';
const CONTAINER_VERSION = 'dvc-1';

/**
 * Padded plaintext length, in bytes, before encryption.
 *
 * Fixed so ciphertext length is fixed -- see rule 2 above. 12000 leaves room
 * for roughly 12-20 typical credentials once each row's own v2 envelope and
 * base64 expansion are paid for, which is a plausible personal vault. It is
 * NOT derived from the envelope's own 16000-byte slot length: these are
 * different blobs with different contents and coupling them would make a
 * future tier change silently re-shape this one.
 */
const PLAINTEXT_LEN = 12000;

const storageKey = (userId) => `${STORAGE_KEY}:${userId}`;

/** Raised when a caller's decoy items do not fit the fixed-length container. */
export class DecoyCapacityError extends HiddenVaultError {}

const toB64 = (bytes) => {
  let binary = '';
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.byteLength; i += 1) {
    binary += String.fromCharCode(arr[i]);
  }
  return btoa(binary);
};

const fromB64 = (b64) => {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
};

const importDecoyKey = (dekBytes) => window.crypto.subtle.importKey(
  'raw',
  dekBytes,
  { name: 'AES-GCM', length: 256 },
  false,
  ['encrypt', 'decrypt'],
);

/**
 * JSON, then NUL-pad to exactly PLAINTEXT_LEN.
 *
 * Throws rather than truncating. A truncated container decodes to nothing on
 * the next read, which during a coercion episode means the decoy vault
 * silently empties itself -- a far worse outcome than refusing the write.
 */
const padPlaintext = (obj) => {
  const encoded = new TextEncoder().encode(JSON.stringify(obj));
  if (encoded.byteLength > PLAINTEXT_LEN) {
    throw new DecoyCapacityError('Decoy vault contents exceed the available space.');
  }
  const padded = new Uint8Array(PLAINTEXT_LEN);
  padded.set(encoded, 0);
  return padded;
};

const unpadPlaintext = (bytes) => {
  let end = bytes.byteLength;
  while (end > 0 && bytes[end - 1] === 0) end -= 1;
  return JSON.parse(new TextDecoder().decode(bytes.subarray(0, end)));
};

const encryptContainer = async (key, rows) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const padded = padPlaintext({ v: CONTAINER_VERSION, rows });
  const ctBuf = await window.crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, padded);
  const ct = new Uint8Array(ctBuf);
  const out = new Uint8Array(iv.byteLength + ct.byteLength);
  out.set(iv, 0);
  out.set(ct, iv.byteLength);
  return toB64(out);
};

const writeRaw = (userId, value) => {
  try {
    localStorage.setItem(storageKey(userId), value);
    return true;
  } catch {
    // Same accepted degradation as `unlockEnvelopeStore.hasEnvelope`:
    // localStorage throws in private-browsing / disabled-cookie contexts.
    // The decoy then renders empty, which is the behaviour that shipped
    // before this module existed.
    return false;
  }
};

const readRaw = (userId) => {
  try {
    return localStorage.getItem(storageKey(userId));
  } catch {
    return null;
  }
};

// ---------------------------------------------------------------------------
// Provisioning
// ---------------------------------------------------------------------------

/**
 * Write the constant-length blob for an account with no decoy contents.
 *
 * An empty container sealed under a key that is generated, used, and dropped,
 * so nothing can ever decrypt it -- observationally indistinguishable from the
 * blob a configured account carries, which is the entire point.
 *
 * Called by `unlockEnvelopeStore.provision()` for every account so that the
 * PRESENCE of this key says nothing about whether a decoy is configured --
 * rule 1 in this module's header. The key is generated, used, and dropped;
 * nothing can ever decrypt the result, which is the point.
 *
 * Never overwrites an existing blob: a provision running on an account that
 * already has decoy contents (the corrupt-envelope self-heal reaches
 * `provision` with `replaceExisting`) would otherwise destroy them.
 */
export const writeUnconfigured = async (userId) => {
  if (!userId) return false;
  if (readRaw(userId) !== null) return false;
  const throwaway = await importDecoyKey(window.crypto.getRandomValues(new Uint8Array(32)));
  const blob = await encryptContainer(throwaway, []);
  // Re-checked AFTER the awaits, not only before them. `open()` calls this on
  // every successful unlock, and the key-generation plus AES-GCM work above is
  // a real window: another tab (or this one's own setup screen) can seed
  // contents inside it, and an unconditional write here would replace that
  // seed with filler nothing can decrypt -- the next decoy unlock would render
  // empty. Same compare-before-write shape `provision` already uses across its
  // own Argon2 awaits, for the same reason.
  if (readRaw(userId) !== null) return false;
  return writeRaw(userId, blob);
};

// ---------------------------------------------------------------------------
// Seeding (real session)
// ---------------------------------------------------------------------------

/**
 * Replace the decoy vault's contents, given the decoy slot's own key.
 *
 * Called only by `unlockEnvelopeStore.seedDecoyContents`, which opens slot 1
 * and passes what it found. Contents can therefore be edited WITHOUT
 * re-running `setDecoySlot`, so the duress token is never regenerated and
 * never needs re-registering with the server -- seeding and slot
 * configuration are independent operations.
 *
 * @param {Object} args
 * @param {string} args.userId
 * @param {Uint8Array} args.dekBytes - the DECOY slot's 32-byte DEK
 * @param {string} args.saltB64 - the salt that slot stamps
 * @param {Array<Object>} args.items - plain objects, each the `data` of one
 *   vault item, in the schema the vault's own display surfaces read
 *   (`{ name, username, password, website, notes }`).
 * @returns {Promise<boolean>} false when the write itself failed (a
 *   localStorage rejection in private browsing). Callers must not report
 *   success on a false: the contents were never stored.
 * @throws {DecoyCapacityError} the items do not fit
 */
export const seedWithKey = async ({ userId, dekBytes, saltB64, items }) => {
  if (!userId) throw new Error('seedWithKey: userId required');
  if (!(dekBytes instanceof Uint8Array) || dekBytes.byteLength !== 32) {
    throw new Error('seedWithKey: dekBytes must be a 32-byte Uint8Array');
  }
  const key = await importDecoyKey(dekBytes);
  const rows = [];
  for (let i = 0; i < (items || []).length; i += 1) {
    rows.push(await buildRow(key, saltB64, items[i], i));
  }
  // Encrypt BEFORE touching storage: `padPlaintext` raises DecoyCapacityError
  // for an oversized set, and it must do so with the previous contents still
  // intact rather than after having cleared them.
  const blob = await encryptContainer(key, rows);
  return writeRaw(userId, blob);
};

/**
 * Re-key the container to an empty one under a NEW decoy DEK.
 *
 * `setDecoySlot` generates a fresh decoy DEK every time it runs, so replacing
 * a decoy password leaves any existing contents sealed under a key nothing
 * holds any more. `loadForSession` then returns [] and the decoy silently
 * opens empty -- the user believes their decoy vault is intact and it is not.
 *
 * Migration is impossible here: re-encrypting needs the OLD decoy DEK, and
 * `setDecoySlot` is given the real vault password and the NEW decoy password,
 * never the old one. So the honest resolution is to drop the unreadable
 * ciphertext and have the setup screen tell the user to re-enter the contents,
 * which is what `VaultDuressSetup` now does.
 */
export const resetForNewKey = async (userId, dekBytes) => {
  if (!userId) return false;
  if (!(dekBytes instanceof Uint8Array) || dekBytes.byteLength !== 32) return false;
  const key = await importDecoyKey(dekBytes);
  return writeRaw(userId, await encryptContainer(key, []));
};

/**
 * Seal one item into a row shaped exactly like a server row.
 *
 * `item_id` is minted the same way `VaultContext.addItem` mints one, and
 * `created_at` is spread across the recent past rather than set to "now":
 * a decoy vault whose every entry was created in the same second is a tell
 * to anyone who looks at the dashboard's timestamps.
 */
const buildRow = async (key, saltB64, data, index) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(data || {}));
  const ctBuf = await window.crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
  const ageDays = 30 + index * 17;
  return {
    id: `d${index + 1}`,
    item_id: `item_${Date.now() - index * 1000}`,
    item_type: data?.item_type || 'password',
    encrypted_data: JSON.stringify({
      // The shared constant, never a literal. Hard-coding 'v2' here made
      // `decryptItem` reject every seeded row as `_legacyPlaintext`: rows added
      // later went through `encryptDecoyItem` and decrypted fine, so the decoy
      // vault rendered a mix of real entries and warning banners.
      v: PAYLOAD_VERSION,
      iv: toB64(iv),
      ct: toB64(new Uint8Array(ctBuf)),
      salt: saltB64,
    }),
    favorite: Boolean(data?.favorite),
    created_at: new Date(Date.now() - ageDays * 86400000).toISOString(),
  };
};

// ---------------------------------------------------------------------------
// Decoy-session read/write
// ---------------------------------------------------------------------------

/**
 * Read the decoy rows for the CURRENT decoy session.
 *
 * Uses the session key, which in a decoy session IS the decoy DEK
 * (`installRawDek` imported it non-extractably), so no raw key material is
 * handled here.
 *
 * Returns `[]` for every failure -- no blob, an unconfigured random blob, a
 * corrupt one, a wrong key. That fallback direction is deliberate and is the
 * behaviour that shipped before this module existed: rendering the REAL list
 * on failure would be strictly worse than the empty vault we started from.
 * Never throws, because its caller is a render path.
 */
export const loadForSession = async (userId) => {
  if (!userId || !sessionVaultCrypto.isDecoySession()) return [];
  const raw = readRaw(userId);
  if (raw === null) return [];
  try {
    const bytes = fromB64(raw);
    const parsed = await sessionVaultCrypto.decryptDecoyContainer(
      bytes.subarray(0, 12),
      bytes.subarray(12),
    );
    const container = unpadPlaintext(parsed);
    if (!container || container.v !== CONTAINER_VERSION || !Array.isArray(container.rows)) return [];
    // Same tagging `VaultContext.refreshItems` applies to server rows, for the
    // same reason: consumers that render items directly treat them as
    // encrypted/lazy and decrypt on demand.
    return container.rows.map((row) => ({ ...row, _lazyLoaded: true, _decrypted: false }));
  } catch {
    return [];
  }
};

/**
 * Persist a mutated row list for the CURRENT decoy session.
 *
 * Returns false on any failure. Callers surface `DECOY_WRITE_REFUSAL` for a
 * false return -- the byte-identical generic string every decoy-session write
 * failure must use, because in a decoy session that message reaches a
 * coercer's screen and must stay indistinguishable from an ordinary save
 * failure (`sessionVaultCrypto.DECOY_WRITE_REFUSAL`).
 */
export const saveForSession = async (userId, rows, expectedRaw) => {
  if (!userId || !sessionVaultCrypto.isDecoySession()) return false;
  try {
    const { iv, ct } = await sessionVaultCrypto.encryptDecoyContainer(
      padPlaintext({ v: CONTAINER_VERSION, rows: rows.map(stripDisplayFlags) }),
    );
    const out = new Uint8Array(iv.byteLength + ct.byteLength);
    out.set(iv, 0);
    out.set(ct, iv.byteLength);
    // Compare-and-swap against the exact bytes the caller read, when it
    // supplied them. The session-generation checks in `mutate` and inside
    // `encryptDecoyContainer` cover this TAB -- they cannot cover another one,
    // because the generation counter is module state and a second tab has its
    // own. A real session in tab B rotating the decoy password
    // (`setDecoySlot` -> `resetForNewKey`) is invisible to a decoy session in
    // tab A, whose in-flight mutation would otherwise write old-DEK ciphertext
    // over the freshly re-keyed container -- leaving the new decoy password
    // opening a vault nothing can decrypt. Comparing stored BYTES is what
    // crosses the tab boundary; `provision` and `setDecoySlot` already use
    // exactly this idiom on the envelope itself.
    if (expectedRaw !== undefined && readRaw(userId) !== expectedRaw) return false;
    return writeRaw(userId, toB64(out));
  } catch {
    // Includes DecoyCapacityError: a decoy-session add that would overflow is
    // refused, never truncated. The caller turns this into the generic string.
    return false;
  }
};

/**
 * Drop render-only state before persisting.
 *
 * `_lazyLoaded` / `_decrypted` are tags the display layer adds, and `data` is
 * decrypted plaintext some consumers attach in memory. Writing any of them
 * back would put a decoy secret into the container in the clear, beside the
 * ciphertext that was supposed to be the only copy. Allow-list rather than
 * deny-list, so a field added upstream later cannot leak in by default.
 */
const STORED_ROW_FIELDS = ['id', 'item_id', 'item_type', 'encrypted_data', 'favorite', 'created_at', 'updated_at'];

const stripDisplayFlags = (row) => STORED_ROW_FIELDS.reduce((acc, field) => {
  if (row[field] !== undefined) acc[field] = row[field];
  return acc;
}, {});

/**
 * Serialized read-modify-write over the decoy rows.
 *
 * Every decoy-session mutation goes through here, and they are chained rather
 * than run concurrently. Two overlapping mutations each load the SAME snapshot
 * and the second write silently discards the first -- `favoriteInFlightRef`
 * in VaultContext only serializes per item id, so toggling two different rows
 * is enough to lose one. Chaining is the whole fix: the queue is per module,
 * the operations are short, and correctness beats parallelism for a list this
 * size.
 *
 * The generation binding lives here too, not in the callers: `isDecoySession()`
 * answers "is this A decoy session", not "the SAME one" -- a lock plus a
 * second decoy unlock passes the flag test while being a different session
 * (vault-unlock-envelope-integration-plan.md §32).
 *
 * @returns {Promise<boolean>} false if the session moved, the vault locked, the
 *   contents would not fit, or storage refused. Callers turn a false into the
 *   shared `DECOY_WRITE_REFUSAL` string -- never a message of their own.
 */
let mutationQueue = Promise.resolve();

export const mutate = (userId, mutator) => {
  const run = async () => {
    if (!userId || !sessionVaultCrypto.isDecoySession()) return false;
    const generation = sessionVaultCrypto.currentSessionGeneration();
    // The exact stored bytes these rows were decoded from, so the write below
    // can prove nothing replaced them -- including from another tab, which no
    // generation check can see. See `saveForSession`.
    const snapshot = readRaw(userId);
    const rows = await loadForSession(userId);
    if (sessionVaultCrypto.currentSessionGeneration() !== generation) return false;
    let next;
    try {
      next = mutator(rows);
    } catch {
      return false;
    }
    if (sessionVaultCrypto.currentSessionGeneration() !== generation) return false;
    return saveForSession(userId, next, snapshot);
  };
  // The queue must not break on a rejection, so failures are absorbed into a
  // `false` and the chain continues with a resolved promise either way.
  const result = mutationQueue.then(run, run);
  mutationQueue = result.then(() => undefined, () => undefined);
  return result;
};

/**
 * Append one item to the decoy vault.
 *
 * Shared by BOTH write paths rather than reimplemented in each: VaultContext's
 * `addItem`, and the canonical "Add New Password" form in App.jsx, which posts
 * to `/api/vault/` directly and never goes through VaultContext at all (it
 * renders outside `VaultProvider`, so it cannot). Before this, only the first
 * had a decoy branch -- so the form a coercer is most likely to be sitting in
 * front of still visibly failed to save.
 */
export const addRowForSession = async (userId, { data, itemType = 'password', favorite = false, itemId } = {}) => {
  let encrypted;
  try {
    encrypted = await sessionVaultCrypto.encryptDecoyItem(data || {});
  } catch {
    return false;
  }
  const id = itemId || `item_${Date.now()}`;
  return mutate(userId, (rows) => [
    ...rows,
    {
      // Random suffix, not the timestamp alone: `mutate` serializes writes but
      // does nothing about the CLOCK, so two appends inside one millisecond
      // produced the same `id`. `VaultContext.deleteItem` and `toggleFavorite`
      // both match rows by `id`, so one delete would have removed both rows and
      // one favourite toggle flipped both.
      id: `d${Date.now()}_${window.crypto.getRandomValues(new Uint32Array(1))[0].toString(36)}`,
      item_id: id,
      item_type: itemType,
      encrypted_data: encrypted,
      favorite: Boolean(favorite),
      created_at: new Date().toISOString(),
    },
  ]);
};

export default {
  writeUnconfigured,
  seedWithKey,
  resetForNewKey,
  mutate,
  addRowForSession,
  loadForSession,
  saveForSession,
  DecoyCapacityError,
  PLAINTEXT_LEN,
};

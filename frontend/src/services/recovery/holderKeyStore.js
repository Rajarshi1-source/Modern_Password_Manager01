/**
 * Device-local storage for recovery key pairs and sealed shares.
 *
 * - The guardian key pair lives on the guardian's device for as long as they
 *   are a guardian; its public key is what they give the account owner.
 * - A requester key pair is one-time, made per recovery request, and deleted
 *   once the recovery ends.
 * - A guardian keeps a copy of its sealed share (opaque without its key) so it
 *   can re-seal it to a requester when approving.
 *
 * Secret keys are never stored in the clear: localStorage holds them
 * encrypted with AES-256-GCM under a non-extractable CryptoKey kept in
 * IndexedDB. A copy of the browser profile or a storage dump does not reveal
 * them; script running in the page while it is open still can use them, as
 * it can use anything else the page decrypts. Callers load a key pair right
 * before using it and do not keep the secret in component state.
 *
 * Nothing here is sent to the server except public keys and sealed values.
 */
import { hybridKeyPairMatches } from '../quantum/hybridKem';
import { fromB64, newHolderKeyPair, toB64 } from './sealedShareRecovery';

const GUARDIAN_KEY = 'pwm.recovery.guardianKeyPair.v2';
const requesterKey = (requestId) => `pwm.recovery.requesterKeyPair.v2.${requestId}`;
const sealedShareKey = (voucherId) => `pwm.recovery.sealedShare.v1.${voucherId}`;

const DB_NAME = 'pwm-recovery-keys';
const DB_STORE = 'wrapping';
const WRAPPING_KEY_ID = 'aes-gcm-v1';

// Its message is written for the person using the page; other errors here
// (a blocked database, a full disk) are not. Pages tell them apart by name.
class KeyStorageError extends Error {
  constructor(message, { keyLost = false } = {}) {
    super(message);
    this.name = 'KeyStorageError';
    this.keyLost = keyLost;
  }
}

function idbRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Resolves when the transaction commits; a request can succeed and its
// transaction still abort (QuotaExceededError).
function idbCommit(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error || new Error('IndexedDB transaction aborted'));
    tx.onerror = () => reject(tx.error || new Error('IndexedDB transaction failed'));
  });
}

async function openDb() {
  if (typeof indexedDB === 'undefined') {
    throw new KeyStorageError('This browser cannot store recovery keys securely (no IndexedDB).');
  }
  const request = indexedDB.open(DB_NAME, 1);
  request.onupgradeneeded = () => request.result.createObjectStore(DB_STORE);
  return idbRequest(request);
}

const indexedDbBackend = {
  async get(id) {
    const db = await openDb();
    try {
      return await idbRequest(db.transaction(DB_STORE).objectStore(DB_STORE).get(id));
    } finally {
      db.close();
    }
  },
  async add(id, value) {
    const db = await openDb();
    try {
      // add(), not put(): if another tab stored a key first this fails and
      // the caller reads that key instead of replacing it.
      const tx = db.transaction(DB_STORE, 'readwrite');
      const committed = idbCommit(tx);
      tx.objectStore(DB_STORE).add(value, id);
      await committed;
    } finally {
      db.close();
    }
  },
};

let backend = indexedDbBackend;

/** Tests only: replace the IndexedDB backend ({get, add}). */
export function _setWrappingKeyBackendForTests(testBackend) {
  backend = testBackend || indexedDbBackend;
}

// Read from IndexedDB every time, not cached: a key held only in memory would
// keep working after IndexedDB is cleared, then fail after a reload.
async function wrappingKey() {
  const existing = await backend.get(WRAPPING_KEY_ID);
  if (existing) return existing;
  const key = await crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'],
  );
  try {
    await backend.add(WRAPPING_KEY_ID, key);
    return key;
  } catch (err) {
    // Another tab won the race: use its key. Anything else (quota, a
    // blocked database) must fail here, not hand out a key that is not
    // stored and cannot open what it seals after a reload.
    const stored = await backend.get(WRAPPING_KEY_ID);
    if (stored) return stored;
    throw err;
  }
}

async function seal(keyPair, label) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const secret = fromB64(keyPair.secretKey);
  try {
    const ct = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv, additionalData: new TextEncoder().encode(label) },
      await wrappingKey(), secret,
    );
    return { publicKey: keyPair.publicKey, iv: toB64(iv), wrappedSecretKey: toB64(new Uint8Array(ct)) };
  } finally {
    secret.fill(0);
  }
}

// Do not advise clearing site data: that also deletes the wrapped vault keys
// kept in localStorage, which can lock someone out of their vault.
function lostKeyError(label) {
  return new KeyStorageError(
    label === GUARDIAN_KEY
      ? 'The recovery key in this browser can no longer be opened, because part of this '
        + "site's stored data was cleared or changed. You can make a new one on the guardian "
        + 'key page (/recovery/guardian-key), then tell whoever relies on the old key so they '
        + 'can set up their guardians again.'
      : 'This recovery can no longer be finished in this browser, because part of this '
        + "site's stored data was cleared or changed. Start recovery again.",
    { keyLost: true },
  );
}

function holdsPublicKey(publicKeyB64, secret) {
  try {
    return hybridKeyPairMatches(fromB64(publicKeyB64), secret);
  } catch {
    return false;
  }
}

async function unseal(stored, label) {
  let plain;
  try {
    plain = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: fromB64(stored.iv), additionalData: new TextEncoder().encode(label) },
      await wrappingKey(), fromB64(stored.wrappedSecretKey),
    );
  } catch (err) {
    // Part of this site's data is gone or changed: most likely IndexedDB was
    // cleared and localStorage was not, so the wrapping key no longer matches.
    // InvalidCharacterError is a stored value that is no longer valid base64.
    if (err?.name !== 'OperationError' && err?.name !== 'InvalidCharacterError') throw err;
    throw lostKeyError(label);
  }
  const secret = new Uint8Array(plain);
  try {
    // AES-GCM authenticates the secret, not the public key stored beside it. A
    // swapped public key would have an owner seal shares to someone else, and
    // the fingerprint read out to them is computed from that same value.
    if (!holdsPublicKey(stored.publicKey, secret)) throw lostKeyError(label);
    return { publicKey: stored.publicKey, secretKey: toB64(secret) };
  } finally {
    secret.fill(0);
  }
}

function read(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function write(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function remove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* storage unavailable: nothing to remove */
  }
}

// Run `fn` once at a time across this browser's tabs (Web Locks), and once
// at a time within this tab otherwise.
let localQueue = Promise.resolve();
function exclusively(name, fn) {
  if (typeof navigator !== 'undefined' && navigator.locks?.request) {
    return navigator.locks.request(name, fn);
  }
  const run = localQueue.then(fn, fn);
  localQueue = run.catch(() => {});
  return run;
}

/**
 * This device's guardian public key, creating the key pair on first use.
 * Concurrent first uses (two tabs, two components) get the same pair.
 * Throws if the stored pair cannot be opened: handing out its public key
 * would have an owner seal a share that no one can open. The stored pair is
 * left in place until someone chooses replaceLostGuardianKey.
 */
export function getOrCreateGuardianPublicKey() {
  return exclusively('pwm-recovery-guardian-key', async () => {
    const existing = read(GUARDIAN_KEY);
    if (existing?.publicKey && existing?.wrappedSecretKey) {
      await unseal(existing, GUARDIAN_KEY);
      return existing.publicKey;
    }
    // A damaged record is a lost key, not a missing one: someone may rely on
    // it, so a new key is made only when they choose replaceLostGuardianKey.
    if (window.localStorage.getItem(GUARDIAN_KEY) !== null) throw lostKeyError(GUARDIAN_KEY);
    const keyPair = await newHolderKeyPair();
    write(GUARDIAN_KEY, await seal(keyPair, GUARDIAN_KEY));
    return keyPair.publicKey;
  });
}

/**
 * Makes a new guardian key pair, but only if the stored one cannot be opened:
 * a key that still works is returned as it is, and any other failure (a
 * blocked database) throws, so this can never replace a good key.
 */
export function replaceLostGuardianKey() {
  return exclusively('pwm-recovery-guardian-key', async () => {
    const existing = read(GUARDIAN_KEY);
    if (existing?.publicKey && existing?.wrappedSecretKey) {
      try {
        await unseal(existing, GUARDIAN_KEY);
        return existing.publicKey;
      } catch (err) {
        if (!err?.keyLost) throw err;
      }
    }
    const keyPair = await newHolderKeyPair();
    write(GUARDIAN_KEY, await seal(keyPair, GUARDIAN_KEY));
    return keyPair.publicKey;
  });
}

/** The guardian key pair, decrypted for immediate use, or null. */
export async function loadGuardianKeyPair() {
  const stored = read(GUARDIAN_KEY);
  return stored?.wrappedSecretKey ? unseal(stored, GUARDIAN_KEY) : null;
}

/**
 * Throws unless this browser can store a wrapped requester key: the wrapping
 * key loads (or is created and saved) and localStorage accepts a write. Call
 * it before asking the server for a recovery request, so a request is never
 * recorded for a key this device cannot keep.
 */
export async function assertKeyStorageAvailable() {
  await wrappingKey();
  const probe = 'pwm.recovery.storageProbe';
  write(probe, 1);
  remove(probe);
}

export async function newRequesterKeyPair() {
  return newHolderKeyPair();
}

export async function saveRequesterKeyPair(requestId, keyPair) {
  write(requesterKey(requestId), await seal(keyPair, requesterKey(requestId)));
}

/** The one-time requester key pair, decrypted for immediate use, or null. */
export async function loadRequesterKeyPair(requestId) {
  const stored = read(requesterKey(requestId));
  return stored?.wrappedSecretKey ? unseal(stored, requesterKey(requestId)) : null;
}

export function forgetRequesterKeyPair(requestId) {
  remove(requesterKey(requestId));
}

export function saveSealedShare(voucherId, sealedShare) {
  write(sealedShareKey(voucherId), sealedShare);
}

export function getSealedShare(voucherId) {
  return read(sealedShareKey(voucherId));
}

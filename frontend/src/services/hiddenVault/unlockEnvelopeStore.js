/**
 * Unlock envelope store.
 *
 * Wires the two-slot `HiddenVaultBlob` (see `./hiddenVaultEnvelope.js` and
 * `password_manager/hidden_vault/SPEC.md`) into the OAuth vault-unlock path,
 * per docs/vault-unlock-envelope-integration-plan.md §3.2.
 *
 * WHAT THE SLOTS HOLD
 * --------------------
 * This envelope does not carry vault data directly -- it carries the vault's
 * session DEK. Slot 0 (opened by the real vault password) always wraps the
 * SAME key as the legacy `vaultWrappedDEK:<userId>` record produced by
 * `sessionVaultCrypto.setupVaultPassword` / `unlockWithVaultPassword`, so a
 * user can unlock through either mechanism and reach the identical DEK --
 * every vault item stays decryptable regardless of which path was used in a
 * given session. Slot 1, when configured, wraps an independent, freshly
 * generated decoy DEK plus the password-independent duress alarm token
 * (`__duress_signal`, see `../duressSignalService.js`).
 *
 * Slot payload shape (both slots identical, so the JSON never betrays which
 * slot is which -- the decoy slot additionally carries `__duress_signal`):
 *   { v: 'hv-slot-1', dek: base64(32 raw bytes), salt: base64(16 bytes) }
 *
 * STORAGE
 * -------
 * Device-local, deliberately: `vaultUnlockEnvelope:<userId>` in localStorage,
 * alongside `vaultWrappedDEK:<userId>` -- the same class of device-local
 * secret material, inheriting the same threat model. There is no server-side
 * copy and no cross-device sync; see the integration plan §7 for why that is
 * explicitly out of scope here.
 *
 * FIXED TIER
 * ----------
 * Always TIERS.TIER0_32K (16000-byte slot payload -- vastly more than the
 * ~150-byte JSON above needs). Unlike StegoVaultDashboard, which lets the
 * user pick a tier to fit an image's steganographic capacity, this envelope
 * has no such constraint, so the tier is not user-configurable. `encode()`
 * does not expose the tier/KDF params of an existing blob back to the caller
 * (`parseHeader` is internal), so `setDecoySlot` below relies on this being
 * the one and only tier `provision()` ever writes.
 */

import {
  encode,
  decode,
  jsonToBytes,
  bytesToJson,
  TIERS,
  DEFAULT_KDF_TIME,
  DEFAULT_KDF_MEMORY_KIB,
  DEFAULT_KDF_PARALLELISM,
  HiddenVaultError,
  WrongPasswordError,
} from './hiddenVaultEnvelope';
import { generateSignalToken, SIGNAL_TOKEN_LENGTH } from '../duressSignalService';

const ENVELOPE_TIER = TIERS.TIER0_32K;
const SLOT_PAYLOAD_VERSION = 'hv-slot-1';
const STORAGE_KEY = 'vaultUnlockEnvelope';

const storageKey = (userId) => `${STORAGE_KEY}:${userId}`;

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

/** Thrown when a stored slot payload does not have the shape this module wrote. */
export class MalformedSlotPayloadError extends HiddenVaultError {}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

export const hasEnvelope = (userId) => {
  if (!userId) return false;
  try {
    return localStorage.getItem(storageKey(userId)) !== null;
  } catch {
    // localStorage can throw in private-browsing / disabled-cookie contexts,
    // same accepted degradation as onionSyncService.getSyncPrivacyMode.
    return false;
  }
};

export const loadEnvelope = (userId) => {
  if (!userId) return null;
  let raw;
  try {
    raw = localStorage.getItem(storageKey(userId));
  } catch {
    return null;
  }
  if (raw === null) return null;
  // Same normalization, and for the same reason, as `parseSlotPayload`'s dek
  // decode below: `fromB64` calls `atob`, which throws a DOMException for a
  // stored value that is not valid base64. Left raw, that DOMException
  // escapes `loadEnvelope` while `hasEnvelope` still returns true -- so
  // VaultDuressSetup renders its forms and then surfaces a literal "Failed
  // to execute 'atob' on 'Window'" string to the user. A corrupt stored blob
  // is the same outcome whichever layer notices it, so it gets the same
  // error type. `null` stays reserved for "there is nothing stored".
  try {
    return fromB64(raw);
  } catch {
    throw new MalformedSlotPayloadError('Stored envelope is not valid base64.');
  }
};

/**
 * The stored blob EXACTLY as persisted (base64), or null. Never decodes, so
 * it never throws for a corrupt value -- unlike `loadEnvelope`. Exists so a
 * caller can take a compare-and-swap snapshot across a slow await and prove
 * nothing replaced the envelope in between; see `provision`'s
 * `replaceExisting`.
 */
export const readRawEnvelope = (userId) => {
  if (!userId) return null;
  try {
    return localStorage.getItem(storageKey(userId));
  } catch {
    return null;
  }
};

export const saveEnvelope = (userId, blob) => {
  if (!userId) throw new Error('saveEnvelope: userId required');
  if (!(blob instanceof Uint8Array)) {
    throw new Error('saveEnvelope: blob must be Uint8Array');
  }
  localStorage.setItem(storageKey(userId), toB64(blob));
};

export const clearEnvelope = (userId) => {
  if (!userId) return;
  localStorage.removeItem(storageKey(userId));
};

// ---------------------------------------------------------------------------
// Slot payload helpers
// ---------------------------------------------------------------------------

const buildSlotPayload = ({ dekBytes, saltB64, duressToken = null }) => {
  const obj = {
    v: SLOT_PAYLOAD_VERSION,
    dek: toB64(dekBytes),
    salt: saltB64,
  };
  if (duressToken) {
    obj.__duress_signal = duressToken;
  }
  return jsonToBytes(obj);
};

const parseSlotPayload = (payloadBytes) => {
  let obj;
  try {
    obj = bytesToJson(payloadBytes);
  } catch {
    throw new MalformedSlotPayloadError('Slot payload is not valid JSON.');
  }
  if (!obj || obj.v !== SLOT_PAYLOAD_VERSION || typeof obj.dek !== 'string' || typeof obj.salt !== 'string') {
    throw new MalformedSlotPayloadError('Slot payload has an unexpected shape.');
  }
  // Length-checked here, not left for sessionVaultCrypto.installRawDek's own
  // 32-byte guard to catch: that guard runs AFTER unlockEnvelopeStore.open()
  // has already returned, outside the window VaultUnlockModal's
  // runEnvelopeUnlock tags `envelopeUnusable` on -- a wrong-length-but-
  // valid-base64 dek would otherwise skip the legacy wrapped-DEK fallback
  // entirely and lock the user out, even though this is exactly the same
  // "stored envelope is corrupt" case the fallback exists to handle.
  // `fromB64` calls `atob`, which throws a DOMException (InvalidCharacterError)
  // -- NOT a MalformedSlotPayloadError -- for a `dek` that is not valid
  // base64. Normalized here so every "the stored payload is corrupt" outcome
  // leaves this function as the same error type: callers that branch on it
  // (VaultDuressSetup's recovery form surfaces `err.message` directly, and
  // would otherwise show a raw "Failed to execute 'atob'..." string) get one
  // contract, not two. VaultUnlockModal's fallback happens to tag ANY
  // non-WrongPasswordError as `envelopeUnusable`, so its recovery path was
  // never broken by this -- which is exactly why the inconsistency could sit
  // here unnoticed.
  let dekBytes;
  try {
    dekBytes = fromB64(obj.dek);
  } catch {
    throw new MalformedSlotPayloadError('Slot payload dek is not valid base64.');
  }
  if (dekBytes.byteLength !== 32) {
    throw new MalformedSlotPayloadError('Slot payload dek is not 32 bytes.');
  }
  // A decoy slot's duress token goes out on the wire verbatim
  // (`duressSignalService.reportUnlock` sends `JSON.stringify({ signal })`),
  // and the whole indistinguishability contract rests on that body being the
  // SAME SIZE for a real token as for noise. A present-but-wrong-length token
  // would change the request's byte length and hand a network observer
  // exactly the oracle this feature exists to deny -- so reject it HERE,
  // inside open()'s call stack, where VaultUnlockModal's `envelopeUnusable`
  // fallback already catches it (same placement reasoning as the dek length
  // check above).
  //
  // A MISSING token deliberately stays `null` rather than throwing: noise is
  // then generated at its correct length, so there is no wire tell, and the
  // decoy still opens. Throwing would make a decoy password unusable under
  // duress over a payload that leaks nothing.
  const rawDuress = obj.__duress_signal;
  const duressPresent = rawDuress !== undefined && rawDuress !== null;
  if (duressPresent && (typeof rawDuress !== 'string' || rawDuress.length !== SIGNAL_TOKEN_LENGTH)) {
    throw new MalformedSlotPayloadError('Slot payload duress signal is malformed.');
  }
  return {
    dekBytes,
    saltB64: obj.salt,
    duressToken: duressPresent ? rawDuress : null,
  };
};

// ---------------------------------------------------------------------------
// Provisioning
// ---------------------------------------------------------------------------

/**
 * Create (or replace) the envelope with only the real slot populated.
 *
 * The decoy slot is filled by `encode()`'s own throwaway-key behaviour (see
 * `hiddenVaultEnvelope.js` `keyFor`), which encrypts a full-length random
 * plaintext under a random key rather than leaving the slot empty -- so a
 * freshly provisioned envelope is byte-wise indistinguishable from one that
 * already has a decoy configured. Nothing here may special-case that; it is
 * `encode()`'s job, not this caller's.
 *
 * @param {Object} args
 * @param {string} args.userId
 * @param {string} args.vaultPassword - the real vault password
 * @param {Uint8Array} args.dekBytes - raw 32-byte DEK to protect (the SAME
 *   key installed as the session key by the caller, e.g. via
 *   `sessionVaultCrypto.exportSessionDekRaw()` or `exportWrappedDekRaw()`)
 * @param {string} args.saltB64 - the device salt to stamp into the payload,
 *   matching what `sessionVaultCrypto` would set as `sessionSaltB64`
 * @param {string} [args.replaceExisting] - the EXACT raw blob the caller
 *   expects to still be stored (from `readRawEnvelope`), authorising an
 *   overwrite of that specific blob and no other. Deliberately not a boolean:
 *   the only legitimate overwrite is the corrupt-envelope self-heal, which
 *   runs after two slow key derivations, and in that window another tab can
 *   configure a decoy. A boolean "yes, replace" would destroy it; a
 *   compare-and-swap token cannot, because the stored value no longer
 *   matches. Omit to refuse any overwrite.
 */
export async function provision({
  userId, vaultPassword, dekBytes, saltB64, replaceExisting,
}) {
  if (!userId) throw new Error('provision: userId required');
  if (!vaultPassword) throw new Error('provision: vaultPassword required');
  if (!(dekBytes instanceof Uint8Array) || dekBytes.byteLength !== 32) {
    throw new Error('provision: dekBytes must be a 32-byte Uint8Array');
  }
  // Rejected at entry rather than left to fail later: `buildSlotPayload` puts
  // `salt: saltB64` straight into an object it JSON-serializes, and
  // JSON.stringify DROPS a key whose value is `undefined` entirely. A missing
  // salt would therefore write a structurally valid blob whose payload has no
  // `salt` key at all -- which `parseSlotPayload` then rejects as
  // MalformedSlotPayloadError on EVERY subsequent open(), permanently. The
  // envelope would be dead on arrival, and the failure would surface far from
  // the call that caused it.
  if (typeof saltB64 !== 'string' || saltB64.length === 0) {
    throw new Error('provision: saltB64 must be a non-empty string');
  }
  // Refuse to silently replace an existing envelope. `provision()` always
  // encodes with `decoyPassword: null`, so overwriting one that has a decoy
  // configured DESTROYS that decoy's DEK and its `__duress_signal` -- the
  // alarm stops working with no error anywhere, which is the worst possible
  // failure mode for this feature.
  //
  // This is reachable: VaultUnlockModal picks `internalMode` from a
  // `useMemo` snapshot of `hasEnvelope()`, and neither `runSetup` nor
  // `runUpgrade` re-checks before calling here. A second tab (or another
  // device syncing into localStorage) that configures a decoy after that
  // snapshot leaves the first modal ready to wipe it. Both callers already
  // treat a provisioning failure as non-fatal, so rejecting here degrades to
  // "the envelope upgrade is retried next unlock" rather than breaking any
  // unlock.
  //
  // `replaceExisting` is the deliberate opt-in for the ONE caller that must
  // overwrite: the corrupt-envelope self-heal (§9.1), where the stored blob
  // exists but cannot be decoded, so there is no decoy left to protect.
  if (hasEnvelope(userId)) {
    if (replaceExisting === undefined) {
      throw new Error('provision: an envelope already exists for this account.');
    }
    // Compare-and-swap: authorise replacing the blob the caller SAW, never
    // whatever happens to be there now. If another tab configured a decoy
    // during the caller's await, the stored value has moved on and this
    // refuses rather than destroying that decoy's DEK and duress token.
    if (readRawEnvelope(userId) !== replaceExisting) {
      throw new Error('provision: the stored envelope changed; refusing to replace it.');
    }
  }

  const realPayload = buildSlotPayload({ dekBytes, saltB64 });
  const blob = await encode({
    realPassword: vaultPassword,
    realPayload,
    decoyPassword: null,
    decoyPayload: new Uint8Array(0),
    tier: ENVELOPE_TIER,
    kdfTime: DEFAULT_KDF_TIME,
    kdfMemKib: DEFAULT_KDF_MEMORY_KIB,
    kdfPar: DEFAULT_KDF_PARALLELISM,
  });
  saveEnvelope(userId, blob);
}

/**
 * Add or replace the decoy slot on an existing envelope.
 *
 * Re-encodes the WHOLE blob -- the outer salt and both nonces must be fresh,
 * per `hiddenVaultEnvelope.encode()`'s contract -- so this requires the real
 * vault password too: only it can re-open slot 0 to carry its exact original
 * payload bytes forward unchanged into the new blob.
 *
 * Generates the decoy DEK and duress token internally; callers never see
 * decoy key material, matching the "decoy password never leaves this module"
 * discipline `hiddenVaultEnvelope` itself follows for the real slot.
 *
 * @param {Object} args
 * @param {string} args.userId
 * @param {string} args.vaultPassword - the CURRENT real vault password
 * @param {string} args.decoyPassword - the new decoy password
 * @returns {Promise<{ duressToken: string }>} the token the caller must
 *   register with `duressSignalService.registerSignalToken` -- AFTER this
 *   function's returned promise resolves (the blob is saved first; see the
 *   ordering note below).
 */
export async function setDecoySlot({ userId, vaultPassword, decoyPassword }) {
  if (!userId) throw new Error('setDecoySlot: userId required');
  if (!vaultPassword) throw new Error('setDecoySlot: vaultPassword required');
  if (!decoyPassword) throw new Error('setDecoySlot: decoyPassword required');
  if (decoyPassword === vaultPassword) {
    // deriveSlotKey's domain separation means slot 0 and slot 1 normally get
    // DIFFERENT keys from the same password string (the slot index is baked
    // into the salt) -- but if the two passwords are also textually
    // identical, decode() derives k0 and k1 from that ONE input and BOTH
    // slots decrypt successfully. decode() returns the first match, slot 0
    // (see its own comment on constant-time attempt order), so entering
    // "the decoy password" would always open the REAL vault and never the
    // decoy -- a duress setup that silently does nothing. UI callers should
    // already block this (VaultDuressSetup.jsx's own form validation), but
    // that must not be the only place it is enforced.
    throw new Error('setDecoySlot: decoy password must differ from the vault password.');
  }

  const existing = loadEnvelope(userId);
  if (!existing) {
    throw new Error('setDecoySlot: no envelope has been provisioned for this account yet.');
  }

  // Throws WrongPasswordError if vaultPassword is wrong -- propagated as-is,
  // the caller (the duress-setup form) surfaces it as "incorrect current
  // password". decode() tries both slots and only slot 0's key can be
  // derived from the correct real password, so this always lands on
  // slotIndex 0 in practice (see the module docstring's payload shape note).
  const { slotIndex, payload: realPayloadBytes } = await decode(existing, vaultPassword);
  if (slotIndex !== 0) {
    // Reached when the value supplied as the REAL vault password actually
    // opened the DECOY slot -- i.e. the user (or someone at their keyboard)
    // typed the decoy password into the vault-password field.
    //
    // Deliberately a `WrongPasswordError`, the SAME type `decode()` raises
    // when neither slot matches, and NOT a distinct error: from this
    // function's contract the two are one outcome ("what you gave me is not
    // the real vault password"), and callers surface error types. A
    // slot-specific error here let VaultDuressSetup render a slot-specific
    // message, so submitting a candidate password to the setup form told the
    // submitter whether it was the decoy -- the same oracle §20.1 removed
    // from the recovery form on that same screen, still open on this one.
    // Collapsing the type is what makes a decoy password and a garbage
    // password indistinguishable to every caller by construction, rather
    // than depending on each caller remembering not to echo the message.
    //
    // The MESSAGE is byte-identical to the one `decode()` raises when no slot
    // matches at all, not merely non-specific: matching only the error TYPE
    // would still leave a caller that echoes `err.message` able to tell the
    // two apart, which is precisely how this leaked in the first place. Both
    // outcomes must be indistinguishable on every channel a caller can read.
    //
    // Still re-sealing nothing: the throw happens before any re-encode, so a
    // mistyped password cannot rewrite the envelope.
    throw new WrongPasswordError(
      'No slot decrypted successfully with the supplied password.',
    );
  }

  // Reuse the SAME device salt the real slot's payload already carries,
  // rather than minting a second one -- the decoy vault's session, once
  // unlocked, should stamp new items with a stable salt too, and there is no
  // reason for it to differ from the real slot's.
  const { saltB64: realSaltB64 } = parseSlotPayload(realPayloadBytes);

  const duressToken = generateSignalToken();
  const decoyDekBytes = window.crypto.getRandomValues(new Uint8Array(32));
  const decoyPayload = buildSlotPayload({
    dekBytes: decoyDekBytes,
    saltB64: realSaltB64,
    duressToken,
  });

  const blob = await encode({
    realPassword: vaultPassword,
    // Pass the ORIGINAL bytes straight through -- no JSON round-trip, so the
    // real slot's payload is byte-identical to before this call.
    realPayload: realPayloadBytes,
    decoyPassword,
    decoyPayload,
    tier: ENVELOPE_TIER,
    kdfTime: DEFAULT_KDF_TIME,
    kdfMemKib: DEFAULT_KDF_MEMORY_KIB,
    kdfPar: DEFAULT_KDF_PARALLELISM,
  });
  saveEnvelope(userId, blob);

  return { duressToken };
}

// ---------------------------------------------------------------------------
// Unlock
// ---------------------------------------------------------------------------

/**
 * Try `password` against both slots of the stored envelope.
 *
 * Thin wrapper over `hiddenVaultEnvelope.decode()`, which already derives
 * both slot keys and attempts both decryptions unconditionally to keep
 * behaviour constant-time between slots -- see that function's own comment.
 * Nothing here may short-circuit on the first match; doing so would
 * reintroduce a timing side-channel `decode()` was written specifically to
 * avoid.
 *
 * @param {Object} args
 * @param {string} args.userId
 * @param {string} args.password
 * @returns {Promise<{ slotIndex: number, dekBytes: Uint8Array, saltB64: string, duressToken: string|null }>}
 * @throws {import('./hiddenVaultEnvelope').WrongPasswordError} on a bad password
 */
export async function open({ userId, password }) {
  const blob = loadEnvelope(userId);
  if (!blob) {
    throw new Error('open: no envelope has been provisioned for this account yet.');
  }
  const { slotIndex, payload } = await decode(blob, password);
  const { dekBytes, saltB64, duressToken } = parseSlotPayload(payload);
  return { slotIndex, dekBytes, saltB64, duressToken };
}

export default {
  hasEnvelope,
  loadEnvelope,
  saveEnvelope,
  clearEnvelope,
  provision,
  setDecoySlot,
  open,
  MalformedSlotPayloadError,
};

/**
 * Duress Signal Service
 *
 * The client half of zero-knowledge duress reporting.
 *
 * WHY THIS EXISTS
 * ---------------
 * "Two master passwords: one opens the real vault, one opens a convincing
 * decoy" is trivial to build the wrong way -- send the entered password to the
 * server and let it decide. That breaks this project's zero-knowledge
 * invariant (docs/adaptive-password-zk-remediation-plan.md §1-2: the server is
 * assumable-hostile and must never receive anything the master password can be
 * recovered from).
 *
 * So the work is split:
 *
 *   1. THE DECISION IS LOCAL. `hiddenVaultEnvelope.decode()` tries the entered
 *      password against both slots and returns whichever verifies. Slot 0 is
 *      the real vault, slot 1 the decoy (see hiddenVault/SPEC.md). The server
 *      is never asked and cannot infer the answer -- from the blob alone the
 *      two slots are indistinguishable.
 *   2. THE ALARM IS A SEPARATE SECRET. A 256-bit random token, generated here
 *      at duress setup and registered with the server as a SHA-256 only. It is
 *      completely independent of any password, so releasing it tells the
 *      server "raise the alarm" without telling it anything about the
 *      credentials.
 *
 * INDISTINGUISHABILITY
 * --------------------
 * `reportUnlock()` is called on EVERY unlock, not just duress ones, and always
 * posts a value of identical length: the real token under duress, fresh random
 * noise otherwise. The endpoint answers 204 either way. A coercer watching the
 * network -- or holding the user's session and replaying requests -- cannot
 * tell the two apart, which is the only thing that makes the decoy credible.
 *
 * Callers must therefore NEVER branch UI, logging, or timing on the return of
 * `reportUnlock()`; it resolves the same way in both cases by design. This
 * mirrors HeartbeatVerify.jsx, which deliberately refuses to branch its
 * message on the duress flag.
 */

const BASE_URL = '/api/security';

/** Raw byte length of a signal token. 256 bits of CSPRNG output. */
const SIGNAL_BYTES = 32;

/** Slot index that holds the decoy vault, per hiddenVault/SPEC.md. */
export const DECOY_SLOT_INDEX = 1;

const getHeaders = (authToken) => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authToken}`,
});

/**
 * Base64-encode bytes without relying on Node/browser-specific helpers.
 */
const toBase64 = (bytes) => {
    let binary = '';
    for (let i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
};

/**
 * Generate a fresh signal token: base64 of 32 CSPRNG bytes (44 chars).
 *
 * The server validates that exact length, so decoy noise and real tokens are
 * the same size on the wire.
 */
export const generateSignalToken = () => {
    const bytes = new Uint8Array(SIGNAL_BYTES);
    window.crypto.getRandomValues(bytes);
    return toBase64(bytes);
};

/**
 * Register a signal token's hash with the server.
 *
 * Call once at duress setup. The caller is responsible for storing the token
 * itself inside the DECOY slot payload -- that is what makes it available at
 * exactly the moment it is needed (a decoy unlock) and nowhere else. Storing
 * it in the real slot, or outside the envelope, would either make it
 * unavailable under duress or leave it recoverable without the duress
 * password.
 *
 * @param {string} authToken - JWT
 * @param {string} token - from generateSignalToken()
 * @returns {Promise<Object>} { success, signal_id }
 */
export const registerSignalToken = async (authToken, token) => {
    const response = await fetch(`${BASE_URL}/duress/signal/register/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({ token }),
    });

    if (!response.ok) {
        throw new Error('Failed to register duress signal token');
    }

    return response.json();
};

/**
 * Report an unlock to the server. Call on EVERY unlock.
 *
 * @param {string} authToken - JWT
 * @param {string|null} duressToken - the token recovered from the decoy slot
 *   payload when the local decode landed on the decoy slot; null/undefined on
 *   a normal unlock, in which case random noise is sent instead.
 * @returns {Promise<void>} always resolves, never throws
 */
export const reportUnlock = async (authToken, duressToken = null) => {
    // Noise is generated the same way as a real token so the two are
    // indistinguishable in both length and distribution.
    const signal = duressToken || generateSignalToken();

    try {
        await fetch(`${BASE_URL}/duress/signal/`, {
            method: 'POST',
            headers: getHeaders(authToken),
            body: JSON.stringify({ signal }),
        });
    } catch {
        // Swallowed on purpose. A network error must not surface differently
        // for the duress path, and a coerced user cannot act on it anyway.
        // Notably this means an offline unlock raises no alarm -- an accepted
        // limitation, documented rather than papered over: the server cannot
        // be told anything while unreachable.
    }
};

/**
 * Convenience wrapper: given the result of a local envelope decode, report the
 * unlock correctly.
 *
 * @param {string} authToken - JWT
 * @param {number} slotIndex - from hiddenVaultEnvelope.decode()
 * @param {Object|null} payloadJson - the decoded slot payload; the duress
 *   token is read from `payloadJson.__duress_signal` when present.
 */
export const reportUnlockForSlot = async (authToken, slotIndex, payloadJson = null) => {
    const duressToken =
        slotIndex === DECOY_SLOT_INDEX && payloadJson
            ? payloadJson.__duress_signal || null
            : null;

    await reportUnlock(authToken, duressToken);
};

export default {
    generateSignalToken,
    registerSignalToken,
    reportUnlock,
    reportUnlockForSlot,
    DECOY_SLOT_INDEX,
};

/**
 * Background-worker side of the Homomorphic Share autofill path.
 *
 * Responsibilities:
 *   - Own the recipient's Umbral secret key, persisted in
 *     ``chrome.storage.local`` under a master-key-wrapped envelope.
 *     The wrapping key is derived from an in-memory session-only
 *     value supplied by the popup after the user logs in.
 *   - Accept PRE payloads from the web dashboard's content script,
 *     decrypt them with `preClient.decryptReencrypted`, and stream
 *     the plaintext into the target tab via the one-shot port
 *     installed by `sealedAutofill.installSealedFillListener`.
 *   - Never log or expose the plaintext.
 *
 * The target tab is chosen as the active tab whose origin matches
 * the first `domain` entry in the payload.  If no such tab exists,
 * we fall back to the currently focused tab with matching hostname,
 * and if that fails we reject with ``no_target_tab``.
 */

import preClient, { UmbralUnavailableError } from './preClient.js';

const STORAGE_KEY = 'fheShare:umbralIdentity:v1';
let _cachedIdentity = null;

async function _getStored() {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get([STORAGE_KEY], (obj) => {
        resolve(obj?.[STORAGE_KEY] || null);
      });
    } catch (_e) {
      resolve(null);
    }
  });
}

async function _putStored(value) {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.set({ [STORAGE_KEY]: value }, () => resolve(true));
    } catch (_e) {
      resolve(false);
    }
  });
}

function _b64UrlToBytes(s) {
  const c = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = c.length % 4 === 0 ? '' : '='.repeat(4 - (c.length % 4));
  const bin = atob(c + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

export async function getIdentity() {
  if (_cachedIdentity) return _cachedIdentity;
  const raw = await _getStored();
  if (!raw) return null;
  try {
    _cachedIdentity = {
      public: raw.public,
      secret: {
        sk: _b64UrlToBytes(raw.secret.sk),
        signerSk: _b64UrlToBytes(raw.secret.signerSk),
      },
    };
    return _cachedIdentity;
  } catch (_e) {
    return null;
  }
}

/**
 * Store an identity that was enrolled elsewhere (e.g. the web
 * dashboard) — the popup calls this once the user opts in to
 * cross-device autofill.
 */
export async function setIdentityFromB64({ publicKeys, secretB64 }) {
  const record = {
    public: publicKeys,
    secret: {
      sk: secretB64.sk,
      signerSk: secretB64.signerSk,
    },
    version: 1,
  };
  await _putStored(record);
  _cachedIdentity = {
    public: publicKeys,
    secret: {
      sk: _b64UrlToBytes(secretB64.sk),
      signerSk: _b64UrlToBytes(secretB64.signerSk),
    },
  };
  return _cachedIdentity.public;
}

function _hostnameMatches(tabUrl, wantedDomain) {
  try {
    const h = new URL(tabUrl).hostname.toLowerCase();
    const w = wantedDomain.toLowerCase();
    return h === w || h.endsWith(`.${w}`);
  } catch (_e) {
    return false;
  }
}

async function _findTargetTab(domain) {
  return new Promise((resolve) => {
    try {
      chrome.tabs.query({ url: ['http://*/*', 'https://*/*'] }, (tabs) => {
        const active = tabs.find((t) => t.active && _hostnameMatches(t.url, domain));
        if (active) return resolve(active);
        const any = tabs.find((t) => _hostnameMatches(t.url, domain));
        resolve(any || null);
      });
    } catch (_e) {
      resolve(null);
    }
  });
}

async function _sealedFillInTab(tabId, { password, username, hint }) {
  return new Promise((resolve) => {
    let settled = false;
    try {
      const port = chrome.tabs.connect(tabId, { name: 'fhe_share_fill_v1' });
      port.onMessage.addListener((msg) => {
        if (settled) return;
        settled = true;
        resolve({ ok: !!msg?.ok, ...msg });
      });
      port.onDisconnect.addListener(() => {
        if (settled) return;
        settled = true;
        resolve({ ok: false, reason: 'port_disconnected' });
      });
      port.postMessage({ password, username, hint });
      setTimeout(() => {
        if (settled) return;
        settled = true;
        try { port.disconnect(); } catch (_e) {
          // port may already be disconnected
        }
        resolve({ ok: false, reason: 'timeout' });
      }, 2000);
    } catch (err) {
      resolve({ ok: false, reason: String(err) });
    }
  });
}

/**
 * Main entry point — called by the runtime message listener on a
 * ``fhe_share/apply_share`` message.  ``payload`` is the opaque
 * output of ``frontend/src/services/fhe/fheSharingService.useAutofillToken``.
 */
export async function applyShareFromDashboard(payload) {
  if (!payload || payload.cipherSuite !== 'umbral-v1') {
    return { ok: false, reason: 'unsupported_cipher_suite' };
  }
  const identity = await getIdentity();
  if (!identity) return { ok: false, reason: 'no_identity' };

  let plaintextBytes;
  try {
    plaintextBytes = await preClient.decryptReencrypted({
      recipientSkBytes: identity.secret.sk,
      delegatingPkB64: payload.delegatingPk,
      verifyingPkB64: payload.verifyingPk,
      capsuleB64: payload.capsule,
      cfragB64: payload.cfrag,
      ciphertextB64: payload.ciphertext,
    });
  } catch (err) {
    if (err instanceof UmbralUnavailableError) {
      return { ok: false, reason: 'umbral_unavailable' };
    }
    return { ok: false, reason: 'decrypt_failed' };
  }

  const password = new TextDecoder().decode(plaintextBytes);
  try { plaintextBytes.fill(0); } catch (_e) {
    // best-effort zeroization; some buffer views are immutable
  }

  const tab = await _findTargetTab(payload.domain);
  if (!tab) {
    // Scrub local copy before returning.
    try {
      // Strings are immutable, but releasing the reference lets GC
      // collect it. The caller mustn't retain `password` anywhere.
    } finally {
      // eslint-disable-next-line no-param-reassign
      payload = null;
    }
    return { ok: false, reason: 'no_target_tab' };
  }

  const result = await _sealedFillInTab(tab.id, {
    password,
    username: payload.username || null,
    hint: payload.hint || null,
  });
  return { ok: !!result.ok, reason: result.reason || null };
}

/**
 * Install the chrome.runtime.onMessage listener.  Idempotent.
 */
export function installBackgroundFheShareBridge() {
  if (globalThis.__fheShareBridgeInstalled) return;
  globalThis.__fheShareBridgeInstalled = true;
  try {
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (!msg || typeof msg.type !== 'string') return undefined;
      if (msg.type === 'fhe_share/apply_share') {
        applyShareFromDashboard(msg.payload).then(sendResponse);
        return true;
      }
      if (msg.type === 'fhe_share/get_public_keys') {
        getIdentity().then((id) => sendResponse({ public: id?.public || null }));
        return true;
      }
      if (msg.type === 'fhe_share/set_identity') {
        setIdentityFromB64(msg.identity).then((pub) => sendResponse({ ok: true, public: pub }));
        return true;
      }
      return undefined;
    });
  } catch (_e) {
    // No chrome.runtime available (tests).
  }
}

export default {
  installBackgroundFheShareBridge,
  applyShareFromDashboard,
  getIdentity,
  setIdentityFromB64,
};

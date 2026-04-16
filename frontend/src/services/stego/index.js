/**
 * High-level facade combining ``hiddenVaultEnvelope`` with ``pngLsb``.
 *
 * Components should prefer these helpers over the lower-level modules:
 *
 *   * ``embedVault`` - turn two vaults + two passwords + cover image
 *     into a single PNG containing both encrypted slots.
 *   * ``extractVault`` - given a stego PNG and one password, return
 *     the slot's JSON payload (we never reveal which slot was which
 *     semantically; the caller decides).
 *   * ``computeCoverHash`` - SHA-256 of the raw cover bytes; useful to
 *     later detect upstream JPEG re-encoding.
 */

import {
  TIERS,
  decode as decodeBlob,
  encode as encodeBlob,
  jsonToBytes,
  bytesToJson,
  tierBytes,
} from '../hiddenVault/hiddenVaultEnvelope';
import {
  embedBlobInPng,
  extractBlobFromPng,
  pngCapacityBytes,
} from './pngLsb';

export { TIERS };

export async function computeCoverHash(coverBytes) {
  const buf = await window.crypto.subtle.digest('SHA-256', coverBytes);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function pickTier(coverCapacityBytes, tierPriority = [TIERS.TIER0_32K, TIERS.TIER1_128K, TIERS.TIER2_1M]) {
  for (const tier of tierPriority) {
    if (coverCapacityBytes >= tierBytes(tier)) return tier;
  }
  return null;
}

export async function embedVault({
  coverBytes,
  realPassword,
  realVault,
  decoyPassword = null,
  decoyVault = null,
  tier: explicitTier = null,
  stegoKey = null,
}) {
  if (!realPassword) throw new Error('realPassword is required');
  if (!realVault) throw new Error('realVault is required');

  const realPayload = jsonToBytes(realVault);
  const decoyPayload = decoyVault ? jsonToBytes(decoyVault) : null;

  let tier = explicitTier;
  if (tier == null) {
    const cap = await pngCapacityBytes(coverBytes);
    tier = pickTier(cap);
    if (tier == null) {
      throw new Error(
        `Cover image too small for the smallest hidden-vault tier (${tierBytes(TIERS.TIER0_32K)} bytes required).`,
      );
    }
  }

  const blob = await encodeBlob({
    realPassword,
    realPayload,
    decoyPassword,
    decoyPayload,
    tier,
  });

  // Default stego key matches the backend constant so a blob embedded
  // client-side can be extracted server-side (and vice versa) without
  // out-of-band metadata. Callers wanting a user-scoped permutation
  // can pass their own ``stegoKey`` and persist it alongside the vault.
  const effectiveKey =
    stegoKey || new TextEncoder().encode('default-png-lsb-key');
  const stegoPng = await embedBlobInPng(coverBytes, blob, { stegoKey: effectiveKey });
  return { stegoPng, tier, blobBytes: blob.length };
}

export async function extractVault({ stegoBytes, password, stegoKey = null }) {
  // The effective key must match the one used at embed. We derive
  // the same "stego:SHA256(first 24 bytes of blob)" scheme lazily by
  // requiring the caller to try both variants (explicit key, then
  // default). In practice, components call this with an explicit
  // ``stegoKey`` loaded from the server-side ``StegoVault`` record.
  const effectiveKey =
    stegoKey || new TextEncoder().encode('default-png-lsb-key');
  const blob = await extractBlobFromPng(stegoBytes, { stegoKey: effectiveKey });
  const { slotIndex, payload } = await decodeBlob(blob, password);
  return { slotIndex, payload, json: bytesToJson(payload) };
}

export async function capacityReport(coverBytes) {
  const cap = await pngCapacityBytes(coverBytes);
  return {
    capacityBytes: cap,
    fitsTier0: cap >= tierBytes(TIERS.TIER0_32K),
    fitsTier1: cap >= tierBytes(TIERS.TIER1_128K),
    fitsTier2: cap >= tierBytes(TIERS.TIER2_1M),
  };
}

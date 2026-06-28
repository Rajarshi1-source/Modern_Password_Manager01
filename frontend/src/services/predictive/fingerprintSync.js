/**
 * Fingerprint Sync (Zero-Knowledge)
 * =================================
 *
 * Bridges the decrypted vault and the predictive-expiration fingerprint
 * ingest endpoint. For each password item it computes the structural
 * fingerprint in the browser (via clientPatternEngine) and derives only a
 * *coarse* domain class — never the exact site — then uploads the batch.
 *
 * Nothing reversible leaves the device: no password, no dictionary word,
 * no exact domain.
 */

import { computeFingerprint } from './clientPatternEngine';
import { submitFingerprints } from '../predictiveExpirationService';

// Coarse domain classes accepted by the server. Keep in sync with
// DOMAIN_CLASSES in predictive_expiration_serializers.py.
const DOMAIN_KEYWORDS = {
  finance: ['bank', 'paypal', 'chase', 'wellsfargo', 'finance', 'crypto', 'coinbase', 'wallet', 'capitalone', 'amex', 'visa', 'mastercard'],
  healthcare: ['health', 'clinic', 'hospital', 'medical', 'pharma', 'doctor', 'patient', 'kaiser', 'cigna', 'aetna'],
  government: ['gov', 'irs', 'dmv', 'usps', 'state', 'gob', 'gouv'],
  education: ['edu', 'university', 'college', 'school', 'campus', 'coursera', 'udemy'],
  email: ['mail', 'gmail', 'outlook', 'proton', 'yahoo', 'icloud', 'fastmail'],
  social: ['facebook', 'instagram', 'twitter', 'x.com', 'tiktok', 'linkedin', 'reddit', 'discord', 'snapchat'],
  shopping: ['amazon', 'ebay', 'shop', 'store', 'etsy', 'walmart', 'target', 'aliexpress'],
  technology: ['github', 'gitlab', 'aws', 'azure', 'google', 'microsoft', 'cloud', 'api', 'dev', 'heroku', 'digitalocean'],
  retail: ['retail', 'market'],
};

// Server-side batch cap (FingerprintIngestSerializer.MAX_FINGERPRINT_BATCH).
// Uploads are chunked to this size so large vaults don't trip the 400.
const MAX_FINGERPRINT_BATCH = 500;

/**
 * Whether a coarse-class keyword matches a host on a label/suffix boundary
 * rather than as an arbitrary substring. A dotted keyword (e.g. "x.com")
 * must be the host or one of its suffixes; a bare token (e.g. "bank") must
 * appear within a host label — so "annex.com" no longer matches "x.com".
 */
function hostMatchesKeyword(host, kw) {
  if (kw.includes('.')) {
    return host === kw || host.endsWith(`.${kw}`);
  }
  return host.split('.').some((label) => label.includes(kw));
}

/**
 * Derive a coarse domain class from a URL/host. Returns 'other' when no
 * category matches and '' when there is nothing to classify.
 */
export function deriveDomainClass(url) {
  if (!url) return '';
  let host = String(url).toLowerCase();
  try {
    // Tolerate bare hosts as well as full URLs.
    host = new URL(host.includes('://') ? host : `https://${host}`).hostname;
  } catch {
    // Fall back to the raw string if it isn't a parseable URL.
  }
  for (const [cls, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
    if (keywords.some((kw) => hostMatchesKeyword(host, kw))) return cls;
  }
  return 'other';
}

/** Whole-day age of a credential from its creation timestamp. */
export function ageDays(createdAt) {
  if (!createdAt) return 0;
  const created = new Date(createdAt).getTime();
  if (Number.isNaN(created)) return 0;
  const diff = Date.now() - created;
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

/**
 * Build a single fingerprint upload payload from a decrypted vault item.
 * Returns null for non-password items or items without a password.
 */
export async function buildFingerprintPayload(item) {
  if (!item || item.item_type !== 'password') return null;
  const password = item.data?.password;
  if (!password) return null;

  const fingerprint = await computeFingerprint(password);
  // Age is measured from the last password rotation when known, falling back to
  // the item's creation date. This keeps a freshly-rotated password scored as
  // young on *every* sync — not just the one right after rotation. Only use the
  // rotation timestamp when it parses to a real date; a malformed value would
  // otherwise make ageDays() return 0 and score an old password as fresh.
  const rotatedAt = item.data?.passwordChangedAt;
  const ageBasis =
    rotatedAt && !Number.isNaN(new Date(rotatedAt).getTime())
      ? rotatedAt
      : item.created_at;
  return {
    credential_id: String(item.item_id ?? item.id),
    ...fingerprint,
    age_days: ageDays(ageBasis),
    domain_class: deriveDomainClass(item.data?.url || item.data?.website),
  };
}

/**
 * Compute fingerprints for a list of decrypted vault items and upload them.
 *
 * @param {Array<Object>} decryptedItems - vault items with a decrypted `data`
 * @returns {Promise<Object|null>} the ingest response, or null if nothing to send
 */
export async function syncVaultFingerprints(decryptedItems) {
  if (!Array.isArray(decryptedItems) || decryptedItems.length === 0) return null;

  const payloads = [];
  for (const item of decryptedItems) {
    const fp = await buildFingerprintPayload(item);
    if (fp) payloads.push(fp);
  }

  if (payloads.length === 0) return null;

  // Chunk to the server's batch cap so large vaults don't get rejected.
  const results = [];
  for (let i = 0; i < payloads.length; i += MAX_FINGERPRINT_BATCH) {
    results.push(
      await submitFingerprints(payloads.slice(i, i + MAX_FINGERPRINT_BATCH))
    );
  }

  return {
    processed: results.reduce((sum, r) => sum + (r?.processed ?? 0), 0),
    rules: results.flatMap((r) => r?.rules ?? []),
  };
}

export default {
  deriveDomainClass,
  ageDays,
  buildFingerprintPayload,
  syncVaultFingerprints,
};

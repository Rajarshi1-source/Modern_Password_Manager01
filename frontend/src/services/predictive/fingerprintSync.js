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
    if (keywords.some((kw) => host.includes(kw))) return cls;
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
  return {
    credential_id: String(item.item_id ?? item.id),
    ...fingerprint,
    age_days: ageDays(item.created_at),
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
  return submitFingerprints(payloads);
}

export default {
  deriveDomainClass,
  ageDays,
  buildFingerprintPayload,
  syncVaultFingerprints,
};

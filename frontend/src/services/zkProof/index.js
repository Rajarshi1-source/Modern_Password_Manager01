/**
 * Zero-Knowledge Proof service entry point.
 *
 * Today there is a single provider (`commitment-schnorr-v1`). A future
 * Groth16/PLONK provider implementing the same surface can register itself
 * here and the rest of the app — vault-save hooks, ZKVerificationDashboard,
 * etc. — picks it up automatically.
 */

import commitmentSchnorrProvider from './commitmentSchnorrProvider';
import zkProofApi from './zkProofApi';
import sessionsApi from './sessionsApi';

const PROVIDERS = {
  [commitmentSchnorrProvider.scheme]: commitmentSchnorrProvider,
};

export const DEFAULT_SCHEME = commitmentSchnorrProvider.scheme;

export const getProvider = (scheme = DEFAULT_SCHEME) => {
  const provider = PROVIDERS[scheme];
  if (!provider) throw new Error(`Unknown ZK scheme: ${scheme}`);
  return provider;
};

// ---------------------------------------------------------------------------
// Base64 helpers — canonical standard base64 matching the backend
// `Base64BytesField` output format.
// ---------------------------------------------------------------------------

export const toBase64 = (bytes) => {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
};

export const fromBase64 = (b64) => {
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
};

/**
 * Convenience: derive a commitment for (password, itemId) and register it
 * with the backend under the given scope. Returns the created/updated
 * `ZKCommitment` record.
 *
 * Failures bubble up so callers can decide whether to ignore (vault save is
 * still the primary write) or surface to the user.
 */
export const commitAndRegister = async ({
  password,
  itemId,
  scopeType,
  scheme = DEFAULT_SCHEME,
}) => {
  if (!password) throw new Error('commitAndRegister: password required');
  if (!itemId) throw new Error('commitAndRegister: itemId required');
  if (!scopeType) throw new Error('commitAndRegister: scopeType required');

  const provider = getProvider(scheme);
  const commitmentBytes = provider.commitFromPassword(password, itemId);
  return zkProofApi.registerCommitment({
    scope_type: scopeType,
    scope_id: String(itemId),
    commitment_b64: toBase64(commitmentBytes),
    scheme,
  });
};

export { zkProofApi, sessionsApi };

export default {
  getProvider,
  DEFAULT_SCHEME,
  commitAndRegister,
  toBase64,
  fromBase64,
  zkProofApi,
  sessionsApi,
};

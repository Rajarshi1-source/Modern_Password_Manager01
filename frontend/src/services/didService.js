/**
 * Decentralized Identity client helpers.
 *
 * Uses the already-installed `@noble/curves/ed25519` to sign presentations
 * entirely in the browser so the server never sees the user's private key.
 *
 * did:key identifiers use the Ed25519 multicodec prefix `0xed 0x01` followed
 * by base58btc (bitcoin alphabet) encoding.
 */

import axios from 'axios';
import { ed25519 } from '@noble/curves/ed25519';
import { sha256 } from '@noble/hashes/sha256';

const API_BASE =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

const B58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
const ED25519_MULTICODEC_PREFIX = new Uint8Array([0xed, 0x01]);

// ---------------------------------------------------------------------------
// Base58btc + multibase helpers (minimal, no external dep)
// ---------------------------------------------------------------------------

function concatBytes(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function bytesToBigInt(bytes) {
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  return n;
}

function bigIntToBytes(n) {
  if (n === 0n) return new Uint8Array();
  const out = [];
  while (n > 0n) {
    out.unshift(Number(n & 0xffn));
    n >>= 8n;
  }
  return new Uint8Array(out);
}

function b58encode(bytes) {
  let n = bytesToBigInt(bytes);
  let out = '';
  while (n > 0n) {
    const rem = n % 58n;
    out = B58_ALPHABET[Number(rem)] + out;
    n = n / 58n;
  }
  let leading = 0;
  for (const b of bytes) {
    if (b === 0) leading++;
    else break;
  }
  return '1'.repeat(leading) + out;
}

function b58decode(text) {
  let n = 0n;
  for (const ch of text) {
    const idx = B58_ALPHABET.indexOf(ch);
    if (idx < 0) throw new Error(`Invalid base58 character: ${ch}`);
    n = n * 58n + BigInt(idx);
  }
  const raw = bigIntToBytes(n);
  let leading = 0;
  for (const ch of text) {
    if (ch === '1') leading++;
    else break;
  }
  return concatBytes(new Uint8Array(leading), raw);
}

export function multibaseEncodeEd25519Pub(publicKeyBytes) {
  if (publicKeyBytes.length !== 32) throw new Error('Ed25519 public key must be 32 bytes');
  return 'z' + b58encode(concatBytes(ED25519_MULTICODEC_PREFIX, publicKeyBytes));
}

export function multibaseDecode(multibase) {
  if (!multibase || multibase[0] !== 'z') throw new Error('Only base58btc multibase is supported');
  const raw = b58decode(multibase.slice(1));
  if (raw[0] !== ED25519_MULTICODEC_PREFIX[0] || raw[1] !== ED25519_MULTICODEC_PREFIX[1]) {
    throw new Error('Not an Ed25519 multibase key');
  }
  return raw.slice(2);
}

// ---------------------------------------------------------------------------
// DID key generation
// ---------------------------------------------------------------------------

function toHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

function fromHex(hex) {
  if (hex.length % 2) throw new Error('odd-length hex');
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

export function generateDidKey() {
  const privateKey = ed25519.utils.randomPrivateKey();
  const publicKey = ed25519.getPublicKey(privateKey);
  const multibase = multibaseEncodeEd25519Pub(publicKey);
  const did = `did:key:${multibase}`;
  return {
    did,
    multibase,
    privateKeyHex: toHex(privateKey),
    publicKeyHex: toHex(publicKey),
  };
}

export function publicKeyFromDidKey(did) {
  if (!did.startsWith('did:key:')) throw new Error('Not a did:key');
  return multibaseDecode(did.slice('did:key:'.length));
}

// ---------------------------------------------------------------------------
// JWS (compact JWT) helpers
// ---------------------------------------------------------------------------

function b64u(bytes) {
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64uJson(obj) {
  const enc = new TextEncoder();
  const canonical = JSON.stringify(obj, Object.keys(obj).sort());
  return b64u(enc.encode(canonical));
}

function jsonCanonicalEncoding(obj) {
  return b64uJson(obj);
}

export async function signVp({ holderDid, privateKeyHex, nonce, audience, verifiableCredential = [] }) {
  const privateKey = fromHex(privateKeyHex);
  const publicKeyMultibase = multibaseEncodeEd25519Pub(ed25519.getPublicKey(privateKey));
  const kid = `${holderDid}#${publicKeyMultibase}`;
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'EdDSA', typ: 'JWT', kid };
  const payload = {
    iss: holderDid,
    iat: now,
    nbf: now,
    exp: now + 300,
    nonce,
  };
  if (audience) payload.aud = audience;
  payload.vp = {
    '@context': ['https://www.w3.org/2018/credentials/v1'],
    type: ['VerifiablePresentation'],
    holder: holderDid,
    verifiableCredential,
  };
  const signingInput = `${jsonCanonicalEncoding(header)}.${jsonCanonicalEncoding(payload)}`;
  const sig = ed25519.sign(new TextEncoder().encode(signingInput), privateKey);
  return `${signingInput}.${b64u(sig)}`;
}

// ---------------------------------------------------------------------------
// REST calls
// ---------------------------------------------------------------------------

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json',
});

class DIDService {
  async registerDid(did, publicKeyMultibase, makePrimary = true) {
    const { data } = await axios.post(
      `${API_BASE}/api/did/register/`,
      { did_string: did, public_key_multibase: publicKeyMultibase, make_primary: makePrimary },
      { headers: authHeaders() }
    );
    return data;
  }

  async listMyDids() {
    const { data } = await axios.get(`${API_BASE}/api/did/mine/`, { headers: authHeaders() });
    return data;
  }

  async resolve(did) {
    const { data } = await axios.get(
      `${API_BASE}/api/did/resolve/${encodeURIComponent(did)}/`
    );
    return data;
  }

  async listMyCredentials() {
    const { data } = await axios.get(`${API_BASE}/api/did/credentials/mine/`, {
      headers: authHeaders(),
    });
    return data;
  }

  async verifyPresentation(vpJwt, { nonce, audience } = {}) {
    const { data } = await axios.post(`${API_BASE}/api/did/presentations/verify/`, {
      vp_jwt: vpJwt,
      nonce: nonce || '',
      audience: audience || '',
    });
    return data;
  }

  async requestChallenge(did) {
    const { data } = await axios.post(`${API_BASE}/api/did/auth/challenge/`, {
      did_string: did,
    });
    return data;
  }

  async signInVerify({ did, nonce, vpJwt }) {
    const { data } = await axios.post(
      `${API_BASE}/api/did/auth/verify/`,
      { did_string: did, nonce, vp_jwt: vpJwt },
      { validateStatus: () => true }
    );
    return data;
  }
}

const didService = new DIDService();
export default didService;
export { toHex, fromHex };

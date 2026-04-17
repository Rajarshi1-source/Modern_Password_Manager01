/**
 * Tests for the browser-side didService primitives.
 *
 * These verify that our minimal base58btc + multibase implementation is
 * round-trip safe and that did:key generation produces a valid W3C-style
 * identifier whose public key we can recover.
 */

import { describe, it, expect } from 'vitest';
import { ed25519 } from '@noble/curves/ed25519';

import {
  generateDidKey,
  multibaseDecode,
  multibaseEncodeEd25519Pub,
  publicKeyFromDidKey,
  signVp,
  toHex,
  fromHex,
} from '../didService';

describe('didService / base58btc + multibase', () => {
  it('round-trips an Ed25519 public key through multibase', () => {
    const priv = ed25519.utils.randomPrivateKey();
    const pub = ed25519.getPublicKey(priv);
    const multibase = multibaseEncodeEd25519Pub(pub);
    expect(multibase.startsWith('z')).toBe(true);
    const recovered = multibaseDecode(multibase);
    expect(Array.from(recovered)).toEqual(Array.from(pub));
  });

  it('rejects non-"z" multibase prefixes', () => {
    expect(() => multibaseDecode('base64stuff')).toThrow();
  });

  it('rejects 31-byte keys', () => {
    expect(() =>
      multibaseEncodeEd25519Pub(new Uint8Array(31))
    ).toThrow(/32 bytes/);
  });
});

describe('didService / did:key generation', () => {
  it('creates a did:key whose public key recovers to the original bytes', () => {
    const { did, publicKeyHex } = generateDidKey();
    expect(did.startsWith('did:key:z')).toBe(true);
    const recovered = publicKeyFromDidKey(did);
    expect(toHex(recovered)).toBe(publicKeyHex);
  });
});

describe('didService / signVp', () => {
  it('emits a 3-part compact JWS signed by the holder key', async () => {
    const { did, privateKeyHex, publicKeyHex } = generateDidKey();
    const vpJwt = await signVp({
      holderDid: did,
      privateKeyHex,
      nonce: 'test-nonce',
      audience: 'https://verifier.example',
    });
    const parts = vpJwt.split('.');
    expect(parts).toHaveLength(3);

    const signingInput = `${parts[0]}.${parts[1]}`;
    const sigB64 = parts[2].replace(/-/g, '+').replace(/_/g, '/');
    const pad = sigB64.length % 4;
    const paddedSig = pad ? sigB64 + '='.repeat(4 - pad) : sigB64;
    const sig = Uint8Array.from(atob(paddedSig), (c) => c.charCodeAt(0));
    const pub = fromHex(publicKeyHex);
    const ok = ed25519.verify(sig, new TextEncoder().encode(signingInput), pub);
    expect(ok).toBe(true);
  });
});

/**
 * preClient.test.js — Umbral PRE browser wrapper tests.
 *
 * The tests are intentionally split into two tiers:
 *
 *   1. Graceful-degradation tests that run in every environment. They
 *      confirm that when the optional ``@nucypher/umbral-pre`` package
 *      is not installed, the wrapper still returns a well-typed
 *      ``UmbralUnavailableError`` instead of throwing an opaque
 *      bundler failure.
 *
 *   2. A real Umbral round-trip that only runs when the WASM module
 *      can be loaded. This is skipped automatically in CI without the
 *      dependency installed.
 */

import { describe, expect, test } from 'vitest';

import preClient, {
  isPreAvailable,
  UmbralUnavailableError,
  preB64,
} from '../preClient';

describe('preClient base64url helpers', () => {
  test('roundtrips byte-exact', () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 255, 128, 64]);
    const enc = preB64.encode(bytes);
    expect(enc).not.toContain('=');
    expect(enc).not.toContain('+');
    expect(enc).not.toContain('/');
    const dec = preB64.decode(enc);
    expect(Array.from(dec)).toEqual(Array.from(bytes));
  });

  test('decodes strings without padding', () => {
    expect(Array.from(preB64.decode(preB64.encode(new Uint8Array([7, 8]))))).toEqual([7, 8]);
  });
});

describe('preClient graceful degradation', () => {
  test('isPreAvailable resolves to boolean', async () => {
    const ok = await isPreAvailable();
    expect(typeof ok).toBe('boolean');
  });

  test('encryptFor surfaces UmbralUnavailableError when WASM missing', async () => {
    const available = await isPreAvailable();
    if (available) return;
    await expect(
      preClient.encryptFor('AAAA', 'hello'),
    ).rejects.toBeInstanceOf(UmbralUnavailableError);
  });
});

describe('preClient umbral roundtrip', () => {
  test('encrypt → kfrag → decrypt', async () => {
    const available = await isPreAvailable();
    if (!available) {
      console.info('[preClient.test] skipping roundtrip: umbral-pre WASM unavailable');
      return;
    }

    const owner = await preClient.generateKeyPair();
    const recipient = await preClient.generateKeyPair();
    const message = 'correct horse battery staple';

    const { capsule, ciphertext } = await preClient.encryptFor(
      owner.public.umbralPublicKey,
      message,
    );

    const kfrag = await preClient.generateKfrag({
      ownerSkBytes: owner.secret.sk,
      signerSkBytes: owner.secret.signerSk,
      recipientPkB64: recipient.public.umbralPublicKey,
    });

    // In production the server applies the kfrag to the capsule with
    // pyUmbral.  Here we dynamically import the JS module to drive
    // the same re-encryption step in-test.  The specifier is built
    // at runtime so Vite does not try to statically resolve the
    // optional peer dependency during transform.
    const moduleName = ['@nucypher', 'umbral-pre'].join('/');
    const umbral = await import(/* @vite-ignore */ moduleName);
    const caps = umbral.Capsule.fromBytes(preB64.decode(capsule));
    const verifiedKfrag = umbral.KeyFrag.fromBytes(preB64.decode(kfrag)).verify(
      umbral.PublicKey.fromBytes(preB64.decode(owner.public.umbralVerifyingKey)),
      umbral.PublicKey.fromBytes(preB64.decode(owner.public.umbralPublicKey)),
      umbral.PublicKey.fromBytes(preB64.decode(recipient.public.umbralPublicKey)),
    );
    const cfrag = umbral.reencrypt(caps, verifiedKfrag);
    const cfragB64 = preB64.encode(cfrag.toBytes());

    const plain = await preClient.decryptReencrypted({
      recipientSkBytes: recipient.secret.sk,
      delegatingPkB64: owner.public.umbralPublicKey,
      verifyingPkB64: owner.public.umbralVerifyingKey,
      capsuleB64: capsule,
      cfragB64,
      ciphertextB64: ciphertext,
    });
    expect(new TextDecoder().decode(plain)).toBe(message);
  });
});

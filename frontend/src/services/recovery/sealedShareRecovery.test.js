import { describe, expect, it } from 'vitest';
import { sha256 } from '@noble/hashes/sha256';
import { combineShares, splitSecret } from './shamirGf256';
import {
  fromB64,
  keyFingerprint,
  newHolderKeyPair,
  proveShareHolding,
  recoverSeed,
  resealShareForRequester,
  sealSeedForGuardians,
  toB64,
} from './sealedShareRecovery';

describe('GF(256) Shamir', () => {
  it('recombines from any threshold-sized subset', () => {
    const secret = crypto.getRandomValues(new Uint8Array(32));
    const shares = splitSecret(secret, 5, 3);
    expect(shares.map((s) => s[0])).toEqual([1, 2, 3, 4, 5]);
    for (const subset of [[0, 1, 2], [1, 3, 4], [4, 0, 2], [0, 1, 2, 3, 4]]) {
      expect(combineShares(subset.map((i) => shares[i]))).toEqual(secret);
    }
    expect(combineShares([shares[0], shares[1]])).not.toEqual(secret);
  });

  it('rejects repeated or zero-index shares', () => {
    const shares = splitSecret(new Uint8Array([9, 9]), 3, 2);
    expect(() => combineShares([shares[0], shares[0]])).toThrow();
    const zero = shares[1].slice();
    zero[0] = 0;
    expect(() => combineShares([shares[0], zero])).toThrow();
  });
});

describe('guardian recovery on the client', () => {
  it('moves the seed owner -> guardians -> requester without a clear share in transit', async () => {
    const seed = crypto.getRandomValues(new Uint8Array(32));
    const guardians = await Promise.all([1, 2, 3].map(() => newHolderKeyPair()));
    const setup = await sealSeedForGuardians({
      seed, threshold: 2, guardianPublicKeys: guardians.map((g) => g.publicKey),
    });

    // What the server receives holds no share in the clear.
    const sent = JSON.stringify(setup);
    for (const share of splitSecret(seed, 3, 2)) expect(sent).not.toContain(toB64(share));
    expect(sent).not.toContain(toB64(seed));

    // Each guardian proves it can open its own share; the server compares digests.
    for (let i = 0; i < 3; i++) {
      const proof = await proveShareHolding({
        keyPair: guardians[i], sealedShare: setup.shares[i].sealedShare,
      });
      expect(toB64(sha256(fromB64(proof)))).toBe(setup.shares[i].shareProofHash);
    }
    await expect(proveShareHolding({
      keyPair: guardians[1], sealedShare: setup.shares[0].sealedShare,
    })).rejects.toThrow();

    const requester = await newHolderKeyPair();
    const resealed = await Promise.all([0, 2].map((i) => resealShareForRequester({
      keyPair: guardians[i],
      sealedShare: setup.shares[i].sealedShare,
      requesterPublicKey: requester.publicKey,
      confirmedFingerprint: keyFingerprint(requester.publicKey).toLowerCase(),
    })));
    const recovered = await recoverSeed({
      keyPair: requester, sealedShares: resealed, threshold: 2, secretCheck: setup.secretCheck,
    });
    expect(recovered).toEqual(seed);

    // A guardian cannot open what was re-sealed to the requester.
    await expect(recoverSeed({
      keyPair: guardians[0], sealedShares: resealed, threshold: 2, secretCheck: setup.secretCheck,
    })).rejects.toThrow();
  });

  it('re-seals only to the key whose fingerprint the guardian confirmed', async () => {
    const [guardian] = await Promise.all([newHolderKeyPair(), newHolderKeyPair()]);
    const other = await newHolderKeyPair();
    const setup = await sealSeedForGuardians({
      seed: new Uint8Array(32).fill(5), threshold: 2,
      guardianPublicKeys: [guardian.publicKey, other.publicKey],
    });
    const requester = await newHolderKeyPair();
    const substituted = await newHolderKeyPair();
    expect(keyFingerprint(requester.publicKey)).toMatch(/^[0-9A-F]{4}(-[0-9A-F]{4}){4}$/);
    // The server hands over another key than the one the requester read out.
    await expect(resealShareForRequester({
      keyPair: guardian, sealedShare: setup.shares[0].sealedShare,
      requesterPublicKey: substituted.publicKey,
      confirmedFingerprint: keyFingerprint(requester.publicKey),
    })).rejects.toThrow(/fingerprint/);
    await expect(resealShareForRequester({
      keyPair: guardian, sealedShare: setup.shares[0].sealedShare,
      requesterPublicKey: requester.publicKey, confirmedFingerprint: '',
    })).rejects.toThrow(/fingerprint/);
  });

  it('recovers when one of more-than-threshold shares is wrong', async () => {
    const guardians = await Promise.all([1, 2, 3].map(() => newHolderKeyPair()));
    const keys = guardians.map((g) => g.publicKey);
    const good = await sealSeedForGuardians({ seed: new Uint8Array(32).fill(7), threshold: 2, guardianPublicKeys: keys });
    const bad = await sealSeedForGuardians({ seed: new Uint8Array(32).fill(8), threshold: 2, guardianPublicKeys: keys });
    const requester = await newHolderKeyPair();
    const fingerprint = keyFingerprint(requester.publicKey);
    // Guardian 1 hands over a share from another split: subsets {1,2} and
    // {1,3} fail the check, {2,3} recovers.
    const resealed = await Promise.all([[bad, 0], [good, 1], [good, 2]].map(([setup, i]) => resealShareForRequester({
      keyPair: guardians[i], sealedShare: setup.shares[i].sealedShare,
      requesterPublicKey: requester.publicKey, confirmedFingerprint: fingerprint,
    })));
    const seed = await recoverSeed({
      keyPair: requester, sealedShares: resealed, threshold: 2, secretCheck: good.secretCheck,
    });
    expect(Array.from(seed)).toEqual(Array.from(new Uint8Array(32).fill(7)));
  });

  it('refuses a seed that does not match the seed check', async () => {
    const guardians = await Promise.all([1, 2].map(() => newHolderKeyPair()));
    const a = await sealSeedForGuardians({
      seed: new Uint8Array(32).fill(1), threshold: 2,
      guardianPublicKeys: guardians.map((g) => g.publicKey),
    });
    const b = await sealSeedForGuardians({
      seed: new Uint8Array(32).fill(2), threshold: 2,
      guardianPublicKeys: guardians.map((g) => g.publicKey),
    });
    const requester = await newHolderKeyPair();
    // One share from each setup: recombines to garbage, which the check catches.
    const resealed = await Promise.all([[a, 0], [b, 1]].map(([setup, i]) => resealShareForRequester({
      keyPair: guardians[i], sealedShare: setup.shares[i].sealedShare,
      requesterPublicKey: requester.publicKey,
      confirmedFingerprint: keyFingerprint(requester.publicKey),
    })));
    await expect(recoverSeed({
      keyPair: requester, sealedShares: resealed, threshold: 2, secretCheck: a.secretCheck,
    })).rejects.toThrow(/does not match/);
  });
});

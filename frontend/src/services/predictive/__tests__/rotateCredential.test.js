import { describe, it, expect, vi, beforeEach } from 'vitest';

// Stub the API layer so these stay pure unit tests (no axios, no network).
vi.mock('../../predictiveExpirationService', () => ({
  submitFingerprints: vi.fn(async (fps) => ({ processed: fps.length, rules: [] })),
  forceRotation: vi.fn(async (credentialId) => ({
    event_id: 'evt-1',
    message: 'Rotation initiated',
    credential_id: credentialId,
  })),
}));

import { rotateCredential, generateRotationPassword } from '../rotateCredential';
import { submitFingerprints, forceRotation } from '../../predictiveExpirationService';

function makeVault(overrides = {}) {
  const item = {
    id: 7,
    item_id: 'cred-42',
    item_type: 'password',
    created_at: new Date(Date.now() - 400 * 86400 * 1000).toISOString(),
    encrypted_data: 'ciphertext',
  };
  return {
    canEdit: true,
    items: [item],
    decryptItem: vi.fn(async () => ({
      ...item,
      data: { password: 'OldPass123!', url: 'https://chase.com/login' },
      _decrypted: true,
    })),
    updateItem: vi.fn(async (i) => i),
    ...overrides,
  };
}

describe('rotateCredential', () => {
  beforeEach(() => {
    submitFingerprints.mockClear();
    forceRotation.mockClear();
  });

  it('runs the full ZK flow: decrypt → generate → re-encrypt → resync → record', async () => {
    const vault = makeVault();
    const generatePassword = vi.fn(() => 'BrandNewStr0ng#Pass');

    const result = await rotateCredential(vault, 'cred-42', { generatePassword });

    // Decrypted the right item.
    expect(vault.decryptItem).toHaveBeenCalledWith('cred-42');

    // Re-encrypted + stored the NEW password (only via updateItem -> ciphertext).
    expect(vault.updateItem).toHaveBeenCalledTimes(1);
    const stored = vault.updateItem.mock.calls[0][0];
    expect(stored.data.password).toBe('BrandNewStr0ng#Pass');
    // Other fields preserved.
    expect(stored.data.url).toBe('https://chase.com/login');
    expect(stored.id).toBe(7);

    // Re-synced exactly one fingerprint for the new shape.
    expect(submitFingerprints).toHaveBeenCalledTimes(1);
    expect(result.fingerprintSynced).toBe(true);

    // Recorded the rotation event.
    expect(forceRotation).toHaveBeenCalledTimes(1);
    expect(forceRotation.mock.calls[0][0]).toBe('cred-42');

    expect(result.credentialId).toBe('cred-42');
    expect(result.event.event_id).toBe('evt-1');
  });

  it('never sends the plaintext password to the server (ZK invariant)', async () => {
    const vault = makeVault();
    const newPw = 'SuperSecretRotated#9';
    await rotateCredential(vault, 'cred-42', { generatePassword: () => newPw });

    // The fingerprint payload must be irreversible structural metadata only.
    const fpBatch = JSON.stringify(submitFingerprints.mock.calls[0][0]);
    expect(fpBatch).not.toContain(newPw);
    expect(fpBatch).not.toContain('chase.com');

    // The recorded event carries a reason only — no password field.
    const rotatePayload = JSON.stringify(forceRotation.mock.calls[0][1]);
    expect(rotatePayload).not.toContain(newPw);
    expect(rotatePayload).not.toContain('new_password');
  });

  it('resets credential age to 0 in the re-synced fingerprint', async () => {
    const vault = makeVault(); // item created ~400 days ago
    await rotateCredential(vault, 'cred-42', { generatePassword: () => 'Whatever#123' });
    const sent = submitFingerprints.mock.calls[0][0][0];
    expect(sent.age_days).toBe(0);
  });

  it('refuses to rotate when the vault is locked', async () => {
    const vault = makeVault({ canEdit: false });
    await expect(rotateCredential(vault, 'cred-42')).rejects.toThrow(/unlock/i);
    expect(vault.updateItem).not.toHaveBeenCalled();
    expect(forceRotation).not.toHaveBeenCalled();
  });

  it('throws when the credential is not in the unlocked vault', async () => {
    const vault = makeVault();
    await expect(rotateCredential(vault, 'missing-id')).rejects.toThrow(/not in your unlocked vault/i);
    expect(forceRotation).not.toHaveBeenCalled();
  });

  it('does not record a rotation if decryption fails', async () => {
    const vault = makeVault({
      decryptItem: vi.fn(async () => ({ _decryptionFailed: true })),
    });
    await expect(rotateCredential(vault, 'cred-42')).rejects.toThrow(/decrypt/i);
    expect(vault.updateItem).not.toHaveBeenCalled();
    expect(forceRotation).not.toHaveBeenCalled();
  });

  it('still records the rotation if the post-rotation re-sync fails', async () => {
    const vault = makeVault();
    submitFingerprints.mockRejectedValueOnce(new Error('network'));
    const result = await rotateCredential(vault, 'cred-42', {
      generatePassword: () => 'Another#Pass1',
    });
    // Rotation persisted + event recorded despite the sync failure.
    expect(vault.updateItem).toHaveBeenCalledTimes(1);
    expect(forceRotation).toHaveBeenCalledTimes(1);
    expect(result.fingerprintSynced).toBe(false);
  });
});

describe('generateRotationPassword', () => {
  it('generates a strong password of the requested length', () => {
    const pw = generateRotationPassword(24);
    expect(typeof pw).toBe('string');
    expect(pw).toHaveLength(24);
  });
});

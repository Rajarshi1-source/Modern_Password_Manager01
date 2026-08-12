/**
 * Regression tests for the adaptive-password unlock guard.
 *
 * The property under test is an ORDERING one: a wrong master password must be
 * rejected BEFORE any fingerprint key is derived from it. Argon2id has no
 * "wrong password" outcome — it derives different-but-well-formed key material
 * from any input — so deriving first would let a typo silently fingerprint the
 * whole adaptive session under the wrong key, orphaning the rollback chain and
 * history (`PasswordAdaptation` rows a correctly-fingerprinting client can
 * never match).
 *
 * Flagged three times on PR #475 (Codex rounds 1 & 2, CodeRabbit round 3) and
 * deferred each time for want of a verification primitive on the standard
 * (non-OAuth) login path; `sessionVaultCryptoV3.verifyMasterPassword` is that
 * primitive.
 *
 * Asserting only "an error is shown" would pass even if the component derived
 * first and complained afterwards, so these tests assert on `CryptoService`
 * never being constructed.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const cryptoServiceCtor = vi.fn();
const passwordFingerprint = vi.fn(async () => 'fp-stub');

vi.mock('../../../services/cryptoService', () => ({
  CryptoService: class {
    constructor(masterPassword) {
      cryptoServiceCtor(masterPassword);
      this.masterPassword = masterPassword;
    }

    passwordFingerprint(...args) {
      return passwordFingerprint(...args);
    }
  },
}));

const verifyMasterPassword = vi.fn();
const canVerifyMasterPassword = vi.fn(() => true);

vi.mock('../../../services/sessionVaultCryptoV3', () => ({
  verifyMasterPassword: (...args) => verifyMasterPassword(...args),
  canVerifyMasterPassword: (...args) => canVerifyMasterPassword(...args),
}));

vi.mock('../../../contexts/VaultContext', () => ({
  useVault: () => ({
    items: [],
    decryptItem: vi.fn(),
    updateItem: vi.fn(),
    canEdit: true,
  }),
}));

// TypingProfileCard self-fetches; stub it so this test stays about the guard.
vi.mock('../TypingProfileCard', () => ({ default: () => null }));
vi.mock('../AdaptivePasswordSuggestion', () => ({ default: () => null }));

const getConfig = vi.fn(async () => ({
  enabled: true,
  fingerprint_salt: 'salt-abc',
  fp_key_version: 1,
}));

vi.mock('../TypingPatternCapture', () => ({
  adaptivePasswordService: {
    getConfig: (...a) => getConfig(...a),
    makeFingerprinter: (cryptoService, salt) => (
      (password) => cryptoService.passwordFingerprint(password, salt)
    ),
    getHistory: vi.fn(async () => ({ adaptations: [] })),
    getStats: vi.fn(async () => ({})),
  },
}));

/** Render the dashboard and drive it to the master-password form. */
async function renderAtUnlockForm() {
  const { default: AdaptivePasswordDashboard } = await import(
    '../AdaptivePasswordDashboard'
  );
  render(<AdaptivePasswordDashboard />);
  // Tab defaults to 'profile'; the unlock form lives on 'adapt'.
  await userEvent.click(await screen.findByRole('button', { name: /adapt/i }));
  return screen.findByTestId('adaptive-master-password');
}

describe('adaptive unlock verifies the master password before deriving', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    canVerifyMasterPassword.mockReturnValue(true);
    verifyMasterPassword.mockResolvedValue(true);
  });

  it('does not derive a fingerprint key when the password is wrong', async () => {
    verifyMasterPassword.mockRejectedValue(
      new Error('Incorrect password or corrupted vault key.'),
    );
    const field = await renderAtUnlockForm();

    await userEvent.type(field, 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));

    await waitFor(() => {
      expect(screen.getByText(/incorrect password/i)).toBeInTheDocument();
    });
    // The ordering assertion: verification ran, derivation never did.
    expect(verifyMasterPassword).toHaveBeenCalledWith('wrong-password');
    expect(cryptoServiceCtor).not.toHaveBeenCalled();
    expect(passwordFingerprint).not.toHaveBeenCalled();
  });

  it('derives normally once the password verifies', async () => {
    const field = await renderAtUnlockForm();

    await userEvent.type(field, 'right-password');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));

    await waitFor(() => {
      expect(cryptoServiceCtor).toHaveBeenCalledWith('right-password');
    });
    expect(verifyMasterPassword).toHaveBeenCalledWith('right-password');
    expect(passwordFingerprint).toHaveBeenCalled();
  });

  it('fails closed when the password cannot be verified at all', async () => {
    // No cached wrapped-DEK envelope this session. Proceeding unverified is
    // the exact bug this guard closes, so the feature refuses rather than
    // deriving under a password it cannot check.
    canVerifyMasterPassword.mockReturnValue(false);
    const field = await renderAtUnlockForm();

    await userEvent.type(field, 'unverifiable');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));

    await waitFor(() => {
      expect(screen.getByText(/sign out and back in/i)).toBeInTheDocument();
    });
    expect(verifyMasterPassword).not.toHaveBeenCalled();
    expect(cryptoServiceCtor).not.toHaveBeenCalled();
  });
});

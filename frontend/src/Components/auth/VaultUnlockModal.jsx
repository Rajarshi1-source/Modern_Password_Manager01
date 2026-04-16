import React, { useState, useMemo } from 'react';
import Modal from '../../Modal.jsx';
import sessionVaultCrypto from '../../services/sessionVaultCrypto';

/**
 * VaultUnlockModal
 *
 * For OAuth (social) logins the user has no master password, so we can't
 * derive the vault encryption key directly. This modal runs the wrapped-DEK
 * flow from `sessionVaultCrypto`:
 *
 *   - first time on an account    -> "setup" mode (confirm new vault password)
 *   - subsequent logins           -> "unlock" mode (enter vault password)
 *
 * The component is dumb about auth state — parents decide when to show it.
 */
const VaultUnlockModal = ({ isOpen, userId, onUnlocked, onClose }) => {
  const mode = useMemo(
    () => (userId && sessionVaultCrypto.hasWrappedKey(userId) ? 'unlock' : 'setup'),
    // Re-evaluate every time the modal opens so a fresh login picks up the
    // current storage state rather than a stale mode from a previous render.
    [userId, isOpen]
  );

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const resetLocal = () => {
    setPassword('');
    setConfirm('');
    setError('');
    setBusy(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!password) {
      setError('Please enter your vault password.');
      return;
    }

    if (mode === 'setup') {
      if (password.length < 12) {
        setError('Vault password must be at least 12 characters.');
        return;
      }
      if (password !== confirm) {
        setError('Passwords do not match.');
        return;
      }
    }

    setBusy(true);
    try {
      if (mode === 'setup') {
        await sessionVaultCrypto.setupVaultPassword(password, userId);
      } else {
        await sessionVaultCrypto.unlockWithVaultPassword(password, userId);
      }
      resetLocal();
      onUnlocked?.();
    } catch (err) {
      setError(err?.message || 'Failed to unlock the vault.');
    } finally {
      setBusy(false);
    }
  };

  const handleClose = () => {
    resetLocal();
    onClose?.();
  };

  const title = mode === 'setup' ? 'Set up your vault password' : 'Unlock your vault';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={title} size="small">
      <form onSubmit={handleSubmit}>
        <p style={{ marginBottom: '12px', lineHeight: 1.4 }}>
          {mode === 'setup' ? (
            <>
              You signed in with a social provider, which does not give the app a
              master password. Choose a <strong>vault password</strong> to protect
              your entries. This password never leaves your device — we store only
              a wrapped copy of the encryption key.
            </>
          ) : (
            <>
              Enter the vault password you set up previously. This password is
              different from your social sign-in and is required to decrypt your
              saved entries.
            </>
          )}
        </p>

        <div className="form-group">
          <label htmlFor="vault-password">
            {mode === 'setup' ? 'New vault password' : 'Vault password'}
          </label>
          <input
            id="vault-password"
            type="password"
            autoComplete={mode === 'setup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoFocus
            required
          />
        </div>

        {mode === 'setup' && (
          <div className="form-group">
            <label htmlFor="vault-password-confirm">Confirm vault password</label>
            <input
              id="vault-password-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={busy}
              required
            />
          </div>
        )}

        {error && (
          <div
            className="error-message"
            role="alert"
            style={{ marginTop: '8px', color: 'var(--danger)' }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            display: 'flex',
            gap: '8px',
            justifyContent: 'flex-end',
            marginTop: '16px',
          }}
        >
          <button
            type="button"
            className="text-btn"
            onClick={handleClose}
            disabled={busy}
          >
            Later
          </button>
          <button type="submit" className="submit-btn" disabled={busy}>
            {busy
              ? (mode === 'setup' ? 'Setting up…' : 'Unlocking…')
              : (mode === 'setup' ? 'Create vault password' : 'Unlock')}
          </button>
        </div>
      </form>
    </Modal>
  );
};

export default VaultUnlockModal;

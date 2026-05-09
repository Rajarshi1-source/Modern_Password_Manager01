/**
 * Tier-1 (Printable Recovery Key) RECOVERY page.
 *
 * Flow:
 *   1. User enters their recovery key.
 *   2. Client fetches the wrapped DEK + the user's recovery_key
 *      factor blob, then unwraps in the browser.
 *   3. Client forces a master-password change immediately —
 *      recovery without setting a new master password leaves the
 *      account in a half-broken state.
 *
 * ZK invariant: the recovery key is used as the Argon2 secret in the
 * browser. It is NEVER sent to the server.
 */
import React, { useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { normalizeRecoveryKey } from './generateRecoveryKey';

export default function RecoveryKeyUseV2({ onSuccess }) {
  const [recoveryKey, setRecoveryKey] = useState('');
  const [phase, setPhase] = useState('await-key'); // -> 'change-password' -> 'done'
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  // Stashed during handleRecover so handleChangePassword can drive the
  // master-wrapped row rotation. Without these, we'd need to re-list
  // the factors on every password attempt — and `recoveryKey` itself
  // would still be in component state (we can't free it until the
  // user clears the input), so persistence is no worse.
  const [unlockedFactor, setUnlockedFactor] = useState(null);
  const [normalizedKey, setNormalizedKey] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleRecover() {
    const normalized = normalizeRecoveryKey(recoveryKey);
    if (!normalized) {
      setError('Recovery key must be 26 letters/digits.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const factors = await recoveryFactorService.listRecoveryFactors();
      const factor = (factors || []).find((f) => f.factor_type === 'recovery_key');
      if (!factor) {
        throw new Error('No recovery key on file for this account.');
      }
      // The factor record returned by GET /recovery-factors/ does not
      // include the wrapped blob (server-side privacy minimization
      // could theoretically apply later). Today the same endpoint
      // returns the factor row including the blob; if it ever stops
      // doing so, we will need a dedicated /recovery-factors/{id}/blob/
      // route. For now we re-fetch via the wrapped-DEK endpoint —
      // wait, that returns the master-password wrapped DEK, not the
      // recovery-key one. We rely on the listRecoveryFactors response
      // including the blob. If `factor.blob` is missing the server
      // shape changed; surface that loudly.
      if (!factor.blob) {
        throw new Error(
          'Server response missing factor blob — please retry or contact support.',
        );
      }
      await sessionVaultCryptoV3.unlockWithRecoveryFactor(
        factor.blob,
        normalized,
        factor.dek_id,
      );
      // Stash unwrap inputs so handleChangePassword can re-derive an
      // extractable DEK from the same factor blob and rotate the
      // master-wrapped row under the new password.
      setUnlockedFactor(factor);
      setNormalizedKey(normalized);
      setPhase('change-password');
    } catch (err) {
      setError(err?.message || 'Recovery failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleChangePassword() {
    if (newPassword.length < 8) {
      setError('New master password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError('New password and confirmation do not match.');
      return;
    }
    if (!unlockedFactor || !normalizedKey) {
      setError('Recovery state lost — please restart from the beginning.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      // The merged version of this file called changeMasterPassword
      // here. That doesn't actually work: changeMasterPassword fetches
      // the master-wrapped DEK row and tries to unwrap it with its
      // first argument, but the master-wrapped row was wrapped under
      // the FORGOTTEN password's KEK, not under the recovery-key KEK,
      // so unwrap raised "Incorrect password or corrupted vault key."
      // every time. Users would land on the error and never finish
      // recovery — and even worse, on next login the master-wrapped
      // row was still pinned to the forgotten password.
      //
      // The correct primitive is `rewrapMasterPasswordFromRecovery`,
      // which unwraps the DEK from the RECOVERY FACTOR'S blob (the
      // one we just used to unlockWithRecoveryFactor — guaranteed to
      // unwrap with the recovery key) and re-wraps it under the new
      // master password's KEK while keeping `dek_id` stable so other
      // recovery factors are not orphaned.
      await sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery({
        factorBlob: unlockedFactor.blob,
        recoverySecret: normalizedKey,
        newPassword,
        dekId: unlockedFactor.dek_id,
      });
      setPhase('done');
      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err?.message || 'Password change failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-key') {
    return (
      <section data-testid="recovery-key-use-v2">
        <h1>Recover with your Recovery Key</h1>
        <label>
          Recovery Key
          <input
            type="text"
            name="recoveryKey"
            value={recoveryKey}
            onChange={(e) => setRecoveryKey(e.target.value)}
            placeholder="ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-23"
            data-testid="rk-use-input"
            autoComplete="off"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleRecover}
          disabled={busy}
          data-testid="rk-use-recover"
        >
          {busy ? 'Verifying…' : 'Recover'}
        </button>
      </section>
    );
  }

  if (phase === 'change-password') {
    return (
      <section data-testid="recovery-key-use-v2">
        <h1>Set a New Master Password</h1>
        <p>
          You must set a new master password before continuing. Recovery without doing so
          would leave the account in a half-locked state.
        </p>
        <label>
          New master password
          <input
            type="password"
            name="newPassword"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            data-testid="rk-use-new-password"
          />
        </label>
        <label>
          Confirm
          <input
            type="password"
            name="confirmNewPassword"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            data-testid="rk-use-confirm-new-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleChangePassword}
          disabled={busy}
          data-testid="rk-use-set-password"
        >
          {busy ? 'Saving…' : 'Set New Master Password'}
        </button>
      </section>
    );
  }

  return (
    <section data-testid="recovery-key-use-v2">
      <h1>Recovery complete</h1>
      <p data-testid="rk-use-success">Your vault is unlocked. You can continue normally.</p>
    </section>
  );
}

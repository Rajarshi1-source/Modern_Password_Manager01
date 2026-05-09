/**
 * Tier-1 (Printable Recovery Key) RECOVERY page.
 *
 * Flow:
 *   1. User enters their username + recovery key.
 *   2. Client fetches the user's recovery_key factor blob via the
 *      anonymous lookup endpoint (returns a decoy for unknown
 *      usernames so existence is not leaked) and unwraps in the
 *      browser.
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
  const [username, setUsername] = useState('');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [phase, setPhase] = useState('await-key'); // -> 'change-password' -> 'done'
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  // Stashed during handleRecover so handleChangePassword can drive the
  // master-wrapped row rotation. Without these, we'd need to re-fetch
  // on every password attempt — and `recoveryKey` itself would still
  // be in component state (we can't free it until the user clears the
  // input), so persistence is no worse.
  const [unlockedFactor, setUnlockedFactor] = useState(null);
  const [normalizedKey, setNormalizedKey] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleRecover() {
    // Trim leading/trailing whitespace before any submission. Common
    // copy-paste source for usernames is an email line in another
    // app, which often pulls a trailing space along; the backend
    // does an exact `User.objects.get(username=...)` so without this
    // trim a harmless stray space would cause lookup to silently
    // return a decoy (and the unwrap to fail with the same 'wrong
    // key' message a real bad recovery would). Persist the trimmed
    // value so the controlled input also reflects it and
    // handleChangePassword sees the same string.
    const trimmedUsername = username.trim();
    if (trimmedUsername !== username) setUsername(trimmedUsername);
    if (!trimmedUsername) {
      setError('Username is required.');
      return;
    }
    const normalized = normalizeRecoveryKey(recoveryKey);
    if (!normalized) {
      setError('Recovery key must be 26 letters/digits.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      // Anonymous lookup returns the wrapped factor blob (or a
      // synthesized decoy for unknown usernames; the unwrap below
      // simply fails for decoys with the same generic 'incorrect
      // password' error a wrong key produces). Replaces the previous
      // listRecoveryFactors call which:
      //   (a) required authentication (the user is unauthenticated
      //       on this page — they forgot the master password),
      //   (b) didn't include `blob` in its response anyway.
      const factor = await recoveryFactorService.lookupRecoveryFactor(
        trimmedUsername,
        'recovery_key',
      );
      if (!factor || !factor.blob) {
        throw new Error('Recovery factor unavailable.');
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
    // Trim defensively — handleRecover already persists a trimmed
    // username, but a future code path (e.g. resuming from saved
    // state) could land here with whitespace. Same backend exact-
    // match concern applies to the rotate endpoint as it does to
    // the lookup.
    const trimmedUsername = username.trim();
    if (!unlockedFactor || !normalizedKey || !trimmedUsername) {
      setError('Recovery state lost — please restart from the beginning.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      // Calls the anonymous /api/auth/vault/wrapped-dek/recover-rotate/
      // endpoint via the v3 helper. The helper unwraps the factor
      // blob locally with the recovery key (guaranteed to succeed —
      // we just did the same unwrap in handleRecover), wraps the
      // resulting DEK under a new master-password KEK, and POSTs the
      // rotation along with username + factor_type + auth_hash so
      // the server can verify the caller actually possesses the
      // recovery secret (not just the dek_id which lookup discloses).
      // dek_id stays stable so other recovery factors are not
      // orphaned.
      await sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery({
        factorBlob: unlockedFactor.blob,
        recoverySecret: normalizedKey,
        newPassword,
        dekId: unlockedFactor.dek_id,
        username: trimmedUsername,
        factorType: 'recovery_key',
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
          Username
          <input
            type="text"
            name="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            data-testid="rk-use-username"
            autoComplete="username"
          />
        </label>
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

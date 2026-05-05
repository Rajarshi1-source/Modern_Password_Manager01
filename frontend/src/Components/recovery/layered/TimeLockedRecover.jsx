/**
 * Tier-3 (Self-Time-Locked) RECOVERY page.
 *
 * Flow:
 *   1. Username input + `.dlrec` file upload (FileReader -> JSON).
 *   2. POST /time-locked/initiate/ — server starts delay clock,
 *      sends canary alerts to the user's email/SMS.
 *   3. Wait for the delay to elapse (countdown UI + manual poll).
 *   4. POST /time-locked/release/ — server returns its half.
 *   5. Combine halves -> time_seed -> derive KEK -> unwrap DEK ->
 *      force change-master-password.
 */
import React, { useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { combine2of2, _b64 } from '../../../services/shamir2of2';

const DLREC_VERSION = 'dlrec-1';

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

async function readJsonFile(file) {
  const text = await file.text();
  return JSON.parse(text);
}

export default function TimeLockedRecover({ onSuccess }) {
  const [username, setUsername] = useState('');
  const [dlrec, setDlrec] = useState(null);
  const [phase, setPhase] = useState('await-input'); // 'waiting' | 'change-password' | 'done'
  const [releaseAfter, setReleaseAfter] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // The recovery seed (hex) and the time_locked factor row are produced
  // in `handlePoll` and consumed in `handleChangePassword` to drive the
  // master-password rotation. We hold them in state rather than module
  // scope so a remount cleanly resets recovery progress.
  const [recoveredSeedHex, setRecoveredSeedHex] = useState(null);
  const [recoveredFactor, setRecoveredFactor] = useState(null);

  async function handleFileChange(e) {
    setError('');
    const file = e.target.files?.[0];
    if (!file) {
      setDlrec(null);
      return;
    }
    try {
      const parsed = await readJsonFile(file);
      if (parsed.v !== DLREC_VERSION || typeof parsed.halfA !== 'string') {
        throw new Error('Not a valid recovery file.');
      }
      setDlrec(parsed);
    } catch (err) {
      setError(err?.message || 'Could not read recovery file.');
      setDlrec(null);
    }
  }

  async function handleBegin() {
    if (!username || !dlrec) {
      setError('Username and recovery file required.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const r = await recoveryFactorService.initiateTimeLock(username);
      setReleaseAfter(r?.release_after || null);
      setPhase('waiting');
    } catch (err) {
      setError(err?.message || 'Could not start recovery.');
    } finally {
      setBusy(false);
    }
  }

  async function handlePoll() {
    setBusy(true);
    setError('');
    try {
      const r = await recoveryFactorService.pollTimeLockRelease(username);
      if (!r.ready) {
        setReleaseAfter(r.releaseAfter || releaseAfter);
        setError('The delay has not elapsed yet. Please come back later.');
        return;
      }
      const halfB = _b64.decode(r.server_half);
      const halfA = _b64.decode(dlrec.halfA);
      const seed = combine2of2(halfA, halfB);
      const seedHex = bytesToHex(seed);

      const factors = await recoveryFactorService.listRecoveryFactors();
      const factor = (factors || []).find((f) => f.factor_type === 'time_locked');
      if (!factor || !factor.blob) {
        throw new Error('No time-locked factor on file (or server omitted blob).');
      }
      await sessionVaultCryptoV3.unlockWithRecoveryFactor(
        factor.blob,
        seedHex,
        factor.dek_id,
      );
      // Stash the unwrap inputs so handleChangePassword can re-derive
      // them for the master-wrapped row rotation. (The session DEK
      // itself is non-extractable and can't be re-wrapped directly.)
      setRecoveredSeedHex(seedHex);
      setRecoveredFactor(factor);
      setPhase('change-password');
    } catch (err) {
      setError(err?.message || 'Recovery failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleChangePassword() {
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (!recoveredSeedHex || !recoveredFactor) {
      setError('Recovery state lost — please restart from the beginning.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      // Use the recovery seed (the secret that just unwrapped the
      // time_locked factor blob) to unwrap the same DEK again as
      // EXTRACTABLE inside v3, re-wrap it under a fresh KEK derived
      // from the new master password, and PUT it back as the master-
      // wrapped row. dek_id stays stable so other recovery factors
      // (e.g. social mesh, recovery key) are not orphaned.
      await sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery({
        factorBlob: recoveredFactor.blob,
        recoverySecret: recoveredSeedHex,
        newPassword,
        dekId: recoveredFactor.dek_id,
      });
      setPhase('done');
      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err?.message || 'Password change failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-input') {
    return (
      <section data-testid="time-locked-recover">
        <h1>Recover with Time-Locked Self-Recovery</h1>
        <label>
          Username
          <input
            type="text"
            name="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            data-testid="tl-recover-username"
          />
        </label>
        <label>
          Recovery file (.dlrec)
          <input
            type="file"
            accept=".dlrec,application/json"
            onChange={handleFileChange}
            data-testid="tl-recover-file"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleBegin}
          disabled={busy || !username || !dlrec}
          data-testid="tl-recover-begin"
        >
          {busy ? 'Starting…' : 'Begin Recovery'}
        </button>
      </section>
    );
  }

  if (phase === 'waiting') {
    return (
      <section data-testid="time-locked-recover">
        <h1>Waiting for the time-lock delay</h1>
        <p>
          Recovery starts the delay clock. You will receive a canary email each day during
          the delay; if you did not initiate this recovery, click the link in those emails
          to cancel.
        </p>
        {releaseAfter ? (
          <p data-testid="tl-recover-release-after">
            The server will release its half after <strong>{releaseAfter}</strong>.
          </p>
        ) : null}
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handlePoll}
          disabled={busy}
          data-testid="tl-recover-poll"
        >
          {busy ? 'Checking…' : 'Check Status'}
        </button>
      </section>
    );
  }

  if (phase === 'change-password') {
    return (
      <section data-testid="time-locked-recover">
        <h1>Set a New Master Password</h1>
        <label>
          New master password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            data-testid="tl-recover-new-password"
          />
        </label>
        <label>
          Confirm
          <input
            type="password"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            data-testid="tl-recover-confirm-new-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleChangePassword}
          disabled={busy}
          data-testid="tl-recover-set-password"
        >
          {busy ? 'Saving…' : 'Continue'}
        </button>
      </section>
    );
  }

  return (
    <section data-testid="time-locked-recover">
      <h1>Recovery complete</h1>
      <p data-testid="tl-recover-success">Your vault is unlocked.</p>
    </section>
  );
}

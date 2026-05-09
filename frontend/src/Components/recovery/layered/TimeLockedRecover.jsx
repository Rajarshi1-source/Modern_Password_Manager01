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

/**
 * Render a `Uint8Array` as a lowercase hex string. Used to format
 * the reconstructed recovery seed before passing it to the Argon2id
 * KDF (which expects a string secret, not raw bytes).
 *
 * @param {Uint8Array} bytes
 * @returns {string}
 */
function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Read a `File` (from an `<input type="file">`) as JSON.
 *
 * @param {File} file
 * @returns {Promise<object>}
 */
async function readJsonFile(file) {
  const text = await file.text();
  return JSON.parse(text);
}

/**
 * Tier-3 recovery page (anonymous). Five-phase state machine:
 *
 *   await-input     → user enters username and uploads `.dlrec`.
 *   waiting         → server has accepted `initiate`; user must wait
 *                     out the time-lock delay (canary alerts may also
 *                     be in flight to their email/SMS).
 *   change-password → server released its half; we recombined the
 *                     seed, unwrapped the factor blob, and now must
 *                     rotate the master-wrapped row before letting
 *                     the user out of the flow.
 *   done            → terminal success state.
 *
 * @param {object} [props]
 * @param {() => void} [props.onSuccess] - Optional callback for navigation.
 */
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

  /**
   * Validate and stash the uploaded `.dlrec` file. We accept only the
   * `dlrec-1` envelope shape; anything else gets rejected with a
   * generic error so a malformed file doesn't half-populate state.
   */
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

  /**
   * Kick off the time-lock delay clock by hitting the anonymous
   * `initiate` endpoint. The endpoint returns a uniform shape
   * (real or decoy `release_after`) so we surface whatever the
   * server returned without trying to verify it.
   */
  async function handleBegin() {
    if (!username || !dlrec) {
      setError('Username and recovery file required.');
      return;
    }
    // The .dlrec file embeds the username it was generated for. We
    // reject mismatches up front so a typo here doesn't kick off a
    // 7-day delay against the wrong account that would only fail
    // (silently, in a wrong-key generic-error sense) days later
    // when handlePoll tries to combine the wrong server half.
    // Compare case-insensitively because the username could have
    // been entered with mixed case at signup.
    if (
      typeof dlrec.username === 'string'
      && dlrec.username.toLowerCase() !== username.toLowerCase()
    ) {
      setError(
        `This recovery file was generated for "${dlrec.username}" but you typed `
        + `"${username}". Re-check your username before starting the delay.`,
      );
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

  /**
   * Poll the release endpoint for the server's Shamir half. Three
   * branches:
   *   - `ready: false` (still waiting): update countdown, surface a
   *     "come back later" notice.
   *   - server returned the half: recombine with the user's local
   *     half, unwrap the factor blob with the seed, stash the
   *     unwrap inputs for the rotation step.
   *   - any other error (cancelled-by-canary 403, real authz, 5xx)
   *     bubbles from `pollTimeLockRelease` and is surfaced as the
   *     error message.
   */
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

      // The list endpoint requires authentication AND does not return
      // `blob`. We use the anonymous lookup endpoint instead, which
      // returns the wrapped factor blob (or a decoy for unknown
      // usernames — the unwrap below will simply fail in that case
      // with the same generic error a wrong key produces, so
      // attackers cannot distinguish via this endpoint).
      const factor = await recoveryFactorService.lookupRecoveryFactor(
        username,
        'time_locked',
      );
      if (!factor || !factor.blob) {
        throw new Error('Recovery factor unavailable.');
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

  /**
   * Force the master-password rotation that recovery requires. Calls
   * `rewrapMasterPasswordFromRecovery` with the seed + factor stashed
   * during `handlePoll`. On success the master-wrapped row is
   * re-pinned to the new password and the live session DEK is
   * re-installed (non-extractable), so the user can use the vault
   * immediately.
   */
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
        // Required by the anonymous rotation endpoint to address the
        // right user/factor server-side; this page is not yet
        // authenticated.
        username,
        factorType: 'time_locked',
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

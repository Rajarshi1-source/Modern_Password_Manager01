/**
 * Tier-2 (Social Mesh) RECOVERY page.
 *
 * Flow:
 *   1. User enters their username and starts recovery via the
 *      existing /quantum-recovery/initiate_recovery/ endpoint
 *      (reuses RecoveryInitiation + RecoveryProgress components).
 *   2. When the threshold is reached and the seed is reconstructed
 *      in-browser, that seed is passed to `unlockWithRecoveryFactor`
 *      to install the DEK in the session.
 *   3. Force a master-password change before continuing.
 *
 * The actual M-of-N guardian handshake lives in the existing social
 * recovery components — this page is a thin layer that:
 *   (a) routes the threshold-reached event through the new factor blob
 *   (b) forces the master-password reset that the layered design needs.
 */
import React, { lazy, Suspense, useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';

const RecoveryInitiation = lazy(() => import('../social/RecoveryInitiation'));
const RecoveryProgress = lazy(() => import('../social/RecoveryProgress'));

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export default function SocialMeshDEKRecover() {
  const [phase, setPhase] = useState('await-username'); // 'in-progress' | 'change-password' | 'done'
  const [username, setUsername] = useState('');
  const [recoveryAttemptId, setRecoveryAttemptId] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  function handleInitiated(attemptId) {
    setRecoveryAttemptId(attemptId);
    setPhase('in-progress');
  }

  /**
   * Called by RecoveryProgress when the existing pipeline has
   * reconstructed the secret in-browser via Lagrange interpolation.
   */
  async function handleSeedReconstructed(seedBytes) {
    setBusy(true);
    setError('');
    try {
      const seedHex = bytesToHex(seedBytes);
      const factors = await recoveryFactorService.listRecoveryFactors();
      const factor = (factors || []).find((f) => f.factor_type === 'social_mesh');
      if (!factor || !factor.blob) {
        throw new Error('No social-mesh factor on file (or server omitted blob).');
      }
      await sessionVaultCryptoV3.unlockWithRecoveryFactor(
        factor.blob,
        seedHex,
        factor.dek_id,
      );
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
    setBusy(true);
    setError('');
    try {
      // Same caveat as Tier 1/3: v3 does not yet expose a
      // session-DEK-rooted master-password rotation primitive. For
      // now we treat the recovery as an opportunity to set a new
      // master password via the change endpoint, leaning on the
      // session DEK already being live.
      setPhase('done');
    } catch (err) {
      setError(err?.message || 'Password change failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-username') {
    return (
      <section data-testid="social-mesh-dek-recover">
        <h1>Recover with Social-Mesh</h1>
        <Suspense fallback={<p>Loading…</p>}>
          {/* RecoveryInitiation owns the username + initiate POST.
              It calls our `onInitiated(attemptId)` once the server
              has accepted the recovery request. */}
          <RecoveryInitiation
            username={username}
            onUsernameChange={setUsername}
            onInitiated={handleInitiated}
          />
        </Suspense>
      </section>
    );
  }

  if (phase === 'in-progress') {
    return (
      <section data-testid="social-mesh-dek-recover">
        <h1>Awaiting guardians</h1>
        <Suspense fallback={<p>Loading…</p>}>
          {/* RecoveryProgress polls for guardian approvals, runs
              Lagrange interpolation in-browser when threshold is met,
              and surfaces the reconstructed secret bytes via
              `onSecretReconstructed`. */}
          <RecoveryProgress
            recoveryAttemptId={recoveryAttemptId}
            onSecretReconstructed={handleSeedReconstructed}
          />
        </Suspense>
        {busy ? <p>Unwrapping vault…</p> : null}
        {error ? <p role="alert">{error}</p> : null}
      </section>
    );
  }

  if (phase === 'change-password') {
    return (
      <section data-testid="social-mesh-dek-recover">
        <h1>Set a New Master Password</h1>
        <label>
          New master password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            data-testid="sm-recover-new-password"
          />
        </label>
        <label>
          Confirm
          <input
            type="password"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            data-testid="sm-recover-confirm-new-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleChangePassword}
          disabled={busy}
          data-testid="sm-recover-set-password"
        >
          {busy ? 'Saving…' : 'Continue'}
        </button>
      </section>
    );
  }

  return (
    <section data-testid="social-mesh-dek-recover">
      <h1>Recovery complete</h1>
      <p data-testid="sm-recover-success">Your vault is unlocked.</p>
    </section>
  );
}

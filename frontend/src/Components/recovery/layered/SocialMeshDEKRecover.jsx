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
  // Stashed at threshold-met so handleChangePassword can drive the
  // master-wrapped row rotation. The session DEK alone isn't enough
  // because v3's session DEK is non-extractable; we re-derive an
  // extractable handle from the same factor blob + seed inside
  // sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery.
  const [unlockedFactor, setUnlockedFactor] = useState(null);
  const [recoveredSeedHex, setRecoveredSeedHex] = useState(null);
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
      // Anonymous lookup — the recover page is unauthenticated. The
      // legacy `listRecoveryFactors` call here was broken on two
      // axes: it required an auth session and it didn't return
      // `blob`. The new lookup endpoint returns {blob, dek_id} for
      // a real (username, factor_type) pair or a deterministic
      // decoy for unknown ones, so existence isn't leaked.
      const factor = await recoveryFactorService.lookupRecoveryFactor(
        username,
        'social_mesh',
      );
      if (!factor || !factor.blob) {
        throw new Error('Recovery factor unavailable.');
      }
      await sessionVaultCryptoV3.unlockWithRecoveryFactor(
        factor.blob,
        seedHex,
        factor.dek_id,
      );
      setUnlockedFactor(factor);
      setRecoveredSeedHex(seedHex);
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
    if (!unlockedFactor || !recoveredSeedHex || !username) {
      setError('Recovery state lost — please restart from the beginning.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      // Hits the anonymous /api/auth/vault/wrapped-dek/recover-rotate/
      // endpoint via the v3 helper. The helper unwraps the factor
      // blob locally with the recovered seed (guaranteed to succeed
      // — we just did the same unwrap above), wraps the resulting
      // DEK under a new master-password KEK, and POSTs the rotation
      // along with username + factor_type + auth_hash so the server
      // can verify the caller actually possesses the recovery secret
      // (not just dek_id, which lookup discloses). dek_id stays
      // stable so other recovery factors are not orphaned.
      await sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery({
        factorBlob: unlockedFactor.blob,
        recoverySecret: recoveredSeedHex,
        newPassword,
        dekId: unlockedFactor.dek_id,
        username,
        factorType: 'social_mesh',
      });
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

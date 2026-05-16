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
 *
 * The existing ``RecoveryInitiation`` and ``RecoveryProgress``
 * components now accept optional callback props (added in the
 * follow-up to #221):
 *
 *   * ``RecoveryInitiation({ email, onEmailChange, onInitiated })``
 *     — when ``onInitiated`` is supplied, it is invoked with the
 *     server-issued request_id instead of navigating to the legacy
 *     ``/recovery/social/progress/:requestId`` route. Email is
 *     controllable so this page can keep it in its own state.
 *
 *   * ``RecoveryProgress({ recoveryAttemptId, onSecretReconstructed })``
 *     — when ``recoveryAttemptId`` is supplied, it is used instead
 *     of ``useParams()``; when ``onSecretReconstructed`` is
 *     supplied, the polling loop decodes the server-returned
 *     reconstructed_secret (base64) into a Uint8Array and fires
 *     the callback exactly once.
 *
 * Back-compat for the legacy passkey-recovery route is preserved:
 * those components fall back to ``useNavigate`` / ``useParams``
 * when the new props are absent, so existing callers see no
 * behavior change.
 */
import React, { lazy, Suspense, useCallback, useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { bytesToHex } from '../../../utils/hex';

const RecoveryInitiation = lazy(() => import('../social/RecoveryInitiation'));
const RecoveryProgress = lazy(() => import('../social/RecoveryProgress'));

// Mirror of TIER2_ENROLL_BLOCKED on the enroll page. The tier-2
// recover path is end-to-end blocked on the same client-side
// Shamir + Kyber pipeline: the legacy poll endpoint
// (RequestDetailView) does not surface `reconstructed_secret` /
// `secret_bytes`, and the only endpoint that returns the secret
// (CompleteRequestView) performs server-side Shamir, which would
// violate the ZK invariant for the social-mesh DEK seed. Until the
// client-side pipeline lands, this page short-circuits to a
// "not yet available" notice rather than letting users initiate a
// guardian recovery whose shards can never be combined client-side.
const TIER2_RECOVER_BLOCKED = true;

/**
 * Tier-2 social-mesh recovery page. Composes the legacy
 * social-recovery components (now callback-aware) to drive a
 * single-page state machine: ``await-username`` →
 * ``in-progress`` → ``change-password`` → ``done``.
 */
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

  /**
   * Phase-transition handler invoked once the social-recovery
   * pipeline has accepted a recovery request. Wired through
   * ``RecoveryInitiation``'s ``onInitiated`` prop.
   *
   * @param {string} attemptId
   */
  function handleInitiated(attemptId) {
    setRecoveryAttemptId(attemptId);
    setPhase('in-progress');
  }

  /**
   * Phase-transition handler invoked once the social-recovery
   * pipeline has reconstructed the seed in-browser via Lagrange
   * interpolation over the released guardian shards. Looks up the
   * matching wrapped DEK factor (anonymous lookup with a decoy
   * fallback for unknown usernames), unwraps it locally with the
   * reconstructed seed, and stashes the unwrap inputs so
   * handleChangePassword can rotate the master row.
   *
   * Memoized on `username` because `RecoveryProgress` includes its
   * `onSecretReconstructed` prop in the dependency array of the
   * `useCallback` that backs its polling `setInterval`. A new
   * function identity on each parent render would tear down and
   * recreate the 5-second poll, which can never converge if a
   * parent re-render (e.g. setBusy(true) inside this very handler)
   * lands mid-interval.
   *
   * @param {Uint8Array} seedBytes 32-byte recovery seed.
   */
  const handleSeedReconstructed = useCallback(async (seedBytes) => {
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
  }, [username]);

  /**
   * Submit handler for the new-master-password form. Delegates to
   * ``sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery`` with
   * the reconstructed seed as ``recoverySecret`` and
   * ``factorType: 'social_mesh'`` so the helper can hit the
   * anonymous /recover-rotate/ endpoint and pass the auth_hash gate.
   * On success transitions to the terminal 'done' phase.
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
    if (TIER2_RECOVER_BLOCKED) {
      return (
        <section data-testid="social-mesh-dek-recover">
          <h1>Recover with Social-Mesh</h1>
          <p role="alert" data-testid="sm-recover-unavailable">
            Social-Mesh recovery is not yet available. The current poll
            endpoint cannot deliver the reconstructed seed without
            violating the zero-knowledge property of the vault DEK; this
            page is blocked until the client-side Shamir + Kyber pipeline
            lands. Until then, please use Recovery Key or Time-Locked
            recovery.
          </p>
        </section>
      );
    }
    return (
      <section data-testid="social-mesh-dek-recover">
        <h1>Recover with Social-Mesh</h1>
        <Suspense fallback={<p>Loading…</p>}>
          {/* RecoveryInitiation owns the username + initiate POST.
              It calls our `onInitiated(attemptId)` once the server
              has accepted the recovery request. */}
          <RecoveryInitiation
            email={username}
            onEmailChange={setUsername}
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

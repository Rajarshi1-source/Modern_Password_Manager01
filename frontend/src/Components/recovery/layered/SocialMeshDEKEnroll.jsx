/**
 * Tier-2 (Social Mesh) ENROLLMENT page.
 *
 * Two responsibilities, deliberately split for review clarity:
 *
 *   (a) Wrap the vault DEK under a KEK derived from a fresh
 *       `recovery_seed` and POST it as a `social_mesh` factor.
 *   (b) Walk the user through the existing social-recovery setup
 *       flow (CircleSetup) so the `recovery_seed` itself is split
 *       across guardians via the existing Shamir/Kyber pipeline.
 *
 * (b) reuses the existing `Components/recovery/social/CircleSetup`
 * component and the `quantum-recovery/setup_recovery/` endpoint,
 * with the new `secret_type='vault_dek_seed'` discriminator (Unit 3)
 * to keep guardian shards routed to vault-DEK reconstruction rather
 * than passkey-key reconstruction.
 *
 * ZK invariant: `recovery_seed` is generated client-side, used as
 * the Argon2 secret, and split before any guardian-bound shard is
 * sent. The server only ever sees opaque ciphertext.
 */
import React, { lazy, Suspense, useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { bytesToHex } from '../../../utils/hex';

const CircleSetup = lazy(() => import('../social/CircleSetup'));

// Hard gate. While true, the await-password phase shows an
// unavailable notice instead of the master-password input. This
// prevents users from creating a wrapped-DEK row that the legacy
// CircleSetup endpoint cannot finish without violating the ZK
// invariant (server-side Shamir over the vault-DEK seed). Flip to
// false once the client-side Shamir + Kyber pipeline is wired and
// CircleSetup tier-2 mode can complete locally.
const TIER2_ENROLL_BLOCKED = true;

/**
 * Tier-2 (Social-Mesh) ENROLLMENT page for the layered recovery
 * mesh. Two responsibilities, separated for clarity:
 *
 *   1. Wrap the vault DEK under a KEK derived from a fresh 32-byte
 *      `recovery_seed` and POST it as a `social_mesh` recovery
 *      factor (writes a RecoveryWrappedDEK row + the auth_hash gate
 *      proof).
 *   2. Walk the user through the existing CircleSetup flow so the
 *      `recovery_seed` itself is split across guardians via the
 *      Shamir/Kyber pipeline shared with passkey-recovery.
 *
 * recovery_setup_id round-trip is wired in this PR: CircleSetup
 * fires `onComplete(circleId)`, `handleCircleComplete` then PATCHes
 * the id into the wdek factor row's `factor_meta` via
 * `recoveryFactorService.updateRecoveryFactorMeta`, so recovery-side
 * code can locate the matching setup by reading
 * `factor_meta.recovery_setup_id` instead of re-discovering by
 * username.
 *
 * Currently unreachable end-to-end in tier-2 mode: `CircleSetup`
 * hard-refuses to commit when an externally-controlled seed is
 * supplied because the legacy `/api/social-recovery/circles/`
 * endpoint Shamir-splits server-side, which would break the
 * zero-knowledge property of the vault recovery seed. The follow-up
 * client-side Shamir + Kyber pipeline will unblock this; until
 * then `handleStart` refuses upfront (see below) to avoid
 * revoking any prior working `social_mesh` factor row.
 *
 * Reached only when the user is signed in (route is gated by
 * `isAuthenticated` in App.jsx).
 */
export default function SocialMeshDEKEnroll() {
  const [masterPassword, setMasterPassword] = useState('');
  const [phase, setPhase] = useState('await-password'); // -> 'circle-setup' -> 'done'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [recoverySeedHex, setRecoverySeedHex] = useState(null);
  // Stash the current dek_id at enrollment so the post-CircleSetup
  // PATCH can prove DEK possession server-side. enrollRecoveryFactor
  // does not return it directly, so we read it from the v3 session
  // state where v3's enroll/unlock paths install it.
  const [dekId, setDekId] = useState(null);

  /**
   * Step (1) of enrollment: generate the seed, wrap the DEK under
   * a KEK derived from it, and POST the resulting envelope as a
   * `social_mesh` recovery factor. On success advances to the
   * CircleSetup phase that owns step (2).
   *
   * Clears `masterPassword` from React state as soon as the wrap
   * has succeeded — the CircleSetup phase only needs the seed
   * (already in `recoverySeedHex`), not the master password.
   * Holding the plaintext master password through the whole
   * guardian-setup flow would be unnecessarily long-lived.
   *
   * UPFRONT REFUSAL: the next step (CircleSetup tier-2 mode) is
   * intentionally gated until the client-side Shamir + Kyber pipeline
   * lands, so committing the wrapped-DEK row here would (a) revoke
   * any prior ACTIVE `social_mesh` factor (the backend's partial
   * unique constraint revokes on insert) and (b) leave the user with
   * a new factor row whose guardian setup can never complete. The
   * `await-password` render below short-circuits to an unavailable
   * notice instead of showing the password input, so this function
   * is only reachable once the gate is lifted. When the client-side
   * pipeline lands, remove `TIER2_ENROLL_BLOCKED` and the notice.
   */
  async function handleStart() {
    if (!masterPassword) {
      setError('Master password required.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const seed = window.crypto.getRandomValues(new Uint8Array(32));
      const seedHex = bytesToHex(seed);
      // (a) Wrap the DEK under the seed-derived KEK so the social
      //     mesh, once enough guardians release shards, can recover
      //     the vault by reconstructing the seed.
      await sessionVaultCryptoV3.enrollRecoveryFactor({
        factorType: 'social_mesh',
        secret: seedHex,
        masterPassword,
        meta: {
          // Pointer to the social-recovery setup row that owns the
          // shard distribution. Populated by the
          // `handleCircleComplete` callback below after CircleSetup
          // commits and surfaces the circle_id.
          recovery_setup_id: null,
          secret_type: 'vault_dek_seed',
        },
      });
      setRecoverySeedHex(seedHex);
      // Capture the dek_id so handleCircleComplete can supply
      // proof-of-DEK-possession to the meta PATCH endpoint.
      setDekId(sessionVaultCryptoV3.getSessionDEKId());
      // Clear the plaintext master password from React state now
      // that the wrap has completed. CircleSetup doesn't need it.
      setMasterPassword('');
      setPhase('circle-setup');
    } catch (err) {
      setError(err?.message || 'Enrollment failed.');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Invoked by CircleSetup's `onComplete` callback after a
   * guardian circle has been committed server-side. PATCHes the
   * returned `circle_id` into the wdek factor row's factor_meta
   * as `recovery_setup_id` so the recover-side flow can look up
   * the matching setup row by reading the factor's meta.
   *
   * If the patch fails (network blip, auth expired, etc.) we log
   * + surface the error but still advance to the `done` phase —
   * the guardian circle exists, the factor row exists, the only
   * loss is the cross-reference, which recovery-side code can
   * fall back to discovering by username.
   *
   * NOTE: currently unreachable in tier-2 mode. `CircleSetup`
   * refuses to commit when `secretHex` is supplied because the
   * legacy `/api/social-recovery/circles/` endpoint splits the
   * secret server-side, which would break the zero-knowledge
   * property of the vault recovery seed. This callback stays in
   * place for the follow-up that adds a client-side Shamir +
   * Kyber pipeline — at that point `CircleSetup` will fire
   * `onComplete(circleId)` and this PATCH will populate
   * `factor_meta.recovery_setup_id`.
   *
   * @param {string} circleId
   */
  async function handleCircleComplete(circleId) {
    if (!circleId || !dekId) {
      // Surface the missing-id failure to the user instead of
      // silently transitioning to the success screen. The guardian
      // circle and factor row both exist; only the cross-reference
      // is lost, so this is a soft error (recoverable by username),
      // but it must be visible so the user knows the link is missing.
      setError(
        'Guardian circle created, but linking it to the recovery factor did '
        + 'not complete. You can still recover by username on this device.',
      );
      setPhase('done');
      return;
    }
    try {
      await recoveryFactorService.updateRecoveryFactorMeta({
        factorType: 'social_mesh',
        dekId,
        metaPatch: { recovery_setup_id: circleId },
      });
    } catch (err) {
      setError(
        err?.message
        || 'Could not link the new guardian circle to your recovery factor. '
        + 'You can still recover by username on this device.',
      );
    } finally {
      setPhase('done');
    }
  }

  if (phase === 'await-password') {
    if (TIER2_ENROLL_BLOCKED) {
      return (
        <section data-testid="social-mesh-dek-enroll">
          <h1>Set up Social-Mesh Recovery</h1>
          <p role="alert" data-testid="sm-enroll-unavailable">
            Social-Mesh enrollment is not yet available. It depends on the
            client-side Shamir + Kyber pipeline, which is on the roadmap.
            Until then, please use Recovery Key or Time-Locked recovery.
          </p>
        </section>
      );
    }
    return (
      <section data-testid="social-mesh-dek-enroll">
        <h1>Set up Social-Mesh Recovery</h1>
        <p>
          Pick 3–7 trusted guardians. With this turned on, a quorum of those guardians
          can help you recover your vault if you forget your master password. The server
          stores only opaque ciphertext; reconstruction happens in your browser.
        </p>
        <label>
          Master password
          <input
            type="password"
            value={masterPassword}
            onChange={(e) => setMasterPassword(e.target.value)}
            data-testid="sm-enroll-master-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleStart}
          disabled={busy}
          data-testid="sm-enroll-continue"
        >
          {busy ? 'Working…' : 'Continue'}
        </button>
      </section>
    );
  }

  if (phase === 'circle-setup') {
    return (
      <section data-testid="social-mesh-dek-enroll">
        <h1>Pick your Guardians</h1>
        <p>
          Your wrapped DEK is enrolled; next, choose guardians and a threshold. The
          recovery seed will be split across them via the existing social-recovery
          pipeline. None of them, individually or below threshold, can recover your vault.
        </p>
        <Suspense fallback={<p>Loading guardian picker…</p>}>
          {/* CircleSetup component owns the guardian + threshold UX
              and the call to /quantum-recovery/setup_recovery/.
              It accepts `secretType` + `secretHex` so it pre-fills
              with our seed and hides the master-secret input, and
              calls `onComplete(circleId)` once the guardian circle
              is committed server-side. We then PATCH that id back
              onto the wdek factor row's factor_meta so the recovery
              side can locate the setup. */}
          <CircleSetup
            secretType="vault_dek_seed"
            secretHex={recoverySeedHex}
            onComplete={handleCircleComplete}
          />
        </Suspense>
      </section>
    );
  }

  return (
    <section data-testid="social-mesh-dek-enroll">
      <h1>Social-mesh recovery enabled</h1>
      {error ? (
        <p role="alert" data-testid="sm-enroll-link-warning">{error}</p>
      ) : null}
      <p data-testid="sm-enroll-success">
        Your guardians have been notified. They will be asked to help if you ever start
        recovery.
      </p>
    </section>
  );
}

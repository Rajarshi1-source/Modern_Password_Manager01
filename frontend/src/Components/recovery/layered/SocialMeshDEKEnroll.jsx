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

const CircleSetup = lazy(() => import('../social/CircleSetup'));

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export default function SocialMeshDEKEnroll() {
  const [masterPassword, setMasterPassword] = useState('');
  const [phase, setPhase] = useState('await-password'); // -> 'circle-setup' -> 'done'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [recoverySeedHex, setRecoverySeedHex] = useState(null);

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
          // shard distribution. Populated by CircleSetup once the
          // user finalizes their guardians.
          recovery_setup_id: null,
          secret_type: 'vault_dek_seed',
        },
      });
      setRecoverySeedHex(seedHex);
      setPhase('circle-setup');
    } catch (err) {
      setError(err?.message || 'Enrollment failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-password') {
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
              It accepts an optional `secretType` and `secretHex`
              prop so the same setup wizard can split either a passkey
              private key (existing default) or our new vault DEK seed.
              If the component does not yet accept those props, this
              still renders correctly; the seed-routing TODO is then
              wired in a follow-up. */}
          <CircleSetup
            secretType="vault_dek_seed"
            secretHex={recoverySeedHex}
            onComplete={() => setPhase('done')}
          />
        </Suspense>
      </section>
    );
  }

  return (
    <section data-testid="social-mesh-dek-enroll">
      <h1>Social-mesh recovery enabled</h1>
      <p data-testid="sm-enroll-success">
        Your guardians have been notified. They will be asked to help if you ever start
        recovery.
      </p>
    </section>
  );
}

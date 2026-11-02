import React, { useEffect, useState } from 'react';
import ApiService from '../../../services/api';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import { ensureHybridKemReady } from '../../../services/quantum/hybridKem';
import { keyFingerprint, sealSeedForGuardians } from '../../../services/recovery/sealedShareRecovery';
import { bytesToHex } from '../../../utils/hex';

const MIN_GUARDIANS = 3;
const MAX_GUARDIANS = 10;

const emptyGuardian = () => ({ email: '', publicKey: '', fingerprintChecked: false });

function fingerprintOf(publicKey) {
  try {
    return keyFingerprint(publicKey.trim());
  } catch {
    return '';
  }
}

/**
 * Owner: choose guardians (/recovery/guardian/setup).
 *
 * Each guardian makes a key on /recovery/guardian-key and sends it here over
 * another channel. This device makes the recovery seed, wraps the vault key
 * under it, and seals one share to each guardian's key. The server gets sealed
 * shares and the wrapped key, and neither the seed nor a share.
 */
export default function GuardianSetup() {
  const [existing, setExisting] = useState(null);
  const [guardians, setGuardians] = useState(() => Array.from({ length: MIN_GUARDIANS }, emptyGuardian));
  const [threshold, setThreshold] = useState(2);
  const [masterPassword, setMasterPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invitations, setInvitations] = useState(null);

  useEffect(() => {
    ApiService.quantumRecovery.getRecoveryStatus()
      .then(({ data }) => setExisting(data))
      .catch(() => setExisting({ recovery_configured: false }));
  }, []);

  const update = (index, change) => setGuardians((list) => list.map(
    (g, i) => (i === index ? { ...g, ...change } : g),
  ));

  const problem = () => {
    if (guardians.some((g) => !g.email.trim())) return 'Enter an email for every guardian.';
    if (guardians.some((g) => !fingerprintOf(g.publicKey))) return 'A guardian key is not valid. Paste it again.';
    if (new Set(guardians.map((g) => g.publicKey.trim())).size !== guardians.length) {
      return 'Each guardian needs their own key.';
    }
    if (guardians.some((g) => !g.fingerprintChecked)) {
      return 'Check every fingerprint with its guardian by phone or in person.';
    }
    if (threshold < 2 || threshold > guardians.length) {
      return `Choose between 2 and ${guardians.length} guardians to approve a recovery.`;
    }
    if (!masterPassword) return 'Enter your master password.';
    return '';
  };

  const submit = async (e) => {
    e.preventDefault();
    const invalid = problem();
    setError(invalid);
    if (invalid) return;

    setBusy(true);
    const seed = window.crypto.getRandomValues(new Uint8Array(32));
    try {
      await ensureHybridKemReady();
      const sealed = await sealSeedForGuardians({
        seed, threshold, guardianPublicKeys: guardians.map((g) => g.publicKey.trim()),
      });
      // Before the setup: a wrong master password stops here, with nothing sent.
      await sessionVaultCryptoV3.enrollRecoveryFactor({
        factorType: 'social_mesh',
        secret: bytesToHex(seed),
        masterPassword,
        meta: { secret_type: 'vault_dek_seed' },
      });
      setMasterPassword('');
      const { data } = await ApiService.quantumRecovery.setupRecovery({
        threshold_shards: threshold,
        secret_type: 'vault_dek_seed',
        secret_check: sealed.secretCheck,
        guardians: guardians.map((g, i) => ({
          email: g.email.trim(),
          requires_video: false,
          public_key: g.publicKey.trim(),
          share_index: sealed.shares[i].shareIndex,
          sealed_share: sealed.shares[i].sealedShare,
          share_proof_hash: sealed.shares[i].shareProofHash,
        })),
      });
      setInvitations(data.shards_created);
    } catch (err) {
      setError(ApiService.handleError(err).error || err?.message || 'Could not set up guardian recovery.');
    } finally {
      seed.fill(0);
      setBusy(false);
    }
  };

  if (invitations) {
    return (
      <section data-testid="guardian-setup">
        <h1>Invitations sent</h1>
        <p data-testid="guardian-setup-done">
          We emailed each guardian an invitation. Guardian recovery turns on once
          all of them accept, within 7 days.
        </p>
        <p>If an email does not arrive, send that guardian their link yourself:</p>
        <ul>
          {invitations.map((s) => (
            <li key={s.invitation_token}>
              {s.guardian_email}:{' '}
              <code>{`${window.location.origin}/recovery/guardian-invite/${s.invitation_token}`}</code>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (!existing) return <p>Loading…</p>;

  if (existing.recovery_configured && !existing.can_replace) {
    return (
      <section data-testid="guardian-setup">
        <h1>Guardian recovery</h1>
        <p data-testid="guardian-setup-existing">
          {existing.is_active
            ? 'Guardian recovery is on for this account.'
            : 'Guardian recovery is waiting for your guardians to accept their invitations.'}
        </p>
      </section>
    );
  }

  return (
    <section data-testid="guardian-setup">
      <h1>Choose your guardians</h1>
      <p>
        If you lose your master password, enough of these people can together
        help you back in. Fewer than that cannot, and neither can we.
      </p>
      <p>
        Ask each guardian to open <code>{`${window.location.origin}/recovery/guardian-key`}</code>{' '}
        and send you the key it shows. Then compare the fingerprint below with
        theirs by phone or in person.
      </p>
      <form onSubmit={submit}>
        {guardians.map((g, i) => {
          const fingerprint = g.publicKey.trim() ? fingerprintOf(g.publicKey) : '';
          return (
            <fieldset key={i} data-testid={`guardian-setup-row-${i}`}>
              <legend>Guardian {i + 1}</legend>
              <label>
                Email
                <input type="email" value={g.email} data-testid={`guardian-setup-email-${i}`}
                  onChange={(e) => update(i, { email: e.target.value })} />
              </label>
              <label>
                Guardian key
                <textarea rows="3" className="mono" value={g.publicKey}
                  data-testid={`guardian-setup-key-${i}`}
                  onChange={(e) => update(i, { publicKey: e.target.value, fingerprintChecked: false })} />
              </label>
              {fingerprint ? (
                <label>
                  <input type="checkbox" checked={g.fingerprintChecked}
                    data-testid={`guardian-setup-fingerprint-checked-${i}`}
                    onChange={(e) => update(i, { fingerprintChecked: e.target.checked })} />
                  {' '}They read me this fingerprint: <strong className="mono">{fingerprint}</strong>
                </label>
              ) : null}
              {guardians.length > MIN_GUARDIANS ? (
                <button type="button"
                  onClick={() => setGuardians((list) => list.filter((_, j) => j !== i))}>
                  Remove
                </button>
              ) : null}
            </fieldset>
          );
        })}
        {guardians.length < MAX_GUARDIANS ? (
          <button type="button" data-testid="guardian-setup-add"
            onClick={() => setGuardians((list) => [...list, emptyGuardian()])}>
            Add a guardian
          </button>
        ) : null}
        <label>
          Guardians needed to recover
          <input type="number" min="2" max={guardians.length} value={threshold}
            data-testid="guardian-setup-threshold"
            onChange={(e) => setThreshold(Number(e.target.value))} />
        </label>
        <label>
          Master password
          <input type="password" autoComplete="current-password" value={masterPassword}
            data-testid="guardian-setup-master-password"
            onChange={(e) => setMasterPassword(e.target.value)} />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit" disabled={busy} data-testid="guardian-setup-submit">
          {busy ? 'Working…' : 'Send invitations'}
        </button>
      </form>
    </section>
  );
}

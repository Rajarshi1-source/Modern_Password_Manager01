import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import recoveryFactorService from '../../../services/recoveryFactorService';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import { ensureHybridKemReady } from '../../../services/quantum/hybridKem';
import {
  forgetRequesterKeyPair,
  loadRequesterKeyPair,
} from '../../../services/recovery/holderKeyStore';
import {
  keyFingerprint,
  recoverSeed,
  requesterToken,
} from '../../../services/recovery/sealedShareRecovery';
import { bytesToHex } from '../../../utils/hex';

const ATTEMPT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const KEY_FINGERPRINT = /^[0-9A-F]{4}(-[0-9A-F]{4}){4}$/;
const STOPPED = { cancelled: 'was cancelled', failed: 'failed', expired: 'expired' };

const shell = (children) => (
  <section data-testid="guardian-recovery-attempt">
    <h1>Guardian recovery</h1>
    {children}
  </section>
);

/**
 * The link in the guardian recovery email
 * (/recovery/guardian-attempt?attempt=<id>&key=<fingerprint>), and the rest of
 * the requester's recovery.
 *
 * Acting on the attempt takes the ID from the email and a token only the
 * browser that started it can derive from its one-time key. That browser asks
 * the guardians, reads the code out to them, and after the wait opens their
 * re-sealed shares and rewraps the vault under a new master password. The
 * server never sees the seed.
 */
export default function GuardianRecoveryAttempt() {
  const [params] = useSearchParams();
  const attemptId = params.get('attempt') || '';
  const fingerprint = params.get('key') || '';

  const [keyMissing, setKeyMissing] = useState(false);
  const [token, setToken] = useState('');
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [factor, setFactor] = useState(null);
  const [seedHex, setSeedHex] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [done, setDone] = useState(false);
  // Kept while the username is retried: fetching the shares again uses up the
  // hourly recovery limit.
  const recombined = useRef('');

  const validLink = ATTEMPT_ID.test(attemptId) && KEY_FINGERPRINT.test(fingerprint);

  const describe = (err, fallback) => (err?.response?.status === 429
    ? 'Too many tries from this network. Wait a while and try again.'
    : ApiService.handleError(err).error || fallback);

  const refresh = useCallback(async (requesterTokenValue) => {
    const { data } = await ApiService.quantumRecovery.recoveryProgress({
      attempt_id: attemptId, requester_token: requesterTokenValue,
    });
    setProgress(data);
  }, [attemptId]);

  useEffect(() => {
    if (!validLink) return undefined;
    let current = true;
    (async () => {
      let value = '';
      try {
        const keyPair = await loadRequesterKeyPair(fingerprint);
        if (keyPair && keyFingerprint(keyPair.publicKey) === fingerprint) {
          value = requesterToken(keyPair);
        }
      } catch {
        // A key this browser can no longer unwrap or read is as good as none
      }
      if (!current) return;
      if (!value) {
        setKeyMissing(true);
        return;
      }
      setToken(value);
      try {
        await refresh(value);
      } catch (err) {
        if (current) setError(describe(err, 'This recovery cannot be opened. Start again.'));
      }
    })();
    return () => { current = false; };
  }, [validLink, fingerprint, refresh]);

  const run = async (fn, fallback) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (err) {
      setError(describe(err, fallback));
    } finally {
      setBusy(false);
    }
  };

  const confirm = () => run(async () => {
    const { data } = await ApiService.quantumRecovery.confirmRecovery({
      attempt_id: attemptId, requester_token: token,
    });
    setProgress(data);
  }, 'Could not ask your guardians. Try again.');

  const check = () => run(() => refresh(token), 'Could not check this recovery. Try again.');

  const recover = (e) => {
    e.preventDefault();
    return run(async () => {
      if (!recombined.current) {
        const { data } = await ApiService.quantumRecovery.completeRecovery({
          attempt_id: attemptId, requester_token: token,
        });
        await ensureHybridKemReady();
        const keyPair = await loadRequesterKeyPair(fingerprint);
        let seed;
        try {
          seed = await recoverSeed({
            keyPair,
            sealedShares: data.sealed_shares.map((s) => s.sealed_share),
            threshold: data.threshold,
            secretCheck: data.secret_check,
          });
        } catch {
          throw new Error('Your guardians’ shares did not recombine. Start recovery again.');
        }
        recombined.current = bytesToHex(seed);
        seed.fill(0);
      }
      const recoveredHex = recombined.current;
      // A decoy for an unknown username, so a wrong one fails at the unwrap.
      const wrapped = await recoveryFactorService.lookupRecoveryFactor(username.trim(), 'social_mesh');
      await sessionVaultCryptoV3.unlockWithRecoveryFactor(wrapped.blob, recoveredHex, wrapped.dek_id);
      recombined.current = '';
      setFactor(wrapped);
      setSeedHex(recoveredHex);
    }, 'Could not recover. Check the username in the email and try again.');
  };

  const setPassword = (e) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return undefined;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return undefined;
    }
    return run(async () => {
      await sessionVaultCryptoV3.rewrapMasterPasswordFromRecovery({
        factorBlob: factor.blob,
        recoverySecret: seedHex,
        newPassword,
        dekId: factor.dek_id,
        username: username.trim(),
        factorType: 'social_mesh',
      });
      forgetRequesterKeyPair(fingerprint);
      setSeedHex('');
      setNewPassword('');
      setConfirmPassword('');
      setDone(true);
    }, 'Could not change your master password. Try again.');
  };

  const errorLine = error ? <p role="alert">{error}</p> : null;

  if (!validLink) {
    return shell(<p role="alert">This link is incomplete. Open the link from the email again.</p>);
  }
  if (keyMissing) {
    return shell(
      <>
        <p role="alert" data-testid="guardian-recovery-other-device">
          This browser did not start this recovery, so it cannot finish it. Open
          the link in the browser you started from.
        </p>
        <p>If you did not start this recovery, use the cancel link in the same email.</p>
      </>,
    );
  }
  if (done) {
    return shell(
      <p data-testid="guardian-recovery-done">
        Your vault is unlocked and your master password is changed. Sign in with
        the new master password from now on; your other sessions were signed out.
      </p>,
    );
  }
  if (seedHex) {
    return shell(
      <form onSubmit={setPassword}>
        <h2>Set a new master password</h2>
        <label>
          New master password
          <input type="password" autoComplete="new-password" value={newPassword}
            data-testid="guardian-recovery-new-password"
            onChange={(e) => setNewPassword(e.target.value)} />
        </label>
        <label>
          Confirm
          <input type="password" autoComplete="new-password" value={confirmPassword}
            data-testid="guardian-recovery-confirm-password"
            onChange={(e) => setConfirmPassword(e.target.value)} />
        </label>
        {errorLine}
        <button type="submit" disabled={busy} data-testid="guardian-recovery-set-password">
          {busy ? 'Saving…' : 'Continue'}
        </button>
      </form>,
    );
  }
  if (!progress) return shell(errorLine || <p>Loading…</p>);

  if (STOPPED[progress.status]) {
    return shell(
      <p role="alert" data-testid="guardian-recovery-stopped">
        This recovery {STOPPED[progress.status]}. Start a new one if you still need it.
      </p>,
    );
  }

  if (progress.status === 'initiated') {
    return shell(
      <>
        <p>
          Your guardians are asked only after you say this is you. If you did not
          start this recovery, use the cancel link in the email instead.
        </p>
        {errorLine}
        <button type="button" onClick={confirm} disabled={busy} data-testid="guardian-recovery-confirm">
          {busy ? 'Working…' : 'This is me: ask my guardians'}
        </button>
      </>,
    );
  }

  return shell(
    <>
      <p>
        Call or meet your guardians and read them this code. They need it to
        approve, and should refuse a request without it:
      </p>
      <p><strong className="mono" data-testid="guardian-recovery-code">{fingerprint}</strong></p>
      <p data-testid="guardian-recovery-progress">
        {progress.approvals_received} of {progress.threshold} approvals received
        {progress.denials ? `, ${progress.denials} denied` : ''}.
      </p>
      {progress.ask_again ? (
        <button type="button" onClick={confirm} disabled={busy}>Ask my guardians again</button>
      ) : null}
      {progress.ready ? (
        <form onSubmit={recover}>
          <label>
            Username, as written in the email
            <input type="text" autoComplete="username" value={username}
              data-testid="guardian-recovery-username"
              onChange={(e) => setUsername(e.target.value)} />
          </label>
          {errorLine}
          <button type="submit" disabled={busy || !username.trim()} data-testid="guardian-recovery-recover">
            {busy ? 'Working…' : 'Recover my vault'}
          </button>
        </form>
      ) : (
        <>
          <p data-testid="guardian-recovery-wait">
            {progress.release_after ? (
              <>
                For your protection, recovery cannot finish before{' '}
                {new Date(progress.release_after).toLocaleString()}, so you have time to
                stop anything you did not start.
              </>
            ) : 'Recovery cannot finish yet: the alert to your account’s email is not on record. Check again later.'}
          </p>
          {errorLine}
          <button type="button" onClick={check} disabled={busy} data-testid="guardian-recovery-check">
            {busy ? 'Checking…' : 'Check again'}
          </button>
        </>
      )}
    </>,
  );
}

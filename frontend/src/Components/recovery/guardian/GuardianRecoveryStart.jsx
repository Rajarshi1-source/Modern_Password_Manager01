import React, { useState } from 'react';
import ApiService from '../../../services/api';
import { ensureHybridKemReady } from '../../../services/quantum/hybridKem';
import {
  assertKeyStorageAvailable,
  newRequesterKeyPair,
  saveRequesterKeyPair,
} from '../../../services/recovery/holderKeyStore';
import { keyFingerprint, requesterTokenHash } from '../../../services/recovery/sealedShareRecovery';

/**
 * Requester: start guardian recovery (/recovery/guardian/start).
 *
 * The answer is the same for every email, so the attempt ID is not known here:
 * the one-time key is stored under its own fingerprint, which the emailed link
 * carries back to this browser.
 */
export default function GuardianRecoveryStart() {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await assertKeyStorageAvailable();
      await ensureHybridKemReady();
      const keyPair = await newRequesterKeyPair();
      await saveRequesterKeyPair(keyFingerprint(keyPair.publicKey), keyPair);
      const { data } = await ApiService.quantumRecovery.initiateRecovery({
        email: email.trim(),
        requester_public_key: keyPair.publicKey,
        requester_token_hash: requesterTokenHash(keyPair),
      });
      setMessage(data.message);
    } catch (err) {
      setError(ApiService.handleError(err).error || err?.message || 'Could not start recovery.');
    } finally {
      setBusy(false);
    }
  };

  if (message) {
    return (
      <section data-testid="guardian-recovery-start">
        <h1>Check your email</h1>
        <p data-testid="guardian-recovery-start-message">{message}</p>
        <p>
          Open the link in this browser, not on another device: a key that opens
          your guardians&apos; shares is stored only here. Do not clear this
          site&apos;s data until you are finished.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="guardian-recovery-start">
      <h1>Recover with your guardians</h1>
      <p>
        Use this if you set up guardian recovery and can no longer sign in. Your
        guardians will each need to approve, and your account is released after a
        waiting period that lets you stop anything you did not start.
      </p>
      <form onSubmit={submit}>
        <label>
          Account email
          <input type="email" required value={email} data-testid="guardian-recovery-start-email"
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit" disabled={busy || !email.trim()} data-testid="guardian-recovery-start-submit">
          {busy ? 'Working…' : 'Continue'}
        </button>
      </form>
    </section>
  );
}

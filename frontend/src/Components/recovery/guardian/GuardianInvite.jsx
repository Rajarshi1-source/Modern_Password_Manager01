import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import { ensureHybridKemReady } from '../../../services/quantum/hybridKem';
import { loadGuardianKeyPair } from '../../../services/recovery/holderKeyStore';
import { proveShareHolding } from '../../../services/recovery/sealedShareRecovery';

/**
 * Guardian: accept an invitation (/recovery/guardian-invite/:token). Opening
 * the sealed share here proves this browser holds the key it was sealed to, so
 * nobody becomes a guardian with a share they could never open.
 */
export default function GuardianInvite() {
  const { token } = useParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [accepted, setAccepted] = useState(false);

  const accept = async () => {
    setBusy(true);
    setError('');
    try {
      const keyPair = await loadGuardianKeyPair();
      if (!keyPair) {
        setError('This browser has no guardian key. Open this link in the browser that made the key you sent.');
        return;
      }
      const { data } = await ApiService.quantumRecovery.getGuardianInvitation(token);
      await ensureHybridKemReady();
      let shareProof;
      try {
        shareProof = await proveShareHolding({ keyPair, sealedShare: data.sealed_share });
      } catch {
        setError('This browser cannot open the share sealed for you. Open this link in the '
          + 'browser that made the key you sent.');
        return;
      }
      await ApiService.quantumRecovery.acceptGuardianInvitation({
        invitation_token: token, share_proof: shareProof,
      });
      setAccepted(true);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Could not accept this invitation.');
    } finally {
      setBusy(false);
    }
  };

  if (accepted) {
    return (
      <section data-testid="guardian-invite">
        <h1>You are a guardian</h1>
        <p data-testid="guardian-invite-accepted">
          If this person ever needs to recover their account, we will email you.
          Approve from this browser, and keep its data: your key is stored only
          here.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="guardian-invite">
      <h1>Become a recovery guardian</h1>
      <p>
        Someone chose you to help them recover their account. Accept only if you
        know them and gave them your guardian key. You will never be able to read
        their data.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      <button type="button" onClick={accept} disabled={busy} data-testid="guardian-invite-accept">
        {busy ? 'Working…' : 'Accept'}
      </button>
    </section>
  );
}

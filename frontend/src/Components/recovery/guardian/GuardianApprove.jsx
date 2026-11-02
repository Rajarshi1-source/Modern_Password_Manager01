import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import { ensureHybridKemReady } from '../../../services/quantum/hybridKem';
import { loadGuardianKeyPair } from '../../../services/recovery/holderKeyStore';
import { resealShareForRequester } from '../../../services/recovery/sealedShareRecovery';

/**
 * Guardian: answer a recovery request (/recovery/guardian-approve/:token).
 *
 * The share is opened and re-sealed to the requester's one-time key here. The
 * server relays that key, so the code read out by the requester over another
 * channel is what stops a substituted key getting the share.
 */
export default function GuardianApprove() {
  const { token } = useParams();
  const [request, setRequest] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [answer, setAnswer] = useState('');

  useEffect(() => {
    ApiService.quantumRecovery.getGuardianShare(token)
      .then(({ data }) => setRequest(data))
      .catch((err) => setLoadError(ApiService.handleError(err).error || 'This request cannot be opened.'));
  }, [token]);

  const deny = async () => {
    setBusy(true);
    setError('');
    try {
      await ApiService.quantumRecovery.approveRecovery({ approval_token: token, approved: false });
      setAnswer('denied');
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Could not send your answer.');
    } finally {
      setBusy(false);
    }
  };

  const approve = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const keyPair = await loadGuardianKeyPair();
      if (!keyPair) {
        setError('This browser has no guardian key. Open this link in the browser where you accepted the invitation.');
        return;
      }
      await ensureHybridKemReady();
      let resealedShare;
      try {
        resealedShare = await resealShareForRequester({
          keyPair,
          sealedShare: request.sealed_share,
          requesterPublicKey: request.requester_public_key,
          confirmedFingerprint: code,
        });
      } catch (err) {
        setError(/fingerprint/.test(err?.message || '')
          ? 'That code does not match this request. Do not approve: confirm the code with the person directly.'
          : "Could not open your share with this browser's guardian key.");
        return;
      }
      await ApiService.quantumRecovery.approveRecovery({
        approval_token: token, approved: true, resealed_share: resealedShare,
      });
      setAnswer('approved');
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Could not send your answer.');
    } finally {
      setBusy(false);
    }
  };

  if (answer) {
    return (
      <section data-testid="guardian-approve">
        <h1>Thank you</h1>
        <p data-testid="guardian-approve-result">
          {answer === 'approved'
            ? 'You approved this recovery. Your share is sealed so only the person you spoke to can open it.'
            : 'You denied this recovery. Your share was not released.'}
        </p>
      </section>
    );
  }
  if (loadError) {
    return (
      <section data-testid="guardian-approve">
        <h1>Recovery request</h1>
        <p role="alert">{loadError}</p>
      </section>
    );
  }
  if (!request) return <p>Loading…</p>;

  return (
    <section data-testid="guardian-approve">
      <h1>Recovery request</h1>
      <p>
        Call or meet the person named in the email before you answer. An email or
        text message is not enough, because their accounts may be what someone has
        taken over. If they did not start this, deny it.
      </p>
      <form onSubmit={approve}>
        <label>
          The code they read to you
          <input type="text" className="mono" value={code} placeholder="XXXX-XXXX-XXXX-XXXX-XXXX"
            autoComplete="off" data-testid="guardian-approve-code"
            onChange={(e) => setCode(e.target.value)} />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit" disabled={busy || !code.trim()} data-testid="guardian-approve-submit">
          {busy ? 'Working…' : 'Approve'}
        </button>
        <button type="button" onClick={deny} disabled={busy} data-testid="guardian-approve-deny">
          Deny
        </button>
      </form>
    </section>
  );
}

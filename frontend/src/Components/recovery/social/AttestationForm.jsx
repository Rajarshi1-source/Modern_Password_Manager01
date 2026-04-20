import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import './AttestationForm.css';

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

const AttestationForm = () => {
  const { requestId } = useParams();

  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [voucherId, setVoucherId] = useState('');
  const [decision, setDecision] = useState('approve');
  const [signatureB64, setSignatureB64] = useState('');
  const [freshCommitmentB64, setFreshCommitmentB64] = useState('');
  const [proofTB64, setProofTB64] = useState('');
  const [proofSB64, setProofSB64] = useState('');
  const [stakeAmount, setStakeAmount] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const loadRequest = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await ApiService.socialRecovery.getRequest(requestId);
      setRequest(resp.data);
      setError(null);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to load request.');
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    loadRequest();
  }, [loadRequest]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (decision === 'approve') {
        if (!freshCommitmentB64 || !proofTB64 || !proofSB64) {
          setError(
            'Approval requires a Schnorr equality proof: provide fresh_commitment, proof_T, and proof_s.'
          );
          setSubmitting(false);
          return;
        }
      }
      const payload = {
        voucher_id: voucherId,
        decision,
        signature_b64: signatureB64,
        stake_amount: Number(stakeAmount) || 0,
      };
      if (decision === 'approve') {
        payload.fresh_commitment_b64 = freshCommitmentB64;
        payload.proof_T_b64 = proofTB64;
        payload.proof_s_b64 = proofSB64;
      } else {
        if (freshCommitmentB64) payload.fresh_commitment_b64 = freshCommitmentB64;
        if (proofTB64) payload.proof_T_b64 = proofTB64;
        if (proofSB64) payload.proof_s_b64 = proofSB64;
      }

      const resp = await ApiService.socialRecovery.submitAttestation(
        requestId,
        payload
      );
      setResult(resp.data);
      await loadRequest();
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to submit attestation.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="attestation-form placeholder">Loading recovery request...</div>;

  if (!request) {
    return (
      <div className="attestation-form error-state">
        <h2>❌ Request not found</h2>
        <p>{error}</p>
      </div>
    );
  }

  const isFinal = ['completed', 'cancelled', 'expired', 'denied', 'rejected'].includes(request.status);

  return (
    <div className="attestation-form">
      <header>
        <h1>🗳️ Guardian Attestation</h1>
        <p className="lede">
          Review the recovery request and submit your approval or denial.
          Your Ed25519 signature authenticates the decision.
        </p>
      </header>

      <section className="request-summary">
        <h3>Recovery Request</h3>
        <dl>
          <dt>Request ID</dt><dd className="mono">{request.request_id}</dd>
          <dt>Status</dt><dd><span className={`status ${request.status}`}>{request.status}</span></dd>
          <dt>Initiator</dt><dd>{request.initiator_email || '—'}</dd>
          <dt>Challenge Nonce</dt><dd className="mono">{request.challenge_nonce}</dd>
          <dt>Required Approvals</dt><dd>{request.required_approvals}</dd>
          <dt>Received Approvals</dt><dd>{request.received_approvals}</dd>
          <dt>Risk Score</dt><dd>{request.risk_score ?? '—'}</dd>
          <dt>Expires</dt><dd>{formatDate(request.expires_at)}</dd>
        </dl>
      </section>

      {result && (
        <div className="result-banner success">
          ✅ Attestation submitted. Request is now{' '}
          <strong>{result.request_status}</strong> ({result.received_approvals}{' '}
          approvals).
        </div>
      )}

      {!isFinal && (
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Your Voucher ID</label>
            <input
              type="text"
              value={voucherId}
              onChange={(e) => setVoucherId(e.target.value.trim())}
              placeholder="UUID of your voucher in this circle"
              required
              className="mono"
            />
          </div>

          <div className="form-group">
            <label>Decision</label>
            <div className="decision-toggle">
              <button
                type="button"
                className={decision === 'approve' ? 'active approve' : ''}
                onClick={() => setDecision('approve')}
              >
                ✓ Approve
              </button>
              <button
                type="button"
                className={decision === 'deny' ? 'active deny' : ''}
                onClick={() => setDecision('deny')}
              >
                ✗ Deny
              </button>
            </div>
          </div>

          <div className="form-group">
            <label>Ed25519 Signature (base64)</label>
            <textarea
              rows="3"
              value={signatureB64}
              onChange={(e) => setSignatureB64(e.target.value)}
              placeholder="base64 signature of challenge_nonce || decision"
              required
            />
          </div>

          {decision === 'approve' ? (
            <fieldset className="zk-proof-fields">
              <legend>ZK Relationship Proof (required for approval)</legend>
              <div className="form-group">
                <label>Fresh Commitment (base64)</label>
                <input
                  type="text"
                  value={freshCommitmentB64}
                  onChange={(e) => setFreshCommitmentB64(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Proof T (base64)</label>
                <input
                  type="text"
                  value={proofTB64}
                  onChange={(e) => setProofTB64(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Proof s (base64)</label>
                <input
                  type="text"
                  value={proofSB64}
                  onChange={(e) => setProofSB64(e.target.value)}
                  required
                />
              </div>
            </fieldset>
          ) : (
            <details>
              <summary>Advanced: ZK Relationship Proof (optional for denial)</summary>
              <div className="form-group">
                <label>Fresh Commitment (base64)</label>
                <input
                  type="text"
                  value={freshCommitmentB64}
                  onChange={(e) => setFreshCommitmentB64(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Proof T (base64)</label>
                <input
                  type="text"
                  value={proofTB64}
                  onChange={(e) => setProofTB64(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Proof s (base64)</label>
                <input
                  type="text"
                  value={proofSB64}
                  onChange={(e) => setProofSB64(e.target.value)}
                />
              </div>
            </details>
          )}

          <div className="form-group">
            <label>Stake Amount (optional)</label>
            <input
              type="number"
              min="0"
              value={stakeAmount}
              onChange={(e) => setStakeAmount(e.target.value)}
            />
          </div>

          {error && <div className="error-banner">❌ {error}</div>}

          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Attestation'}
          </button>
        </form>
      )}

      {isFinal && (
        <div className="terminal-banner">
          This request is <strong>{request.status}</strong>. No further
          attestations can be submitted.
        </div>
      )}

      {request.attestations?.length > 0 && (
        <section className="attestation-log">
          <h3>Prior Attestations ({request.attestations.length})</h3>
          <ul>
            {request.attestations.map((a) => (
              <li key={a.attestation_id}>
                <span className={`decision ${a.decision}`}>{a.decision}</span>
                <span className="mono">
                  {String(a.voucher).slice(0, 8)}…
                </span>
                <span className="time">{formatDate(a.attested_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default AttestationForm;

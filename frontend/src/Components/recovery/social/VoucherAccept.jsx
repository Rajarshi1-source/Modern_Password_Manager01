import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import './VoucherAccept.css';

const VoucherAccept = () => {
  const { invitationToken } = useParams();
  const [signatureB64, setSignatureB64] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAccept = async (e) => {
    e.preventDefault();
    setError(null);

    if (!signatureB64.trim()) {
      setError('Please paste the Ed25519 signature (base64) of the invitation token.');
      return;
    }

    setSubmitting(true);
    try {
      const resp = await ApiService.socialRecovery.acceptVoucher(
        invitationToken,
        { signature_b64: signatureB64.trim() }
      );
      setResult(resp.data);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to accept invitation.');
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <div className="voucher-accept success">
        <h1>✅ Invitation Accepted</h1>
        <p>You are now registered as a voucher in this recovery circle.</p>
        <dl className="result-grid">
          <dt>Voucher ID</dt>
          <dd className="mono">{result.voucher_id}</dd>
          <dt>Circle ID</dt>
          <dd className="mono">{result.circle_id}</dd>
          <dt>Status</dt>
          <dd>{result.status}</dd>
        </dl>
        <p className="note">
          When the circle owner initiates recovery, you&apos;ll receive a
          request to attest — you can approve or deny from the attestation
          page.
        </p>
      </div>
    );
  }

  return (
    <div className="voucher-accept">
      <h1>🤝 Accept Guardian Invitation</h1>
      <p className="lede">
        You&apos;ve been invited to serve as a voucher in a social-recovery
        circle. To accept, sign the invitation token below with your Ed25519
        private key and paste the base64 signature.
      </p>

      <form onSubmit={handleAccept}>
        <div className="form-group">
          <label>Invitation Token</label>
          <input type="text" value={invitationToken} readOnly className="mono" />
        </div>

        <div className="form-group">
          <label>Ed25519 Signature (base64)</label>
          <textarea
            rows="4"
            value={signatureB64}
            onChange={(e) => setSignatureB64(e.target.value)}
            placeholder="base64-encoded signature over the invitation token"
            required
          />
          <small>
            Produced locally — sign the UTF-8 bytes of the invitation token
            string with the private key matching the public key the circle
            owner registered for you.
          </small>
        </div>

        {error && <div className="error-banner">❌ {error}</div>}

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Verifying...' : 'Accept Invitation'}
        </button>
      </form>
    </div>
  );
};

export default VoucherAccept;

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import DeviceFingerprint from '../../../utils/deviceFingerprint';
import ApiService from '../../../services/api';
import './RecoveryInitiation.css';

export const RecoveryInitiation = () => {
  const [email, setEmail] = useState('');
  const [circleId, setCircleId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleInitiateRecovery = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let deviceFingerprint = '';
      try {
        deviceFingerprint = await DeviceFingerprint.generate();
      } catch {
        /* noop — proceed without fingerprint */
      }

      const resp = await ApiService.socialRecovery.initiateRequest({
        circle_id: circleId.trim(),
        initiator_email: email,
        device_fingerprint: deviceFingerprint,
        geo: {},
      });

      const requestId = resp.data?.request_id;
      if (!requestId) throw new Error('Server did not return a request id');
      navigate(`/recovery/social/progress/${requestId}`);
    } catch (err) {
      const handled = ApiService.handleError(err);
      setError(handled.error || 'Failed to initiate recovery');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recovery-initiation">
      <div className="recovery-header">
        <h1>🛡️ Social Recovery</h1>
        <p className="subtitle">
          Request recovery by proving your identity to your guardian network.
        </p>
      </div>

      <div className="recovery-card">
        <div className="info-section">
          <h3>How it works:</h3>
          <ol>
            <li>We notify each guardian in your recovery circle.</li>
            <li>Guardians attest (approve/deny) by signing a challenge.</li>
            <li>Once the threshold is met, your shares are reconstructed.</li>
          </ol>

          <div className="warning-box">
            <strong>⚠️ Canary:</strong> A canary alert is emitted to the
            circle owner on initiation. If you didn&apos;t request this,
            cancel from the circle dashboard.
          </div>
        </div>

        <form onSubmit={handleInitiateRecovery} className="recovery-form">
          <div className="form-group">
            <label htmlFor="circleId">Circle ID</label>
            <input
              id="circleId"
              type="text"
              value={circleId}
              onChange={(e) => setCircleId(e.target.value)}
              placeholder="UUID of the recovery circle"
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              disabled={loading}
            />
          </div>

          {error && (
            <div className="error-message">❌ {error}</div>
          )}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? (
              <>
                <span className="spinner"></span>
                Initiating Recovery...
              </>
            ) : (
              'Start Recovery'
            )}
          </button>
        </form>

        <div className="help-text">
          <p>Need help? Contact support@securevault.com</p>
        </div>
      </div>
    </div>
  );
};

export default RecoveryInitiation;

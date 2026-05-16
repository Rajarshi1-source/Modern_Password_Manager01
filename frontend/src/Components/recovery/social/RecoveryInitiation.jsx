import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import DeviceFingerprint from '../../../utils/deviceFingerprint';
import ApiService from '../../../services/api';
import './RecoveryInitiation.css';

/**
 * Social-recovery initiation form. Used in two routes:
 *
 *   1. Legacy passkey recovery (/recovery/social/initiate): the
 *      component manages its own email/circleId state and navigates
 *      to /recovery/social/progress/:requestId on success.
 *
 *   2. Layered Recovery Mesh tier-2 (/recovery/social-mesh/recover-v2):
 *      `SocialMeshDEKRecover` composes this component and supplies
 *      callback props so it can drive its own state machine
 *      (`await-username` → `in-progress` → `change-password` →
 *      `done`) without route navigation.
 *
 * Both modes are supported through optional props that default to
 * the legacy navigate-based behavior — back-compat is preserved.
 *
 * @param {object} [props]
 * @param {string} [props.email]               Controlled email value.
 * @param {(email: string) => void} [props.onEmailChange]
 * @param {(requestId: string) => void} [props.onInitiated]
 *   When provided, called with the server-issued `request_id`
 *   INSTEAD of navigating. The caller is responsible for advancing
 *   its own phase. When absent, the legacy navigate-to-progress
 *   behavior fires.
 */
export const RecoveryInitiation = ({
  email: controlledEmail,
  onEmailChange,
  onInitiated,
} = {}) => {
  const [internalEmail, setInternalEmail] = useState('');
  const [circleId, setCircleId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  // Bridge controlled / uncontrolled. We only enter controlled mode
  // when the parent supplies BOTH `email` and a working `onEmailChange`
  // setter — otherwise the input would silently become read-only when
  // a parent passes `email` without a setter.
  const isControlled =
    controlledEmail !== undefined && typeof onEmailChange === 'function';
  const email = isControlled ? controlledEmail : internalEmail;
  const setEmail = (value) => {
    if (isControlled) onEmailChange(value);
    else setInternalEmail(value);
  };

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
      // Hand the request_id to the caller's state machine if the
      // tier-2 wrapper opted in. Otherwise navigate to the legacy
      // progress route.
      if (typeof onInitiated === 'function') {
        onInitiated(requestId);
      } else {
        navigate(`/recovery/social/progress/${requestId}`);
      }
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

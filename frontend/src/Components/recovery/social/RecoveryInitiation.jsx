import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import DeviceFingerprint from '../../../utils/deviceFingerprint';
import ApiService from '../../../services/api';
import {
  newRequesterKeyPair,
  saveRequesterKeyPair,
} from '../../../services/recovery/holderKeyStore';
import { keyFingerprint } from '../../../services/recovery/sealedShareRecovery';
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
  // Shown after initiation and read to each guardian over another channel,
  // so a guardian re-seals only to this device's key.
  const [fingerprint, setFingerprint] = useState(null);
  const [startedRequestId, setStartedRequestId] = useState(null);
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

      // One-time key pair: guardians re-seal their shares to its public
      // half; the private half never leaves this device.
      const keyPair = await newRequesterKeyPair();
      const resp = await ApiService.socialRecovery.initiateRequest({
        circle_id: circleId.trim(),
        initiator_email: email,
        device_fingerprint: deviceFingerprint,
        geo: {},
        requester_public_key: keyPair.publicKey,
      });

      const requestId = resp.data?.request_id;
      if (!requestId) throw new Error('Server did not return a request id');
      saveRequesterKeyPair(requestId, keyPair);
      setFingerprint(keyFingerprint(keyPair.publicKey));
      setStartedRequestId(requestId);
    } catch (err) {
      const handled = ApiService.handleError(err);
      setError(handled.error || 'Failed to initiate recovery');
    } finally {
      setLoading(false);
    }
  };

  const continueToProgress = () => {
    // Hand the request_id to the caller's state machine if the tier-2
    // wrapper opted in. Otherwise navigate to the legacy progress route.
    if (typeof onInitiated === 'function') {
      onInitiated(startedRequestId);
    } else {
      navigate(`/recovery/social/progress/${startedRequestId}`);
    }
  };

  if (fingerprint) {
    return (
      <div className="recovery-initiation">
        <div className="recovery-card">
          <h3>Read this code to each guardian</h3>
          <p className="mono" data-testid="requester-key-fingerprint">{fingerprint}</p>
          <p>
            Tell it to your guardians by phone or in person, not through this
            site. A guardian only releases a share to the device that shows
            this code. Keep this browser open on this device until recovery
            finishes.
          </p>
          <button type="button" className="btn-primary" onClick={continueToProgress}>
            Continue
          </button>
        </div>
      </div>
    );
  }

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
            <li>Once the threshold is met, this device recombines your shares.</li>
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
              // The legacy backend (InitiateRequestSerializer) allows
              // initiator_email to be omitted/blank, and the legacy
              // /recovery/social/initiate route relied on that. The
              // tier-2 wrapper, however, drives downstream factor
              // lookup off this value and cannot accept a blank
              // string. So we require the field only in controlled
              // mode (tier-2) and leave it optional on the legacy
              // route — matching prior UX and serializer behavior.
              required={isControlled}
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

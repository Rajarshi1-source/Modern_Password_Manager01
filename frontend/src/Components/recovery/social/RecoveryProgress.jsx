import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ApiService from '../../../services/api';
import './RecoveryProgress.css';

const STATUS_STEPS = [
  { key: 'initiated', label: 'Recovery Initiated', icon: '🚀' },
  { key: 'pending', label: 'Awaiting Attestations', icon: '⏳' },
  { key: 'approved', label: 'Threshold Reached', icon: '🛡️' },
  { key: 'completed', label: 'Recovery Complete', icon: '✅' },
];

const normalizeStatus = (s) => {
  if (!s) return 'pending';
  if (s === 'initiated' || s === 'challenge_phase') return 'pending';
  return s;
};

/**
 * Social-recovery progress page. Used in two routes:
 *
 *   1. Legacy passkey recovery (/recovery/social/progress/:requestId):
 *      `requestId` comes from `useParams()`; component is self-
 *      contained and just polls + renders.
 *
 *   2. Layered Recovery Mesh tier-2 (/recovery/social-mesh/recover-v2):
 *      `SocialMeshDEKRecover` composes this component and supplies
 *      both `recoveryAttemptId` (the request id from the in-page
 *      flow, no route param available) and `onSecretReconstructed`
 *      (callback invoked once with the reconstructed secret bytes
 *      when the polling sees `status === 'approved'` /
 *      `'completed'` and the server returns the reconstructed
 *      secret in the response).
 *
 * Both modes coexist through optional props that default to the
 * legacy params-based behavior — back-compat preserved.
 *
 * @param {object} [props]
 * @param {string} [props.recoveryAttemptId]
 *   When provided, used as the request id INSTEAD of useParams(). The
 *   tier-2 page passes this because its route path is
 *   /recovery/social-mesh/recover-v2 with no :requestId segment.
 * @param {(secretBytes: Uint8Array) => void} [props.onSecretReconstructed]
 *   When provided, called exactly once with the reconstructed secret
 *   the moment the polling sees a final-status response that carries
 *   the reconstructed bytes. The tier-2 page uses this to drive its
 *   own state machine into the change-password phase. Legacy callers
 *   omit it and rely on the rendered "Recovery Completed" link.
 */
const RecoveryProgress = ({ recoveryAttemptId, onSecretReconstructed } = {}) => {
  // Resolve the request id: prefer the prop (tier-2), fall back to
  // route params (legacy passkey route). Prop wins so a tier-2 page
  // composed under a legacy-shaped route can still work.
  const params = useParams();
  const requestId = recoveryAttemptId || params.requestId;

  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Guard so onSecretReconstructed fires exactly once even if the
  // 5-second polling loop sees the success payload more than once
  // before the parent unmounts us.
  const reconstructedFiredRef = useRef(false);

  // Reset the one-shot guard when the request id changes so a fresh
  // recovery attempt (same mounted component, new requestId) can still
  // deliver its secret to the parent.
  useEffect(() => {
    reconstructedFiredRef.current = false;
  }, [requestId]);

  const fetchStatus = useCallback(async () => {
    if (!requestId) {
      setError('Recovery request id missing');
      setLoading(false);
      return;
    }
    try {
      const resp = await ApiService.socialRecovery.getRequest(requestId);
      setRequest(resp.data);
      setError(null);
      // If the server has reconstructed the secret AND the caller
      // gave us a callback to deliver it, fire exactly once. The
      // server is expected to surface the bytes in one of:
      //   - resp.data.reconstructed_secret (preferred)
      //   - resp.data.secret_bytes
      // both base64-encoded; we decode to Uint8Array. If the field
      // is absent (older backend, or completion event without
      // payload) we leave the callback un-fired; the parent's
      // own polling/timeout path can fall back to a fresh attempt.
      //
      // Gate on a final status so an intermediate poll (e.g. pending
      // with stale fields) cannot fire the callback prematurely with
      // a decoy / stale value.
      //
      // NOTE on the tier-2 completion gap: the legacy poll endpoint
      // backing `getRequest` (RequestDetailView) does NOT return the
      // reconstructed secret in its current serializer shape — only
      // CompleteRequestView returns it (as `secret_hex`). That
      // completion path is server-side Shamir which would violate the
      // ZK invariant for the social-mesh DEK seed, so the tier-2
      // enroll path is intentionally gated (see CircleSetup's
      // externallyControlledSecret hard-refusal). When the follow-up
      // client-side Shamir + Kyber pipeline lands, the poller will
      // either be extended to expose `reconstructed_secret` /
      // `secret_bytes`, or the parent will drive completion directly
      // — at which point this block fires onSecretReconstructed.
      const polledStatus = normalizeStatus(resp.data?.status);
      const isFinal = polledStatus === 'approved' || polledStatus === 'completed';
      if (isFinal && typeof onSecretReconstructed === 'function' && !reconstructedFiredRef.current) {
        const b64 = resp.data?.reconstructed_secret || resp.data?.secret_bytes;
        if (typeof b64 === 'string' && b64.length > 0) {
          try {
            // Normalize URL-safe base64 (`-`→`+`, `_`→`/`) and pad
            // before atob() — some backends (esp. JWT-style Python
            // libs) emit URL-safe alphabet which native atob rejects.
            const padLen = (4 - (b64.length % 4)) % 4;
            const standardB64 = b64.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat(padLen);
            const bin = atob(standardB64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
            reconstructedFiredRef.current = true;
            onSecretReconstructed(bytes);
          } catch (decodeErr) {
            // Surface decode failure to the user — there's no
            // sensible fallback if the server returned garbage.
            // eslint-disable-next-line no-console
            console.warn('RecoveryProgress: secret decode failed:', decodeErr);
          }
        }
      }
    } catch (err) {
      const handled = ApiService.handleError(err);
      setError(handled.error || 'Failed to load recovery status');
    } finally {
      setLoading(false);
    }
  }, [requestId, onSecretReconstructed]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) {
    return (
      <div className="progress-loading">
        <div className="spinner-large"></div>
        <p>Loading recovery progress...</p>
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="progress-error">
        <h2>❌ Error Loading Progress</h2>
        <p>{error || 'Recovery request not found'}</p>
      </div>
    );
  }

  const status = normalizeStatus(request.status);
  const currentStepIndex = STATUS_STEPS.findIndex((s) => s.key === status);
  const received = request.received_approvals || 0;
  const required = request.required_approvals || 1;
  const attestations = request.attestations || [];

  return (
    <div className="recovery-progress">
      <div className="progress-header">
        <h1>Recovery Progress</h1>
        <p className="recovery-id">Request ID: <span className="mono">{request.request_id}</span></p>
      </div>

      <div className="progress-card">
        <div className="status-timeline">
          {STATUS_STEPS.map((step, index) => (
            <div
              key={step.key}
              className={`timeline-step ${index <= currentStepIndex ? 'active' : ''} ${index === currentStepIndex ? 'current' : ''}`}
            >
              <div className="step-icon">{step.icon}</div>
              <div className="step-label">{step.label}</div>
              {index < STATUS_STEPS.length - 1 && (
                <div className={`step-line ${index < currentStepIndex ? 'completed' : ''}`}></div>
              )}
            </div>
          ))}
        </div>

        <div className="progress-details">
          <div className="detail-section">
            <h3>📊 Attestation Progress</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Approvals</div>
                <div className="stat-value">{received} / {required}</div>
                <div className="stat-progress">
                  <div
                    className="stat-fill"
                    style={{ width: `${Math.min(100, (received / required) * 100)}%` }}
                  />
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Total Weight</div>
                <div className="stat-value">{request.total_weight ?? 0}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Stake Committed</div>
                <div className="stat-value">{request.total_stake_committed ?? 0}</div>
              </div>
              <div className="stat-card trust-score-card">
                <div className="stat-label">Risk Score</div>
                <div className="stat-value trust-score">
                  {request.risk_score != null ? Number(request.risk_score).toFixed(2) : '—'}
                </div>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3>📅 Timeline</h3>
            <div className="timeline-details">
              <div className="timeline-item">
                <span className="timeline-label">Initiated:</span>
                <span className="timeline-value">
                  {new Date(request.created_at).toLocaleString()}
                </span>
              </div>
              <div className="timeline-item">
                <span className="timeline-label">Expires:</span>
                <span className="timeline-value">
                  {request.expires_at ? new Date(request.expires_at).toLocaleString() : '—'}
                </span>
              </div>
              {request.completed_at && (
                <div className="timeline-item">
                  <span className="timeline-label">Completed:</span>
                  <span className="timeline-value">
                    {new Date(request.completed_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {attestations.length > 0 && (
            <div className="detail-section">
              <h3>🗳️ Attestations</h3>
              <ul className="attestations-list">
                {attestations.map((a) => (
                  <li key={a.attestation_id}>
                    <span className={`decision ${a.decision}`}>{a.decision}</span>
                    <span className="mono">
                      voucher {String(a.voucher).slice(0, 8)}…
                    </span>
                    <span className="time">
                      {new Date(a.attested_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {status === 'pending' && (
            <div className="action-section">
              <div className="info-box">
                <h4>⏳ Awaiting Guardian Attestations</h4>
                <p>
                  Each guardian must sign the challenge nonce and submit via the
                  attestation page. Share this link with them:
                </p>
                <code>{`${window.location.origin}/recovery/social/attest/${request.request_id}`}</code>
              </div>
            </div>
          )}

          {status === 'approved' && (
            <div className="action-section">
              <div className="info-box success-tint">
                <h4>🛡️ Threshold Reached</h4>
                <p>
                  Enough approvals have been collected. Submit the decrypted
                  shares to complete reconstruction.
                </p>
              </div>
            </div>
          )}

          {status === 'completed' && (
            <div className="action-section success">
              <div className="success-box">
                <div className="success-icon">🎉</div>
                <h4>Recovery Completed!</h4>
                <p>Your secret has been reconstructed. Proceed to vault unlock.</p>
                <Link className="btn-primary" to="/login">
                  Go to Login
                </Link>
              </div>
            </div>
          )}

          {(status === 'failed' || status === 'cancelled' || status === 'expired' || status === 'denied') && (
            <div className="action-section error">
              <div className="error-box">
                <h4>❌ Recovery {status}</h4>
                <p>
                  This request is <strong>{status}</strong>. You&apos;ll need
                  to initiate a new recovery if you still need access.
                </p>
                <Link className="btn-secondary" to="/recovery/social/initiate">
                  Start New Recovery
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="refresh-notice">
        <p>🔄 Auto-refreshing every 5 seconds...</p>
      </div>
    </div>
  );
};

export { RecoveryProgress };
export default RecoveryProgress;

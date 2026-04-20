import React, { useCallback, useEffect, useState } from 'react';
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

const RecoveryProgress = () => {
  const { requestId } = useParams();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await ApiService.socialRecovery.getRequest(requestId);
      setRequest(resp.data);
      setError(null);
    } catch (err) {
      const handled = ApiService.handleError(err);
      setError(handled.error || 'Failed to load recovery status');
    } finally {
      setLoading(false);
    }
  }, [requestId]);

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

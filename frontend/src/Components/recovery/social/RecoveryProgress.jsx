import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import './RecoveryProgress.css';

export const RecoveryProgress = () => {
  const { attemptId } = useParams();
  const [attempt, setAttempt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchAttemptStatus();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchAttemptStatus, 5000);
    
    return () => clearInterval(interval);
  }, [attemptId]);
  
  const fetchAttemptStatus = async () => {
    try {
      const response = await fetch(`/api/auth/quantum-recovery/attempt/${attemptId}/status/`, {
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch recovery status');
      }
      
      const data = await response.json();
      setAttempt(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="progress-loading">
        <div className="spinner-large"></div>
        <p>Loading recovery progress...</p>
      </div>
    );
  }
  
  if (error || !attempt) {
    return (
      <div className="progress-error">
        <h2>❌ Error Loading Progress</h2>
        <p>{error || 'Recovery attempt not found'}</p>
      </div>
    );
  }
  
  const statusSteps = [
    { key: 'initiated', label: 'Recovery Initiated', icon: '🚀' },
    { key: 'challenge_phase', label: 'Identity Challenges', icon: '🔐' },
    { key: 'guardian_approval', label: 'Guardian Approvals', icon: '🛡️' },
    { key: 'shard_collection', label: 'Shard Collection', icon: '🧩' },
    { key: 'completed', label: 'Recovery Complete', icon: '✅' }
  ];
  
  const currentStepIndex = statusSteps.findIndex(step => step.key === attempt.status);
  
  return (
    <div className="recovery-progress">
      <div className="progress-header">
        <h1>Recovery Progress</h1>
        <p className="recovery-id">Attempt ID: {attempt.id}</p>
      </div>
      
      {attempt.canary_alert_sent_at && !attempt.canary_alert_acknowledged && (
        <div className="canary-alert">
          <h3>⚠️ Canary Alert Sent</h3>
          <p>A security alert was sent to your email. If you didn't initiate this recovery, 
             please cancel it immediately using the link in the email.</p>
          <p className="alert-time">Sent: {new Date(attempt.canary_alert_sent_at).toLocaleString()}</p>
        </div>
      )}
      
      <div className="progress-card">
        <div className="status-timeline">
          {statusSteps.map((step, index) => (
            <div 
              key={step.key}
              className={`timeline-step ${index <= currentStepIndex ? 'active' : ''} ${index === currentStepIndex ? 'current' : ''}`}
            >
              <div className="step-icon">{step.icon}</div>
              <div className="step-label">{step.label}</div>
              {index < statusSteps.length - 1 && (
                <div className={`step-line ${index < currentStepIndex ? 'completed' : ''}`}></div>
              )}
            </div>
          ))}
        </div>
        
        <div className="progress-details">
          <div className="detail-section">
            <h3>📊 Progress Statistics</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Challenges</div>
                <div className="stat-value">
                  {attempt.challenges_completed} / {attempt.challenges_sent}
                </div>
                <div className="stat-progress">
                  <div 
                    className="stat-fill"
                    style={{ width: `${(attempt.challenges_completed / attempt.challenges_sent) * 100}%` }}
                  ></div>
                </div>
              </div>
              
              <div className="stat-card">
                <div className="stat-label">Guardian Approvals</div>
                <div className="stat-value">
                  {attempt.guardian_approvals_received?.length || 0} / {attempt.guardian_approvals_required}
                </div>
                <div className="stat-progress">
                  <div 
                    className="stat-fill"
                    style={{ 
                      width: `${((attempt.guardian_approvals_received?.length || 0) / attempt.guardian_approvals_required) * 100}%` 
                    }}
                  ></div>
                </div>
              </div>
              
              <div className="stat-card">
                <div className="stat-label">Shards Collected</div>
                <div className="stat-value">
                  {attempt.shards_collected?.length || 0} / {attempt.shards_required}
                </div>
                <div className="stat-progress">
                  <div 
                    className="stat-fill"
                    style={{ 
                      width: `${((attempt.shards_collected?.length || 0) / attempt.shards_required) * 100}%` 
                    }}
                  ></div>
                </div>
              </div>
              
              <div className="stat-card trust-score-card">
                <div className="stat-label">Trust Score</div>
                <div className="stat-value trust-score">
                  {(attempt.trust_score * 100).toFixed(1)}%
                </div>
                <div className={`trust-indicator ${attempt.trust_score >= 0.8 ? 'high' : attempt.trust_score >= 0.5 ? 'medium' : 'low'}`}>
                  {attempt.trust_score >= 0.8 ? '🟢 High' : attempt.trust_score >= 0.5 ? '🟡 Medium' : '🔴 Low'}
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
                  {new Date(attempt.initiated_at).toLocaleString()}
                </span>
              </div>
              <div className="timeline-item">
                <span className="timeline-label">Expires:</span>
                <span className="timeline-value">
                  {new Date(attempt.expires_at).toLocaleString()}
                </span>
              </div>
              {attempt.completed_at && (
                <div className="timeline-item">
                  <span className="timeline-label">Completed:</span>
                  <span className="timeline-value">
                    {new Date(attempt.completed_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>
          
          {attempt.status === 'challenge_phase' && (
            <div className="action-section">
              <div className="info-box">
                <h4>📧 Check Your Email</h4>
                <p>Temporal challenges are being sent to your email over the next few days. 
                   Answer them as they arrive to increase your trust score.</p>
              </div>
            </div>
          )}
          
          {attempt.status === 'guardian_approval' && (
            <div className="action-section">
              <div className="info-box">
                <h4>⏳ Waiting for Guardians</h4>
                <p>Your guardians have been notified and asked to approve this recovery. 
                   This may take some time as they verify your identity.</p>
              </div>
            </div>
          )}
          
          {attempt.status === 'completed' && (
            <div className="action-section success">
              <div className="success-box">
                <div className="success-icon">🎉</div>
                <h4>Recovery Completed!</h4>
                <p>Your account has been successfully recovered. You can now log in with your restored passkey.</p>
                <button className="btn-primary" onClick={() => window.location.href = '/login'}>
                  Go to Login
                </button>
              </div>
            </div>
          )}
          
          {attempt.status === 'failed' && (
            <div className="action-section error">
              <div className="error-box">
                <h4>❌ Recovery Failed</h4>
                <p>{attempt.failure_reason || 'The recovery attempt was unsuccessful.'}</p>
                <button className="btn-secondary" onClick={() => window.location.href = '/recovery'}>
                  Start New Recovery
                </button>
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

export default RecoveryProgress;


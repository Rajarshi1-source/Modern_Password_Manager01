import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { generate as generateFingerprint } from '../../../utils/deviceFingerprint';
import './RecoveryInitiation.css';

export const RecoveryInitiation = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  
  const handleInitiateRecovery = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      // Get device fingerprint
      const deviceFingerprint = await generateFingerprint();
      
      // Call API to initiate recovery
      const response = await fetch('/api/auth/quantum-recovery/initiate_recovery/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          device_fingerprint: deviceFingerprint,
          initiated_from_location: {} // Will be populated by backend from IP
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to initiate recovery');
      }
      
      const data = await response.json();
      
      // Navigate to recovery progress page
      navigate(`/recovery/progress/${data.attempt_id}`);
    } catch (err) {
      setError(err.message || 'Failed to initiate recovery');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="recovery-initiation">
      <div className="recovery-header">
        <h1>🛡️ Social Mesh Recovery</h1>
        <p className="subtitle">Recover your passkey using your guardian network and identity verification</p>
      </div>
      
      <div className="recovery-card">
        <div className="info-section">
          <h3>How it works:</h3>
          <ol>
            <li>We'll send you 5 identity verification challenges over 3 days</li>
            <li>Your guardians will be asked to approve the recovery</li>
            <li>Once verified, your passkey will be securely restored</li>
          </ol>
          
          <div className="warning-box">
            <strong>⚠️ Important:</strong> A canary alert will be sent to your email. 
            If you didn't initiate this recovery, you'll have 48 hours to cancel it.
          </div>
        </div>
        
        <form onSubmit={handleInitiateRecovery} className="recovery-form">
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              required
              disabled={loading}
              autoFocus
            />
          </div>
          
          {error && (
            <div className="error-message">
              ❌ {error}
            </div>
          )}
          
          <button 
            type="submit" 
            disabled={loading}
            className="btn-primary"
          >
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
          <p>Need help? Contact support at support@securevault.com</p>
        </div>
      </div>
    </div>
  );
};

export default RecoveryInitiation;


import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { errorTracker } from '../../services/errorTracker';
import PasskeyRegistration from './PasskeyRegistration';
import './PasskeyManagement.css';

const PasskeyManagement = () => {
  const [passkeys, setPasskeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // Fetch user's passkeys on component mount
  useEffect(() => {
    const fetchPasskeys = async () => {
      try {
        setLoading(true);
        const response = await axios.get('/api/auth/passkeys/');
        // Handle both old and new response formats
        const passkeyData = response.data.passkeys || response.data.data?.passkeys || [];
        setPasskeys(passkeyData);
        setLoading(false);
      } catch (err) {
        setError('Failed to load your passkeys');
        setLoading(false);
        errorTracker.captureError(err, 'PasskeyManagement:FetchPasskeys', {}, 'error');
      }
    };

    fetchPasskeys();
  }, []);

  // Handle passkey deletion
  const deletePasskey = async (passkeyId) => {
    try {
      await axios.delete(`/api/auth/passkeys/${passkeyId}/`);
      
      // Update the list
      setPasskeys(passkeys.filter(key => key.id !== passkeyId));
      setDeleteConfirm(null);
      setError(null); // Clear any previous errors
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.response?.data?.message || 'Failed to delete passkey';
      setError(errorMsg);
      errorTracker.captureError(err, 'PasskeyManagement:DeletePasskey', { passkeyId }, 'error');
    }
  };

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  // Handle successful registration of new passkey
  const handleRegistrationSuccess = async () => {
    // Refresh the passkey list
    try {
      const response = await axios.get('/api/auth/passkeys/');
      const passkeyData = response.data.passkeys || response.data.data?.passkeys || [];
      setPasskeys(passkeyData);
      setError(null); // Clear any previous errors
    } catch (err) {
      errorTracker.captureError(err, 'PasskeyManagement:RefreshPasskeys', {}, 'error');
      setError('Passkey registered but failed to refresh list. Please reload the page.');
    }
  };

  return (
    <div className="passkey-management">
      <h2>Manage Your Passkeys</h2>
      
      {error && <div className="error-message">{error}</div>}
      
      <div className="passkey-registration-section">
        <h3>Add a New Passkey</h3>
        <PasskeyRegistration onRegistrationSuccess={handleRegistrationSuccess} />
      </div>
      
      <div className="passkey-list-section">
        <h3>Your Passkeys</h3>
        
        {loading ? (
          <p className="loading">Loading your passkeys...</p>
        ) : passkeys.length === 0 ? (
          <p className="no-passkeys">You haven't set up any passkeys yet.</p>
        ) : (
          <div className="passkey-list">
            {passkeys.map(passkey => (
              <div key={passkey.id} className="passkey-item">
                <div className="passkey-info">
                  <div className="passkey-device">
                    <span className="device-icon">
                      {/* Display different icon based on device type */}
                      {passkey.device_type === 'iOS' && '📱'}
                      {passkey.device_type === 'Android' && '📱'}
                      {passkey.device_type === 'MacOS' && '💻'}
                      {passkey.device_type === 'Windows' && '💻'}
                      {passkey.device_type === 'Linux' && '💻'}
                      {!['iOS', 'Android', 'MacOS', 'Windows', 'Linux'].includes(passkey.device_type) && '🔑'}
                    </span>
                    <span className="device-name">{passkey.device_type || 'Unknown Device'}</span>
                  </div>
                  
                  <div className="passkey-details">
                    <p>Created: {formatDate(passkey.created_at)}</p>
                    {passkey.last_used_at && (
                      <p>Last used: {formatDate(passkey.last_used_at)}</p>
                    )}
                  </div>
                </div>
                
                {deleteConfirm === passkey.id ? (
                  <div className="delete-confirm">
                    <p>Are you sure?</p>
                    <div className="confirm-buttons">
                      <button 
                        onClick={() => deletePasskey(passkey.id)}
                        className="confirm-delete"
                      >
                        Yes, Delete
                      </button>
                      <button 
                        onClick={() => setDeleteConfirm(null)}
                        className="cancel-delete"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button 
                    onClick={() => setDeleteConfirm(passkey.id)}
                    className="delete-passkey"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="passkey-info-box">
        <h4>About Passkeys</h4>
        <p>
          Passkeys are a secure and easy way to sign in without using passwords.
          They use biometric verification like fingerprints or facial recognition,
          or a device PIN to authenticate you.
        </p>
        <p>
          Your passkeys are securely stored on your devices and are more phishing-resistant
          than traditional passwords.
        </p>
      </div>
    </div>
  );
};

export default PasskeyManagement;
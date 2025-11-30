import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { errorTracker } from '../../services/errorTracker';
import deviceFingerprint from '../../utils/deviceFingerprint';

// Component for handling social media logins with security features
const SocialMediaLogin = ({ socialAccountId }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [accountDetails, setAccountDetails] = useState(null);
  const [isLocked, setIsLocked] = useState(false);
  const navigate = useNavigate();

  // Fetch account details on component mount
  useEffect(() => {
    const fetchAccountDetails = async () => {
      try {
        const response = await axios.get(`/api/social-accounts/${socialAccountId}/`);
        setAccountDetails(response.data);
        setIsLocked(response.data.is_locked);
        setUsername(response.data.account_username);
      } catch (error) {
        toast.error('Failed to fetch account details');
        errorTracker.captureError(error, 'SocialMediaLogin:FetchAccount', { socialAccountId }, 'error');
      }
    };

    if (socialAccountId) {
      fetchAccountDetails();
    }
  }, [socialAccountId]);

  // Handle login attempt
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Get device fingerprint for device tracking
      const deviceId = await deviceFingerprint.generate();

      // First, attempt to retrieve encrypted password from our password manager
      const passwordResponse = await axios.get(`/api/social-accounts/${socialAccountId}/password/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });

      // Now notify our backend about this login attempt
      // This is where suspicious login detection happens
      const loginResponse = await axios.post(
        `/api/social-accounts/${socialAccountId}/record_login/`,
        { device_id: deviceId },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        }
      );

      // If the login is not flagged as suspicious, proceed with the actual login
      // to the social media platform
      if (!loginResponse.data.is_suspicious) {
        // Here you would implement the actual login to the social media platform
        // using their respective APIs or SDKs
        
        // For example with Facebook SDK:
        // FB.login(function(response) {
        //   // Handle response
        // }, {scope: 'public_profile,email'});
        
        toast.success(`Successfully logged into ${accountDetails.platform}`);
        navigate('/dashboard');
      }
    } catch (error) {
      // Check if this was denied because of suspicious activity
      if (error.response && error.response.status === 403 && 
          error.response.data && error.response.data.account_locked) {
        
        setIsLocked(true);
        toast.error(`Security alert: ${error.response.data.reason}. Account has been locked.`);
        
        // Navigate to verification page
        navigate(`/verify-identity/${socialAccountId}`);
      } else {
        toast.error('Login failed. Please check your credentials.');
        errorTracker.captureError(error, 'SocialMediaLogin:Login', { socialAccountId }, 'error');
      }
    } finally {
      setLoading(false);
    }
  };

  if (isLocked) {
    return (
      <div className="locked-account-container">
        <div className="alert alert-danger">
          <h4>Account Locked</h4>
          <p>This account has been locked due to suspicious login activity.</p>
          <p>Reason: {accountDetails?.lock_reason || 'Suspicious activity detected'}</p>
          <button 
            className="btn btn-primary"
            onClick={() => navigate(`/verify-identity/${socialAccountId}`)}
          >
            Verify Your Identity to Unlock
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="social-login-container">
      <h3>Login to {accountDetails?.platform}</h3>
      <form onSubmit={handleLogin}>
        <div className="form-group">
          <label>Username</label>
          <input
            type="text"
            className="form-control"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            type="password"
            className="form-control"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled
            placeholder="Stored securely in your password manager"
          />
        </div>
        <button 
          type="submit" 
          className="btn btn-primary btn-block" 
          disabled={loading}
        >
          {loading ? 'Logging in...' : 'Login with Password Manager'}
        </button>
      </form>
    </div>
  );
};

export default SocialMediaLogin; 
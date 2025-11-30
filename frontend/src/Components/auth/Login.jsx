import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { errorTracker } from '../../services/errorTracker';
import PasskeyAuth from './PasskeyAuth';
import './Login.css';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [passkeySupport, setPasskeySupport] = useState({
    supported: false,
    platform: false,
    conditional: false,
  });
  const navigate = useNavigate();

  // Check WebAuthn support on component mount
  useEffect(() => {
    const checkPasskeySupport = async () => {
      // Basic support
      const isSupported = window.PublicKeyCredential !== undefined;
      
      // Check for platform authenticator (like Touch ID, Face ID, Windows Hello)
      let hasPlatformAuth = false;
      let hasConditionalUI = false;
      
      if (isSupported) {
        try {
          hasPlatformAuth = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
          
          // Check for conditional UI (passkey autofill)
          hasConditionalUI = 'conditional' in PublicKeyCredential.prototype.get || 
                            window.PublicKeyCredential?.isConditionalMediationAvailable?.();
        } catch (e) {
          errorTracker.captureError(e, 'Login:CheckWebAuthnCapabilities', {}, 'warning');
        }
      }
      
      setPasskeySupport({
        supported: isSupported,
        platform: hasPlatformAuth,
        conditional: hasConditionalUI
      });
    };
    
    checkPasskeySupport();
  }, []);
  
  // Handle regular password login
  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      const response = await axios.post('/api/auth/login/', {
        username,
        password
      });
      
      setLoading(false);
      
      if (response.data.success) {
        // Store authentication token
        localStorage.setItem('authToken', response.data.token);
        
        // Redirect to vault
        navigate('/vault');
      } else {
        setError(response.data.error || 'Login failed');
      }
    } catch (err) {
      setLoading(false);
      
      // Handle network errors
      if (!err.response) {
        setError('Network error: Unable to connect to the server. Please check your internet connection.');
        return;
      }
      
      // Handle specific error responses
      const errorMessage = err.response?.data?.error || 
                          err.response?.data?.message || 
                          err.response?.data?.detail ||
                          'An error occurred during login. Please try again.';
      
      setError(errorMessage);
      console.error('Login error:', err);
    }
  };
  
  // Handle successful passkey login
  const handlePasskeyLoginSuccess = (user) => {
    // Store authentication token if returned
    if (user.token) {
      localStorage.setItem('authToken', user.token);
    }
    
    // Redirect to vault
    navigate('/vault');
  };
  
  // Generate the passkey support message
  const getPasskeySupportMessage = () => {
    if (!passkeySupport.supported) {
      return "Your browser doesn't support passkeys.";
    }
    
    if (!passkeySupport.platform) {
      return "This browser has partial passkey support. You may be able to use a passkey from a nearby device.";
    }
    
    return "Your browser fully supports passkeys.";
  };

  return (
    <div className="login-container">
      <h1>Password Manager</h1>
      
      <div className="login-form-container">
        <h2>Login to Your Vault</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handlePasswordLogin} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <button 
            type="submit" 
            className="login-button"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login to Vault'}
          </button>
        </form>
        
        <div className="divider">
          <span>OR</span>
        </div>
        
        {/* Passkey login option */}
        <div className="passkey-section">
          {passkeySupport.supported ? (
            <PasskeyAuth onLoginSuccess={handlePasskeyLoginSuccess} />
          ) : (
            <p className="passkey-not-supported">
              Your browser doesn't support passkeys.
            </p>
          )}
          
          <p className="passkey-support-info">
            {getPasskeySupportMessage()}
          </p>
        </div>
        
        <div className="additional-links">
          <a href="/password-recovery">Forgot Password?</a>
          <a href="/signup">Create an Account</a>
        </div>
      </div>
    </div>
  );
};

export default Login;
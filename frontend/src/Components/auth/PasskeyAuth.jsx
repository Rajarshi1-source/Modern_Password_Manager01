import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { errorTracker } from '../../services/errorTracker';

/**
 * Component for signing in with passkeys
 */
const PasskeyAuth = ({ onLoginSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [email, setEmail] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [supportsPasskeys, setSupportsPasskeys] = useState(false);
  const [isConditionalUI, setIsConditionalUI] = useState(false);
  const [authSuccess, setAuthSuccess] = useState(false);

  // Check browser capabilities on mount
  useEffect(() => {
    async function checkPasskeySupport() {
      // Check basic WebAuthn support
      const basicSupport = window.PublicKeyCredential !== undefined;
      setSupportsPasskeys(basicSupport);
      
      // Check for conditional UI (autofill) support
      if (basicSupport && window.PublicKeyCredential.isConditionalMediationAvailable) {
        const conditionalSupport = await window.PublicKeyCredential.isConditionalMediationAvailable();
        setIsConditionalUI(conditionalSupport);
      }
    }
    
    checkPasskeySupport();
  }, []);

  // Helper function to convert base64 string to array buffer
  const base64ToArrayBuffer = (base64) => {
    const binaryString = window.atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  };

  // Helper function to convert array buffer to base64 string
  const arrayBufferToBase64 = (buffer) => {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  };
  
  // Function to verify if user exists
  const verifyUserCredentials = async (e) => {
    if (e) e.preventDefault();
    
    if (!email || !email.trim()) {
      setError('Please enter your email');
      return;
    }
    
    // Validate that email is a Gmail address
    if (!email.toLowerCase().endsWith('@gmail.com')) {
      setError('Please enter a valid Gmail address');
      return;
    }
    
    try {
      setVerificationLoading(true);
      setError(null);
      
      // Call the email verification API endpoint
      const response = await axios.post('/api/auth/verify-email-exists/', { email });
      
      if (response.data.exists) {
        // Email exists, user is verified
        setIsVerified(true);
        
        // If conditional UI is supported, try autofill immediately
        if (isConditionalUI) {
          await startAuthenticationWithConditionalUI();
        }
      } else {
        // Email doesn't exist
        setError("We couldn't find an account with that email. Please register first.");
      }
    } catch (err) {
      setError('Verification failed. Please try again.');
      errorTracker.captureError(err, 'PasskeyAuth:EmailVerification', { email }, 'error');
    } finally {
      setVerificationLoading(false);
    }
  };

  // Function to initiate passkey authentication
  const startAuthentication = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Step 1: Get authentication options from server
      const optionsResponse = await axios.post('/api/auth/passkey/authenticate/begin/');
      const authOptions = optionsResponse.data;
      
      // Convert challenge and allowCredentials from base64 to ArrayBuffer
      const challengeBuffer = base64ToArrayBuffer(authOptions.challenge);
      const allowCredentials = authOptions.allowCredentials?.map(cred => ({
        ...cred,
        id: base64ToArrayBuffer(cred.id),
      })) || [];
      
      // Step 2: Call WebAuthn API to get credential
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge: challengeBuffer,
          rpId: authOptions.rpId,
          allowCredentials,
          userVerification: "required", // Upgraded to required
          timeout: authOptions.timeout,
        }
      });
      
      return await verifyCredentialWithServer(credential);
    } catch (err) {
      handleAuthError(err);
      return null;
    }
  };
  
  // Conditional UI (autofill) authentication
  const startAuthenticationWithConditionalUI = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get options from server
      const optionsResponse = await axios.post('/api/auth/passkey/authenticate/begin/');
      const authOptions = optionsResponse.data;
      
      // Process options
      const challengeBuffer = base64ToArrayBuffer(authOptions.challenge);
      const allowCredentials = authOptions.allowCredentials?.map(cred => ({
        ...cred,
        id: base64ToArrayBuffer(cred.id),
      })) || [];
      
      // Use conditional UI
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge: challengeBuffer,
          rpId: authOptions.rpId,
          allowCredentials,
          userVerification: "required",
          timeout: 300000, // Longer timeout for conditional UI
        },
        mediation: "conditional" // Enable autofill UI
      });
      
      return await verifyCredentialWithServer(credential);
    } catch (err) {
      // Only show errors for explicit authentication attempts
      // For conditional UI, silent errors are expected
      if (!isConditionalUI) {
        handleAuthError(err);
      }
      return null;
    } finally {
      setLoading(false);
    }
  };
  
  // Shared function to verify credential with server
  const verifyCredentialWithServer = async (credential) => {
    // Prepare credential for sending to server
    const authResponse = {
      id: credential.id,
      rawId: arrayBufferToBase64(credential.rawId),
      response: {
        authenticatorData: arrayBufferToBase64(
          credential.response.authenticatorData
        ),
        clientDataJSON: arrayBufferToBase64(
          credential.response.clientDataJSON
        ),
        signature: arrayBufferToBase64(
          credential.response.signature
        ),
        userHandle: credential.response.userHandle ? 
          arrayBufferToBase64(credential.response.userHandle) : null,
      },
      type: credential.type,
    };
    
    // Send credential to server for verification
    const verifyResponse = await axios.post(
      '/api/auth/passkey/authenticate/complete/', 
      authResponse
    );
    
    setLoading(false);
    
    // Handle successful login (supports both success and status fields)
    if (verifyResponse.data.success === true || verifyResponse.data.status === 'success') {
      const userData = verifyResponse.data.user;
      const tokens = verifyResponse.data.tokens;
      
      // Store JWT tokens if provided
      if (tokens) {
        localStorage.setItem('token', tokens.access);
        localStorage.setItem('refreshToken', tokens.refresh);
      }
      
      // Set authentication success for test assertions
      setAuthSuccess(true);
      
      if (onLoginSuccess) {
        onLoginSuccess(userData, tokens);
      }
      return userData;
    } else {
      throw new Error(verifyResponse.data.message || 'Authentication failed');
    }
  };
  
  // Error handling helper
  const handleAuthError = (err) => {
    setLoading(false);
    
    // Handle network errors
    if (!err.response && !err.name) {
      setError('Network error: Unable to connect to the server. Please check your internet connection.');
      return;
    }
    
    // Provide user-friendly error messages
    if (err.name === 'NotAllowedError') {
      setError('Authentication was declined or timed out. Please try again.');
    } else if (err.name === 'SecurityError') {
      setError('Security error: This operation requires a secure connection (HTTPS).');
    } else if (err.name === 'InvalidStateError') {
      setError('This passkey is already registered. Please use a different one.');
    } else if (err.response?.data?.error) {
      setError(err.response.data.error);
    } else if (err.response?.data?.message) {
      setError(err.response.data.message);
    } else if (err.response?.data?.detail) {
      setError(err.response.data.detail);
    } else {
      setError('Authentication failed. Please try again or use password login.');
      errorTracker.captureError(err, 'PasskeyAuth:Authentication', { email }, 'error');
    }
    
    console.error('Passkey authentication error:', err);
  };

  // Render UI based on device capabilities
  return (
    <div className="passkey-auth">
      {error && <div className="error-message">{error}</div>}
      
      {/* Test-friendly authentication status indicator */}
      {authSuccess && (
        <span className="sr-only" data-testid="passkey-auth-status">
          Passkey Authentication Successful
        </span>
      )}
      
      {!supportsPasskeys ? (
        <div className="browser-warning">
          <p>Your browser doesn't support passkeys. Please use a modern browser like Chrome, Safari, or Edge.</p>
          <p>Alternatively, you can authenticate with your username and password.</p>
        </div>
      ) : !isVerified ? (
        <div className="verification-container">
          <h3>Verify Your Credentials to Authenticate</h3>
          <p>Please enter your email to verify your account before using passkeys.</p>
          
          <form onSubmit={verifyUserCredentials} className="verification-form">
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@gmail.com"
                autoComplete="webauthn"
                required
              />
              <small className="email-hint" style={{ display: 'block', marginTop: '4px', color: 'var(--info)', fontSize: '0.8rem' }}>
                Only Gmail addresses (@gmail.com) are supported
              </small>
            </div>
            
            <button 
              type="submit"
              disabled={verificationLoading || !email || !email.toLowerCase().endsWith('@gmail.com')}
              className="verification-button"
              style={{ 
                opacity: (!email || !email.toLowerCase().endsWith('@gmail.com')) ? 0.6 : 1,
                cursor: (!email || !email.toLowerCase().endsWith('@gmail.com')) ? 'not-allowed' : 'pointer'
              }}
            >
              {verificationLoading ? 'Verifying...' : 'Verify'}
            </button>
          </form>
        </div>
      ) : (
        <div className="passkey-options">
          <button 
            onClick={startAuthentication} 
            disabled={loading}
            className="passkey-button"
          >
            {loading ? 'Authenticating...' : 'Sign in with a passkey'}
          </button>
          
          {/* Show cross-device instructions */}
          <div className="cross-device-info">
            <p>You can also use a passkey from a nearby device</p>
            <button 
              onClick={startAuthentication}
              disabled={loading}
              className="secondary-button"
            >
              {loading ? 'Authenticating...' : 'Use a passkey from another device'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PasskeyAuth;
import React, { useState } from 'react';
import axios from 'axios';
import { errorTracker } from '../../services/errorTracker';

/**
 * Component for registering new passkeys
 * This would typically be used in account settings after a user is logged in
 */
const PasskeyRegistration = ({ onRegistrationSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

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

  // Function to detect device type (for labeling the passkey)
  const detectDeviceType = () => {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (/iphone|ipad|ipod/.test(userAgent)) return 'iOS';
    if (/android/.test(userAgent)) return 'Android';
    if (/macintosh|mac os x/.test(userAgent)) return 'MacOS';
    if (/windows|win32|win64/.test(userAgent)) return 'Windows';
    if (/linux/.test(userAgent)) return 'Linux';
    
    return 'Unknown';
  };

  // Function to register a new passkey
  const registerPasskey = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);
      
      // Step 1: Get registration options from server
      const optionsResponse = await axios.post('/api/auth/passkey/register/begin/');
      const registrationOptions = optionsResponse.data;
      
      // Convert challenge and user.id from base64 to ArrayBuffer
      const challengeBuffer = base64ToArrayBuffer(registrationOptions.challenge);
      const userIdBuffer = base64ToArrayBuffer(registrationOptions.user.id);
      
      // Convert excluded credentials if any
      const excludeCredentials = registrationOptions.excludeCredentials?.map(cred => ({
        ...cred,
        id: base64ToArrayBuffer(cred.id),
      })) || [];
      
      // Step 2: Call WebAuthn API to create credential
      const credential = await navigator.credentials.create({
        publicKey: {
          challenge: challengeBuffer,
          rp: registrationOptions.rp,
          user: {
            ...registrationOptions.user,
            id: userIdBuffer,
          },
          pubKeyCredParams: registrationOptions.pubKeyCredParams,
          timeout: registrationOptions.timeout,
          excludeCredentials,
          authenticatorSelection: registrationOptions.authenticatorSelection,
          attestation: registrationOptions.attestation,
          extensions: registrationOptions.extensions,
        }
      });
      
      // Step 3: Prepare credential for sending to server
      const registrationResponse = {
        id: credential.id,
        rawId: arrayBufferToBase64(credential.rawId),
        response: {
          attestationObject: arrayBufferToBase64(
            credential.response.attestationObject
          ),
          clientDataJSON: arrayBufferToBase64(
            credential.response.clientDataJSON
          ),
        },
        type: credential.type,
        device_type: detectDeviceType(),
        clientExtensionResults: credential.getClientExtensionResults(),
      };
      
      // Step 4: Send credential to server for verification
      const verifyResponse = await axios.post(
        '/api/auth/passkey/register/complete/', 
        registrationResponse
      );
      
      setLoading(false);
      
      // Step 5: Handle successful registration
      if (verifyResponse.data.success === true || verifyResponse.data.status === 'success') {
        setSuccess(true);
        if (onRegistrationSuccess) {
          onRegistrationSuccess();
        }
      } else {
        throw new Error(verifyResponse.data.message || 'Registration verification failed');
      }
    } catch (err) {
      setLoading(false);
      
      // Provide user-friendly error messages
      if (err.name === 'NotAllowedError') {
        setError('Registration was declined or timed out');
      } else if (err.name === 'SecurityError') {
        setError('The operation is insecure');
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Registration failed. Please try again.');
        errorTracker.captureError(err, 'PasskeyRegistration:Register', {}, 'error');
      }
    }
  };

  // Check if WebAuthn is supported in this browser
  const isWebAuthnSupported = () => {
    return window.PublicKeyCredential !== undefined;
  };

  // Check if conditional UI is supported
  const isConditionalUiSupported = async () => {
    if (!isWebAuthnSupported()) return false;
    return await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  };

  return (
    <div className="passkey-registration">
      {error && <div className="error-message">{error}</div>}
      {success && (
        <div className="success-message">
          Passkey registered successfully! You can now use this device to sign in.
        </div>
      )}
      
      {!isWebAuthnSupported() ? (
        <p className="browser-warning">
          Your browser doesn't support passkeys. Please use a modern browser.
        </p>
      ) : (
        <button 
          onClick={registerPasskey} 
          disabled={loading}
          className="register-passkey-button"
        >
          {loading ? 'Registering...' : 'Register a Passkey on this Device'}
        </button>
      )}
      
      <p className="passkey-info">
        Passkeys use biometrics like fingerprint or face recognition to securely
        sign you in without a password.
      </p>
    </div>
  );
};

export default PasskeyRegistration;
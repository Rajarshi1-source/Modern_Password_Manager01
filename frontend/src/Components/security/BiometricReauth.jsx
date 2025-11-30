import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaFingerprint, FaExclamationCircle, FaCheckCircle, FaLock } from 'react-icons/fa';

const ReauthModal = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.3s ease-out;

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
`;

const ReauthContent = styled.div`
  background: var(--bg-secondary);
  border-radius: 16px;
  padding: 2rem;
  max-width: 450px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s ease-out;

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const ReauthHeader = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 2rem;
  text-align: center;
`;

const IconWrapper = styled.div`
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: ${props => props.$error ? 'rgba(255, 107, 107, 0.1)' : 'var(--primary-light)'};
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
  
  svg {
    font-size: 40px;
    color: ${props => props.$error ? 'var(--danger)' : 'var(--primary)'};
  }
`;

const Title = styled.h2`
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
`;

const Description = styled.p`
  color: var(--text-secondary);
  font-size: 0.95rem;
  line-height: 1.5;
`;

const ActionButton = styled.button`
  width: 100%;
  padding: 1rem;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;

  &.primary {
    background: var(--primary-gradient);
    color: white;
    box-shadow: 0 4px 15px rgba(123, 104, 238, 0.3);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(123, 104, 238, 0.4);
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }
  }

  &.secondary {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);

    &:hover {
      background: var(--primary-light);
      border-color: var(--primary);
      color: var(--primary);
    }
  }
`;

const ErrorMessage = styled.div`
  background: rgba(255, 107, 107, 0.1);
  color: var(--danger);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;

  svg {
    font-size: 1.2rem;
  }
`;

const SuccessMessage = styled.div`
  background: rgba(0, 200, 151, 0.1);
  color: var(--success);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;

  svg {
    font-size: 1.2rem;
  }
`;

const PasswordFallback = styled.div`
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
`;

const PasswordInput = styled.input`
  width: 100%;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 1rem;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: all 0.3s ease;

  &:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(123, 104, 238, 0.2);
  }
`;

/**
 * BiometricReauth Component
 * 
 * Requires biometric or password re-authentication for sensitive operations.
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is open
 * @param {function} props.onSuccess - Callback when authentication succeeds
 * @param {function} props.onCancel - Callback when user cancels
 * @param {string} props.operation - Description of the sensitive operation
 */
const BiometricReauth = ({ isOpen, onSuccess, onCancel, operation = "this action" }) => {
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [showPasswordFallback, setShowPasswordFallback] = useState(false);
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (isOpen) {
      checkBiometricAvailability();
    }
  }, [isOpen]);

  const checkBiometricAvailability = async () => {
    try {
      // Check if WebAuthn is supported
      if (window.PublicKeyCredential) {
        const available = await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
        setBiometricAvailable(available);
      } else {
        setBiometricAvailable(false);
      }
    } catch (err) {
      console.error('Error checking biometric availability:', err);
      setBiometricAvailable(false);
    }
  };

  const handleBiometricAuth = async () => {
    setLoading(true);
    setError('');

    try {
      // Get authentication options from server
      const optionsResponse = await fetch('/api/auth/passkey/authenticate/begin/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!optionsResponse.ok) {
        throw new Error('Failed to initiate biometric authentication');
      }

      const authOptions = await optionsResponse.json();

      // Convert challenge from base64
      const challenge = Uint8Array.from(atob(authOptions.challenge), c => c.charCodeAt(0));
      
      // Prepare credential request options
      const credentialRequestOptions = {
        publicKey: {
          challenge: challenge,
          rpId: authOptions.rpId,
          timeout: 60000,
          userVerification: 'required'
        }
      };

      // Get credential from authenticator
      const credential = await navigator.credentials.get(credentialRequestOptions);

      if (!credential) {
        throw new Error('Authentication was cancelled');
      }

      // Verify credential with server
      const verifyResponse = await fetch('/api/auth/passkey/authenticate/complete/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          id: credential.id,
          rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
          type: credential.type,
          response: {
            authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
            clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
            signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
            userHandle: credential.response.userHandle ? btoa(String.fromCharCode(...new Uint8Array(credential.response.userHandle))) : null
          }
        })
      });

      if (!verifyResponse.ok) {
        throw new Error('Biometric authentication failed');
      }

      setSuccess(true);
      setTimeout(() => {
        onSuccess();
      }, 1000);

    } catch (err) {
      console.error('Biometric authentication error:', err);
      setError(err.message || 'Biometric authentication failed. Please try using your password.');
      setShowPasswordFallback(true);
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordAuth = async () => {
    setLoading(true);
    setError('');

    try {
      // Verify password with server
      const response = await fetch('/api/auth/verify-password/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ password })
      });

      if (!response.ok) {
        throw new Error('Invalid password');
      }

      setSuccess(true);
      setTimeout(() => {
        onSuccess();
      }, 1000);

    } catch (err) {
      console.error('Password verification error:', err);
      setError('Invalid password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <ReauthModal onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <ReauthContent>
        <ReauthHeader>
          <IconWrapper $error={!!error && !success}>
            {success ? (
              <FaCheckCircle />
            ) : error && showPasswordFallback ? (
              <FaLock />
            ) : (
              <FaFingerprint />
            )}
          </IconWrapper>
          <Title>
            {success ? 'Authentication Successful' : 'Authentication Required'}
          </Title>
          <Description>
            {success
              ? 'You can now proceed with the operation.'
              : `To proceed with ${operation}, please verify your identity.`}
          </Description>
        </ReauthHeader>

        {!success && !showPasswordFallback && biometricAvailable && (
          <>
            <ActionButton 
              className="primary" 
              onClick={handleBiometricAuth}
              disabled={loading}
            >
              <FaFingerprint />
              {loading ? 'Authenticating...' : 'Use Biometric Authentication'}
            </ActionButton>
            <ActionButton 
              className="secondary" 
              onClick={() => setShowPasswordFallback(true)}
              disabled={loading}
            >
              Use Password Instead
            </ActionButton>
          </>
        )}

        {!success && (showPasswordFallback || !biometricAvailable) && (
          <PasswordFallback>
            <Description style={{ marginBottom: '1rem', textAlign: 'left' }}>
              Enter your master password to continue:
            </Description>
            <PasswordInput
              type="password"
              placeholder="Enter your master password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handlePasswordAuth()}
              disabled={loading}
            />
            <ActionButton 
              className="primary" 
              onClick={handlePasswordAuth}
              disabled={loading || !password}
            >
              {loading ? 'Verifying...' : 'Verify Password'}
            </ActionButton>
          </PasswordFallback>
        )}

        {error && !success && (
          <ErrorMessage>
            <FaExclamationCircle />
            {error}
          </ErrorMessage>
        )}

        {success && (
          <SuccessMessage>
            <FaCheckCircle />
            Authentication successful! Proceeding...
          </SuccessMessage>
        )}

        {!success && (
          <ActionButton className="secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </ActionButton>
        )}
      </ReauthContent>
    </ReauthModal>
  );
};

export default BiometricReauth;


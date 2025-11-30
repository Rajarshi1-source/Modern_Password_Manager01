import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { CryptoService } from '../../services/cryptoService';
import ApiService from '../../services/api';
import { errorTracker } from '../../services/errorTracker';

/**
 * Recovery Key Setup Component
 * 
 * Implements a secure recovery key generation and verification flow:
 * 1. Verifies user email to ensure they have an account
 * 2. Generates a cryptographically secure recovery key
 * 3. Encrypts vault data with the recovery key using Argon2 for key derivation
 * 4. Verifies the recovery key before finalizing setup
 * 5. Stores the encrypted vault data on the server
 */
const RecoveryKeySetup = () => {
  const [recoveryKey, setRecoveryKey] = useState('');
  const [showRecoveryKey, setShowRecoveryKey] = useState(false);
  const [confirmationStep, setConfirmationStep] = useState(false);
  const [verificationStep, setVerificationStep] = useState(false);
  const [authenticationStep, setAuthenticationStep] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [testRecoveryKey, setTestRecoveryKey] = useState('');
  const [verificationSuccess, setVerificationSuccess] = useState(false);
  const [verificationError, setVerificationError] = useState('');
  const [vaultData, setVaultData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  // Fetch vault data on component mount
  useEffect(() => {
    const fetchVaultData = async () => {
      try {
        setLoading(true);
        const response = await ApiService.vault.list();
        setVaultData(response.data.results || response.data);
        setError(null);
      } catch (err) {
        errorTracker.captureError(err, 'RecoveryKeySetup:FetchVault', {}, 'error');
        setError('Failed to load your vault data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchVaultData();
  }, []);

  // Function to generate a strong recovery key (24 characters)
  const generateRecoveryKey = () => {
    // Define character set for recovery key
    const charset = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Removed similar looking characters
    let result = '';
    
    // Generate 24 random characters
    const randomValues = new Uint32Array(24);
    window.crypto.getRandomValues(randomValues);
    
    for (let i = 0; i < 24; i++) {
      result += charset[randomValues[i] % charset.length];
    }
    
    // Format with hyphens for readability (e.g., XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)
    return result.match(/.{1,4}/g).join('-');
  };
  
  // Function to encrypt the vault data with the recovery key
  const encryptVaultWithRecoveryKey = async (vaultData, recoveryKey) => {
    try {
      // Generate a cryptographically secure salt
      const cryptoService = new CryptoService();
      // Use crypto service to generate salt
      const salt = window.crypto.getRandomValues(new Uint8Array(16));
      const saltBase64 = btoa(String.fromCharCode.apply(null, salt));
      
      // Derive key from recovery key using Argon2
      const derivedKey = await cryptoService.deriveKeyFromRecoveryKey(recoveryKey, saltBase64);
      
      // Encrypt vault data with the derived key
      const encryptedData = await cryptoService.encrypt(vaultData, derivedKey);
      
      return {
        data: encryptedData,
        salt: saltBase64,
        method: 'recovery-key-argon2id'
      };
    } catch (error) {
      errorTracker.captureError(error, 'RecoveryKeySetup:EncryptVault', {}, 'error');
      throw new Error('Failed to encrypt vault with recovery key');
    }
  };
  
  // Function to test decryption using a recovery key
  const testDecryptWithRecoveryKey = async (encryptedData, salt, testKey) => {
    try {
      const cryptoService = new CryptoService();
      
      // Derive key from the test recovery key
      const derivedKey = await cryptoService.deriveKeyFromRecoveryKey(testKey, salt);
      
      // Try to decrypt
      await cryptoService.decrypt(encryptedData, derivedKey);
      
      // If no error is thrown, decryption succeeded
      return true;
    } catch (error) {
      errorTracker.captureError(error, 'RecoveryKeySetup:TestDecrypt', {}, 'warning');
      return false;
    }
  };

  // Function to show the authentication step
  const showAuthenticationStep = () => {
    setAuthenticationStep(true);
    setError(null);
  };

  // Function to verify user credentials
  const verifyUserCredentials = async () => {
    if (!userEmail) {
      setError('Please enter your email address.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Check if the email exists in the database
      const response = await ApiService.auth.verifyEmailExists({ email: userEmail });
      
      if (response.data.exists) {
        // Email exists, proceed to generate recovery key
        const newRecoveryKey = generateRecoveryKey();
        setRecoveryKey(newRecoveryKey);
        
        // Show the recovery key to the user
        setShowRecoveryKey(true);
        setAuthenticationStep(false);
      } else {
        // Email doesn't exist
        setError('No account found with this email. Please check your email or create an account first.');
      }
    } catch (err) {
      errorTracker.captureError(err, 'RecoveryKeySetup:VerifyEmail', { userEmail }, 'error');
      setError('Unable to verify your account. Please try again later.');
    } finally {
      setLoading(false);
    }
  };
  
  const confirmRecoveryKeyCopied = async () => {
    try {
      if (!vaultData) {
        setError('No vault data available. Please try again later.');
        return;
      }
      
      // Re-encrypt vault with recovery key
      const encryptedVault = await encryptVaultWithRecoveryKey(vaultData, recoveryKey);
      
      // Store the encrypted vault data for the verification step
      window.sessionStorage.setItem('tempEncryptedVault', encryptedVault.data);
      window.sessionStorage.setItem('tempSalt', encryptedVault.salt);
      
      // Move to verification step
      setVerificationStep(true);
      setShowRecoveryKey(false);
    } catch (err) {
      errorTracker.captureError(err, 'RecoveryKeySetup:ConfirmKeyCopied', {}, 'error');
      setError('Failed to set up recovery key. Please try again.');
    }
  };
  
  const verifyRecoveryKey = async () => {
    setLoading(true);
    
    try {
      // Get the encrypted test data
      const encryptedData = window.sessionStorage.getItem('tempEncryptedVault');
      const salt = window.sessionStorage.getItem('tempSalt');
      
      if (!encryptedData || !salt) {
        setVerificationError('Test data not available. Please start over.');
        setLoading(false);
        return;
      }
      
      // Test if the entered key can decrypt the data
      const isValid = await testDecryptWithRecoveryKey(encryptedData, salt, testRecoveryKey);
      
      if (isValid) {
        setVerificationSuccess(true);
        setVerificationError('');
        
        // Clean up temporary storage
        window.sessionStorage.removeItem('tempEncryptedVault');
        window.sessionStorage.removeItem('tempSalt');
        
        // After verification, move to final confirmation step
        setTimeout(() => {
          setVerificationStep(false);
          setConfirmationStep(true);
        }, 1500);
      } else {
        setVerificationError('The recovery key you entered is incorrect. Please try again.');
      }
    } catch (error) {
      errorTracker.captureError(error, 'RecoveryKeySetup:VerifyKey', {}, 'error');
      setVerificationError('An error occurred during verification. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const finishSetup = async () => {
    try {
      if (!vaultData) {
        setError('No vault data available. Please try again later.');
        return;
      }
      
      setLoading(true);
      
      // Re-encrypt vault with recovery key
      const encryptedVault = await encryptVaultWithRecoveryKey(vaultData, recoveryKey);
      
      // Send the encrypted vault and recovery info to the backend
      await ApiService.auth.setupRecoveryKey({
        encryptedVault: encryptedVault.data,
        salt: encryptedVault.salt,
        method: encryptedVault.method,
        email: userEmail // Include the email to associate with this recovery key
      });
      
      // Update user profile to indicate recovery key is set up
      await ApiService.auth.updateRecoveryStatus({
        has_recovery_key: true,
        email: userEmail
      });
      
      // Navigate back to home page
      navigate('/');
    } catch (err) {
      errorTracker.captureError(err, 'RecoveryKeySetup:FinishSetup', { userEmail }, 'error');
      setError('Failed to complete setup. Your recovery key may not be properly saved.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="recovery-key-setup loading">Loading...</div>;
  }

  return (
    <div className="recovery-key-setup">
      {!showRecoveryKey && !confirmationStep && !verificationStep && !authenticationStep && (
        <div className="recovery-key-intro">
          <h2>Set Up Your Recovery Key</h2>
          <p>
            A recovery key allows you to regain access to your passwords if you forget your master password.
          </p>
          <p>
            This key will be generated for you and you should store it in a safe place.
          </p>
          <p className="important-note">
            <strong>Important:</strong> If you lose both your master password and recovery key, your data cannot be recovered.
          </p>
          <p className="important-note">
            <strong>Important:</strong> If you're locked out of your account and haven't turned on a recovery method, you may need to reset your account, which erases all of your data. SecureVault never stores or shares your Master Password, so we can't tell you your password if you forget it. We have no way to help you log in to your account. You can follow the steps in our troubleshooting articles to check if you're truly locked out.
          </p>
          <div className="help-links" style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px', marginBottom: '16px' }}>
            <a href="/help/forgot-password" className="recovery-link">I forgot my Master Password</a>
            <a href="/help/locked-out" className="recovery-link">I can't access my passwordless SecureVault account</a>
          </div>
          {error && <div className="error-message">{error}</div>}
          <div className="button-group">
            <button className="secondary-btn" onClick={() => navigate('/')}>Cancel</button>
            <button className="submit-btn" onClick={showAuthenticationStep}>Generate Recovery Key</button>
          </div>
        </div>
      )}

      {authenticationStep && !showRecoveryKey && !confirmationStep && !verificationStep && (
        <div className="auth-verification">
          <h2>Verify Your Credentials</h2>
          <p className="important-note">
            To authenticate your account and generate a recovery key, please enter your email address.
          </p>
          
          <div className="form-group">
            <label htmlFor="user-email">Email Address</label>
            <input 
              type="email" 
              id="user-email"
              value={userEmail}
              onChange={(e) => setUserEmail(e.target.value)}
              placeholder="name@example.com"
              required
            />
            {error && <p className="error-message">{error}</p>}
          </div>
          
          <div className="button-group">
            <button 
              className="secondary-btn" 
              onClick={() => setAuthenticationStep(false)}
            >
              Go Back
            </button>
            <button 
              className="submit-btn" 
              onClick={verifyUserCredentials}
              disabled={loading || !userEmail}
            >
              {loading ? 'Verifying...' : 'Verify & Continue'}
            </button>
          </div>
        </div>
      )}
      
      {showRecoveryKey && !confirmationStep && !verificationStep && (
        <div className="recovery-key-display">
          <h2>Your Recovery Key</h2>
          <p className="important-note">
            <strong>Important:</strong> Save this recovery key in a secure location. It can be used to recover your account if you forget your master password.
          </p>
          
          <div className="recovery-key-box">
            <code>{recoveryKey}</code>
          </div>
          
          <div className="qr-code-container">
            <QRCodeSVG value={recoveryKey} size={200} />
          </div>
          
          <p className="warning-text">
            Warning: We cannot recover this key for you if you lose it. Please store it securely.
          </p>
          
          {error && <div className="error-message">{error}</div>}
          <div className="button-group">
            <button className="secondary-btn" onClick={() => navigate('/')}>Cancel</button>
            <button className="submit-btn" onClick={confirmRecoveryKeyCopied}>
              I've Saved My Recovery Key
            </button>
          </div>
        </div>
      )}
      
      {verificationStep && !confirmationStep && (
        <div className="recovery-key-verify">
          <h2>Verify Your Recovery Key</h2>
          <p>
            To ensure you've correctly saved your recovery key, please enter it below:
          </p>
          
          <div className="form-group">
            <label htmlFor="test-recovery-key">Recovery Key</label>
            <input 
              type="text" 
              id="test-recovery-key"
              value={testRecoveryKey}
              onChange={(e) => setTestRecoveryKey(e.target.value)}
              placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
              className={verificationError ? 'error' : ''}
            />
            {verificationError && <p className="error-message">{verificationError}</p>}
            {verificationSuccess && <p className="success-message">Verification successful! Your recovery key works correctly.</p>}
          </div>
          
          <div className="button-group">
            <button className="secondary-btn" onClick={() => {
              setVerificationStep(false);
              setShowRecoveryKey(true);
            }}>
              Go Back
            </button>
            <button 
              className="submit-btn" 
              onClick={verifyRecoveryKey}
              disabled={loading || !testRecoveryKey || testRecoveryKey.length < 20}
            >
              {loading ? 'Verifying...' : 'Verify Recovery Key'}
            </button>
          </div>
        </div>
      )}
      
      {confirmationStep && (
        <div className="recovery-key-confirm">
          <h2>Confirm Recovery Key</h2>
          <p>
            You've successfully verified your recovery key!
          </p>
          <p>
            Remember that this key is the only way to recover your account if you forget your master password.
          </p>
          <p className="important-note">
            <strong>Where should you store your recovery key?</strong>
          </p>
          <ul>
            <li>Print it and store it in a secure location</li>
            <li>Save it in a password-protected document on a secure device</li>
            <li>Write it down and keep it in a safe</li>
            <li>Store it with a trusted family member</li>
          </ul>
          <p className="warning-text">
            Do NOT store your recovery key in the same location as your master password.
          </p>
          
          {error && <div className="error-message">{error}</div>}
          <div className="button-group">
            <button className="secondary-btn" onClick={() => navigate('/')}>Cancel</button>
            <button 
              className="submit-btn" 
              onClick={finishSetup}
              disabled={loading}
            >
              {loading ? 'Finishing Setup...' : 'Finish Setup'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RecoveryKeySetup;

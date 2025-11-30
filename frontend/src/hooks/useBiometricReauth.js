import { useState, useCallback } from 'react';

/**
 * Custom hook for biometric re-authentication
 * 
 * Usage:
 * const { requireReauth, ReauthComponent } = useBiometricReauth();
 * 
 * // In your component JSX:
 * <div>
 *   {ReauthComponent}
 *   <button onClick={() => requireReauth('delete your account', handleDeleteAccount)}>
 *     Delete Account
 *   </button>
 * </div>
 */
const useBiometricReauth = () => {
  const [isReauthOpen, setIsReauthOpen] = useState(false);
  const [operation, setOperation] = useState('');
  const [onSuccessCallback, setOnSuccessCallback] = useState(null);

  /**
   * Request biometric re-authentication before performing a sensitive operation
   * 
   * @param {string} operationDescription - Description of the operation (e.g., "delete your account")
   * @param {function} onSuccess - Callback to execute after successful authentication
   * @returns {Promise<void>}
   */
  const requireReauth = useCallback((operationDescription, onSuccess) => {
    return new Promise((resolve, reject) => {
      setOperation(operationDescription);
      setOnSuccessCallback(() => () => {
        resolve();
        if (onSuccess) {
          onSuccess();
        }
        setIsReauthOpen(false);
      });
      setIsReauthOpen(true);
    });
  }, []);

  /**
   * Cancel the re-authentication request
   */
  const cancelReauth = useCallback(() => {
    setIsReauthOpen(false);
    setOperation('');
    setOnSuccessCallback(null);
  }, []);

  /**
   * Handle successful re-authentication
   */
  const handleReauthSuccess = useCallback(() => {
    if (onSuccessCallback) {
      onSuccessCallback();
    }
  }, [onSuccessCallback]);

  return {
    isReauthOpen,
    operation,
    requireReauth,
    cancelReauth,
    handleReauthSuccess
  };
};

export default useBiometricReauth;


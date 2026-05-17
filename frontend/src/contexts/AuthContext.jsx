import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import ApiService from '../services/api';
import { setStoredUser } from '../utils/userStorage';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Initialize auth state. We no longer read the user profile from
  // `localStorage` (CodeQL #1048, see utils/userStorage.js). To avoid
  // the UX regression that CodeRabbit + Codex flagged on PR #245
  // (`user` permanently null after reload so consumers of
  // `currentUser.email` show empty values), we explicitly hydrate
  // from `GET /api/auth/me/` when a token is present. If that fetch
  // 401s, the token is dead and we drop it.
  useEffect(() => {
    let cancelled = false;

    const initializeAuth = async () => {
      const token = localStorage.getItem('token');

      // Clean up any pre-fix 'user' blob that might be lurking from
      // an older build. Subsequent reads will get null which the
      // updated consumers expect.
      localStorage.removeItem('user');

      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }

      axios.defaults.headers.common['Authorization'] = `Token ${token}`;

      // Hydrate the user profile from the server. The `/api/auth/me/`
      // endpoint identifies the user from `request.user` so we don't
      // need to carry a user_id around in localStorage.
      try {
        const resp = await axios.get('/api/auth/me/');
        if (!cancelled) {
          setCurrentUser(resp.data);
          setIsAuthenticated(true);
        }
      } catch (err) {
        if (err?.response?.status === 401) {
          // Token is dead. Drop it and leave the user signed out.
          // (We do NOT clear localStorage indiscriminately here;
          // logout has its own path for that.)
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
        } else if (!cancelled) {
          // Network error / 5xx → we have a token, we just couldn't
          // fetch the profile right now. Mark authenticated so the
          // routes don't bounce the user to login; consumers handle
          // null currentUser gracefully (matching the post-PR-#245
          // contract).
          setIsAuthenticated(true);
        }
      }

      // Initialize device fingerprint for existing sessions (best-effort)
      try {
        await ApiService.initializeDeviceFingerprint();
      } catch (error) {
        console.warn('Failed to initialize device fingerprint:', error);
      }

      if (!cancelled) setLoading(false);
    };

    initializeAuth();
    return () => { cancelled = true; };
  }, []);

  const login = async (username, password) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post('/auth/login/', { username, password });
      
      // Extract data from response
      const { token, user_id, salt } = response.data;
      
      // Store auth data
      localStorage.setItem('token', token);
      localStorage.setItem('salt', salt);
      
      // Set default auth header for all requests
      axios.defaults.headers.common['Authorization'] = `Token ${token}`;
      
      // Fetch user details
      const userResponse = await axios.get(`/api/users/${user_id}/`);
      const userData = userResponse.data;
      
      setCurrentUser(userData);
      // setStoredUser no longer writes to localStorage (CodeQL #1048,
      // Copilot Autofix accepted). It clears any pre-fix payload so
      // old sessions don't leave a stale user object behind. The
      // profile now lives only in React state — see
      // utils/userStorage.js and PR #246 for the full architecture.
      setStoredUser('user', userData);
      setIsAuthenticated(true);
      
      // Initialize device fingerprint after successful login
      try {
        await ApiService.initializeDeviceFingerprint();
      } catch (error) {
        console.warn('Failed to initialize device fingerprint after login:', error);
      }
      
      return { token, salt };
    } catch (error) {
      const message = error.response?.data?.error || 'Login failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };

  // WebAuthn/Passkey login
  const loginWithPasskey = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Start authentication process
      const authOptionsResponse = await ApiService.auth.authenticatePasskeyBegin();
      
      // Convert challenge and allowCredentials from base64 to ArrayBuffer
      const challengeBuffer = _base64ToArrayBuffer(authOptionsResponse.challenge);
      
      // Format options for WebAuthn API
      const authOptions = {
        challenge: challengeBuffer,
        rpId: authOptionsResponse.rpId,
        allowCredentials: authOptionsResponse.allowCredentials?.map(cred => ({
          id: _base64ToArrayBuffer(cred.id),
          type: cred.type,
          transports: cred.transports
        })) || [],
        timeout: authOptionsResponse.timeout,
        userVerification: authOptionsResponse.userVerification
      };
      
      // Request credential from browser
      const credential = await navigator.credentials.get({
        publicKey: authOptions
      });
      
      // Format credential for server
      const authResponse = {
        id: credential.id,
        rawId: _arrayBufferToBase64(credential.rawId),
        response: {
          authenticatorData: _arrayBufferToBase64(credential.response.authenticatorData),
          clientDataJSON: _arrayBufferToBase64(credential.response.clientDataJSON),
          signature: _arrayBufferToBase64(credential.response.signature),
          userHandle: credential.response.userHandle ? _arrayBufferToBase64(credential.response.userHandle) : null
        },
        type: credential.type
      };
      
      // Send credential to server
      const authCompleteResponse = await ApiService.auth.authenticatePasskeyComplete(authResponse);
      
      // Handle successful authentication  
      if (authCompleteResponse.success === true || authCompleteResponse.status === 'success') {
        const { user, tokens } = authCompleteResponse;
        
        // Handle JWT tokens (new format) or fallback to old token format
        if (tokens) {
          // New JWT format
          localStorage.setItem('token', tokens.access);
          localStorage.setItem('refreshToken', tokens.refresh);
          axios.defaults.headers.common['Authorization'] = `Bearer ${tokens.access}`;
        } else {
          // Legacy token format
          const token = authCompleteResponse.token || 'passkey-auth-token';
          localStorage.setItem('token', token);
          axios.defaults.headers.common['Authorization'] = `Token ${token}`;
        }
        
        // Set user data — scrub before persisting (see userStorage.js)
        setCurrentUser(user);
        setStoredUser('user', user);
        setIsAuthenticated(true);
        
        // Initialize device fingerprint after successful passkey login
        try {
          await ApiService.initializeDeviceFingerprint();
        } catch (error) {
          console.warn('Failed to initialize device fingerprint after passkey login:', error);
        }
        
        return user;
      } else {
        throw new Error(authCompleteResponse.message || 'Passkey authentication failed');
      }
    } catch (error) {
      console.error('Passkey authentication error:', error);
      const message = error.message || 'Passkey authentication failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };
  
  // Register a new passkey
  const registerPasskey = async (deviceName = 'Default Device') => {
    try {
      setLoading(true);
      setError(null);
      
      // Get registration options from server
      const regOptionsResponse = await ApiService.auth.registerPasskeyBegin();
      
      // Convert challenge and user.id from base64 to ArrayBuffer
      const challengeBuffer = _base64ToArrayBuffer(regOptionsResponse.challenge);
      const userIdBuffer = _base64ToArrayBuffer(regOptionsResponse.user.id);
      
      // Format options for WebAuthn API
      const createOptions = {
        challenge: challengeBuffer,
        rp: regOptionsResponse.rp,
        user: {
          ...regOptionsResponse.user,
          id: userIdBuffer,
        },
        pubKeyCredParams: regOptionsResponse.pubKeyCredParams,
        timeout: regOptionsResponse.timeout,
        excludeCredentials: regOptionsResponse.excludeCredentials?.map(cred => ({
          id: _base64ToArrayBuffer(cred.id),
          type: cred.type,
          transports: cred.transports
        })) || [],
        authenticatorSelection: regOptionsResponse.authenticatorSelection,
        attestation: regOptionsResponse.attestation
      };
      
      // Create credential
      const credential = await navigator.credentials.create({
        publicKey: createOptions
      });
      
      // Format credential for server
      const attestationResponse = {
        id: credential.id,
        rawId: _arrayBufferToBase64(credential.rawId),
        response: {
          attestationObject: _arrayBufferToBase64(credential.response.attestationObject),
          clientDataJSON: _arrayBufferToBase64(credential.response.clientDataJSON)
        },
        type: credential.type,
        device_type: deviceName
      };
      
      // Register credential with server
      const registerResponse = await ApiService.auth.registerPasskeyComplete(attestationResponse);
      
      if (registerResponse.status === 'success') {
        return true;
      } else {
        throw new Error('Passkey registration failed');
      }
    } catch (error) {
      console.error('Passkey registration error:', error);
      const message = error.message || 'Passkey registration failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };
  
  // Helper methods for ArrayBuffer/Base64 conversion
  const _base64ToArrayBuffer = (base64) => {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  };
  
  const _arrayBufferToBase64 = (buffer) => {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  };

  const register = async (userData) => {
    try {
      setLoading(true);
      setError(null);
      
      const { username, email, password, passwordConfirm, masterPassword, authHash } = userData;
      
      // Validate passwords match
      if (password !== passwordConfirm) {
        throw new Error('Passwords do not match');
      }
      
      // Register user
      const response = await axios.post('/auth/register/', {
        username,
        email,
        password,
        auth_hash: authHash,
      });
      
      // Extract data from response
      const { token, user_id, salt } = response.data;
      
      // Store auth data
      localStorage.setItem('token', token);
      localStorage.setItem('salt', salt);
      
      // Set default auth header
      axios.defaults.headers.common['Authorization'] = `Token ${token}`;
      
      // Set user data
      const newUser = {
        id: user_id,
        username,
        email
      };
      
      setCurrentUser(newUser);
      setStoredUser('user', newUser);
      setIsAuthenticated(true);
      
      // Initialize device fingerprint after successful registration
      try {
        await ApiService.initializeDeviceFingerprint();
      } catch (error) {
        console.warn('Failed to initialize device fingerprint after registration:', error);
      }
      
      return { token, salt };
    } catch (error) {
      const message = error.response?.data?.error || 'Registration failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      // Clear device fingerprint first
      ApiService.clearDeviceFingerprint();
      
      // Call logout endpoint (optional)
      await axios.post('/auth/logout/');
    } catch (error) {
      console.error('Logout API error:', error);
    } finally {
      // Clear local storage
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('salt');
      
      // Clear auth header
      delete axios.defaults.headers.common['Authorization'];
      
      // Update state
      setCurrentUser(null);
      setIsAuthenticated(false);
    }
  };

  const verifyMasterPassword = async (masterPassword) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post('/auth/verify_master/', {
        master_password: masterPassword
      });
      
      return response.data.is_valid;
    } catch (error) {
      const message = error.response?.data?.error || 'Verification failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };

  const updateProfile = async (userData) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.patch(`/api/users/${currentUser.id}/`, userData);
      
      // Update current user
      const updatedUser = { ...currentUser, ...response.data };
      setCurrentUser(updatedUser);
      setStoredUser('user', updatedUser);
      
      return updatedUser;
    } catch (error) {
      const message = error.response?.data?.error || 'Update failed';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  };

  // Get passkey status for the current user
  const getPasskeyStatus = async () => {
    try {
      const response = await ApiService.auth.getPasskeyStatus();
      return response;
    } catch (error) {
      console.error('Error getting passkey status:', error);
      return { has_passkeys: false, passkey_count: 0 };
    }
  };

  // Get list of user's passkeys
  const listPasskeys = async () => {
    try {
      const response = await ApiService.auth.listPasskeys();
      return response.passkeys || [];
    } catch (error) {
      console.error('Error listing passkeys:', error);
      return [];
    }
  };

  // Delete a passkey
  const deletePasskey = async (id) => {
    try {
      const response = await ApiService.auth.deletePasskey(id);
      return response.status === 'success';
    } catch (error) {
      console.error('Error deleting passkey:', error);
      return false;
    }
  };

  // Rename a passkey
  const renamePasskey = async (id, name) => {
    try {
      const response = await ApiService.auth.renamePasskey(id, name);
      return response.status === 'success';
    } catch (error) {
      console.error('Error renaming passkey:', error);
      return false;
    }
  };

  const value = {
    currentUser,
    isAuthenticated,
    loading,
    error,
    login,
    loginWithPasskey,
    register,
    registerPasskey,
    logout,
    verifyMasterPassword,
    updateProfile,
    getPasskeyStatus,
    listPasskeys,
    deletePasskey,
    renamePasskey
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

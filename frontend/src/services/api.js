import axios from 'axios';
import DeviceFingerprint from '../utils/deviceFingerprint';

// Create API instance with enforced HTTPS
const createSecureApiInstance = (baseURL) => {
  // Force HTTPS in production
  if (import.meta.env.PROD && baseURL.startsWith('http://')) {
    baseURL = baseURL.replace('http://', 'https://');
  }
  
  const instance = axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
    withCredentials: false, // Set to true if using cookie-based sessions
    timeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '30000'),
  });
  
  // Add interceptor to enforce HTTPS
  instance.interceptors.request.use(config => {
    // Redirect to HTTPS if HTTP is used in production
    if (import.meta.env.PROD && config.url.startsWith('http://')) {
      config.url = config.url.replace('http://', 'https://');
    }
    return config;
  });
  
  return instance;
};

// Use environment variable for API base URL
// In development, use empty string to leverage Vite proxy
// In production, use the configured API URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');
const api = createSecureApiInstance(API_BASE_URL);

// Add auth token and device fingerprint to requests if available
api.interceptors.request.use(async (config) => {
  const token = localStorage.getItem('token');
  
  if (token) {
    // Add authentication token
    config.headers.Authorization = `Token ${token}`;
    
    // Add device fingerprint for security tracking
    try {
      const deviceFingerprint = await DeviceFingerprint.generate();
      config.headers['X-Device-Fingerprint'] = deviceFingerprint;
    } catch (error) {
      console.warn('Failed to generate device fingerprint:', error);
      // Continue with request even if fingerprint generation fails
    }
  }
  
  return config;
});

// Response interceptor for handling auth errors and device tracking
api.interceptors.response.use(
  (response) => {
    // Handle successful responses
    return response;
  },
  (error) => {
    // Handle authentication errors
    if (error.response && error.response.status === 401) {
      // Clear token and device fingerprint on unauthorized
      localStorage.removeItem('token');
      DeviceFingerprint.clear();
      
      // Redirect to login if not already there
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

// API endpoints
const ApiService = {
  // Initialize device fingerprint (call this on app startup)
  async initializeDeviceFingerprint() {
    try {
      const fingerprint = await DeviceFingerprint.generate();
      console.log('Device fingerprint initialized:', fingerprint.substring(0, 8) + '...');
      return fingerprint;
    } catch (error) {
      console.error('Failed to initialize device fingerprint:', error);
      return null;
    }
  },
  
  // Clear device fingerprint (call this on logout)
  clearDeviceFingerprint() {
    DeviceFingerprint.clear();
  },
  
  // Auth endpoints
  auth: {
    register: (userData) => api.post('/auth/register/', userData),
    login: (credentials) => api.post('/auth/login/', credentials),
    logout: () => {
      // Clear device fingerprint on logout
      DeviceFingerprint.clear();
      return api.post('/auth/logout/');
    },
    verifyMaster: (authHash) => api.post('/auth/verify_master/', { auth_hash: authHash }),
    changeMaster: (data) => api.post('/auth/change_master/', data),
    setupTwoFactor: (data) => api.post('/auth/two_factor_auth/', data),
    verifyTwoFactor: (data) => api.post('/auth/two_factor_auth/', data),
    requestPasswordReset: (email) => api.post('/auth/request_password_reset/', { email }),
    resetPassword: (data) => api.post('/auth/reset_password/', data),
    // Email verification endpoint
    verifyEmailExists: (data) => api.post('/auth/verify-email-exists/', data),
    // Recovery key endpoints
    setupRecoveryKey: (data) => api.post('/auth/setup-recovery-key/', data),
    updateRecoveryStatus: (status) => api.post('/auth/update-recovery-status/', status),
    validateRecoveryKey: (data) => api.post('/auth/validate-recovery-key/', data),
    getEncryptedVault: (data) => api.post('/auth/get-encrypted-vault/', data),
    resetWithRecoveryKey: (data) => api.post('/auth/reset-with-recovery-key/', data),
    // Passkey endpoints
    registerPasskeyBegin: () => api.post('/auth/passkey/register/begin/'),
    registerPasskeyComplete: (data) => api.post('/auth/passkey/register/complete/', data),
    authenticatePasskeyBegin: () => api.post('/auth/passkey/authenticate/begin/'),
    authenticatePasskeyComplete: (data) => api.post('/auth/passkey/authenticate/complete/', data),
    // Passkey management endpoints
    listPasskeys: () => api.get('/auth/passkeys/'),
    deletePasskey: (id) => api.delete(`/auth/passkeys/${id}/`),
    getPasskeyStatus: () => api.get('/auth/passkeys/status/'),
    renamePasskey: (id, name) => api.put(`/auth/passkeys/${id}/rename/`, { name }),
  },
  
  // Primary Passkey Recovery endpoints (with fallback to Social Mesh Recovery)
  passkeyPrimaryRecovery: {
    // Setup primary recovery backup
    setupRecovery: (data) => api.post('/auth/passkey-recovery/setup/', data),
    // List user's recovery backups
    listBackups: () => api.get('/auth/passkey-recovery/backups/'),
    // Initiate recovery (step 1: identify user)
    initiateRecovery: (data) => api.post('/auth/passkey-recovery/initiate/', data),
    // Complete recovery (step 2: decrypt with recovery key)
    completeRecovery: (data) => api.post('/auth/passkey-recovery/complete/', data),
    // Fallback to social mesh recovery if primary fails
    fallbackToSocialMesh: (data) => api.post('/auth/passkey-recovery/fallback/', data),
    // Revoke a recovery backup
    revokeBackup: (backupId, data) => api.post(`/auth/passkey-recovery/backups/${backupId}/revoke/`, data),
    // Get overall recovery status
    getRecoveryStatus: () => api.get('/auth/passkey-recovery/status/'),
  },
  
  // Quantum Recovery (Social Mesh) endpoints
  quantumRecovery: {
    setupRecovery: (data) => api.post('/auth/quantum-recovery/setup/', data),
    listGuardians: () => api.get('/auth/quantum-recovery/guardians/'),
    acceptGuardianInvitation: (invitationId) => api.post(`/auth/quantum-recovery/invitations/${invitationId}/accept/`),
    revokeGuardian: (guardianId) => api.post(`/auth/quantum-recovery/guardians/${guardianId}/revoke/`),
    initiateRecovery: (data) => api.post('/auth/quantum-recovery/initiate/', data),
    submitChallengeResponse: (data) => api.post('/auth/quantum-recovery/challenge/submit/', data),
    completeRecovery: (data) => api.post('/auth/quantum-recovery/complete/', data),
  },
  
  // Vault endpoints
  vault: {
    list: (params) => api.get('/vault/', { params }),
    get: (id) => api.get(`/vault/${id}/`),
    create: (data) => api.post('/vault/', data),
    update: (id, data) => api.put(`/vault/${id}/`, data),
    delete: (id) => api.delete(`/vault/${id}/`),
    favorite: (id, isFavorite) => api.post(`/vault/${id}/favorite/`, { favorite: isFavorite }),
    getSalt: () => api.get('/vault/get_salt/'),
    sync: (data) => api.post('/vault/sync/', data),
  },
  
  // Security endpoints
  security: {
    checkBreached: (hashPrefixes) => api.post('/security/check_breached/', { hash_prefixes: hashPrefixes }),
    passwordHealth: () => api.get('/security/password_health/'),
    auditLog: () => api.get('/security/audit_log/'),
  },
  
  // Error handler helper
  handleError: (error) => {
    console.error('API Error:', error);
    
    if (error.response) {
      // The request was made and the server responded with an error status
      console.error('Response data:', error.response.data);
      console.error('Status:', error.response.status);
      
      // Handle authentication errors
      if (error.response.status === 401) {
        // Clear token and device fingerprint on unauthorized
        localStorage.removeItem('token');
        DeviceFingerprint.clear();
        window.location.href = '/login';
      }
      
      return error.response.data;
    } else if (error.request) {
      // The request was made but no response was received
      console.error('No response received:', error.request);
      return { error: 'No response from server. Please check your connection.' };
    } else {
      // Something happened in setting up the request
      console.error('Request setup error:', error.message);
      return { error: 'Failed to send request: ' + error.message };
    }
  }
};

export default ApiService;

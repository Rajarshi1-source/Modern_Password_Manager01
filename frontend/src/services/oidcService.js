/**
 * OpenID Connect (OIDC) Service
 * 
 * Provides OIDC integration for:
 * - Enterprise SSO (Okta, Azure AD, Auth0)
 * - ID Token validation
 * - OIDC Discovery
 * - Nonce-based replay protection
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

class OIDCService {
  constructor() {
    this.discoveryCache = new Map();
    this.nonceStorage = new Map();
  }

  /**
   * Generate a cryptographic nonce for replay protection
   */
  generateNonce() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Generate a state parameter with embedded data
   */
  generateState(data = {}) {
    const stateData = {
      random: this.generateNonce().substring(0, 32),
      timestamp: Date.now(),
      ...data,
    };
    return btoa(JSON.stringify(stateData));
  }

  /**
   * Validate state parameter
   */
  validateState(state, maxAge = 600000) {
    try {
      const data = JSON.parse(atob(state));
      if (Date.now() - data.timestamp > maxAge) {
        return null;
      }
      return data;
    } catch {
      return null;
    }
  }

  /**
   * Get OIDC Discovery configuration from server
   */
  async getDiscovery() {
    const cacheKey = 'server_discovery';
    
    if (this.discoveryCache.has(cacheKey)) {
      return this.discoveryCache.get(cacheKey);
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/api/auth/oidc/.well-known/openid-configuration`);
      this.discoveryCache.set(cacheKey, response.data);
      return response.data;
    } catch (error) {
      console.error('Error fetching OIDC discovery:', error);
      throw error;
    }
  }

  /**
   * List all available OIDC providers
   */
  async getProviders() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/auth/oidc/providers/`);
      return response.data;
    } catch (error) {
      console.error('Error fetching OIDC providers:', error);
      throw error;
    }
  }

  /**
   * Initiate OIDC authorization flow
   * @param {string} provider - OIDC provider name (e.g., 'microsoft', 'okta', 'auth0')
   * @param {Object} options - Additional options
   */
  async initiateLogin(provider, options = {}) {
    const { redirectUri, loginHint, extraParams } = options;
    
    const nonce = this.generateNonce();
    const state = this.generateState({ provider, nonce });
    
    // Store nonce for validation after callback
    this.nonceStorage.set(state, { nonce, provider, timestamp: Date.now() });

    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oidc/authorize/`, {
        provider,
        redirect_uri: redirectUri || `${window.location.origin}/auth/callback`,
        state,
        login_hint: loginHint,
        ...extraParams,
      });

      if (response.data.success && response.data.authorization_url) {
        // Open authorization URL
        if (options.popup) {
          return this._openPopup(response.data.authorization_url, provider);
        } else {
          // Redirect to authorization URL
          window.location.href = response.data.authorization_url;
          return null;
        }
      }

      throw new Error(response.data.message || 'Failed to initiate OIDC login');
    } catch (error) {
      console.error(`Error initiating ${provider} OIDC login:`, error);
      throw error;
    }
  }

  /**
   * Open OIDC authorization in popup window
   */
  _openPopup(authUrl, provider) {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      authUrl,
      `${provider}_oidc`,
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no`
    );

    if (!popup) {
      throw new Error('Popup was blocked. Please allow popups for this site.');
    }

    return new Promise((resolve, reject) => {
      const messageHandler = (event) => {
        if (event.origin !== window.location.origin) return;

        if (event.data.type === 'oidc_success') {
          window.removeEventListener('message', messageHandler);
          popup.close();
          resolve(event.data);
        } else if (event.data.type === 'oidc_error') {
          window.removeEventListener('message', messageHandler);
          popup.close();
          reject(new Error(event.data.error || 'OIDC authentication failed'));
        }
      };

      window.addEventListener('message', messageHandler);

      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          window.removeEventListener('message', messageHandler);
          reject(new Error('OIDC popup was closed'));
        }
      }, 1000);
    });
  }

  /**
   * Handle OIDC callback
   * @param {URLSearchParams} params - URL search params from callback
   */
  async handleCallback(params) {
    const token = params.get('token');
    const refresh = params.get('refresh');
    const provider = params.get('provider');
    const state = params.get('state');
    const error = params.get('error');
    const errorMessage = params.get('message');

    if (error) {
      throw new Error(errorMessage || `OIDC error: ${error}`);
    }

    // Validate state
    const stateData = this.validateState(state);
    if (state && !stateData) {
      console.warn('Invalid or expired state parameter');
    }

    // If we have tokens, the server handled everything
    if (token && refresh) {
      // Clean up stored nonce
      if (state) {
        this.nonceStorage.delete(state);
      }

      return {
        success: true,
        tokens: { access: token, refresh },
        provider,
        authMethod: 'oidc',
      };
    }

    throw new Error('Invalid OIDC callback parameters');
  }

  /**
   * Validate an ID token
   * @param {string} provider - OIDC provider name
   * @param {string} idToken - ID token to validate
   * @param {string} nonce - Expected nonce (optional)
   */
  async validateIdToken(provider, idToken, nonce = null) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oidc/validate-token/`, {
        provider,
        id_token: idToken,
        nonce,
      });

      return response.data;
    } catch (error) {
      console.error('Error validating ID token:', error);
      throw error;
    }
  }

  /**
   * Get current user's info from OIDC UserInfo endpoint
   * @param {string} accessToken - Access token for authentication
   */
  async getUserInfo(accessToken) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/auth/oidc/userinfo/`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      return response.data;
    } catch (error) {
      console.error('Error fetching user info:', error);
      throw error;
    }
  }

  /**
   * Exchange authorization code for tokens
   * @param {string} provider - OIDC provider name
   * @param {string} code - Authorization code
   * @param {string} redirectUri - Original redirect URI
   */
  async exchangeCode(provider, code, redirectUri) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oidc/token/`, {
        provider,
        code,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      });

      return response.data;
    } catch (error) {
      console.error('Error exchanging code for tokens:', error);
      throw error;
    }
  }

  // ===================== Enterprise SSO Shortcuts =====================

  /**
   * Login with Microsoft (Azure AD / Entra ID)
   */
  async loginWithMicrosoft(options = {}) {
    return this.initiateLogin('microsoft', options);
  }

  /**
   * Login with Okta
   */
  async loginWithOkta(options = {}) {
    return this.initiateLogin('okta', options);
  }

  /**
   * Login with Auth0
   */
  async loginWithAuth0(options = {}) {
    return this.initiateLogin('auth0', options);
  }

  /**
   * Login with generic OIDC provider
   */
  async loginWithOIDC(providerName, options = {}) {
    return this.initiateLogin(providerName, options);
  }

  // ===================== Utility Methods =====================

  /**
   * Decode JWT token without verification (for display purposes only)
   */
  decodeToken(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new Error('Invalid token format');
      }
      
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
      return payload;
    } catch (error) {
      console.error('Error decoding token:', error);
      return null;
    }
  }

  /**
   * Check if ID token is expired
   */
  isTokenExpired(token) {
    const decoded = this.decodeToken(token);
    if (!decoded || !decoded.exp) {
      return true;
    }
    
    // Add 60 seconds buffer
    return (decoded.exp * 1000) < (Date.now() - 60000);
  }

  /**
   * Get claims from ID token
   */
  getTokenClaims(token) {
    return this.decodeToken(token);
  }

  /**
   * Clear all stored nonces and caches
   */
  clearCache() {
    this.discoveryCache.clear();
    this.nonceStorage.clear();
  }
}

// Export singleton instance
const oidcService = new OIDCService();
export default oidcService;
export { OIDCService };


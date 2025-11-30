/**
 * OAuth Service for handling social login (Google, GitHub, Apple)
 */
import axios from 'axios';

// Use relative paths in development to leverage Vite proxy
const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

class OAuthService {
  /**
   * Get list of available OAuth providers
   */
  async getProviders() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/auth/oauth/providers/`);
      return response.data;
    } catch (error) {
      console.error('Error fetching OAuth providers:', error);
      throw error;
    }
  }

  /**
   * Initiate OAuth login flow
   * @param {string} provider - The OAuth provider (google, github, apple)
   */
  async initiateLogin(provider) {
    const validProviders = ['google', 'github', 'apple'];
    
    if (!validProviders.includes(provider.toLowerCase())) {
      throw new Error(`Invalid OAuth provider: ${provider}`);
    }

    try {
      // For OAuth, we need to redirect to the provider's authorization URL
      // The backend will handle the OAuth flow
      const callbackUrl = `${window.location.origin}/auth/callback`;
      const oauthUrl = `${API_BASE_URL}/api/auth/oauth/${provider}/?redirect_uri=${encodeURIComponent(callbackUrl)}`;
      
      // Open OAuth in a popup window
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      
      const popup = window.open(
        oauthUrl,
        `${provider}_oauth`,
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no`
      );

      if (!popup) {
        throw new Error('Popup was blocked. Please allow popups for this site.');
      }

      // Return a promise that resolves when OAuth completes
      return new Promise((resolve, reject) => {
        // Listen for messages from the popup
        const messageHandler = (event) => {
          // Verify origin for security
          if (event.origin !== window.location.origin) {
            return;
          }

          if (event.data.type === 'oauth_success') {
            window.removeEventListener('message', messageHandler);
            popup.close();
            resolve(event.data);
          } else if (event.data.type === 'oauth_error') {
            window.removeEventListener('message', messageHandler);
            popup.close();
            reject(new Error(event.data.error || 'OAuth authentication failed'));
          }
        };

        window.addEventListener('message', messageHandler);

        // Check if popup was closed
        const checkClosed = setInterval(() => {
          if (popup.closed) {
            clearInterval(checkClosed);
            window.removeEventListener('message', messageHandler);
            reject(new Error('OAuth popup was closed'));
          }
        }, 1000);
      });
    } catch (error) {
      console.error(`Error initiating ${provider} OAuth:`, error);
      throw error;
    }
  }

  /**
   * Complete OAuth login with authorization code
   * @param {string} provider - The OAuth provider
   * @param {string} code - Authorization code from OAuth provider
   */
  async completeLogin(provider, code, state) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oauth/${provider}/`, {
        code,
        state,
      });

      return response.data;
    } catch (error) {
      console.error(`Error completing ${provider} OAuth:`, error);
      throw error;
    }
  }

  /**
   * Handle OAuth callback (used in callback page)
   * @param {URLSearchParams} params - URL search params from callback
   */
  async handleCallback(params) {
    const provider = params.get('provider');
    const code = params.get('code');
    const state = params.get('state');
    const error = params.get('error');
    const token = params.get('token');
    const refresh = params.get('refresh');

    if (error) {
      throw new Error(`OAuth error: ${error}`);
    }

    // If we already have tokens (backend handled everything), return them
    if (token && refresh) {
      return {
        success: true,
        tokens: {
          access: token,
          refresh: refresh
        },
        provider
      };
    }

    // Otherwise, complete the OAuth flow
    if (code && provider) {
      return await this.completeLogin(provider, code, state);
    }

    throw new Error('Invalid OAuth callback parameters');
  }

  /**
   * Login with Google
   */
  async loginWithGoogle() {
    return this.initiateLogin('google');
  }

  /**
   * Login with GitHub
   */
  async loginWithGitHub() {
    return this.initiateLogin('github');
  }

  /**
   * Login with Apple
   */
  async loginWithApple() {
    return this.initiateLogin('apple');
  }

  /**
   * Initiate Authy fallback when OAuth fails
   * @param {string} email - User's email
   * @param {string} phone - User's phone number
   * @param {string} countryCode - Phone country code (default: '1')
   */
  async initiateAuthyFallback(email, phone, countryCode = '1') {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oauth/fallback/authy/`, {
        email,
        phone,
        country_code: countryCode
      });

      return response.data;
    } catch (error) {
      console.error('Error initiating Authy fallback:', error);
      throw error;
    }
  }

  /**
   * Verify Authy code for fallback authentication
   * @param {string} authyId - Authy ID from initial request
   * @param {string} token - Verification token from SMS/push
   */
  async verifyAuthyFallback(authyId, token) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/oauth/fallback/authy/verify/`, {
        authy_id: authyId,
        token
      });

      return response.data;
    } catch (error) {
      console.error('Error verifying Authy fallback:', error);
      throw error;
    }
  }

  /**
   * Handle OAuth failure and check for fallback options
   * @param {Object} error - Error response from OAuth
   */
  handleOAuthFailure(error) {
    const response = error.response?.data;
    
    if (response && response.fallback_available && response.fallback_method === 'authy') {
      return {
        fallbackAvailable: true,
        fallbackMethod: 'authy',
        email: response.email,
        message: response.message || 'OAuth failed. Authy fallback available.'
      };
    }

    return {
      fallbackAvailable: false,
      message: error.message || 'Authentication failed'
    };
  }
}

// Export singleton instance
const oauthService = new OAuthService();
export default oauthService;


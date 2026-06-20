import axios from 'axios';

/**
 * VaultService - vault API operations (metadata / CRUD / sync).
 *
 * End-to-end encryption is NOT handled here. As of the vault crypto
 * unification (PRs E/F/G) all encrypt/decrypt goes through
 * `sessionVaultCrypto` (v2) + `sessionVaultCryptoV3` (v3) via the shared
 * `services/vaultEnvelope` helper. The legacy `cryptoService` /
 * `encryptionKey` path that used to live here was dead (never initialised in
 * the live flow) and has been removed to avoid future confusion.
 */
export class VaultService {
  constructor() {
    this.api = axios.create({
      baseURL: '/api',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for standardized error handling
    this.api.interceptors.response.use(
      response => response,
      error => {
        const errorData = {
          status: error.response?.status || 500,
          code: error.response?.data?.code || 'unknown_error',
          message: error.response?.data?.message || error.response?.data?.error || error.message || 'An unknown error occurred',
          details: error.response?.data?.details || {},
          originalError: error
        };

        // Log all API errors for debugging
        console.error('Vault API Error:', errorData);

        // Throw standardized error for consistent handling in UI
        const enhancedError = new Error(errorData.message);
        enhancedError.errorData = errorData;
        throw enhancedError;
      }
    );

    this.sessionTimeout = null;
  }

  /**
   * Check if vault is initialized for the current user
   * @returns {Promise<Object>} Initialization status
   */
  async checkInitialization() {
    try {
      const response = await this.api.get('/vault/check_initialization/');
      return {
        initialized: response.data.initialized || false,
        has_salt: response.data.has_salt || false,
        has_items: response.data.has_items || false
      };
    } catch (error) {
      // If endpoint doesn't exist or user not authenticated, assume not initialized
      console.warn('Vault initialization check failed:', error.message);
      return {
        initialized: false,
        has_salt: false,
        has_items: false
      };
    }
  }

  /**
   * Toggle the favorite flag on a vault item.
   *
   * `favorite` is non-secret metadata, so this is a lightweight PATCH that
   * updates ONLY that field — it never decrypts or re-encrypts the item
   * payload. The backend serializer exposes `favorite` and the ViewSet's
   * partial update applies it without requiring `encrypted_data`.
   *
   * @param {string|number} id - Database id of the vault item
   * @param {boolean} favorite - Desired favorite state
   * @returns {Promise<Object>} API response
   * @throws {Error} If the update fails
   */
  async toggleFavorite(id, favorite) {
    try {
      return await this.api.patch(`/vault/${id}/`, { favorite });
    } catch (error) {
      const contextError = new Error(`Failed to update favorite: ${error.message}`);
      contextError.errorData = error.errorData || {
        code: 'favorite_update_failed',
        status: error.errorData?.status || 500,
        details: { originalError: error.message, id }
      };
      throw contextError;
    }
  }

  /**
   * Helper to generate a random UUID
   * @returns {string} Random UUID
   */
  generateRandomId() {
    return (([1e7]) + (-1e3) + (-4e3) + (-8e3) + (-1e11)).replace(/[018]/g, c =>
      (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
  }

  /**
   * Log out and clear sensitive data
   * @returns {Promise<Object>} API response
   */
  async logout() {
    try {
      // Clear any session storage
      sessionStorage.removeItem('vaultSession');

      // Return to login page
      return await this.api.post('/auth/logout/');
    } catch (error) {
      console.error('Logout error:', error);
      // Even if API call fails, we still want to clear local data
      return { success: true };
    }
  }

  /**
   * Initialize session timeout for auto-lock
   * @param {number} timeoutMinutes - Minutes until auto-lock
   */
  initSessionTimeout(timeoutMinutes = 15) {
    // Clear any existing timeout
    if (this.sessionTimeout) {
      clearTimeout(this.sessionTimeout);
    }

    // Set new timeout
    this.sessionTimeout = setTimeout(() => {
      this.clearKeys();
      // You could trigger a UI event here to inform the user
      window.dispatchEvent(new CustomEvent('vault:session-expired'));
    }, timeoutMinutes * 60 * 1000);
  }

  /**
   * Reset timeout on user activity
   */
  resetSessionTimeout() {
    if (this.sessionTimeout) {
      clearTimeout(this.sessionTimeout);
      this.initSessionTimeout();
    }
  }

  /**
   * No-op retained for callers (e.g. VaultContext.handleLockVault and the
   * session-timeout). Session-key lifecycle now lives in
   * sessionVaultCrypto.clearSessionKey(); this service holds no key to clear.
   */
  clearKeys() {}

  /**
   * Delete a vault item
   * @param {string} itemId - ID of the item to delete
   * @returns {Promise<Object>} API response
   * @throws {Error} If deletion fails
   */
  async deleteVaultItem(itemId) {
    try {
      return await this.api.delete(`/vault/${itemId}/`);
    } catch (error) {
      const contextError = new Error('Failed to delete vault item: ' + error.message);
      contextError.errorData = error.errorData || {
        code: 'item_deletion_failed',
        status: error.errorData?.status || 500,
        details: {
          originalError: error.message,
          itemId
        }
      };
      throw contextError;
    }
  }

  /**
   * Synchronize vault with server
   * @param {Object} syncData - Data to synchronize
   * @returns {Promise<Object>} Sync results
   * @throws {Error} If sync fails
   */
  async syncVault(syncData) {
    try {
      const response = await this.api.post('/vault/sync/', syncData);
      return response.data;
    } catch (error) {
      const contextError = new Error('Vault synchronization failed: ' + error.message);
      contextError.errorData = error.errorData || {
        code: 'sync_failed',
        status: error.errorData?.status || 500,
        details: { originalError: error.message }
      };
      throw contextError;
    }
  }
}

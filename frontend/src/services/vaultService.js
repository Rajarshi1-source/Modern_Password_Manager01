import axios from 'axios';
import { CryptoService } from './cryptoService';

/**
 * VaultService - Handles all vault-related operations
 * This service communicates with the vault API endpoints and manages encryption/decryption
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
    
    this.cryptoService = null;
    this.encryptionKey = null;
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
   * Initialize encryption with master password
   * @param {string} masterPassword - User's master password
   * @returns {Promise<Object>} Verification result
   * @throws {Error} If initialization fails
   */
  async initialize(masterPassword) {
    try {
      this.cryptoService = new CryptoService(masterPassword);
      
      // Get user's salt from server
      const response = await this.api.get('/vault/get_salt/');
      const salt = response.data.salt;
      
      // Derive encryption key from master password and salt
      this.encryptionKey = await this.cryptoService.deriveKey(salt);
      
      // Verify master password
      return this.verifyMasterPassword(masterPassword);
    } catch (error) {
      // Add context to the error
      const contextError = new Error('Failed to initialize vault: ' + error.message);
      contextError.errorData = error.errorData || {
        code: 'initialization_failed',
        status: 500,
        details: { originalError: error.message }
      };
      throw contextError;
    }
  }
  
  /**
   * Verify master password with server
   * @param {string} masterPassword - User's master password
   * @returns {Promise<Object>} Verification result
   * @throws {Error} If verification fails
   */
  async verifyMasterPassword(masterPassword) {
    try {
      const response = await this.api.post('/vault/verify_master_password/', {
        master_password: masterPassword
      });
      return response.data;
    } catch (error) {
      // Add context to the error
      const contextError = new Error('Password verification failed: ' + error.message);
      contextError.errorData = error.errorData || {
        code: 'password_verification_failed',
        status: error.errorData?.status || 400,
        details: { originalError: error.message }
      };
      
      throw contextError;
    }
  }
  
  /**
   * Get all vault items for the authenticated user with optional lazy loading
   * @param {boolean} lazyLoad - If true, don't decrypt immediately (default: true)
   * @returns {Promise<Array>} Vault items (decrypted or with lazy-load flags)
   * @throws {Error} If retrieval fails
   */
  async getVaultItems(lazyLoad = true) {
    try {
      // Fetch items from backend with metadata_only flag if lazy loading
      const response = await this.api.get('/vault/', {
        params: { metadata_only: lazyLoad }
      });
      
      const items = response.data.items || response.data || [];
      
      if (lazyLoad) {
        // Return items with lazy decryption flag
        return items.map(item => ({
          ...item,
          _lazyLoaded: true,
          _decrypted: false,
          preview: {
            title: this.cryptoService.extractPreviewTitle(item.item_type),
            type: item.item_type,
            favorite: item.favorite,
            lastModified: item.updated_at
          }
        }));
      }
      
      // Full decryption (original behavior)
      const decryptedItems = await Promise.all(items.map(async (item) => {
        try {
          return await this.decryptItemFull(item);
        } catch (decryptError) {
          console.error(`Failed to decrypt item ${item.id}:`, decryptError);
          // Return item with placeholder data to prevent entire list from failing
          return {
            id: item.id,
            item_id: item.item_id,
            type: item.item_type,
            data: { error: 'This item could not be decrypted' },
            created_at: item.created_at,
            updated_at: item.updated_at,
            favorite: item.favorite || false,
            _decryptionFailed: true
          };
        }
      }));
      
      return decryptedItems;
    } catch (error) {
      const contextError = new Error('Failed to load vault items: ' + error.message);
      contextError.errorData = error.errorData || {
        code: 'items_retrieval_failed',
        status: error.errorData?.status || 500,
        details: { originalError: error.message }
      };
      throw contextError;
    }
  }
  
  /**
   * Decrypt a single item on-demand
   * @param {Object} item - The item to decrypt
   * @returns {Promise<Object>} Decrypted item
   * @throws {Error} If decryption fails
   */
  async decryptItemOnDemand(item) {
    // If already decrypted, return as-is
    if (item._decrypted) {
      return item;
    }
    
    try {
      console.time(`decrypt-item-${item.item_id}`);
      
      // Decrypt the item data
      const decryptedData = await this.cryptoService.decrypt(
        item.encrypted_data,
        this.encryptionKey
      );
      
      console.timeEnd(`decrypt-item-${item.item_id}`);
      
      // Return fully decrypted item
      return {
        ...item,
        data: decryptedData,
        _decrypted: true,
        _lazyLoaded: false
      };
      
    } catch (error) {
      console.error(`Failed to decrypt item ${item.item_id}:`, error);
      throw new Error('Failed to decrypt item: ' + error.message);
    }
  }
  
  /**
   * Bulk decrypt multiple items (for export, search, etc.)
   * @param {Array} items - Items to decrypt
   * @param {Function} onProgress - Progress callback (optional)
   * @returns {Promise<Array>} Decrypted items
   */
  async bulkDecryptItems(items, onProgress = null) {
    const decrypted = [];
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      
      try {
        const decryptedItem = await this.decryptItemOnDemand(item);
        decrypted.push(decryptedItem);
        
        if (onProgress) {
          onProgress((i + 1) / items.length * 100, decryptedItem);
        }
      } catch (error) {
        console.error(`Failed to decrypt item ${i}:`, error);
        // Continue with other items
      }
    }
    
    return decrypted;
  }
  
  /**
   * Full decryption (original method for backward compatibility)
   * @param {Object} item - The item to decrypt
   * @returns {Promise<Object>} Decrypted item
   */
  async decryptItemFull(item) {
    const decryptedData = await this.cryptoService.decrypt(
      item.encrypted_data,
      this.encryptionKey
    );
    
    return {
      id: item.id,
      item_id: item.item_id,
      type: item.item_type,
      data: decryptedData,
      favorite: item.favorite || false,
      created_at: item.created_at,
      updated_at: item.updated_at,
      _decrypted: true,
      _lazyLoaded: false
    };
  }
  
  /**
   * Save a vault item (create or update)
   * @param {Object} item - The item to save
   * @returns {Promise<Object>} API response data
   * @throws {Error} If saving fails
   */
  async saveVaultItem(item) {
    try {
      // Generate random item ID if new
      const itemId = item.item_id || this.generateRandomId();
      
      // Encrypt item data
      const encryptedData = await this.cryptoService.encrypt(
        item.data,
        this.encryptionKey
      );
      
      // Send to server
      const payload = {
        item_id: itemId,
        item_type: item.type, // Frontend uses 'type', backend uses 'item_type'
        encrypted_data: encryptedData,
        favorite: item.favorite || false
      };
      
      let response;
      
      if (item.id) {
        // Update existing item
        response = await this.api.put(`/vault/${item.id}/`, payload);
      } else {
        // Create new item
        response = await this.api.post('/vault/', payload);
      }
      
      return response;
    } catch (error) {
      const action = item.id ? 'update' : 'create';
      const contextError = new Error(`Failed to ${action} vault item: ${error.message}`);
      contextError.errorData = error.errorData || {
        code: `item_${action}_failed`,
        status: error.errorData?.status || 500,
        details: { 
          originalError: error.message,
          itemId: item.item_id
        }
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
      // Clear sensitive data
      if (this.cryptoService) {
        this.cryptoService.clearKeys();
      }
      this.encryptionKey = null;
      
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
   * Clear sensitive key data
   */
  clearKeys() {
    if (this.cryptoService) {
      this.cryptoService.clearKeys();
    }
    this.encryptionKey = null;
  }
  
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
   * Decrypt a single item (used by sync functions)
   * @param {string} encryptedData - Encrypted item data
   * @returns {Promise<Object>} Decrypted data
   * @throws {Error} If decryption fails
   */
  async decryptItem(encryptedData) {
    try {
      return await this.cryptoService.decrypt(encryptedData, this.encryptionKey);
    } catch (error) {
      const contextError = new Error('Failed to decrypt item: ' + error.message);
      contextError.errorData = {
        code: 'decryption_failed',
        status: 400,
        details: { originalError: error.message }
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

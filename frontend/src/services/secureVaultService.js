/**
 * SecureVaultService - Zero-Knowledge Vault Operations
 * 
 * This service manages vault operations with client-side encryption:
 * - All sensitive data encrypted in browser before sending to server
 * - Server stores only encrypted blobs
 * - Decryption happens only in browser
 * - Master password never sent to server
 * 
 * Architecture:
 * 1. Client derives encryption key from master password using Argon2id
 * 2. Data encrypted with AES-256-GCM before API calls
 * 3. Server stores encrypted_data blob + non-sensitive metadata
 * 4. Decryption happens on client after retrieval
 * 
 * @author SecureVault Password Manager
 * @version 2.0.0
 */

import axios from 'axios';
import { SecureVaultCrypto, getSecureVaultCrypto, resetSecureVaultCrypto } from './secureVaultCrypto';

// API Configuration
const API_BASE = '/api';
const VAULT_ENDPOINT = `${API_BASE}/vault`;

// Cache configuration
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * SecureVaultService class for zero-knowledge vault operations
 */
export class SecureVaultService {
  constructor() {
    this.crypto = null;
    this.initialized = false;
    this.userId = null;
    this.salt = null;
    
    // Local cache for decrypted items (never sent to server)
    this._decryptedCache = new Map();
    this._cacheTimestamps = new Map();
    
    // Session management
    this._sessionTimeout = null;
    this._sessionDuration = 15 * 60 * 1000; // 15 minutes default
    
    // Create axios instance with interceptors
    this.api = this._createApiClient();
  }

  /**
   * Create configured axios instance
   * @private
   */
  _createApiClient() {
    const client = axios.create({
      baseURL: API_BASE,
      headers: {
        'Content-Type': 'application/json'
      },
      // Enable compression
      decompress: true
    });

    // Request interceptor - add auth token
    client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('accessToken');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle errors
    client.interceptors.response.use(
      (response) => response,
      (error) => {
        const errorData = {
          status: error.response?.status || 500,
          code: error.response?.data?.code || 'unknown_error',
          message: error.response?.data?.message || error.message,
          details: error.response?.data?.details || {}
        };
        
        // Handle session expiry
        if (errorData.status === 401) {
          this.clearSession();
          window.dispatchEvent(new CustomEvent('vault:session-expired'));
        }
        
        const enhancedError = new Error(errorData.message);
        enhancedError.errorData = errorData;
        throw enhancedError;
      }
    );

    return client;
  }

  /**
   * Initialize the vault with master password
   * 
   * @param {string} masterPassword - User's master password
   * @returns {Promise<Object>} Initialization result
   */
  async initialize(masterPassword) {
    try {
      console.log('[SecureVault] Initializing vault service...');
      
      // Get user's salt from server
      const saltResponse = await this.api.get('/vault/get_salt/');
      this.salt = saltResponse.data.salt;
      this.userId = saltResponse.data.user_id;
      
      // Initialize crypto service with master password
      this.crypto = getSecureVaultCrypto();
      const success = await this.crypto.initialize(masterPassword, this.salt);
      
      if (!success) {
        throw new Error('Failed to initialize encryption');
      }
      
      // Generate auth hash for password verification (NOT the password itself)
      const authHash = await this.crypto.generateAuthHash(masterPassword, this.salt);
      
      // Verify with server using auth hash
      const verifyResponse = await this.api.post('/vault/verify_auth/', {
        auth_hash: authHash
      });
      
      if (!verifyResponse.data.valid) {
        throw new Error('Invalid master password');
      }
      
      this.initialized = true;
      this._startSessionTimer();
      
      console.log('[SecureVault] Vault initialized successfully');
      
      return {
        success: true,
        userId: this.userId,
        cryptoStatus: this.crypto.getStatus()
      };
      
    } catch (error) {
      console.error('[SecureVault] Initialization failed:', error);
      this.clearSession();
      throw error;
    }
  }

  /**
   * Save a vault item (create or update)
   * 
   * @param {Object} item - Item to save
   * @returns {Promise<Object>} Saved item (encrypted)
   */
  async saveItem(item) {
    this._ensureInitialized();
    
    try {
      // Extract sensitive data to encrypt
      const sensitiveData = {
        name: item.name,
        username: item.username,
        password: item.password,
        url: item.url,
        notes: item.notes,
        customFields: item.customFields || [],
        // Any other sensitive fields
      };
      
      // Encrypt sensitive data client-side
      const encryptedData = await this.crypto.encrypt(sensitiveData, {
        compress: true,
        additionalData: { itemId: item.item_id, type: item.type }
      });
      
      // Prepare payload with encrypted blob + non-sensitive metadata
      const payload = {
        item_id: item.item_id || this._generateItemId(),
        item_type: item.type || 'password',
        encrypted_data: JSON.stringify(encryptedData),
        favorite: item.favorite || false,
        folder_id: item.folder_id || null,
        // Non-sensitive metadata for search/filter (optional, hashed)
        domain_hash: item.url ? await this._hashDomain(item.url) : null,
        crypto_version: 2
      };
      
      let response;
      if (item.id) {
        // Update existing
        response = await this.api.put(`/vault/${item.id}/`, payload);
      } else {
        // Create new
        response = await this.api.post('/vault/', payload);
      }
      
      // Cache decrypted version locally
      const savedItem = response.data;
      this._cacheDecryptedItem(savedItem.id, {
        ...savedItem,
        _decrypted: sensitiveData
      });
      
      console.log('[SecureVault] Item saved successfully');
      return savedItem;
      
    } catch (error) {
      console.error('[SecureVault] Save failed:', error);
      throw error;
    }
  }

  /**
   * Get all vault items (encrypted from server, decrypted locally)
   * 
   * @param {Object} options - Fetch options
   * @returns {Promise<Array>} Decrypted vault items
   */
  async getItems(options = {}) {
    this._ensureInitialized();
    
    const {
      type = null,
      favorites = false,
      folder = null,
      lazyDecrypt = true
    } = options;
    
    try {
      // Build query params
      const params = new URLSearchParams();
      if (type) params.append('type', type);
      if (favorites) params.append('favorites', 'true');
      if (folder) params.append('folder', folder);
      
      // Fetch encrypted items from server
      const response = await this.api.get(`/vault/?${params}`);
      const encryptedItems = response.data.items || response.data || [];
      
      if (lazyDecrypt) {
        // Return items with lazy decryption markers
        return encryptedItems.map(item => ({
          ...item,
          _needsDecryption: true,
          _cached: this._decryptedCache.has(item.id)
        }));
      }
      
      // Decrypt all items
      const decryptedItems = await this.batchDecrypt(encryptedItems);
      return decryptedItems;
      
    } catch (error) {
      console.error('[SecureVault] Get items failed:', error);
      throw error;
    }
  }

  /**
   * Decrypt a single item on-demand
   * 
   * @param {Object} item - Encrypted item from server
   * @returns {Promise<Object>} Decrypted item
   */
  async decryptItem(item) {
    this._ensureInitialized();
    
    // Check cache first
    if (this._decryptedCache.has(item.id)) {
      const cached = this._decryptedCache.get(item.id);
      const timestamp = this._cacheTimestamps.get(item.id);
      
      if (Date.now() - timestamp < CACHE_TTL) {
        return cached;
      }
      // Cache expired, remove it
      this._decryptedCache.delete(item.id);
      this._cacheTimestamps.delete(item.id);
    }
    
    try {
      let encryptedData = item.encrypted_data;
      
      // Parse if string
      if (typeof encryptedData === 'string') {
        encryptedData = JSON.parse(encryptedData);
      }
      
      // Decrypt using crypto service
      const decryptedData = await this.crypto.decrypt(encryptedData, {
        additionalData: { itemId: item.item_id, type: item.item_type }
      });
      
      const decryptedItem = {
        id: item.id,
        item_id: item.item_id,
        type: item.item_type,
        favorite: item.favorite,
        folder_id: item.folder_id,
        created_at: item.created_at,
        updated_at: item.updated_at,
        data: decryptedData,
        _decrypted: true
      };
      
      // Cache decrypted item
      this._cacheDecryptedItem(item.id, decryptedItem);
      
      return decryptedItem;
      
    } catch (error) {
      console.error('[SecureVault] Decrypt failed:', error);
      throw new Error('Failed to decrypt item: ' + error.message);
    }
  }

  /**
   * Batch decrypt multiple items (optimized)
   * 
   * @param {Array} items - Encrypted items
   * @param {Function} onProgress - Progress callback
   * @returns {Promise<Array>} Decrypted items
   */
  async batchDecrypt(items, onProgress = null) {
    this._ensureInitialized();
    
    const results = [];
    const batchSize = 10; // Process in batches to avoid blocking UI
    
    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);
      
      const batchResults = await Promise.all(
        batch.map(async (item) => {
          try {
            return await this.decryptItem(item);
          } catch (error) {
            console.error(`[SecureVault] Failed to decrypt item ${item.id}:`, error);
            return {
              id: item.id,
              item_id: item.item_id,
              type: item.item_type,
              data: { error: 'Decryption failed' },
              _decryptionFailed: true
            };
          }
        })
      );
      
      results.push(...batchResults);
      
      if (onProgress) {
        onProgress((i + batch.length) / items.length * 100);
      }
      
      // Yield to browser for UI responsiveness
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    
    return results;
  }

  /**
   * Delete a vault item
   * 
   * @param {string} itemId - Item ID to delete
   * @returns {Promise<boolean>} Success status
   */
  async deleteItem(itemId) {
    this._ensureInitialized();
    
    try {
      await this.api.delete(`/vault/${itemId}/`);
      
      // Remove from cache
      this._decryptedCache.delete(itemId);
      this._cacheTimestamps.delete(itemId);
      
      return true;
    } catch (error) {
      console.error('[SecureVault] Delete failed:', error);
      throw error;
    }
  }

  /**
   * Search vault items (client-side search on decrypted data)
   * 
   * @param {string} query - Search query
   * @param {Array} items - Decrypted items to search
   * @returns {Array} Matching items
   */
  searchItems(query, items) {
    if (!query || !items?.length) return items || [];
    
    const lowerQuery = query.toLowerCase();
    
    return items.filter(item => {
      const data = item.data || item._decrypted;
      if (!data) return false;
      
      // Search in name, username, URL, notes
      const searchFields = [
        data.name,
        data.username,
        data.url,
        data.notes
      ].filter(Boolean);
      
      return searchFields.some(field => 
        field.toLowerCase().includes(lowerQuery)
      );
    });
  }

  /**
   * Export vault items (client-side operation)
   * 
   * @param {Array} items - Decrypted items to export
   * @param {string} format - Export format ('json' | 'csv')
   * @param {string} password - Optional encryption password for export
   * @returns {Promise<Blob>} Export file blob
   */
  async exportVault(items, format = 'json', password = null) {
    this._ensureInitialized();
    
    try {
      // Ensure all items are decrypted
      const decryptedItems = await this.batchDecrypt(items);
      
      let content;
      let mimeType;
      
      if (format === 'csv') {
        content = this._itemsToCSV(decryptedItems);
        mimeType = 'text/csv';
      } else {
        content = JSON.stringify({
          version: '2.0',
          exported_at: new Date().toISOString(),
          items: decryptedItems.map(item => ({
            type: item.type,
            ...item.data,
            favorite: item.favorite
          }))
        }, null, 2);
        mimeType = 'application/json';
      }
      
      // Optionally encrypt export
      if (password) {
        const exportCrypto = new SecureVaultCrypto();
        const exportSalt = exportCrypto.generateSalt();
        await exportCrypto.initialize(password, exportSalt);
        
        const encrypted = await exportCrypto.encrypt(content);
        content = JSON.stringify({
          encrypted: true,
          salt: exportCrypto._bytesToBase64(exportSalt),
          data: encrypted
        });
        
        exportCrypto.clearKeys();
      }
      
      return new Blob([content], { type: mimeType });
      
    } catch (error) {
      console.error('[SecureVault] Export failed:', error);
      throw error;
    }
  }

  /**
   * Import vault items from file
   * 
   * @param {File|string} data - Import data
   * @param {string} format - Import format
   * @param {string} password - Decryption password if encrypted
   * @returns {Promise<Object>} Import results
   */
  async importVault(data, format = 'json', password = null) {
    this._ensureInitialized();
    
    try {
      let content = typeof data === 'string' ? data : await data.text();
      let importData;
      
      // Handle encrypted export
      try {
        const parsed = JSON.parse(content);
        if (parsed.encrypted && password) {
          const importCrypto = new SecureVaultCrypto();
          const salt = importCrypto._base64ToBytes(parsed.salt);
          await importCrypto.initialize(password, salt);
          content = await importCrypto.decrypt(parsed.data);
          importCrypto.clearKeys();
        }
        importData = typeof content === 'string' ? JSON.parse(content) : content;
      } catch {
        importData = { items: [] };
      }
      
      const items = importData.items || [];
      const results = { imported: 0, failed: 0, errors: [] };
      
      for (const item of items) {
        try {
          await this.saveItem({
            type: item.type || 'password',
            name: item.name,
            username: item.username,
            password: item.password,
            url: item.url,
            notes: item.notes,
            customFields: item.customFields
          });
          results.imported++;
        } catch (error) {
          results.failed++;
          results.errors.push({ item: item.name, error: error.message });
        }
      }
      
      return results;
      
    } catch (error) {
      console.error('[SecureVault] Import failed:', error);
      throw error;
    }
  }

  /**
   * Clear session and sensitive data
   */
  clearSession() {
    if (this.crypto) {
      this.crypto.clearKeys();
    }
    
    resetSecureVaultCrypto();
    this.crypto = null;
    this.initialized = false;
    this.salt = null;
    this.userId = null;
    
    // Clear caches
    this._decryptedCache.clear();
    this._cacheTimestamps.clear();
    
    // Clear session timer
    if (this._sessionTimeout) {
      clearTimeout(this._sessionTimeout);
      this._sessionTimeout = null;
    }
    
    console.log('[SecureVault] Session cleared');
  }

  /**
   * Reset session timeout on user activity
   */
  resetSessionTimeout() {
    if (this._sessionTimeout) {
      clearTimeout(this._sessionTimeout);
      this._startSessionTimer();
    }
  }

  /**
   * Set session timeout duration
   * @param {number} minutes - Session duration in minutes
   */
  setSessionDuration(minutes) {
    this._sessionDuration = minutes * 60 * 1000;
  }

  // ============================================================================
  // PRIVATE HELPER METHODS
  // ============================================================================

  /**
   * Ensure service is initialized
   * @private
   */
  _ensureInitialized() {
    if (!this.initialized || !this.crypto) {
      throw new Error('Vault service not initialized. Call initialize() first.');
    }
  }

  /**
   * Start session timeout timer
   * @private
   */
  _startSessionTimer() {
    if (this._sessionTimeout) {
      clearTimeout(this._sessionTimeout);
    }
    
    this._sessionTimeout = setTimeout(() => {
      console.log('[SecureVault] Session expired');
      this.clearSession();
      window.dispatchEvent(new CustomEvent('vault:session-expired'));
    }, this._sessionDuration);
  }

  /**
   * Cache a decrypted item
   * @private
   */
  _cacheDecryptedItem(id, item) {
    this._decryptedCache.set(id, item);
    this._cacheTimestamps.set(id, Date.now());
    
    // Limit cache size
    if (this._decryptedCache.size > 500) {
      const oldest = [...this._cacheTimestamps.entries()]
        .sort((a, b) => a[1] - b[1])
        .slice(0, 100);
      
      oldest.forEach(([key]) => {
        this._decryptedCache.delete(key);
        this._cacheTimestamps.delete(key);
      });
    }
  }

  /**
   * Generate unique item ID
   * @private
   */
  _generateItemId() {
    const array = new Uint8Array(16);
    window.crypto.getRandomValues(array);
    return Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Hash domain for server-side search optimization
   * @private
   */
  async _hashDomain(url) {
    try {
      const domain = new URL(url).hostname;
      const encoder = new TextEncoder();
      const data = encoder.encode(domain);
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
    } catch {
      return null;
    }
  }

  /**
   * Convert items to CSV format
   * @private
   */
  _itemsToCSV(items) {
    const headers = ['name', 'username', 'password', 'url', 'notes', 'type'];
    const rows = items.map(item => {
      const data = item.data || {};
      return headers.map(h => {
        const value = data[h] || item[h] || '';
        // Escape CSV special characters
        return `"${String(value).replace(/"/g, '""')}"`;
      }).join(',');
    });
    
    return [headers.join(','), ...rows].join('\n');
  }
}

// Singleton instance
let secureVaultServiceInstance = null;

/**
 * Get singleton instance of SecureVaultService
 * @returns {SecureVaultService} Singleton instance
 */
export function getSecureVaultService() {
  if (!secureVaultServiceInstance) {
    secureVaultServiceInstance = new SecureVaultService();
  }
  return secureVaultServiceInstance;
}

/**
 * Reset singleton instance
 */
export function resetSecureVaultService() {
  if (secureVaultServiceInstance) {
    secureVaultServiceInstance.clearSession();
    secureVaultServiceInstance = null;
  }
}

export default SecureVaultService;


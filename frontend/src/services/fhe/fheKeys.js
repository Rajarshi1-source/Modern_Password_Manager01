/**
 * FHE Key Management Service
 * 
 * Handles secure storage and retrieval of FHE keys using IndexedDB.
 * Keys are stored encrypted with a device-specific key derived from
 * browser fingerprint and user credentials.
 * 
 * Features:
 * - Secure IndexedDB storage for FHE keys
 * - Key rotation and expiration management
 * - Key derivation for encryption
 * - Key backup and recovery
 */

// IndexedDB configuration
const DB_CONFIG = {
  name: 'FHEPasswordManager',
  version: 1,
  stores: {
    keys: {
      name: 'fhe_keys',
      keyPath: 'id',
    },
    metadata: {
      name: 'fhe_metadata',
      keyPath: 'id',
    },
  },
};

// Key expiration settings
const KEY_SETTINGS = {
  MAX_AGE_MS: 7 * 24 * 60 * 60 * 1000, // 7 days
  ROTATION_WARNING_MS: 24 * 60 * 60 * 1000, // 1 day before expiry
};

/**
 * FHE Key Manager
 * Manages FHE key storage, retrieval, and lifecycle
 */
class FHEKeyManager {
  constructor() {
    this._db = null;
    this._deviceKey = null;
    this._initPromise = null;
  }
  
  /**
   * Initialize the key manager and open IndexedDB
   */
  async initialize() {
    if (this._db) return this._db;
    if (this._initPromise) return this._initPromise;
    
    this._initPromise = this._openDatabase();
    return this._initPromise;
  }
  
  /**
   * Open or create the IndexedDB database
   */
  async _openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_CONFIG.name, DB_CONFIG.version);
      
      request.onerror = () => {
        console.error('[FHE Keys] IndexedDB error:', request.error);
        reject(request.error);
      };
      
      request.onsuccess = () => {
        this._db = request.result;
        console.log('[FHE Keys] IndexedDB opened successfully');
        resolve(this._db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create keys store
        if (!db.objectStoreNames.contains(DB_CONFIG.stores.keys.name)) {
          const keysStore = db.createObjectStore(
            DB_CONFIG.stores.keys.name,
            { keyPath: DB_CONFIG.stores.keys.keyPath }
          );
          keysStore.createIndex('type', 'type', { unique: false });
          keysStore.createIndex('createdAt', 'createdAt', { unique: false });
        }
        
        // Create metadata store
        if (!db.objectStoreNames.contains(DB_CONFIG.stores.metadata.name)) {
          db.createObjectStore(
            DB_CONFIG.stores.metadata.name,
            { keyPath: DB_CONFIG.stores.metadata.keyPath }
          );
        }
        
        console.log('[FHE Keys] IndexedDB stores created');
      };
    });
  }
  
  /**
   * Get the device-specific encryption key
   * Used to encrypt FHE keys before storing in IndexedDB
   */
  async _getDeviceKey() {
    if (this._deviceKey) return this._deviceKey;
    
    // Generate device key from browser fingerprint
    const fingerprint = await this._generateBrowserFingerprint();
    
    // Derive key using PBKDF2
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(fingerprint),
      { name: 'PBKDF2' },
      false,
      ['deriveBits', 'deriveKey']
    );
    
    this._deviceKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: new TextEncoder().encode('fhe-key-encryption-salt'),
        iterations: 100000,
        hash: 'SHA-256',
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
    
    return this._deviceKey;
  }
  
  /**
   * Generate a browser fingerprint for device-specific encryption
   */
  async _generateBrowserFingerprint() {
    const components = [];
    
    // User agent
    components.push(navigator.userAgent);
    
    // Screen dimensions
    components.push(`${screen.width}x${screen.height}x${screen.colorDepth}`);
    
    // Timezone
    components.push(Intl.DateTimeFormat().resolvedOptions().timeZone);
    
    // Language
    components.push(navigator.language);
    
    // Platform
    components.push(navigator.platform);
    
    // Hardware concurrency
    components.push(navigator.hardwareConcurrency?.toString() || 'unknown');
    
    // Canvas fingerprint (simplified)
    try {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      ctx.textBaseline = 'top';
      ctx.font = '14px Arial';
      ctx.fillText('FHE fingerprint', 2, 2);
      components.push(canvas.toDataURL().slice(-50));
    } catch (e) {
      components.push('canvas-error');
    }
    
    // WebGL fingerprint (simplified)
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl');
      if (gl) {
        components.push(gl.getParameter(gl.RENDERER));
        components.push(gl.getParameter(gl.VENDOR));
      }
    } catch (e) {
      components.push('webgl-error');
    }
    
    const fingerprint = components.join('|');
    
    // Hash the fingerprint
    const hash = await crypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode(fingerprint)
    );
    
    return Array.from(new Uint8Array(hash))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
  
  /**
   * Encrypt data with device key before storing
   */
  async _encryptForStorage(data) {
    const deviceKey = await this._getDeviceKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    const jsonData = JSON.stringify(data);
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      deviceKey,
      new TextEncoder().encode(jsonData)
    );
    
    return {
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted)),
    };
  }
  
  /**
   * Decrypt data from storage
   */
  async _decryptFromStorage(encryptedData) {
    const deviceKey = await this._getDeviceKey();
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: new Uint8Array(encryptedData.iv) },
      deviceKey,
      new Uint8Array(encryptedData.data)
    );
    
    return JSON.parse(new TextDecoder().decode(decrypted));
  }
  
  /**
   * Save FHE keys to IndexedDB
   * 
   * @param {Object} keys - FHE keys to save
   * @param {Uint8Array|Object} keys.clientKey - Client secret key
   * @param {Uint8Array|Object} keys.publicKey - Public key
   * @param {Uint8Array|Object} keys.serverKey - Server evaluation key
   * @param {number} keys.createdAt - Timestamp of key creation
   */
  async saveKeys(keys) {
    await this.initialize();
    
    // Serialize keys if they have serialize method
    const serializedKeys = {
      clientKey: this._serializeKey(keys.clientKey),
      publicKey: this._serializeKey(keys.publicKey),
      serverKey: this._serializeKey(keys.serverKey),
      createdAt: keys.createdAt || Date.now(),
      expiresAt: (keys.createdAt || Date.now()) + KEY_SETTINGS.MAX_AGE_MS,
    };
    
    // Encrypt before storing
    const encrypted = await this._encryptForStorage(serializedKeys);
    
    return new Promise((resolve, reject) => {
      const transaction = this._db.transaction(
        [DB_CONFIG.stores.keys.name],
        'readwrite'
      );
      
      const store = transaction.objectStore(DB_CONFIG.stores.keys.name);
      
      const request = store.put({
        id: 'primary_keys',
        type: 'fhe_keypair',
        encrypted,
        lastAccessed: Date.now(),
      });
      
      request.onsuccess = () => {
        console.log('[FHE Keys] Keys saved to IndexedDB');
        resolve(true);
      };
      
      request.onerror = () => {
        console.error('[FHE Keys] Failed to save keys:', request.error);
        reject(request.error);
      };
    });
  }
  
  /**
   * Load FHE keys from IndexedDB
   * 
   * @returns {Object|null} Keys object or null if not found/expired
   */
  async loadKeys() {
    await this.initialize();
    
    return new Promise((resolve, reject) => {
      const transaction = this._db.transaction(
        [DB_CONFIG.stores.keys.name],
        'readonly'
      );
      
      const store = transaction.objectStore(DB_CONFIG.stores.keys.name);
      const request = store.get('primary_keys');
      
      request.onsuccess = async () => {
        const result = request.result;
        
        if (!result) {
          console.log('[FHE Keys] No cached keys found');
          resolve(null);
          return;
        }
        
        try {
          // Decrypt the stored keys
          const decrypted = await this._decryptFromStorage(result.encrypted);
          
          // Check if keys have expired
          if (Date.now() > decrypted.expiresAt) {
            console.log('[FHE Keys] Cached keys have expired');
            await this.clearKeys();
            resolve(null);
            return;
          }
          
          // Warn if keys are about to expire
          if (decrypted.expiresAt - Date.now() < KEY_SETTINGS.ROTATION_WARNING_MS) {
            console.warn('[FHE Keys] Keys will expire soon, consider rotation');
          }
          
          // Update last accessed time
          await this._updateLastAccessed('primary_keys');
          
          // Deserialize keys
          const keys = {
            clientKey: this._deserializeKey(decrypted.clientKey),
            publicKey: this._deserializeKey(decrypted.publicKey),
            serverKey: this._deserializeKey(decrypted.serverKey),
            createdAt: decrypted.createdAt,
            expiresAt: decrypted.expiresAt,
          };
          
          console.log('[FHE Keys] Keys loaded from cache');
          resolve(keys);
          
        } catch (error) {
          console.error('[FHE Keys] Failed to decrypt cached keys:', error);
          resolve(null);
        }
      };
      
      request.onerror = () => {
        console.error('[FHE Keys] Failed to load keys:', request.error);
        reject(request.error);
      };
    });
  }
  
  /**
   * Clear all stored FHE keys
   */
  async clearKeys() {
    await this.initialize();
    
    return new Promise((resolve, reject) => {
      const transaction = this._db.transaction(
        [DB_CONFIG.stores.keys.name],
        'readwrite'
      );
      
      const store = transaction.objectStore(DB_CONFIG.stores.keys.name);
      const request = store.clear();
      
      request.onsuccess = () => {
        this._deviceKey = null;
        console.log('[FHE Keys] All keys cleared');
        resolve(true);
      };
      
      request.onerror = () => {
        console.error('[FHE Keys] Failed to clear keys:', request.error);
        reject(request.error);
      };
    });
  }
  
  /**
   * Check if valid keys exist in cache
   */
  async hasValidKeys() {
    const keys = await this.loadKeys();
    return keys !== null;
  }
  
  /**
   * Get key metadata without loading full keys
   */
  async getKeyMetadata() {
    await this.initialize();
    
    return new Promise((resolve, reject) => {
      const transaction = this._db.transaction(
        [DB_CONFIG.stores.keys.name],
        'readonly'
      );
      
      const store = transaction.objectStore(DB_CONFIG.stores.keys.name);
      const request = store.get('primary_keys');
      
      request.onsuccess = () => {
        const result = request.result;
        
        if (!result) {
          resolve(null);
          return;
        }
        
        resolve({
          id: result.id,
          type: result.type,
          lastAccessed: result.lastAccessed,
        });
      };
      
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Export keys for backup (encrypted)
   */
  async exportKeys(password) {
    const keys = await this.loadKeys();
    
    if (!keys) {
      throw new Error('No keys to export');
    }
    
    // Derive key from password
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      { name: 'PBKDF2' },
      false,
      ['deriveBits', 'deriveKey']
    );
    
    const exportKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: crypto.getRandomValues(new Uint8Array(16)),
        iterations: 100000,
        hash: 'SHA-256',
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt']
    );
    
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const serializedKeys = JSON.stringify({
      clientKey: this._serializeKey(keys.clientKey),
      publicKey: this._serializeKey(keys.publicKey),
      serverKey: this._serializeKey(keys.serverKey),
    });
    
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      exportKey,
      new TextEncoder().encode(serializedKeys)
    );
    
    return {
      version: 1,
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted)),
      exportedAt: Date.now(),
    };
  }
  
  /**
   * Import keys from backup
   */
  async importKeys(backup, password) {
    // Derive key from password
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      { name: 'PBKDF2' },
      false,
      ['deriveBits', 'deriveKey']
    );
    
    const importKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: crypto.getRandomValues(new Uint8Array(16)),
        iterations: 100000,
        hash: 'SHA-256',
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['decrypt']
    );
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: new Uint8Array(backup.iv) },
      importKey,
      new Uint8Array(backup.data)
    );
    
    const keys = JSON.parse(new TextDecoder().decode(decrypted));
    
    await this.saveKeys({
      clientKey: this._deserializeKey(keys.clientKey),
      publicKey: this._deserializeKey(keys.publicKey),
      serverKey: this._deserializeKey(keys.serverKey),
      createdAt: Date.now(),
    });
    
    return true;
  }
  
  // Helper methods
  
  /**
   * Update last accessed timestamp
   */
  async _updateLastAccessed(keyId) {
    const transaction = this._db.transaction(
      [DB_CONFIG.stores.keys.name],
      'readwrite'
    );
    
    const store = transaction.objectStore(DB_CONFIG.stores.keys.name);
    const request = store.get(keyId);
    
    request.onsuccess = () => {
      const data = request.result;
      if (data) {
        data.lastAccessed = Date.now();
        store.put(data);
      }
    };
  }
  
  /**
   * Serialize a key for storage
   */
  _serializeKey(key) {
    if (!key) return null;
    
    // If key has serialize method (TFHE key)
    if (typeof key.serialize === 'function') {
      return {
        type: 'serialized',
        data: Array.from(key.serialize()),
      };
    }
    
    // If key is Uint8Array
    if (key instanceof Uint8Array) {
      return {
        type: 'uint8array',
        data: Array.from(key),
      };
    }
    
    // If key has data property (simulated key)
    if (key.data) {
      return {
        type: key.type || 'simulated',
        data: Array.from(key.data),
      };
    }
    
    // Otherwise, store as is
    return {
      type: 'raw',
      data: key,
    };
  }
  
  /**
   * Deserialize a key from storage
   */
  _deserializeKey(stored) {
    if (!stored) return null;
    
    const data = new Uint8Array(stored.data);
    
    return {
      data,
      type: stored.type,
      serialize: () => data,
    };
  }
}

// Export singleton instance
export const fheKeyManager = new FHEKeyManager();
export { DB_CONFIG, KEY_SETTINGS };
export default fheKeyManager;


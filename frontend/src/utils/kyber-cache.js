/**
 * IndexedDB Cache for Kyber Operations
 * 
 * Client-side caching for:
 * - Public keys (with expiration)
 * - Encrypted passwords (offline access)
 * - Session data
 * 
 * Features:
 * - Automatic expiration and cleanup
 * - Quota management
 * - Encryption at rest (optional)
 * 
 * Usage:
 *   import { kyberCache } from '@/utils/kyber-cache';
 *   
 *   await kyberCache.init();
 *   await kyberCache.cachePublicKey(userId, publicKey);
 *   const key = await kyberCache.getCachedPublicKey(userId);
 */

const DB_NAME = 'KyberCacheDB';
const DB_VERSION = 1;

// Store names
const STORES = {
  PUBLIC_KEYS: 'publicKeys',
  ENCRYPTED_PASSWORDS: 'encryptedPasswords',
  SESSIONS: 'sessions',
  METADATA: 'metadata'
};

// Default TTLs (in milliseconds)
const TTL = {
  PUBLIC_KEY: 24 * 60 * 60 * 1000,      // 24 hours
  SESSION: 60 * 60 * 1000,               // 1 hour
  ENCRYPTED_PASSWORD: 7 * 24 * 60 * 60 * 1000  // 7 days
};

class KyberCache {
  constructor() {
    this.db = null;
    this.isInitialized = false;
    this.initPromise = null;
    
    // Performance metrics
    this.metrics = {
      hits: 0,
      misses: 0,
      sets: 0,
      deletes: 0,
      errors: 0
    };
  }

  /**
   * Initialize IndexedDB
   * 
   * @returns {Promise<IDBDatabase>} Database instance
   */
  async init() {
    // Return existing promise if initializing
    if (this.initPromise) {
      return this.initPromise;
    }
    
    // Return if already initialized
    if (this.isInitialized && this.db) {
      return this.db;
    }
    
    this.initPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      
      request.onerror = () => {
        console.error('[KyberCache] Failed to open database:', request.error);
        this.metrics.errors++;
        reject(request.error);
      };
      
      request.onsuccess = () => {
        this.db = request.result;
        this.isInitialized = true;
        console.log('[KyberCache] Database initialized');
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object stores
        
        // Public keys store
        if (!db.objectStoreNames.contains(STORES.PUBLIC_KEYS)) {
          const keyStore = db.createObjectStore(STORES.PUBLIC_KEYS, { keyPath: 'userId' });
          keyStore.createIndex('expiresAt', 'expiresAt', { unique: false });
          keyStore.createIndex('createdAt', 'createdAt', { unique: false });
        }
        
        // Encrypted passwords store
        if (!db.objectStoreNames.contains(STORES.ENCRYPTED_PASSWORDS)) {
          const pwdStore = db.createObjectStore(STORES.ENCRYPTED_PASSWORDS, { 
            keyPath: 'id',
            autoIncrement: true 
          });
          pwdStore.createIndex('userId', 'userId', { unique: false });
          pwdStore.createIndex('serviceName', 'serviceName', { unique: false });
          pwdStore.createIndex('userId_serviceName', ['userId', 'serviceName'], { unique: false });
          pwdStore.createIndex('expiresAt', 'expiresAt', { unique: false });
          pwdStore.createIndex('createdAt', 'createdAt', { unique: false });
        }
        
        // Sessions store
        if (!db.objectStoreNames.contains(STORES.SESSIONS)) {
          const sessionStore = db.createObjectStore(STORES.SESSIONS, { keyPath: 'sessionId' });
          sessionStore.createIndex('userId', 'userId', { unique: false });
          sessionStore.createIndex('expiresAt', 'expiresAt', { unique: false });
        }
        
        // Metadata store
        if (!db.objectStoreNames.contains(STORES.METADATA)) {
          db.createObjectStore(STORES.METADATA, { keyPath: 'key' });
        }
        
        console.log('[KyberCache] Database schema created');
      };
    });
    
    return this.initPromise;
  }

  /**
   * Ensure database is initialized
   * @private
   */
  async _ensureDb() {
    if (!this.isInitialized || !this.db) {
      await this.init();
    }
    return this.db;
  }

  // ===========================================================================
  // PUBLIC KEY CACHING
  // ===========================================================================

  /**
   * Cache a public key
   * 
   * @param {string|number} userId - User identifier
   * @param {string} publicKey - Base64-encoded public key
   * @param {Object} options - Options
   * @param {number} options.ttl - Time-to-live in ms
   * @param {string} options.algorithm - Algorithm name
   * @param {number} options.keyVersion - Key version
   */
  async cachePublicKey(userId, publicKey, options = {}) {
    const db = await this._ensureDb();
    
    const {
      ttl = TTL.PUBLIC_KEY,
      algorithm = 'Kyber768',
      keyVersion = 1
    } = options;
    
    const now = Date.now();
    
    const entry = {
      userId: String(userId),
      publicKey,
      algorithm,
      keyVersion,
      createdAt: now,
      expiresAt: now + ttl
    };
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.PUBLIC_KEYS], 'readwrite');
      const store = tx.objectStore(STORES.PUBLIC_KEYS);
      
      const request = store.put(entry);
      
      request.onsuccess = () => {
        this.metrics.sets++;
        console.log(`[KyberCache] Cached public key for user ${userId}`);
        resolve(true);
      };
      
      request.onerror = () => {
        this.metrics.errors++;
        console.error('[KyberCache] Error caching public key:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Get cached public key
   * 
   * @param {string|number} userId - User identifier
   * @returns {Promise<string|null>} Base64-encoded public key or null
   */
  async getCachedPublicKey(userId) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.PUBLIC_KEYS], 'readonly');
      const store = tx.objectStore(STORES.PUBLIC_KEYS);
      
      const request = store.get(String(userId));
      
      request.onsuccess = () => {
        const result = request.result;
        
        if (result && result.expiresAt > Date.now()) {
          this.metrics.hits++;
          resolve(result.publicKey);
        } else {
          this.metrics.misses++;
          
          // Delete expired entry
          if (result) {
            this.invalidatePublicKey(userId).catch(console.error);
          }
          
          resolve(null);
        }
      };
      
      request.onerror = () => {
        this.metrics.errors++;
        reject(request.error);
      };
    });
  }

  /**
   * Invalidate (delete) cached public key
   * 
   * @param {string|number} userId - User identifier
   */
  async invalidatePublicKey(userId) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.PUBLIC_KEYS], 'readwrite');
      const store = tx.objectStore(STORES.PUBLIC_KEYS);
      
      const request = store.delete(String(userId));
      
      request.onsuccess = () => {
        this.metrics.deletes++;
        resolve(true);
      };
      
      request.onerror = () => {
        this.metrics.errors++;
        reject(request.error);
      };
    });
  }

  // ===========================================================================
  // ENCRYPTED PASSWORD CACHING
  // ===========================================================================

  /**
   * Cache encrypted password
   * 
   * @param {Object} data - Password data
   * @param {string|number} data.userId - User identifier
   * @param {string} data.serviceName - Service name
   * @param {string} data.username - Username
   * @param {Object} data.encrypted - Encrypted data object
   * @param {number} data.ttl - Optional TTL
   */
  async cacheEncryptedPassword(data) {
    const db = await this._ensureDb();
    
    const {
      userId,
      serviceName,
      username,
      encrypted,
      ttl = TTL.ENCRYPTED_PASSWORD
    } = data;
    
    const now = Date.now();
    
    const entry = {
      userId: String(userId),
      serviceName,
      username,
      encrypted,
      createdAt: now,
      expiresAt: now + ttl,
      lastAccessed: now
    };
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.ENCRYPTED_PASSWORDS], 'readwrite');
      const store = tx.objectStore(STORES.ENCRYPTED_PASSWORDS);
      
      const request = store.add(entry);
      
      request.onsuccess = () => {
        this.metrics.sets++;
        resolve(request.result); // Return the auto-generated ID
      };
      
      request.onerror = () => {
        this.metrics.errors++;
        reject(request.error);
      };
    });
  }

  /**
   * Get cached encrypted passwords for a user
   * 
   * @param {string|number} userId - User identifier
   * @param {string} serviceName - Optional service name filter
   * @returns {Promise<Array>} Array of encrypted password entries
   */
  async getCachedPasswords(userId, serviceName = null) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.ENCRYPTED_PASSWORDS], 'readonly');
      const store = tx.objectStore(STORES.ENCRYPTED_PASSWORDS);
      
      let request;
      
      if (serviceName) {
        const index = store.index('userId_serviceName');
        request = index.getAll([String(userId), serviceName]);
      } else {
        const index = store.index('userId');
        request = index.getAll(String(userId));
      }
      
      request.onsuccess = () => {
        const now = Date.now();
        const results = request.result.filter(r => r.expiresAt > now);
        
        if (results.length > 0) {
          this.metrics.hits++;
        } else {
          this.metrics.misses++;
        }
        
        resolve(results);
      };
      
      request.onerror = () => {
        this.metrics.errors++;
        reject(request.error);
      };
    });
  }

  /**
   * Update encrypted password entry
   * 
   * @param {number} id - Entry ID
   * @param {Object} updates - Fields to update
   */
  async updateEncryptedPassword(id, updates) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.ENCRYPTED_PASSWORDS], 'readwrite');
      const store = tx.objectStore(STORES.ENCRYPTED_PASSWORDS);
      
      const getRequest = store.get(id);
      
      getRequest.onsuccess = () => {
        const entry = getRequest.result;
        
        if (!entry) {
          reject(new Error('Entry not found'));
          return;
        }
        
        const updated = {
          ...entry,
          ...updates,
          lastAccessed: Date.now()
        };
        
        const putRequest = store.put(updated);
        
        putRequest.onsuccess = () => resolve(true);
        putRequest.onerror = () => reject(putRequest.error);
      };
      
      getRequest.onerror = () => reject(getRequest.error);
    });
  }

  /**
   * Delete encrypted password entry
   * 
   * @param {number} id - Entry ID
   */
  async deleteEncryptedPassword(id) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.ENCRYPTED_PASSWORDS], 'readwrite');
      const store = tx.objectStore(STORES.ENCRYPTED_PASSWORDS);
      
      const request = store.delete(id);
      
      request.onsuccess = () => {
        this.metrics.deletes++;
        resolve(true);
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  // ===========================================================================
  // SESSION CACHING
  // ===========================================================================

  /**
   * Cache session data
   * 
   * @param {string} sessionId - Session identifier
   * @param {Object} data - Session data
   * @param {number} ttl - Time-to-live in ms
   */
  async cacheSession(sessionId, data, ttl = TTL.SESSION) {
    const db = await this._ensureDb();
    
    const now = Date.now();
    
    const entry = {
      sessionId,
      ...data,
      createdAt: now,
      expiresAt: now + ttl
    };
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.SESSIONS], 'readwrite');
      const store = tx.objectStore(STORES.SESSIONS);
      
      const request = store.put(entry);
      
      request.onsuccess = () => {
        this.metrics.sets++;
        resolve(true);
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get cached session
   * 
   * @param {string} sessionId - Session identifier
   * @returns {Promise<Object|null>} Session data or null
   */
  async getCachedSession(sessionId) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.SESSIONS], 'readonly');
      const store = tx.objectStore(STORES.SESSIONS);
      
      const request = store.get(sessionId);
      
      request.onsuccess = () => {
        const result = request.result;
        
        if (result && result.expiresAt > Date.now()) {
          this.metrics.hits++;
          resolve(result);
        } else {
          this.metrics.misses++;
          
          if (result) {
            this.invalidateSession(sessionId).catch(console.error);
          }
          
          resolve(null);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Invalidate session
   * 
   * @param {string} sessionId - Session identifier
   */
  async invalidateSession(sessionId) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORES.SESSIONS], 'readwrite');
      const store = tx.objectStore(STORES.SESSIONS);
      
      const request = store.delete(sessionId);
      
      request.onsuccess = () => {
        this.metrics.deletes++;
        resolve(true);
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  // ===========================================================================
  // CACHE MANAGEMENT
  // ===========================================================================

  /**
   * Clear all expired entries from all stores
   */
  async clearExpiredCache() {
    const db = await this._ensureDb();
    const now = Date.now();
    let deletedCount = 0;
    
    console.log('[KyberCache] Clearing expired entries...');
    
    // Clear expired public keys
    deletedCount += await this._clearExpiredFromStore(
      STORES.PUBLIC_KEYS, 
      'expiresAt', 
      now
    );
    
    // Clear expired passwords
    deletedCount += await this._clearExpiredFromStore(
      STORES.ENCRYPTED_PASSWORDS, 
      'expiresAt', 
      now
    );
    
    // Clear expired sessions
    deletedCount += await this._clearExpiredFromStore(
      STORES.SESSIONS, 
      'expiresAt', 
      now
    );
    
    console.log(`[KyberCache] Cleared ${deletedCount} expired entries`);
    return deletedCount;
  }

  /**
   * Clear expired entries from a specific store
   * @private
   */
  async _clearExpiredFromStore(storeName, indexName, now) {
    const db = await this._ensureDb();
    
    return new Promise((resolve, reject) => {
      const tx = db.transaction([storeName], 'readwrite');
      const store = tx.objectStore(storeName);
      const index = store.index(indexName);
      
      const range = IDBKeyRange.upperBound(now);
      const request = index.openCursor(range);
      
      let deletedCount = 0;
      
      request.onsuccess = (event) => {
        const cursor = event.target.result;
        
        if (cursor) {
          cursor.delete();
          deletedCount++;
          this.metrics.deletes++;
          cursor.continue();
        } else {
          resolve(deletedCount);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Clear all cache data
   */
  async clearAll() {
    const db = await this._ensureDb();
    
    const stores = [
      STORES.PUBLIC_KEYS,
      STORES.ENCRYPTED_PASSWORDS,
      STORES.SESSIONS
    ];
    
    for (const storeName of stores) {
      await new Promise((resolve, reject) => {
        const tx = db.transaction([storeName], 'readwrite');
        const store = tx.objectStore(storeName);
        const request = store.clear();
        
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });
    }
    
    console.log('[KyberCache] All cache cleared');
  }

  /**
   * Get cache statistics
   */
  async getStats() {
    const db = await this._ensureDb();
    
    const stats = {
      publicKeys: 0,
      encryptedPasswords: 0,
      sessions: 0,
      totalSize: 0
    };
    
    for (const [key, storeName] of Object.entries({
      publicKeys: STORES.PUBLIC_KEYS,
      encryptedPasswords: STORES.ENCRYPTED_PASSWORDS,
      sessions: STORES.SESSIONS
    })) {
      const count = await new Promise((resolve, reject) => {
        const tx = db.transaction([storeName], 'readonly');
        const store = tx.objectStore(storeName);
        const request = store.count();
        
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      
      stats[key] = count;
    }
    
    return stats;
  }

  /**
   * Get performance metrics
   */
  getMetrics() {
    const total = this.metrics.hits + this.metrics.misses;
    
    return {
      ...this.metrics,
      hitRate: total > 0 ? (this.metrics.hits / total * 100).toFixed(2) + '%' : '0%',
      totalOperations: this.metrics.hits + this.metrics.misses + this.metrics.sets + this.metrics.deletes
    };
  }

  /**
   * Reset metrics
   */
  resetMetrics() {
    this.metrics = {
      hits: 0,
      misses: 0,
      sets: 0,
      deletes: 0,
      errors: 0
    };
  }

  /**
   * Check if IndexedDB is supported
   */
  static isSupported() {
    return typeof indexedDB !== 'undefined';
  }
}

// Export singleton instance
export const kyberCache = new KyberCache();

// Export class for testing
export { KyberCache };

// Export constants
export { STORES, TTL };


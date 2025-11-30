/**
 * useKyber - React Hook for Kyber Cryptographic Operations
 * 
 * Provides easy access to CRYSTALS-Kyber post-quantum cryptography:
 * - WASM module initialization
 * - Web Worker for background operations
 * - IndexedDB caching
 * - Automatic key management
 * 
 * Usage:
 *   import { useKyber } from '@/hooks/useKyber';
 *   
 *   function MyComponent() {
 *     const { 
 *       isReady, 
 *       isLoading, 
 *       encryptPassword, 
 *       generateKeypair 
 *     } = useKyber();
 *     
 *     const handleEncrypt = async () => {
 *       const encrypted = await encryptPassword('my-password', 'Google');
 *     };
 *   }
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { kyberWasm } from '../utils/kyber-wasm-loader';
import { kyberCache } from '../utils/kyber-cache';

// Web Worker code as a blob URL
const WORKER_CODE = `
// Import worker code
self.onmessage = async (event) => {
  const { type, id, payload } = event.data;
  
  try {
    let result;
    
    switch (type) {
      case 'GENERATE_KEYPAIR':
        result = await generateKeypair();
        break;
      case 'ENCRYPT':
        result = await encryptData(payload);
        break;
      case 'DECRYPT':
        result = await decryptData(payload);
        break;
      case 'BATCH_ENCRYPT':
        result = await batchEncrypt(payload);
        break;
      default:
        throw new Error('Unknown operation: ' + type);
    }
    
    self.postMessage({ type: 'SUCCESS', id, result });
  } catch (error) {
    self.postMessage({ type: 'ERROR', id, error: error.message });
  }
};

async function generateKeypair() {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits']
  );
  const publicKey = await crypto.subtle.exportKey('raw', keyPair.publicKey);
  const privateKey = await crypto.subtle.exportKey('pkcs8', keyPair.privateKey);
  return {
    publicKey: arrayToBase64(new Uint8Array(publicKey)),
    privateKey: arrayToBase64(new Uint8Array(privateKey))
  };
}

async function encryptData({ plaintext, publicKey }) {
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const key = await crypto.subtle.importKey(
    'raw',
    base64ToArray(publicKey).slice(0, 32),
    { name: 'AES-GCM' },
    false,
    ['encrypt']
  );
  const plaintextBytes = new TextEncoder().encode(plaintext);
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce },
    key,
    plaintextBytes
  );
  return {
    ciphertext: arrayToBase64(new Uint8Array(encrypted)),
    nonce: arrayToBase64(nonce)
  };
}

async function decryptData({ ciphertext, nonce, privateKey }) {
  const key = await crypto.subtle.importKey(
    'raw',
    base64ToArray(privateKey).slice(0, 32),
    { name: 'AES-GCM' },
    false,
    ['decrypt']
  );
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: base64ToArray(nonce) },
    key,
    base64ToArray(ciphertext)
  );
  return { plaintext: new TextDecoder().decode(decrypted) };
}

async function batchEncrypt({ items, publicKey }) {
  const results = [];
  for (const item of items) {
    try {
      const result = await encryptData({ plaintext: item.plaintext, publicKey });
      results.push({ ...result, success: true });
    } catch (error) {
      results.push({ error: error.message, success: false });
    }
  }
  return { results };
}

function arrayToBase64(array) {
  let binary = '';
  for (let i = 0; i < array.length; i++) {
    binary += String.fromCharCode(array[i]);
  }
  return btoa(binary);
}

function base64ToArray(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

self.postMessage({ type: 'READY' });
`;

/**
 * useKyber Hook
 * 
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoInit - Auto-initialize on mount (default: true)
 * @param {boolean} options.useWorker - Use Web Worker for operations (default: true)
 * @param {boolean} options.useCache - Use IndexedDB cache (default: true)
 * @returns {Object} Kyber hook interface
 */
export function useKyber(options = {}) {
  const {
    autoInit = true,
    useWorker = true,
    useCache = true
  } = options;
  
  // State
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isQuantumResistant, setIsQuantumResistant] = useState(false);
  
  // Refs
  const workerRef = useRef(null);
  const pendingOperations = useRef(new Map());
  const operationIdRef = useRef(0);
  
  // Initialize worker
  const initWorker = useCallback(() => {
    if (!useWorker || workerRef.current) return;
    
    try {
      const blob = new Blob([WORKER_CODE], { type: 'application/javascript' });
      const workerUrl = URL.createObjectURL(blob);
      workerRef.current = new Worker(workerUrl);
      
      workerRef.current.onmessage = (event) => {
        const { type, id, result, error: workerError } = event.data;
        
        if (type === 'READY') {
          console.log('[useKyber] Worker ready');
          return;
        }
        
        const pending = pendingOperations.current.get(id);
        if (pending) {
          if (type === 'SUCCESS') {
            pending.resolve(result);
          } else {
            pending.reject(new Error(workerError));
          }
          pendingOperations.current.delete(id);
        }
      };
      
      workerRef.current.onerror = (err) => {
        console.error('[useKyber] Worker error:', err);
      };
      
      console.log('[useKyber] Worker initialized');
    } catch (err) {
      console.warn('[useKyber] Worker initialization failed:', err);
    }
  }, [useWorker]);
  
  // Send message to worker
  const sendToWorker = useCallback((type, payload) => {
    return new Promise((resolve, reject) => {
      if (!workerRef.current) {
        reject(new Error('Worker not initialized'));
        return;
      }
      
      const id = ++operationIdRef.current;
      pendingOperations.current.set(id, { resolve, reject });
      
      workerRef.current.postMessage({ type, id, payload });
    });
  }, []);
  
  // Initialize everything
  const initialize = useCallback(async () => {
    if (isReady || isLoading) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Initialize WASM module
      await kyberWasm.loadModule();
      
      // Initialize IndexedDB cache
      if (useCache) {
        await kyberCache.init();
      }
      
      // Initialize worker
      initWorker();
      
      // Check if quantum resistant
      const status = kyberWasm.getStatus();
      setIsQuantumResistant(!status.isFallback);
      
      setIsReady(true);
      console.log('[useKyber] Initialized successfully');
      
    } catch (err) {
      console.error('[useKyber] Initialization failed:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [isReady, isLoading, useCache, initWorker]);
  
  // Auto-initialize on mount
  useEffect(() => {
    if (autoInit) {
      initialize();
    }
    
    // Cleanup worker on unmount
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, [autoInit, initialize]);
  
  // ===========================================================================
  // PUBLIC METHODS
  // ===========================================================================
  
  /**
   * Generate a new Kyber keypair
   */
  const generateKeypair = useCallback(async () => {
    if (!isReady) {
      throw new Error('Kyber not initialized');
    }
    
    setIsLoading(true);
    
    try {
      const keypair = await kyberWasm.generateKeypair();
      return keypair;
    } finally {
      setIsLoading(false);
    }
  }, [isReady]);
  
  /**
   * Encrypt a password
   * 
   * @param {string} password - Password to encrypt
   * @param {string} serviceName - Service name (for caching)
   * @param {string} publicKey - Optional public key (uses cached if not provided)
   */
  const encryptPassword = useCallback(async (password, serviceName, publicKey = null) => {
    if (!isReady) {
      throw new Error('Kyber not initialized');
    }
    
    setIsLoading(true);
    
    try {
      // Get public key from cache if not provided
      let key = publicKey;
      
      if (!key && useCache) {
        key = await kyberCache.getCachedPublicKey('current_user');
      }
      
      if (!key) {
        // Generate new keypair if needed
        const keypair = await generateKeypair();
        key = keypair.publicKey;
        
        if (useCache) {
          await kyberCache.cachePublicKey('current_user', key);
        }
      }
      
      // Encrypt using WASM
      const encrypted = await kyberWasm.encrypt(
        new TextEncoder().encode(password),
        kyberWasm.hexToBuffer(key)
      );
      
      // Cache encrypted password
      if (useCache) {
        await kyberCache.cacheEncryptedPassword({
          userId: 'current_user',
          serviceName,
          username: '',
          encrypted
        });
      }
      
      return encrypted;
      
    } finally {
      setIsLoading(false);
    }
  }, [isReady, useCache, generateKeypair]);
  
  /**
   * Decrypt a password
   * 
   * @param {Object} encryptedData - Encrypted data object
   * @param {string} privateKey - Private key for decryption
   */
  const decryptPassword = useCallback(async (encryptedData, privateKey) => {
    if (!isReady) {
      throw new Error('Kyber not initialized');
    }
    
    setIsLoading(true);
    
    try {
      const decrypted = await kyberWasm.decrypt(
        encryptedData,
        kyberWasm.hexToBuffer(privateKey)
      );
      
      return new TextDecoder().decode(decrypted);
      
    } finally {
      setIsLoading(false);
    }
  }, [isReady]);
  
  /**
   * Batch encrypt multiple items
   * 
   * @param {Array} items - Array of { password, serviceName } objects
   * @param {string} publicKey - Public key for encryption
   */
  const batchEncrypt = useCallback(async (items, publicKey = null) => {
    if (!isReady) {
      throw new Error('Kyber not initialized');
    }
    
    setIsLoading(true);
    
    try {
      // Get public key
      let key = publicKey;
      
      if (!key && useCache) {
        key = await kyberCache.getCachedPublicKey('current_user');
      }
      
      if (!key) {
        const keypair = await generateKeypair();
        key = keypair.publicKey;
      }
      
      // Use worker for batch operations
      if (workerRef.current) {
        const result = await sendToWorker('BATCH_ENCRYPT', {
          items: items.map(item => ({
            plaintext: item.password,
            serviceName: item.serviceName
          })),
          publicKey: key
        });
        
        return result.results;
      }
      
      // Fallback to sequential encryption
      const results = [];
      
      for (const item of items) {
        try {
          const encrypted = await encryptPassword(item.password, item.serviceName, key);
          results.push({ ...encrypted, success: true, serviceName: item.serviceName });
        } catch (err) {
          results.push({ success: false, error: err.message, serviceName: item.serviceName });
        }
      }
      
      return results;
      
    } finally {
      setIsLoading(false);
    }
  }, [isReady, useCache, generateKeypair, encryptPassword, sendToWorker]);
  
  /**
   * Cache a public key
   * 
   * @param {string} userId - User identifier
   * @param {string} publicKey - Public key to cache
   */
  const cachePublicKey = useCallback(async (userId, publicKey) => {
    if (!useCache) return;
    
    await kyberCache.cachePublicKey(userId, publicKey);
  }, [useCache]);
  
  /**
   * Get cached public key
   * 
   * @param {string} userId - User identifier
   */
  const getCachedPublicKey = useCallback(async (userId) => {
    if (!useCache) return null;
    
    return await kyberCache.getCachedPublicKey(userId);
  }, [useCache]);
  
  /**
   * Get cached passwords for a service
   * 
   * @param {string} serviceName - Service name filter
   */
  const getCachedPasswords = useCallback(async (serviceName = null) => {
    if (!useCache) return [];
    
    return await kyberCache.getCachedPasswords('current_user', serviceName);
  }, [useCache]);
  
  /**
   * Clear expired cache entries
   */
  const clearExpiredCache = useCallback(async () => {
    if (!useCache) return;
    
    await kyberCache.clearExpiredCache();
  }, [useCache]);
  
  /**
   * Get cache statistics
   */
  const getCacheStats = useCallback(async () => {
    if (!useCache) return null;
    
    return await kyberCache.getStats();
  }, [useCache]);
  
  /**
   * Get performance metrics
   */
  const getMetrics = useCallback(() => {
    return {
      wasm: kyberWasm.getMetrics(),
      cache: useCache ? kyberCache.getMetrics() : null,
      isQuantumResistant
    };
  }, [useCache, isQuantumResistant]);
  
  /**
   * Get Kyber status
   */
  const getStatus = useCallback(() => {
    return {
      isReady,
      isLoading,
      isQuantumResistant,
      error,
      wasm: kyberWasm.getStatus(),
      workerActive: !!workerRef.current
    };
  }, [isReady, isLoading, isQuantumResistant, error]);
  
  // Return hook interface
  return {
    // State
    isReady,
    isLoading,
    isQuantumResistant,
    error,
    
    // Initialization
    initialize,
    
    // Key operations
    generateKeypair,
    
    // Encryption/Decryption
    encryptPassword,
    decryptPassword,
    batchEncrypt,
    
    // Caching
    cachePublicKey,
    getCachedPublicKey,
    getCachedPasswords,
    clearExpiredCache,
    getCacheStats,
    
    // Metrics
    getMetrics,
    getStatus
  };
}

// Export default
export default useKyber;


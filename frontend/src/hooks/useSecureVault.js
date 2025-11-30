/**
 * useSecureVault - React Hook for Zero-Knowledge Vault Operations
 * 
 * Provides a React-friendly interface to the SecureVaultService:
 * - Initialization with master password
 * - CRUD operations for vault items
 * - Client-side encryption/decryption
 * - Session management
 * 
 * All sensitive data is encrypted client-side before being sent to the server.
 * The server never sees plaintext passwords.
 * 
 * Usage:
 *   import { useSecureVault } from '@/hooks/useSecureVault';
 *   
 *   function VaultComponent() {
 *     const { 
 *       isInitialized, 
 *       items, 
 *       saveItem, 
 *       decryptItem,
 *       initialize 
 *     } = useSecureVault();
 *     
 *     // Initialize vault with master password
 *     await initialize(masterPassword);
 *     
 *     // Save encrypted item
 *     await saveItem({ name: 'Google', password: 'secret' });
 *   }
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { 
  SecureVaultService, 
  getSecureVaultService, 
  resetSecureVaultService 
} from '../services/secureVaultService';

/**
 * useSecureVault Hook
 * 
 * @param {Object} options - Hook options
 * @param {number} options.sessionTimeout - Session timeout in minutes (default: 15)
 * @param {boolean} options.autoLoadItems - Auto-load items after initialization
 * @returns {Object} Vault hook interface
 */
export function useSecureVault(options = {}) {
  const {
    sessionTimeout = 15,
    autoLoadItems = true
  } = options;
  
  // State
  const [isInitialized, setIsInitialized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [items, setItems] = useState([]);
  const [cryptoStatus, setCryptoStatus] = useState(null);
  const [stats, setStats] = useState(null);
  
  // Service reference
  const serviceRef = useRef(null);
  
  // Activity tracking for session management
  const lastActivityRef = useRef(Date.now());
  
  /**
   * Get or create vault service
   */
  const getService = useCallback(() => {
    if (!serviceRef.current) {
      serviceRef.current = getSecureVaultService();
    }
    return serviceRef.current;
  }, []);
  
  /**
   * Track user activity
   */
  const trackActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    
    if (serviceRef.current?.initialized) {
      serviceRef.current.resetSessionTimeout();
    }
  }, []);
  
  /**
   * Initialize vault with master password
   * 
   * @param {string} masterPassword - User's master password
   * @returns {Promise<Object>} Initialization result
   */
  const initialize = useCallback(async (masterPassword) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const service = getService();
      service.setSessionDuration(sessionTimeout);
      
      const result = await service.initialize(masterPassword);
      
      setIsInitialized(true);
      setCryptoStatus(result.cryptoStatus);
      
      // Auto-load items if enabled
      if (autoLoadItems) {
        const loadedItems = await service.getItems({ lazyDecrypt: true });
        setItems(loadedItems);
      }
      
      console.log('[useSecureVault] Vault initialized');
      return result;
      
    } catch (err) {
      setError(err.message);
      setIsInitialized(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [getService, sessionTimeout, autoLoadItems]);
  
  /**
   * Load vault items
   * 
   * @param {Object} options - Load options
   * @returns {Promise<Array>} Loaded items
   */
  const loadItems = useCallback(async (options = {}) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      const loadedItems = await service.getItems(options);
      setItems(loadedItems);
      return loadedItems;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, getService, trackActivity]);
  
  /**
   * Save a vault item (create or update)
   * 
   * @param {Object} item - Item to save
   * @returns {Promise<Object>} Saved item
   */
  const saveItem = useCallback(async (item) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      const savedItem = await service.saveItem(item);
      
      // Update local items list
      setItems(prevItems => {
        const existingIndex = prevItems.findIndex(i => i.id === savedItem.id);
        if (existingIndex >= 0) {
          const newItems = [...prevItems];
          newItems[existingIndex] = savedItem;
          return newItems;
        }
        return [...prevItems, savedItem];
      });
      
      return savedItem;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, getService, trackActivity]);
  
  /**
   * Decrypt a single item on-demand
   * 
   * @param {Object} item - Encrypted item
   * @returns {Promise<Object>} Decrypted item
   */
  const decryptItem = useCallback(async (item) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    trackActivity();
    
    try {
      const service = getService();
      const decrypted = await service.decryptItem(item);
      
      // Update item in local state
      setItems(prevItems => 
        prevItems.map(i => i.id === item.id ? decrypted : i)
      );
      
      return decrypted;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [isInitialized, getService, trackActivity]);
  
  /**
   * Batch decrypt multiple items
   * 
   * @param {Array} itemsToDecrypt - Items to decrypt
   * @param {Function} onProgress - Progress callback
   * @returns {Promise<Array>} Decrypted items
   */
  const batchDecrypt = useCallback(async (itemsToDecrypt, onProgress = null) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      const decrypted = await service.batchDecrypt(itemsToDecrypt, onProgress);
      
      // Update items in local state
      setItems(prevItems => {
        const decryptedMap = new Map(decrypted.map(d => [d.id, d]));
        return prevItems.map(item => decryptedMap.get(item.id) || item);
      });
      
      return decrypted;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, getService, trackActivity]);
  
  /**
   * Delete a vault item
   * 
   * @param {string} itemId - Item ID to delete
   * @returns {Promise<boolean>} Success status
   */
  const deleteItem = useCallback(async (itemId) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      await service.deleteItem(itemId);
      
      // Remove from local state
      setItems(prevItems => prevItems.filter(i => i.id !== itemId));
      
      return true;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, getService, trackActivity]);
  
  /**
   * Search items (client-side on decrypted data)
   * 
   * @param {string} query - Search query
   * @returns {Array} Matching items
   */
  const searchItems = useCallback((query) => {
    if (!isInitialized || !items.length) return [];
    
    trackActivity();
    
    const service = getService();
    return service.searchItems(query, items);
  }, [isInitialized, items, getService, trackActivity]);
  
  /**
   * Export vault
   * 
   * @param {string} format - Export format ('json' | 'csv')
   * @param {string} password - Optional encryption password
   * @returns {Promise<Blob>} Export blob
   */
  const exportVault = useCallback(async (format = 'json', password = null) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      return await service.exportVault(items, format, password);
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, items, getService, trackActivity]);
  
  /**
   * Import vault
   * 
   * @param {File|string} data - Import data
   * @param {string} format - Import format
   * @param {string} password - Decryption password if encrypted
   * @returns {Promise<Object>} Import results
   */
  const importVault = useCallback(async (data, format = 'json', password = null) => {
    if (!isInitialized) {
      throw new Error('Vault not initialized');
    }
    
    setIsLoading(true);
    trackActivity();
    
    try {
      const service = getService();
      const result = await service.importVault(data, format, password);
      
      // Reload items after import
      await loadItems();
      
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [isInitialized, getService, trackActivity, loadItems]);
  
  /**
   * Generate a secure password
   * 
   * @param {number} length - Password length
   * @param {Object} options - Generation options
   * @returns {string} Generated password
   */
  const generatePassword = useCallback((length = 20, options = {}) => {
    if (!isInitialized) {
      // Can still generate password without full init
      const { SecureVaultCrypto } = require('../services/secureVaultCrypto');
      const crypto = new SecureVaultCrypto();
      return crypto.generatePassword(length, options);
    }
    
    const service = getService();
    return service.crypto.generatePassword(length, options);
  }, [isInitialized, getService]);
  
  /**
   * Lock the vault (clear session)
   */
  const lock = useCallback(() => {
    resetSecureVaultService();
    serviceRef.current = null;
    setIsInitialized(false);
    setItems([]);
    setCryptoStatus(null);
    setError(null);
    
    console.log('[useSecureVault] Vault locked');
  }, []);
  
  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);
  
  // Listen for session expiry events
  useEffect(() => {
    const handleSessionExpiry = () => {
      console.log('[useSecureVault] Session expired');
      lock();
    };
    
    window.addEventListener('vault:session-expired', handleSessionExpiry);
    
    return () => {
      window.removeEventListener('vault:session-expired', handleSessionExpiry);
    };
  }, [lock]);
  
  // Track activity on user interactions
  useEffect(() => {
    if (!isInitialized) return;
    
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    
    events.forEach(event => {
      window.addEventListener(event, trackActivity, { passive: true });
    });
    
    return () => {
      events.forEach(event => {
        window.removeEventListener(event, trackActivity);
      });
    };
  }, [isInitialized, trackActivity]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Don't clear service on unmount - it should persist across components
      // Only clear on explicit lock or session expiry
    };
  }, []);
  
  return {
    // State
    isInitialized,
    isLoading,
    error,
    items,
    cryptoStatus,
    stats,
    
    // Actions
    initialize,
    loadItems,
    saveItem,
    decryptItem,
    batchDecrypt,
    deleteItem,
    searchItems,
    exportVault,
    importVault,
    generatePassword,
    lock,
    clearError,
    
    // Utilities
    trackActivity
  };
}

export default useSecureVault;


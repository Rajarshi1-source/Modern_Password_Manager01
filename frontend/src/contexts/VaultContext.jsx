import React, { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { VaultService } from '../services/vaultService';
import firebaseService from '../services/firebaseService';
import api from '../services/api';

const VaultContext = createContext();

// Default auto-lock timeout in minutes
const DEFAULT_AUTO_LOCK_TIMEOUT = 5;
// Maximum number of pending changes to prevent memory issues
const MAX_PENDING_CHANGES = 500;

export const VaultProvider = ({ children }) => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoLockTimeout, setAutoLockTimeout] = useState(
    parseInt(localStorage.getItem('autoLockTimeout')) || DEFAULT_AUTO_LOCK_TIMEOUT
  );
  const [syncStatus, setSyncStatus] = useState('idle');
  const [firebaseInitialized, setFirebaseInitialized] = useState(false);
  const [pendingChanges, setPendingChanges] = useState([]);
  const [lastSyncTime, setLastSyncTime] = useState(localStorage.getItem('lastSyncTime') || new Date().toISOString());
  const [decryptedItems, setDecryptedItems] = useState(new Map());
  const [lazyLoadEnabled, setLazyLoadEnabled] = useState(true);
  
  // Fix #8: Use useMemo for vaultService
  const vaultService = useMemo(() => new VaultService(), []);
  
  const autoLockTimerRef = useRef(null);
  const broadcastChannelRef = useRef(null);
  const lastActivityRef = useRef(Date.now());
  const isMountedRef = useRef(true); // Fix #6: Track component mount state
  
  // Clean up mounted ref on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);
  
  const updateActivity = () => { 
    lastActivityRef.current = Date.now(); 
  };
  
  // Initialize broadcast channel for cross-tab communication
  useEffect(() => {
    if (typeof BroadcastChannel !== 'undefined') {
      broadcastChannelRef.current = new BroadcastChannel('vault_state_channel');
      
      broadcastChannelRef.current.onmessage = (event) => {
        if (event.data.type === 'LOCK_VAULT') {
          // Another tab locked the vault, lock this one too
          handleLockVault(false); // Don't broadcast again to avoid loops
        } else if (event.data.type === 'VAULT_UPDATED') {
          // Another tab updated the vault items, refresh if unlocked
          if (isUnlocked) {
            refreshItems();
          }
        }
      };
      
      return () => {
        broadcastChannelRef.current.close();
      };
    } else {
      // Fallback for browsers that don't support BroadcastChannel
      window.addEventListener('storage', handleStorageEvent);
      return () => {
        window.removeEventListener('storage', handleStorageEvent);
      };
    }
  }, [isUnlocked, handleLockVault, handleStorageEvent, refreshItems]);
  
  // Handle storage events for cross-tab communication fallback
  const handleStorageEvent = useCallback((event) => {
    if (event.key === 'vaultLockState' && event.newValue === 'locked') {
      handleLockVault(false);
    } else if (event.key === 'vaultUpdated') {
      if (isUnlocked) {
        refreshItems();
      }
    }
  }, [handleLockVault, isUnlocked, refreshItems]);
  
  // Setup activity monitoring for auto-lock
  useEffect(() => {
    // Only set up the timer if the vault is unlocked
    if (!isUnlocked) return;
    
    // Convert minutes to milliseconds
    const timeoutMs = autoLockTimeout * 60 * 1000;
    
    // Create the auto-lock timer that checks elapsed time since last activity
    const checkInactivity = () => {
      const now = Date.now();
      const timeElapsed = now - lastActivityRef.current;
      
      if (timeElapsed >= timeoutMs) {
        // Lock vault if inactive for too long
        handleLockVault(true);
      } else {
        // Schedule next check at the remaining time
        const remainingTime = Math.max(0, timeoutMs - timeElapsed);
        autoLockTimerRef.current = setTimeout(checkInactivity, Math.min(remainingTime, 10000));
      }
    };
    
    // Start monitoring inactivity
    autoLockTimerRef.current = setTimeout(checkInactivity, timeoutMs);
    
    // Track user activity events
    const activityEvents = [
      'mousedown', 'mousemove', 'keydown', 
      'scroll', 'touchstart', 'click', 'focus'
    ];
    
    // Add event listeners for all activity types
    activityEvents.forEach(event => {
      window.addEventListener(event, updateActivity, { passive: true });
    });
    
    // Clean up
    return () => {
      clearTimeout(autoLockTimerRef.current);
      activityEvents.forEach(event => {
        window.removeEventListener(event, updateActivity);
      });
    };
  }, [isUnlocked, autoLockTimeout, handleLockVault]);
  
  // Fix #6: Check if component is mounted before updating state
  const checkIfInitialized = useCallback(async () => {
    try {
      const status = await vaultService.checkInitialization();
      if (isMountedRef.current) {
        setIsInitialized(status.initialized);
      }
    } catch (error) {
      console.error('Failed to check initialization status', error);
    }
  }, [vaultService]);
  
  // Check if vault is initialized on mount
  useEffect(() => {
    checkIfInitialized();
  }, [checkIfInitialized]);
  
  const refreshItems = useCallback(async () => {
    try {
      const items = await vaultService.getVaultItems();
      if (isMountedRef.current) {
        setItems(items);
      }
    } catch (error) {
      console.error('Failed to refresh vault items', error);
    }
  }, [vaultService]);
  
  const broadcastVaultUpdate = () => {
    if (broadcastChannelRef.current) {
      broadcastChannelRef.current.postMessage({ type: 'VAULT_UPDATED' });
    } else {
      localStorage.setItem('vaultUpdated', Date.now().toString());
    }
  };
  
  const broadcastVaultLock = () => {
    if (broadcastChannelRef.current) {
      broadcastChannelRef.current.postMessage({ type: 'LOCK_VAULT' });
    } else {
      localStorage.setItem('vaultLockState', 'locked');
    }
  };

  const unlockVault = async (masterPassword) => {
    try {
      setLoading(true);
      setError(null);
      
      // Initialize crypto service with master password
      const result = await vaultService.initialize(masterPassword);
      
      if (!isMountedRef.current) return;
      
      if (result.is_valid || result.status === 'setup_complete') {
        setIsUnlocked(true);
        
        // Load vault items with lazy decryption enabled
        console.time('vault-unlock');
        const items = await vaultService.getVaultItems(lazyLoadEnabled);
        console.timeEnd('vault-unlock');
        
        setItems(items);
      } else {
        setError('Invalid master password');
      }
    } catch (error) {
      if (isMountedRef.current) {
        setError(error.message || 'Failed to unlock vault');
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  /**
   * Decrypt a specific item on-demand
   * @param {string} itemId - The item ID to decrypt
   * @returns {Promise<Object>} Decrypted item
   */
  const decryptItem = useCallback(async (itemId) => {
    // Check if already decrypted
    if (decryptedItems.has(itemId)) {
      return decryptedItems.get(itemId);
    }
    
    // Find the item
    const item = items.find(i => i.item_id === itemId);
    if (!item) {
      throw new Error('Item not found');
    }
    
    try {
      console.time(`on-demand-decrypt-${itemId}`);
      const decryptedItem = await vaultService.decryptItemOnDemand(item);
      console.timeEnd(`on-demand-decrypt-${itemId}`);
      
      // Cache the decrypted item
      setDecryptedItems(prev => new Map(prev).set(itemId, decryptedItem));
      
      // Update the item in the list
      setItems(prevItems => 
        prevItems.map(i => i.item_id === itemId ? decryptedItem : i)
      );
      
      return decryptedItem;
    } catch (error) {
      console.error('On-demand decryption failed:', error);
      throw error;
    }
  }, [items, decryptedItems, vaultService]);
  
  const handleLockVault = useCallback((broadcast = true) => {
    setIsUnlocked(false);
    setItems([]);
    // Clear crypto service
    vaultService.clearKeys();
    
    // Reset last activity timestamp
    lastActivityRef.current = Date.now();
    
    // Clear auto-lock timer
    clearTimeout(autoLockTimerRef.current);
    
    // Broadcast lock event to other tabs if needed
    if (broadcast) {
      broadcastVaultLock();
    }
  }, [vaultService]);
  
  // For backward compatibility
  const lockVault = () => handleLockVault(true);
  
  // Fix #9: Add firebaseInitialized to dependency array
  useEffect(() => {
    if (isUnlocked && !firebaseInitialized) {
      const initializeFirebase = async () => {
        try {
          // Get Firebase token from backend
          const response = await api.get('/auth/firebase_token/');
          if (response.data.token && isMountedRef.current) {
            const success = await firebaseService.initialize(response.data.token);
            if (success && isMountedRef.current) {
              setFirebaseInitialized(true);
              // Start listening for changes
              const userId = response.data.user_id;
              firebaseService.listenForChanges(userId, handleFirebaseUpdate);
            }
          }
        } catch (error) {
          console.error('Failed to initialize Firebase:', error);
        }
      };
      
      initializeFirebase();
    }
    
    return () => {
      if (firebaseInitialized) {
        firebaseService.detachListeners();
      }
    };
  }, [isUnlocked, firebaseInitialized, handleFirebaseUpdate]); // Fixed dependency array
  
  // Fix #7: Add firebaseService to dependency array and handle decryption errors
  const handleFirebaseUpdate = useCallback(async (firebaseItems) => {
    if (!isUnlocked) return;
    
    try {
      // Process items and decrypt first
      const processedItems = [];
      let hasChanges = false;
      
      // Create a working copy of current items
      const currentItems = [...items];
      
      for (const fbItem of firebaseItems) {
        try {
          const localItemIndex = currentItems.findIndex(item => item.id === fbItem.id);
          
          if (localItemIndex === -1) {
            // New item from another device - decrypt it first
            const decryptedData = await vaultService.decryptItem(fbItem.encrypted_data);
            
            processedItems.push({
              ...fbItem,
              type: fbItem.item_type,
              data: decryptedData,
            });
            hasChanges = true;
          } else {
            const localItem = currentItems[localItemIndex];
            const fbTimestamp = new Date(fbItem.last_modified).getTime();
            const localTimestamp = new Date(localItem.updated_at).getTime();
            
            if (fbTimestamp > localTimestamp) {
              // Firebase has newer version - decrypt it
              const decryptedData = await vaultService.decryptItem(fbItem.encrypted_data);
              
              // Update the item in current items array
              currentItems[localItemIndex] = {
                ...fbItem,
                type: fbItem.item_type,
                data: decryptedData,
              };
              hasChanges = true;
            } else {
              // Keep the local version
              currentItems[localItemIndex] = localItem;
            }
          }
        } catch (error) {
          console.error(`Failed to decrypt item from Firebase: ${error.message}`);
          // Skip this item but continue processing others
        }
      }
      
      // Only update state if component is still mounted and there are changes
      if (isMountedRef.current && hasChanges) {
        // For new items, append to existing
        const newItems = currentItems.filter(item => 
          !processedItems.some(pi => pi.id === item.id)
        );
        
        setItems([...newItems, ...processedItems]);
      }
    } catch (error) {
      console.error("Error processing Firebase updates:", error);
    }
  }, [isUnlocked, vaultService, items, firebaseService]);
  
  // Update addItem to sync with Firebase and limit pending changes
  const addItem = async (item) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await vaultService.saveVaultItem(item);
      
      if (!isMountedRef.current) return;
      
      // Add new item to state
      const newItem = {
        id: response.data.id,
        item_id: response.data.item_id,
        type: item.type,
        data: item.data,
        favorite: false,
        created_at: response.data.created_at,
        updated_at: response.data.updated_at,
        encrypted_data: response.data.encrypted_data
      };
      
      setItems(prevItems => [...prevItems, newItem]);
      
      // Sync to Firebase
      if (firebaseInitialized) {
        await firebaseService.syncItem(newItem);
      }
      
      // Broadcast update to other tabs
      broadcastVaultUpdate();
      
      // Fix #5: Limit pendingChanges size
      setPendingChanges(prev => {
        const updated = [...prev, {
          operation: 'add', 
          item: newItem
        }];
        
        // Auto-sync if too many pending changes
        if (updated.length > MAX_PENDING_CHANGES) {
          // Schedule sync in the next tick to avoid state update during render
          setTimeout(() => syncVault(), 0);
          return updated.slice(0, MAX_PENDING_CHANGES);
        }
        
        return updated;
      });
      
      return newItem;
    } catch (error) {
      if (isMountedRef.current) {
        setError(error.message || 'Failed to add item');
      }
      throw error;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  const updateItem = async (item) => {
    try {
      setLoading(true);
      setError(null);
      
      await vaultService.saveVaultItem(item);
      
      if (!isMountedRef.current) return;
      
      // Update item in state
      setItems(prevItems => 
        prevItems.map(i => i.id === item.id ? { ...i, ...item, updated_at: new Date().toISOString() } : i)
      );
      
      // Broadcast update to other tabs
      broadcastVaultUpdate();
      
      // Fix #5: Limit pendingChanges size
      setPendingChanges(prev => {
        const updated = [...prev, {
          operation: 'update', 
          item
        }];
        
        // Auto-sync if too many pending changes
        if (updated.length > MAX_PENDING_CHANGES) {
          setTimeout(() => syncVault(), 0);
          return updated.slice(0, MAX_PENDING_CHANGES);
        }
        
        return updated;
      });
      
      return item;
    } catch (error) {
      if (isMountedRef.current) {
        setError(error.message || 'Failed to update item');
      }
      throw error;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  const deleteItem = async (itemId) => {
    try {
      setLoading(true);
      setError(null);
      
      await vaultService.deleteVaultItem(itemId);
      
      if (!isMountedRef.current) return;
      
      // Remove item from state
      setItems(prevItems => prevItems.filter(i => i.id !== itemId));
      
      // Broadcast update to other tabs
      broadcastVaultUpdate();
      
      // Fix #5: Limit pendingChanges size
      setPendingChanges(prev => {
        const updated = [...prev, {
          operation: 'delete', 
          id: itemId
        }];
        
        // Auto-sync if too many pending changes
        if (updated.length > MAX_PENDING_CHANGES) {
          setTimeout(() => syncVault(), 0);
          return updated.slice(0, MAX_PENDING_CHANGES);
        }
        
        return updated;
      });
    } catch (error) {
      if (isMountedRef.current) {
        setError(error.message || 'Failed to delete item');
      }
      throw error;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  const updateAutoLockTimeout = (minutes) => {
    setAutoLockTimeout(minutes);
    localStorage.setItem('autoLockTimeout', minutes.toString());
    // Reset the timer with new timeout
    if (isUnlocked) {
      clearTimeout(autoLockTimerRef.current);
      autoLockTimerRef.current = setTimeout(() => {
        handleLockVault(true);
      }, minutes * 60 * 1000);
    }
  };
  
  const generatePassword = (options) => {
    return vaultService.cryptoService?.generatePassword(options);
  };
  
  // Add these new methods for backup/restore
  const createBackup = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post('/vault/create_backup/', {
        name: `Backup ${new Date().toLocaleString()}`
      });
      
      return response.data;
    } catch (error) {
      if (isMountedRef.current) {
        setError('Failed to create backup: ' + error.message);
      }
      throw error;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  const getBackups = async () => {
    try {
      const response = await api.get('/vault/backups/');
      return response.data;
    } catch (error) {
      if (isMountedRef.current) {
        setError('Failed to load backups: ' + error.message);
      }
      throw error;
    }
  };
  
  const restoreBackup = async (backupId) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post(`/vault/restore_backup/${backupId}/`);
      
      if (!isMountedRef.current) return;
      
      // Refresh vault after restore
      await refreshItems();
      
      return response.data;
    } catch (error) {
      if (isMountedRef.current) {
        setError('Failed to restore backup: ' + error.message);
      }
      throw error;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  // Fix #1 and #4: Add error handling and status updates to syncVault
  const syncVault = async () => {
    if (pendingChanges.length === 0) return;
    
    try {
      // Update sync status
      setSyncStatus('syncing');
      
      // Process all changes at once rather than in batches
      // Prepare changes in the format expected by the backend
      const syncData = {
        last_sync: lastSyncTime,
        items: [],
        deleted_items: []
      };
      
      // Process all pending changes
      pendingChanges.forEach(change => {
        if (change.operation === 'add' || change.operation === 'update') {
          // Convert frontend 'type' to backend 'item_type' format
          const itemData = {
            ...change.item,
            // Ensure we're using the key the backend expects
            item_type: change.item.type,
            // Include required fields explicitly
            item_id: change.item.item_id,
            encrypted_data: change.item.encrypted_data,
            // Use consistent naming scheme with backend
            favorite: change.item.favorite || false
          };
          
          // Remove redundant fields before sending to backend
          delete itemData.type; // Backend uses item_type
          delete itemData.data; // Backend doesn't need decrypted data
          
          syncData.items.push(itemData);
        } else if (change.operation === 'delete') {
          syncData.deleted_items.push(change.id);
        }
      });
      
      try {
        // Use the new syncVault method in vaultService
        const response = await vaultService.syncVault(syncData);
        
        if (!isMountedRef.current) return;
        
        // Check for expected response format
        if (response.success && response.items) {
          // Process any server changes and update local state if needed
          const serverItems = response.items;
          const serverDeletedIds = response.deleted_items || [];
          
          // Check if we need to update local items with server changes
          if (serverItems.length > 0 || serverDeletedIds.length > 0) {
            // Process server deletions
            setItems(prevItems => 
              prevItems.filter(item => !serverDeletedIds.includes(item.item_id))
            );
            
            // Process server items - need to decrypt them first
            const processedItems = await Promise.all(
              serverItems.map(async (serverItem) => {
                try {
                  // Convert from backend format to frontend format
                  const decryptedData = await vaultService.decryptItem(serverItem.encrypted_data);
                  return {
                    id: serverItem.id,
                    item_id: serverItem.item_id,
                    type: serverItem.item_type, // Convert backend item_type to frontend type
                    data: decryptedData,
                    encrypted_data: serverItem.encrypted_data,
                    favorite: serverItem.favorite || false,
                    created_at: serverItem.created_at,
                    updated_at: serverItem.updated_at
                  };
                } catch (error) {
                  console.error("Failed to decrypt item during sync:", error);
                  return null;
                }
              })
            );
            
            // Filter out failed decryptions and update local items
            const validItems = processedItems.filter(item => item !== null);
            if (validItems.length > 0) {
              setItems(prevItems => {
                // Create a map for O(1) lookups
                const itemMap = new Map(prevItems.map(item => [item.id, item]));
                
                // Update existing items or add new ones
                validItems.forEach(item => {
                  itemMap.set(item.id, item);
                });
                
                return Array.from(itemMap.values());
              });
            }
          }
          
          // Update last sync time
          const newSyncTime = response.sync_time || new Date().toISOString();
          setLastSyncTime(newSyncTime);
          localStorage.setItem('lastSyncTime', newSyncTime);
        }
        
        // Clear pending changes and update status
        setPendingChanges([]);
        setSyncStatus('success');
        setError(null);
        
      } catch (syncError) {
        console.error('Sync request failed:', syncError);
        setSyncStatus('error');
        setError(syncError.message || 'Failed to sync with server');
        
        // Don't clear pendingChanges so we can retry later
      }
    } catch (error) {
      console.error('Error preparing sync data:', error);
      setSyncStatus('error');
      setError('Error preparing data for sync: ' + error.message);
    }
  };
  
  const value = {
    isInitialized,
    isUnlocked,
    items,
    loading,
    error,
    autoLockTimeout,
    unlockVault,
    lockVault,
    addItem,
    updateItem,
    deleteItem,
    generatePassword,
    updateAutoLockTimeout,
    createBackup,
    getBackups,
    restoreBackup,
    syncStatus,
    syncVault,
    pendingChanges,
    lastSyncTime,
    decryptItem,  // New: on-demand decryption
    lazyLoadEnabled,  // New: lazy load setting
    setLazyLoadEnabled  // New: toggle lazy loading
  };
  
  return (
    <VaultContext.Provider value={value}>
      {children}
    </VaultContext.Provider>
  );
};

export const useVault = () => {
  const context = useContext(VaultContext);
  if (!context) {
    throw new Error('useVault must be used within a VaultProvider');
  }
  return context;
};

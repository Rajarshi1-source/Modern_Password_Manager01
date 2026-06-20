import React, { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import axios from 'axios';
import { VaultService } from '../services/vaultService';
import firebaseService from '../services/firebaseService';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';
import sessionVaultCrypto from '../services/sessionVaultCrypto';
import sessionVaultCryptoV3 from '../services/sessionVaultCryptoV3';
import { decryptEnvelope, encryptEnvelope } from '../services/vaultEnvelope';

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
  // Fix stale closure in syncVault when called via setTimeout
  const pendingChangesRef = useRef(pendingChanges);

  useEffect(() => {
    pendingChangesRef.current = pendingChanges;
  }, [pendingChanges]);

  const [lastSyncTime, setLastSyncTime] = useState(localStorage.getItem('lastSyncTime') || new Date().toISOString());
  const [decryptedItems, setDecryptedItems] = useState(new Map());
  const [lazyLoadEnabled, setLazyLoadEnabled] = useState(true);
  // PR F: the dashboard's edit gate (canEdit). Editing re-encrypts the secret,
  // so it requires a live session key. The authoritative crypto unlock is
  // sessionVaultCrypto (v2) — set during login and cleared on logout — NOT the
  // never-initialised vaultService.encryptionKey the old `isUnlocked` tracked.
  // Recomputed on auth change and on 'vault:updated' (which the login flow now
  // dispatches once the session key is established).
  const [sessionUnlocked, setSessionUnlocked] = useState(() => sessionVaultCrypto.hasSessionKey());
  const { isAuthenticated, user } = useAuth(); // Get auth status + identity

  // Fix #8: Use useMemo for vaultService
  const vaultService = useMemo(() => new VaultService(), []);

  const autoLockTimerRef = useRef(null);
  const broadcastChannelRef = useRef(null);
  const lastActivityRef = useRef(Date.now());
  const isMountedRef = useRef(true); // Fix #6: Track component mount state
  const favoriteInFlightRef = useRef(new Set()); // Serialize favorite toggles per item id
  const refreshAbortRef = useRef(null); // Cancels a superseded in-flight item refresh

  // Clean up mounted ref on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const updateActivity = () => {
    lastActivityRef.current = Date.now();
  };


  // Fix #6: Check if component is mounted before updating state
  const checkIfInitialized = useCallback(async () => {
    // Only check if user is authenticated
    if (!isAuthenticated) {
      if (isMountedRef.current) {
        setIsInitialized(false);
        setLoading(false); // Assuming loading should be false if not authenticated
      }
      return;
    }

    try {
      const status = await vaultService.checkInitialization();
      if (isMountedRef.current) {
        setIsInitialized(status.initialized);
      }
    } catch (error) {
      console.error('Failed to check initialization status', error);
    }
  }, [vaultService, isAuthenticated]);

  // Check if vault is initialized on mount or when auth status changes
  const initCheckRef = useRef(false);

  useEffect(() => {
    if (isAuthenticated) {
      if (!initCheckRef.current) {
        checkIfInitialized();
        initCheckRef.current = true;
      }
    } else {
      initCheckRef.current = false;
    }
  }, [checkIfInitialized, isAuthenticated]);

  const refreshItems = useCallback(async () => {
    // Cancel any in-flight refresh so a slower earlier response (e.g. from a
    // rapid identity change or a burst of vault:updated events) can't overwrite
    // a newer one with stale items.
    if (refreshAbortRef.current) {
      refreshAbortRef.current.abort();
    }
    const controller = new AbortController();
    refreshAbortRef.current = controller;
    try {
      // Load the canonical item list the same way the /vault page always has:
      // via the default JWT-authenticated axios client (auth is attached by the
      // useAuth request interceptor / axios defaults). This loads ciphertext
      // only; decryption happens on demand via the shared sessionVaultCrypto
      // (vaultEnvelope) helper — never the removed vaultService crypto path.
      // Parse defensively: only an array is a valid item list, so a non-list
      // payload yields [] instead of throwing on .map.
      const response = await axios.get('/api/vault/', { signal: controller.signal });
      const data = response?.data;
      const rawList = Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : [];
      // These rows are ciphertext (encrypted_data, no decrypted `data`).
      // Tag them as lazy so consumers that render items directly (e.g. the
      // dashboard's VaultItemCard) treat them as encrypted/lazy rather than
      // dereferencing a missing `data` object. Decryption happens on demand.
      const list = rawList.map(row => ({ ...row, _lazyLoaded: true, _decrypted: false }));
      if (isMountedRef.current && !controller.signal.aborted) {
        setItems(list);
        setError(null);
      }
    } catch (err) {
      // A superseded request was aborted on purpose — leave state to the newer one.
      if (err?.name === 'CanceledError' || err?.name === 'AbortError' || axios.isCancel?.(err)) {
        return;
      }
      console.error('Failed to refresh vault items', err);
      // Surface the failure so the vault view can show an error instead of a
      // misleading "no passwords saved" empty state after items were cleared.
      if (isMountedRef.current) {
        setError('Failed to load your password vault. Please try again.');
      }
    }
  }, []);

  // VaultContext is the single source of truth for the vault item list (PR C).
  // Load the (lazy/ciphertext) list whenever the authenticated identity
  // changes, clear it on logout, and refresh on demand when another part of
  // the app (e.g. the /vault add flow) signals a change via 'vault:updated'.
  // This loads only metadata/ciphertext, so it needs no decryption key —
  // decryption stays with the views' sessionVaultCrypto.
  useEffect(() => {
    if (!isAuthenticated) {
      setItems([]);
      // Drop any cached decrypted plaintext on logout so it can never be
      // served (decryptItem reads this cache by item_id before the list).
      setDecryptedItems(new Map());
      setSessionUnlocked(false);
      return undefined;
    }
    // Clear any previous account's items BEFORE refetching so a session or
    // identity change never shows the prior user's vault while the refresh is
    // in flight (or indefinitely if it fails) — matching the old App-level
    // clear-before-refetch isolation guard. Also drop the decrypted cache so a
    // colliding item_id from the new account can't return the prior account's
    // plaintext.
    setItems([]);
    setDecryptedItems(new Map());
    setSessionUnlocked(sessionVaultCrypto.hasSessionKey());
    refreshItems();
    // 'vault:updated' fires from the add/edit write paths AND from the login
    // flow once the session key is established — recompute canEdit on each.
    const onVaultUpdated = () => {
      refreshItems();
      setSessionUnlocked(sessionVaultCrypto.hasSessionKey());
    };
    window.addEventListener('vault:updated', onVaultUpdated);
    return () => window.removeEventListener('vault:updated', onVaultUpdated);
    // user id/email keep this isolated per-account: switching users refetches
    // instead of showing the previous account's vault.
  }, [isAuthenticated, user?.id, user?.email, refreshItems]);

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
      // PR F: decrypt via the shared sessionVaultCrypto (v2→v3) envelope helper
      // — the same proven path the /vault list uses — instead of the
      // never-initialised vaultService.cryptoService.
      const data = await decryptEnvelope(item.encrypted_data);
      console.timeEnd(`on-demand-decrypt-${itemId}`);

      // A `_legacyPlaintext` marker (or any payload with no usable object)
      // is NOT editable: re-encrypting an empty form over it would corrupt the
      // item. Surface a failure placeholder the dashboard refuses to open, and
      // don't cache it so a later attempt (after a proper unlock) can retry.
      if (!data || data._legacyPlaintext) {
        return { ...item, _decryptionFailed: true };
      }

      const decryptedItem = { ...item, data, _decrypted: true, _lazyLoaded: false };

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
  }, [items, decryptedItems]);

  const handleLockVault = useCallback((broadcast = true) => {
    setIsUnlocked(false);
    // Lock the dashboard edit gate (canEdit) — the session key is about to go.
    setSessionUnlocked(false);
    setItems([]);

    // Drop the in-memory vault session keys (v2 + v3) so they cannot be reused
    // after a manual or cross-tab lock — matching the logout path in App.jsx.
    // (vaultService.clearKeys() is now a no-op; the live keys live in
    // sessionVaultCrypto/V3, so clearing them here is what actually locks the
    // vault rather than just hiding the items.)
    sessionVaultCrypto.clearSessionKey();
    try {
      sessionVaultCryptoV3.clearSessionKey();
    } catch (clearErr) {
      // Defensive: a throw means an in-memory DEK survived the lock — log it
      // rather than swallow, mirroring the logout handler.
      console.warn('Failed to clear v3 vault session key on lock:', clearErr);
    }

    // Reset last activity timestamp
    lastActivityRef.current = Date.now();

    // Clear auto-lock timer
    clearTimeout(autoLockTimerRef.current);

    // Broadcast lock event to other tabs if needed
    if (broadcast) {
      broadcastVaultLock();
    }
  }, []);

  // For backward compatibility
  const lockVault = () => handleLockVault(true);

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

  // Handle Firebase real-time updates
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
            const decryptedData = await decryptEnvelope(fbItem.encrypted_data);

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
              const decryptedData = await decryptEnvelope(fbItem.encrypted_data);

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
  }, [isUnlocked, items]);

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
  }, [isUnlocked, firebaseInitialized, handleFirebaseUpdate]);

  // Fix #1 and #4: Add error handling and status updates to syncVault
  const syncVault = useCallback(async () => {
    // Use ref to avoid stale closure issues when called via setTimeout
    const currentPendingChanges = pendingChangesRef.current;
    if (currentPendingChanges.length === 0) return;

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
      currentPendingChanges.forEach(change => {
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
                  const decryptedData = await decryptEnvelope(serverItem.encrypted_data);
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
  }, [lastSyncTime, vaultService]);

  // Add a new item. Mirrors the proven /vault add flow (App.handleSubmit):
  // encrypt via sessionVaultCrypto (encryptEnvelope) and POST to the detail
  // route — NOT the never-initialised vaultService.cryptoService. Gated on a
  // live session key; only ciphertext (never the plaintext `data`) is sent.
  const addItem = useCallback(async (item) => {
    if (!sessionVaultCrypto.hasSessionKey()) {
      const lockedErr = new Error('Unlock your vault to add items.');
      if (isMountedRef.current) setError(lockedErr.message);
      throw lockedErr;
    }
    try {
      setLoading(true);
      setError(null);

      const encrypted_data = await encryptEnvelope(item.data);
      const item_id = item.item_id || `item_${Date.now()}`;
      const response = await axios.post('/api/vault/', {
        item_type: item.type || item.item_type || 'password',
        item_id,
        encrypted_data,
        favorite: item.favorite || false,
      });

      if (!isMountedRef.current) return;

      // Add new item to state
      const created = response?.data || {};
      const newItem = {
        id: created.id,
        item_id: created.item_id || item_id,
        type: item.type,
        data: item.data,
        favorite: created.favorite || false,
        created_at: created.created_at,
        updated_at: created.updated_at,
        encrypted_data,
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
  }, [firebaseInitialized, syncVault]);

  // PR F: edit re-encrypts the secret and persists it via the proven detail
  // route (/api/vault/{id}/). Crypto goes through sessionVaultCrypto (v2) via
  // encryptEnvelope — the same key the /vault add flow and list use — NOT the
  // never-initialised vaultService.cryptoService. Gated on a live session key;
  // only the ciphertext (never the plaintext `data`) is sent to the server.
  //
  // PATCH, not PUT: EncryptedVaultItemSerializer exposes `user` as a writable
  // (non-read-only) field, so a full PUT would require `user` in the body and
  // 400. A partial PATCH of just `encrypted_data` is also safer — it never
  // touches `favorite` (owned by the metadata-only toggleFavorite PATCH) or
  // `item_type`, so an edit can't clobber a concurrent favorite change.
  const updateItem = useCallback(async (item) => {
    if (!sessionVaultCrypto.hasSessionKey()) {
      const lockedErr = new Error('Unlock your vault to edit items.');
      if (isMountedRef.current) setError(lockedErr.message);
      throw lockedErr;
    }
    try {
      setLoading(true);
      setError(null);

      const encrypted_data = await encryptEnvelope(item.data);
      const response = await axios.patch(`/api/vault/${item.id}/`, { encrypted_data });

      if (!isMountedRef.current) return;

      const updatedAt = response?.data?.updated_at || new Date().toISOString();
      // Replace the row with the freshly-encrypted ciphertext, keeping the
      // in-memory plaintext usable for this session.
      setItems(prevItems =>
        prevItems.map(i =>
          i.id === item.id
            ? { ...i, ...item, encrypted_data, updated_at: updatedAt }
            : i
        )
      );

      // Invalidate the cached plaintext for this item so a re-open re-decrypts
      // the new ciphertext rather than serving the pre-edit snapshot.
      setDecryptedItems(prev => {
        if (!prev.has(item.item_id)) return prev;
        const next = new Map(prev);
        next.delete(item.item_id);
        return next;
      });

      // Keep other tabs / the /vault list in sync.
      broadcastVaultUpdate();

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
  }, []);

  const deleteItem = useCallback(async (itemId) => {
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
  }, [vaultService, syncVault]);

  // Toggle the favorite flag on a vault item.
  //
  // Favorite is non-secret metadata, so this deliberately does NOT go through
  // updateItem (which re-encrypts the whole item and requires the decrypted
  // payload — wrong and risky for a lazy-loaded item). Instead it issues a
  // lightweight metadata-only PATCH. The flag is flipped optimistically
  // for a snappy UI and rolled back if the request fails. It is intentionally
  // NOT added to pendingChanges, since it is persisted immediately.
  const toggleFavorite = useCallback(async (id) => {
    // Serialize toggles per item: ignore a new toggle while one is already
    // in flight for the same id, so out-of-order PATCH responses can't
    // persist stale state.
    if (favoriteInFlightRef.current.has(id)) return;

    const target = items.find(i => i.id === id);
    if (!target) return;

    const previousFavorite = target.favorite;
    const nextFavorite = !previousFavorite;

    favoriteInFlightRef.current.add(id);

    // Optimistic update
    setItems(prevItems =>
      prevItems.map(i => (i.id === id ? { ...i, favorite: nextFavorite } : i))
    );

    try {
      await vaultService.toggleFavorite(id, nextFavorite);
      // Keep other tabs in sync
      broadcastVaultUpdate();
    } catch (error) {
      // Roll back the optimistic flip
      if (isMountedRef.current) {
        setItems(prevItems =>
          prevItems.map(i => (i.id === id ? { ...i, favorite: previousFavorite } : i))
        );
        setError(error.message || 'Failed to update favorite');
      }
      throw error;
    } finally {
      favoriteInFlightRef.current.delete(id);
    }
  }, [items, vaultService]);

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



  const value = useMemo(() => ({
    isInitialized,
    isUnlocked,
    canEdit: sessionUnlocked,  // PR F: reactive session-key gate for the dashboard
    items,
    loading,
    error,
    autoLockTimeout,
    lockVault,
    addItem,
    updateItem,
    deleteItem,
    refreshItems,  // New: reload the canonical item list (single source of truth)
    toggleFavorite,  // New: metadata-only favorite toggle
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
  }), [
    isInitialized, isUnlocked, sessionUnlocked, items, loading, error, autoLockTimeout,
    syncStatus, pendingChanges, lastSyncTime, lazyLoadEnabled,
    lockVault, addItem, updateItem, deleteItem, refreshItems, toggleFavorite,
    syncVault, decryptItem
  ]);

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

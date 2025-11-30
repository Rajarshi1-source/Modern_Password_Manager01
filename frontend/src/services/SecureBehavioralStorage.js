/**
 * Secure Behavioral Storage
 * 
 * Handles encrypted storage of behavioral profiles in IndexedDB
 * Ensures behavioral data never leaves device in plaintext
 */

import { CryptoService } from './cryptoService';

export class SecureBehavioralStorage {
  constructor() {
    this.dbName = 'BehavioralRecoveryDB';
    this.dbVersion = 1;
    this.storeName = 'behavioral_profiles';
    this.db = null;
    this.cryptoService = new CryptoService();
  }
  
  /**
   * Initialize IndexedDB
   */
  async initialize() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        if (!db.objectStoreNames.contains(this.storeName)) {
          const objectStore = db.createObjectStore(this.storeName, { keyPath: 'id' });
          objectStore.createIndex('timestamp', 'timestamp', { unique: false });
          objectStore.createIndex('userId', 'userId', { unique: false });
        }
      };
    });
  }
  
  /**
   * Save behavioral profile (encrypted)
   */
  async saveBehavioralProfile(profile, encryptionKey) {
    if (!this.db) {
      await this.initialize();
    }
    
    try {
      // Encrypt profile data
      const profileJson = JSON.stringify(profile);
      const encryptedData = await this.cryptoService.encrypt(profileJson, encryptionKey);
      
      // Prepare storage object
      const storageObject = {
        id: 'current_profile',
        userId: profile.userId || 'anonymous',
        encrypted_data: encryptedData,
        timestamp: Date.now(),
        metadata: {
          samples_count: profile.samples?.length || 0,
          quality_score: profile.overall_quality || 0,
          created_at: profile.profileBuildStarted || Date.now()
        }
      };
      
      // Save to IndexedDB
      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([this.storeName], 'readwrite');
        const store = transaction.objectStore(this.storeName);
        const request = store.put(storageObject);
        
        request.onsuccess = () => {
          console.log('Behavioral profile saved securely');
          resolve(request.result);
        };
        request.onerror = () => reject(request.error);
      });
      
    } catch (error) {
      console.error('Error saving behavioral profile:', error);
      throw error;
    }
  }
  
  /**
   * Load behavioral profile (decrypt)
   */
  async loadBehavioralProfile(encryptionKey) {
    if (!this.db) {
      await this.initialize();
    }
    
    try {
      const storageObject = await this._getStorageObject('current_profile');
      
      if (!storageObject) {
        return null;
      }
      
      // Decrypt profile data
      const decryptedJson = await this.cryptoService.decrypt(
        storageObject.encrypted_data,
        encryptionKey
      );
      
      const profile = JSON.parse(decryptedJson);
      
      console.log('Behavioral profile loaded successfully');
      return profile;
      
    } catch (error) {
      console.error('Error loading behavioral profile:', error);
      return null;
    }
  }
  
  /**
   * Get storage object from IndexedDB
   */
  async _getStorageObject(id) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.get(id);
      
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Save snapshot (periodic backup)
   */
  async saveSnapshot(snapshot, encryptionKey) {
    if (!this.db) {
      await this.initialize();
    }
    
    try {
      // Encrypt snapshot
      const snapshotJson = JSON.stringify(snapshot);
      const encryptedData = await this.cryptoService.encrypt(snapshotJson, encryptionKey);
      
      const storageObject = {
        id: `snapshot_${Date.now()}`,
        userId: snapshot.userId || 'anonymous',
        encrypted_data: encryptedData,
        timestamp: Date.now(),
        metadata: {
          type: 'snapshot',
          quality: snapshot.overall_quality || 0
        }
      };
      
      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([this.storeName], 'readwrite');
        const store = transaction.objectStore(this.storeName);
        const request = store.add(storageObject);
        
        request.onsuccess = () => {
          console.log('Snapshot saved');
          this._cleanupOldSnapshots();  // Remove old snapshots
          resolve(request.result);
        };
        request.onerror = () => reject(request.error);
      });
      
    } catch (error) {
      console.error('Error saving snapshot:', error);
      throw error;
    }
  }
  
  /**
   * Load all snapshots
   */
  async loadSnapshots(encryptionKey, limit = 30) {
    if (!this.db) {
      await this.initialize();
    }
    
    try {
      const allSnapshots = await this._getAllStorageObjects();
      
      // Filter snapshots (exclude current profile)
      const snapshots = allSnapshots
        .filter(obj => obj.id.startsWith('snapshot_'))
        .sort((a, b) => b.timestamp - a.timestamp)
        .slice(0, limit);
      
      // Decrypt snapshots
      const decrypted = await Promise.all(
        snapshots.map(async (obj) => {
          try {
            const decryptedJson = await this.cryptoService.decrypt(obj.encrypted_data, encryptionKey);
            return JSON.parse(decryptedJson);
          } catch (error) {
            console.error('Error decrypting snapshot:', error);
            return null;
          }
        })
      );
      
      return decrypted.filter(s => s !== null);
      
    } catch (error) {
      console.error('Error loading snapshots:', error);
      return [];
    }
  }
  
  /**
   * Get all storage objects
   */
  async _getAllStorageObjects() {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.getAll();
      
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Cleanup old snapshots (keep only last 30 days)
   */
  async _cleanupOldSnapshots() {
    const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
    
    try {
      const allObjects = await this._getAllStorageObjects();
      const oldSnapshots = allObjects.filter(obj => 
        obj.id.startsWith('snapshot_') && obj.timestamp < thirtyDaysAgo
      );
      
      if (oldSnapshots.length > 0) {
        const transaction = this.db.transaction([this.storeName], 'readwrite');
        const store = transaction.objectStore(this.storeName);
        
        oldSnapshots.forEach(obj => {
          store.delete(obj.id);
        });
        
        console.log(`Cleaned up ${oldSnapshots.length} old snapshots`);
      }
    } catch (error) {
      console.error('Error cleaning up snapshots:', error);
    }
  }
  
  /**
   * Delete all behavioral data
   */
  async deleteAllData() {
    if (!this.db) {
      await this.initialize();
    }
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const request = store.clear();
      
      request.onsuccess = () => {
        console.log('All behavioral data deleted');
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Export encrypted data for backup
   */
  async exportEncryptedBackup() {
    if (!this.db) {
      await this.initialize();
    }
    
    const allObjects = await this._getAllStorageObjects();
    
    return {
      version: '1.0.0',
      exportDate: new Date().toISOString(),
      data: allObjects,
      count: allObjects.length
    };
  }
  
  /**
   * Import encrypted backup
   */
  async importEncryptedBackup(backup) {
    if (backup.version !== '1.0.0') {
      throw new Error('Incompatible backup version');
    }
    
    if (!this.db) {
      await this.initialize();
    }
    
    // Clear existing data
    await this.deleteAllData();
    
    // Import data
    const transaction = this.db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    
    let imported = 0;
    for (const obj of backup.data) {
      try {
        await new Promise((resolve, reject) => {
          const request = store.add(obj);
          request.onsuccess = () => {
            imported++;
            resolve();
          };
          request.onerror = () => reject(request.error);
        });
      } catch (error) {
        console.error('Error importing object:', error);
      }
    }
    
    console.log(`Imported ${imported} behavioral data objects`);
    return imported;
  }
  
  /**
   * Get storage statistics
   */
  async getStorageStats() {
    if (!this.db) {
      await this.initialize();
    }
    
    const allObjects = await this._getAllStorageObjects();
    
    const profiles = allObjects.filter(obj => obj.id === 'current_profile');
    const snapshots = allObjects.filter(obj => obj.id.startsWith('snapshot_'));
    
    // Calculate total size (approximate)
    const totalSize = allObjects.reduce((sum, obj) => {
      const size = new Blob([JSON.stringify(obj)]).size;
      return sum + size;
    }, 0);
    
    return {
      totalObjects: allObjects.length,
      profiles: profiles.length,
      snapshots: snapshots.length,
      totalSizeBytes: totalSize,
      totalSizeMB: (totalSize / (1024 * 1024)).toFixed(2),
      oldestSnapshot: snapshots.length > 0 
        ? new Date(Math.min(...snapshots.map(s => s.timestamp)))
        : null,
      newestSnapshot: snapshots.length > 0
        ? new Date(Math.max(...snapshots.map(s => s.timestamp)))
        : null
    };
  }
}

// Export singleton instance
export const secureBehavioralStorage = new SecureBehavioralStorage();


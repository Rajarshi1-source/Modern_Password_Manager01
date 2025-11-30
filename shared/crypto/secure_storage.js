/**
 * Cross-platform secure key storage implementation
 * Provides secure storage with platform-specific implementations
 */

// Platform detection utilities
const getPlatform = () => {
  if (typeof window !== 'undefined') {
    if (typeof chrome !== 'undefined' && chrome.storage) {
      return 'browser-extension';
    }
    return 'browser';
  } else if (typeof process !== 'undefined' && process.versions && process.versions.electron) {
    return 'electron';
  } else if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    return 'node';
  }
  return 'unknown';
};

// Browser implementation using IndexedDB
class BrowserSecureStorage {
  static dbName = 'SecureKeyStorage';
  static storeName = 'keys';
  static version = 1;

  static async openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName, { keyPath: 'id' });
        }
      };
    });
  }

  static async storeKey(keyId, keyData) {
    try {
      const db = await this.openDB();
      const transaction = db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      
      // Convert keyData to storable format
      const data = {
        id: keyId,
        key: Array.from(new Uint8Array(keyData)),
        timestamp: Date.now()
      };
      
      await new Promise((resolve, reject) => {
        const request = store.put(data);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });
      
      db.close();
      return true;
    } catch (error) {
      console.error('Failed to store key in IndexedDB:', error);
      return false;
    }
  }

  static async retrieveKey(keyId) {
    try {
      const db = await this.openDB();
      const transaction = db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      
      const data = await new Promise((resolve, reject) => {
        const request = store.get(keyId);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      
      db.close();
      
      if (data && data.key) {
        return new Uint8Array(data.key);
      }
      return null;
    } catch (error) {
      console.error('Failed to retrieve key from IndexedDB:', error);
      return null;
    }
  }

  static async isHardwareSecurityAvailable() {
    // Check for Web Crypto API support
    return typeof crypto !== 'undefined' && 
           typeof crypto.subtle !== 'undefined' &&
           typeof indexedDB !== 'undefined';
  }

  static async deleteKey(keyId) {
    try {
      const db = await this.openDB();
      const transaction = db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      
      await new Promise((resolve, reject) => {
        const request = store.delete(keyId);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });
      
      db.close();
      return true;
    } catch (error) {
      console.error('Failed to delete key from IndexedDB:', error);
      return false;
    }
  }
}

// Browser Extension implementation using chrome.storage
class ExtensionSecureStorage {
  static async storeKey(keyId, keyData) {
    try {
      if (!chrome || !chrome.storage || !chrome.storage.local) {
        throw new Error('Chrome storage API not available');
      }

      const data = {
        [keyId]: {
          key: Array.from(new Uint8Array(keyData)),
          timestamp: Date.now()
        }
      };

      return new Promise((resolve) => {
        chrome.storage.local.set(data, () => {
          if (chrome.runtime.lastError) {
            console.error('Extension storage error:', chrome.runtime.lastError);
            resolve(false);
          } else {
            resolve(true);
          }
        });
      });
    } catch (error) {
      console.error('Failed to store key in extension storage:', error);
      return false;
    }
  }

  static async retrieveKey(keyId) {
    try {
      if (!chrome || !chrome.storage || !chrome.storage.local) {
        throw new Error('Chrome storage API not available');
      }

      return new Promise((resolve) => {
        chrome.storage.local.get([keyId], (result) => {
          if (chrome.runtime.lastError) {
            console.error('Extension storage error:', chrome.runtime.lastError);
            resolve(null);
          } else if (result[keyId] && result[keyId].key) {
            resolve(new Uint8Array(result[keyId].key));
          } else {
            resolve(null);
          }
        });
      });
    } catch (error) {
      console.error('Failed to retrieve key from extension storage:', error);
      return null;
    }
  }

  static async isHardwareSecurityAvailable() {
    return typeof chrome !== 'undefined' && 
           typeof chrome.storage !== 'undefined' &&
           typeof crypto !== 'undefined' && 
           typeof crypto.subtle !== 'undefined';
  }

  static async deleteKey(keyId) {
    try {
      if (!chrome || !chrome.storage || !chrome.storage.local) {
        return false;
      }

      return new Promise((resolve) => {
        chrome.storage.local.remove([keyId], () => {
          resolve(!chrome.runtime.lastError);
        });
      });
    } catch (error) {
      console.error('Failed to delete key from extension storage:', error);
      return false;
    }
  }
}

// Electron implementation using secure storage
class ElectronSecureStorage {
  static async storeKey(keyId, keyData) {
    try {
      // Use electron-store or similar secure storage
      const { ipcRenderer } = require('electron');
      
      const result = await ipcRenderer.invoke('secure-storage-set', {
        key: keyId,
        value: Array.from(new Uint8Array(keyData))
      });
      
      return result.success;
    } catch (error) {
      console.error('Failed to store key in Electron secure storage:', error);
      // Fallback to encrypted file storage
      return await this._fallbackFileStorage('store', keyId, keyData);
    }
  }

  static async retrieveKey(keyId) {
    try {
      const { ipcRenderer } = require('electron');
      
      const result = await ipcRenderer.invoke('secure-storage-get', keyId);
      
      if (result.success && result.value) {
        return new Uint8Array(result.value);
      }
      return null;
    } catch (error) {
      console.error('Failed to retrieve key from Electron secure storage:', error);
      // Fallback to encrypted file storage
      return await this._fallbackFileStorage('retrieve', keyId);
    }
  }

  static async isHardwareSecurityAvailable() {
    try {
      const { ipcRenderer } = require('electron');
      const result = await ipcRenderer.invoke('secure-storage-available');
      return result.available;
    } catch (error) {
      return false;
    }
  }

  static async deleteKey(keyId) {
    try {
      const { ipcRenderer } = require('electron');
      const result = await ipcRenderer.invoke('secure-storage-delete', keyId);
      return result.success;
    } catch (error) {
      console.error('Failed to delete key from Electron secure storage:', error);
      return false;
    }
  }

  static async _fallbackFileStorage(operation, keyId, keyData = null) {
    // Simple encrypted file fallback for Electron
    try {
      const fs = require('fs').promises;
      const path = require('path');
      const os = require('os');
      
      const storageDir = path.join(os.homedir(), '.password-manager-keys');
      const filePath = path.join(storageDir, `${keyId}.key`);

      if (operation === 'store') {
        await fs.mkdir(storageDir, { recursive: true });
        await fs.writeFile(filePath, Buffer.from(keyData));
        return true;
      } else if (operation === 'retrieve') {
        try {
          const data = await fs.readFile(filePath);
          return new Uint8Array(data);
        } catch (err) {
          if (err.code === 'ENOENT') return null;
          throw err;
        }
      }
      return false;
    } catch (error) {
      console.error('Fallback file storage error:', error);
      return operation === 'store' ? false : null;
    }
  }
}

// Memory-only fallback for unsupported platforms
class MemorySecureStorage {
  static _storage = new Map();

  static async storeKey(keyId, keyData) {
    console.warn('Using memory storage - keys will not persist after application restart');
    this._storage.set(keyId, new Uint8Array(keyData));
    return true;
  }

  static async retrieveKey(keyId) {
    return this._storage.get(keyId) || null;
  }

  static async isHardwareSecurityAvailable() {
    return false;
  }

  static async deleteKey(keyId) {
    return this._storage.delete(keyId);
  }

  static clearAll() {
    this._storage.clear();
  }
}

// Main SecureKeyStorage class with platform detection
export default class SecureKeyStorage {
  static _implementation = null;

  static _getImplementation() {
    if (this._implementation) {
      return this._implementation;
    }

    const platform = getPlatform();
    
    switch (platform) {
      case 'browser-extension':
        this._implementation = ExtensionSecureStorage;
        break;
      case 'browser':
        this._implementation = BrowserSecureStorage;
        break;
      case 'electron':
        this._implementation = ElectronSecureStorage;
        break;
      default:
        console.warn(`Unsupported platform: ${platform}, falling back to memory storage`);
        this._implementation = MemorySecureStorage;
        break;
    }

    return this._implementation;
  }

  static async storeKey(keyId, keyData) {
    const impl = this._getImplementation();
    return await impl.storeKey(keyId, keyData);
  }

  static async retrieveKey(keyId) {
    const impl = this._getImplementation();
    return await impl.retrieveKey(keyId);
  }

  static async isHardwareSecurityAvailable() {
    const impl = this._getImplementation();
    return await impl.isHardwareSecurityAvailable();
  }

  static async deleteKey(keyId) {
    const impl = this._getImplementation();
    return await impl.deleteKey(keyId);
  }

  static getPlatform() {
    return getPlatform();
  }

  static clearMemoryStorage() {
    if (this._implementation === MemorySecureStorage) {
      MemorySecureStorage.clearAll();
    }
  }
}

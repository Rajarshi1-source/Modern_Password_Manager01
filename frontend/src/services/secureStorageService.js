import { CryptoService } from './cryptoService';

class SecureStorageService {
  constructor() {
    this.storage = window.sessionStorage;
    this.cryptoService = new CryptoService();
  }
  
  // Store data with an optional TTL (time to live in seconds)
  async setItem(key, value, ttl = null) {
    try {
      const data = {
        value,
        expires: ttl ? Date.now() + (ttl * 1000) : null
      };
      
      // Use a random encryption key and store it in memory only (not persistent)
      const encryptionKey = window.crypto.getRandomValues(new Uint8Array(16));
      const encryptedData = await this.cryptoService.encrypt(data, encryptionKey);
      
      this.storage.setItem(key, encryptedData);
      return true;
    } catch (error) {
      console.error('Error storing data securely:', error);
      return false;
    }
  }
  
  async getItem(key) {
    try {
      const encryptedData = this.storage.getItem(key);
      if (!encryptedData) return null;
      
      // [Add decryption code here]
      
      // Check if data has expired
      if (data.expires && Date.now() > data.expires) {
        this.removeItem(key);
        return null;
      }
      
      return data.value;
    } catch (error) {
      console.error('Error retrieving data securely:', error);
      return null;
    }
  }
  
  removeItem(key) {
    this.storage.removeItem(key);
  }
  
  clear() {
    this.storage.clear();
  }
}

export const secureStorage = new SecureStorageService();

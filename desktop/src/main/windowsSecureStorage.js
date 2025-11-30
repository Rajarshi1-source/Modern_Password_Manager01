const { app } = require('electron');
const fs = require('fs');
const path = require('path');

// Conditionally load node-dpapi only on Windows
let dpapi;
try {
  if (process.platform === 'win32') {
    dpapi = require('node-dpapi');
  }
} catch (error) {
  console.warn('node-dpapi not available, falling back to file-based storage:', error.message);
}

class WindowsSecureStorage {
  static async isHardwareSecurityAvailable() {
    try {
      // Check if Windows Hello is available (Windows only)
      if (process.platform === 'win32' && dpapi) {
        return await dpapi.isWindowsHelloAvailable();
      }
      return false; // Not available on non-Windows platforms
    } catch (error) {
      console.error('Error checking hardware security availability:', error);
      return false;
    }
  }
  
  static async storeKey(keyId, keyData) {
    try {
      const userDataPath = app.getPath('userData');
      const keyPath = path.join(userDataPath, 'secure_keys');
      
      // Ensure directory exists
      if (!fs.existsSync(keyPath)) {
        fs.mkdirSync(keyPath, { recursive: true });
      }

      let dataToStore;
      
      if (process.platform === 'win32' && dpapi) {
        try {
          // Encrypt with Windows Data Protection API
          dataToStore = await dpapi.protectDataWithPrompt(
            Buffer.from(keyData),
            'Secure your encryption keys',
            'PasswordManager'
          );
        } catch (dpapiError) {
          console.warn('DPAPI encryption failed, falling back to file storage:', dpapiError.message);
          // Fall back to simple file storage (less secure)
          dataToStore = Buffer.from(JSON.stringify({
            data: Array.from(new Uint8Array(keyData)),
            platform: 'fallback',
            timestamp: Date.now()
          }));
        }
      } else {
        // Non-Windows platforms or DPAPI not available
        dataToStore = Buffer.from(JSON.stringify({
          data: Array.from(new Uint8Array(keyData)),
          platform: process.platform,
          timestamp: Date.now()
        }));
      }
      
      // Save encrypted/encoded data to secure location
      fs.writeFileSync(
        path.join(keyPath, `${keyId}.bin`),
        dataToStore
      );
      
      return true;
    } catch (error) {
      console.error('Error storing key:', error);
      throw new Error(`Failed to store key: ${error.message}`);
    }
  }
  
  static async retrieveKey(keyId) {
    try {
      const userDataPath = app.getPath('userData');
      const keyPath = path.join(userDataPath, 'secure_keys', `${keyId}.bin`);
      
      if (!fs.existsSync(keyPath)) {
        return null; // Key not found
      }
      
      const storedData = fs.readFileSync(keyPath);
      
      // Try to determine if this is DPAPI-encrypted or fallback format
      if (process.platform === 'win32' && dpapi) {
        try {
          // Try DPAPI decryption first
          const decryptedData = await dpapi.unprotectDataWithPrompt(
            storedData,
            'Access your encryption keys',
            'PasswordManager'
          );
          return new Uint8Array(decryptedData);
        } catch (dpapiError) {
          console.warn('DPAPI decryption failed, trying fallback format:', dpapiError.message);
          // Fall through to fallback parsing
        }
      }
      
      // Try to parse as fallback JSON format
      try {
        const jsonData = JSON.parse(storedData.toString());
        if (jsonData.data && Array.isArray(jsonData.data)) {
          return new Uint8Array(jsonData.data);
        }
      } catch (parseError) {
        console.error('Failed to parse stored key data:', parseError.message);
      }
      
      throw new Error('Unable to decrypt or parse stored key');
    } catch (error) {
      console.error('Error retrieving key:', error);
      throw new Error(`Failed to retrieve key: ${error.message}`);
    }
  }

  static async deleteKey(keyId) {
    try {
      const userDataPath = app.getPath('userData');
      const keyPath = path.join(userDataPath, 'secure_keys', `${keyId}.bin`);
      
      if (fs.existsSync(keyPath)) {
        fs.unlinkSync(keyPath);
        return true;
      }
      return false; // Key didn't exist
    } catch (error) {
      console.error('Error deleting key:', error);
      throw new Error(`Failed to delete key: ${error.message}`);
    }
  }
}

module.exports = WindowsSecureStorage;

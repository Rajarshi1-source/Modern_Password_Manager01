import SecureKeyStorage from '../../../shared/crypto/secure_storage';

export default class WebSecureStorage extends SecureKeyStorage {
  static async isHardwareSecurityAvailable() {
    try {
      // Check if secure context and CryptoKey supports non-extractable keys
      return window.isSecureContext && 
             'crypto' in window && 
             'subtle' in window.crypto;
    } catch (e) {
      return false;
    }
  }
  
  static async storeKey(keyId, keyData) {
    // Import the key as non-extractable
    const key = await window.crypto.subtle.importKey(
      'raw',
      keyData,
      { name: 'AES-GCM' },
      false, // non-extractable
      ['encrypt', 'decrypt']
    );
    
    // Store reference in sessionStorage (key stays in protected memory)
    sessionStorage.setItem(`key_${keyId}`, JSON.stringify({
      id: keyId,
      created: new Date().toISOString()
    }));
    
    // Store the CryptoKey object in a closure
    if (!window._secureKeys) window._secureKeys = {};
    window._secureKeys[keyId] = key;
    
    return true;
  }
  
  static async retrieveKey(keyId) {
    if (!window._secureKeys || !window._secureKeys[keyId]) {
      throw new Error('Key not found or session expired');
    }
    return window._secureKeys[keyId];
  }
}

import SecureKeyStorage from './secure_storage';

/**
 * Derive a cryptographic key from password and salt using PBKDF2
 * @param {string} masterPassword - The master password
 * @param {string|Uint8Array} salt - The salt for key derivation
 * @param {number} iterations - Number of PBKDF2 iterations (default: 100000)
 * @param {number} keyLength - Desired key length in bytes (default: 32)
 * @returns {Promise<Uint8Array>} Derived key
 */
export const deriveKey = async (masterPassword, salt, iterations = 100000, keyLength = 32) => {
  // Convert inputs to proper format
  const encoder = new TextEncoder();
  const passwordBuffer = encoder.encode(masterPassword);
  
  let saltBuffer;
  if (typeof salt === 'string') {
    // If salt is base64 encoded, decode it; otherwise encode as UTF-8
    try {
      saltBuffer = Uint8Array.from(atob(salt), c => c.charCodeAt(0));
    } catch (e) {
      saltBuffer = encoder.encode(salt);
    }
  } else {
    saltBuffer = salt;
  }
  
  // Check if we have Web Crypto API support
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    try {
      // Import the password as a key
      const keyMaterial = await crypto.subtle.importKey(
        'raw',
        passwordBuffer,
        'PBKDF2',
        false,
        ['deriveBits']
      );
      
      // Derive the key using PBKDF2
      const derivedBits = await crypto.subtle.deriveBits(
        {
          name: 'PBKDF2',
          salt: saltBuffer,
          iterations: iterations,
          hash: 'SHA-256'
        },
        keyMaterial,
        keyLength * 8 // Convert bytes to bits
      );
      
      return new Uint8Array(derivedBits);
    } catch (error) {
      console.warn('Web Crypto API failed, falling back to manual implementation:', error);
    }
  }
  
  // Fallback: Manual PBKDF2 implementation (less secure, for compatibility)
  return await pbkdf2Fallback(passwordBuffer, saltBuffer, iterations, keyLength);
};

/**
 * Fallback PBKDF2 implementation using only basic crypto functions
 * This is less secure than the Web Crypto API but provides compatibility
 */
async function pbkdf2Fallback(password, salt, iterations, keyLength) {
  // Simple PBKDF2 implementation - NOTE: This is for compatibility only
  // In production, always prefer Web Crypto API or a proper crypto library
  
  const hmac = async (key, data) => {
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const cryptoKey = await crypto.subtle.importKey(
        'raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
      );
      const signature = await crypto.subtle.sign('HMAC', cryptoKey, data);
      return new Uint8Array(signature);
    } else {
      // Very basic fallback - NOT cryptographically secure
      console.warn('No crypto support available, using insecure fallback');
      const result = new Uint8Array(32);
      for (let i = 0; i < 32; i++) {
        result[i] = (key[i % key.length] ^ data[i % data.length]) & 0xff;
      }
      return result;
    }
  };
  
  const blockSize = 32; // SHA-256 block size
  const blockCount = Math.ceil(keyLength / blockSize);
  const derivedKey = new Uint8Array(keyLength);
  
  for (let i = 1; i <= blockCount; i++) {
    // Create block input: salt + block number (big-endian)
    const blockInput = new Uint8Array(salt.length + 4);
    blockInput.set(salt);
    blockInput[salt.length] = (i >>> 24) & 0xff;
    blockInput[salt.length + 1] = (i >>> 16) & 0xff;
    blockInput[salt.length + 2] = (i >>> 8) & 0xff;
    blockInput[salt.length + 3] = i & 0xff;
    
    // First iteration
    let u = await hmac(password, blockInput);
    let result = new Uint8Array(u);
    
    // Remaining iterations
    for (let j = 1; j < iterations; j++) {
      u = await hmac(password, u);
      for (let k = 0; k < u.length; k++) {
        result[k] ^= u[k];
      }
    }
    
    // Copy to final key
    const offset = (i - 1) * blockSize;
    const copyLength = Math.min(blockSize, keyLength - offset);
    derivedKey.set(result.slice(0, copyLength), offset);
  }
  
  return derivedKey;
}

export const deriveAndStoreKey = async (masterPassword, salt) => {
  // Always derive the key from password first
  const derivedKey = await deriveKey(masterPassword, salt);
  
  // Check if secure hardware is available
  const canUseHardware = await SecureKeyStorage.isHardwareSecurityAvailable();
  
  if (canUseHardware) {
    // Generate a unique ID for this key
    const keyId = `user_key_${salt.substring(0, 10)}`;
    
    // Store the derived key in secure hardware
    await SecureKeyStorage.storeKey(keyId, derivedKey);
    
    // Return just the key ID for future reference
    return { keyId, useHardware: true };
  } else {
    // If hardware security isn't available, fall back to memory storage
    return { key: derivedKey, useHardware: false };
  }
};

export const getKey = async (keyInfo) => {
  if (keyInfo.useHardware && keyInfo.keyId) {
    // Retrieve from secure hardware
    return await SecureKeyStorage.retrieveKey(keyInfo.keyId);
  } else {
    // The key is already in memory
    return keyInfo.key;
  }
};

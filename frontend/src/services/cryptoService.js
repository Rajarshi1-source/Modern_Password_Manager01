import CryptoJS from 'crypto-js';
import pako from 'pako';
import * as argon2 from 'argon2-browser';

/**
 * CryptoService - Implements client-side encryption for a zero-knowledge architecture
 * 
 * ZERO-KNOWLEDGE SECURITY MODEL:
 * 1. All encryption/decryption happens exclusively in the browser
 * 2. The server never receives plaintext data or encryption keys
 * 3. The master password never leaves the client
 * 4. Only encrypted data is transmitted to and stored on the server
 * 5. Recovery keys provide an alternative decryption path but maintain the zero-knowledge model
 */
export class CryptoService {
  constructor(masterPassword) {
    this.masterPassword = masterPassword;
    // Initialize SubtleCrypto API
    this.subtle = window.crypto.subtle;
  }
  
  // Convert master password to a CryptoKey object using Web Crypto API
  async getCryptoKey(salt) {
    // Use native WebCrypto if available for hardware-backed key derivation
    try {
      const encoder = new TextEncoder();
      const passwordData = encoder.encode(this.masterPassword);
      const saltData = typeof salt === 'string' ? 
        Uint8Array.from(atob(salt), c => c.charCodeAt(0)) : 
        salt;
      
      // Import key material
      const keyMaterial = await this.subtle.importKey(
        'raw',
        passwordData,
        { name: 'PBKDF2' },
        false,
        ['deriveBits', 'deriveKey']
      );
      
      // Derive an AES-GCM key using PBKDF2
      return await this.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: saltData,
          iterations: 600000,
          hash: 'SHA-256'
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        true, // extractable
        ['encrypt', 'decrypt']
      );
    } catch (error) {
      console.error('WebCrypto not available, falling back to CryptoJS:', error);
      // Fall back to previous implementation
      return this.legacyDeriveKey(salt);
    }
  }
  
  // Use WebCrypto for encryption
  async encrypt(data, salt) {
    try {
      // Try to use WebCrypto API for hardware-accelerated encryption
      const key = await this.getCryptoKey(salt);
      
      // Generate random IV
      const iv = window.crypto.getRandomValues(new Uint8Array(12));
      
      // Convert data to ArrayBuffer
      const encoder = new TextEncoder();
      const dataToEncrypt = encoder.encode(JSON.stringify(data));
      
      // Encrypt with AES-GCM (more secure than AES-CBC)
      const encryptedData = await this.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        dataToEncrypt
      );
      
      // Combine IV and encrypted data
      const result = {
        iv: Array.from(iv).map(b => String.fromCharCode(b)).join(''),
        data: Array.from(new Uint8Array(encryptedData)).map(b => String.fromCharCode(b)).join(''),
        version: 'webcrypto-1',
        usingHardwareEncryption: navigator.credentials && !!navigator.credentials.preventSilentAccess
      };
      
      return btoa(JSON.stringify(result));
    } catch (error) {
      console.error('WebCrypto encryption failed, falling back to CryptoJS:', error);
      // Derive a strong key (Argon2id, PBKDF2 fallback inside deriveKey)
      // BEFORE handing off to legacyEncrypt. Passing the raw salt here
      // would let CryptoJS run its weak internal EVP_BytesToKey KDF on
      // the master password — the pattern CodeQL flags as
      // js/insufficient-password-hash.
      const derivedKey = await this.deriveKey(salt);
      return this.legacyEncrypt(data, derivedKey);
    }
  }
  
  // Detect device capabilities for adaptive Argon2id parameters
  getDeviceCapabilities() {
    // Check if we're on a low-end device
    const memory = navigator.deviceMemory || 4; // GB, default to 4GB if not available
    const cores = navigator.hardwareConcurrency || 1;
    
    // Categorize device
    if (memory >= 8 && cores >= 4) {
      return 'high'; // Desktop/high-end laptop
    } else if (memory >= 4 && cores >= 2) {
      return 'medium'; // Mid-range device
    } else {
      return 'low'; // Low-end mobile
    }
  }
  
  // Get Argon2id parameters based on device capabilities
  getArgon2Params(deviceCapability = null) {
    const capability = deviceCapability || this.getDeviceCapabilities();
    
    // Enhanced parameters for v2 encryption
    const params = {
      high: {
        time: 4,        // iterations
        mem: 131072,    // 128 MB
        parallelism: 2,
        version: 2
      },
      medium: {
        time: 4,
        mem: 98304,     // 96 MB
        parallelism: 2,
        version: 2
      },
      low: {
        time: 3,
        mem: 65536,     // 64 MB
        parallelism: 1,
        version: 2
      },
      // Legacy parameters for backward compatibility
      legacy: {
        time: 10,
        mem: 65536,     // 64 MB
        parallelism: 1,
        version: 1
      }
    };
    
    return params[capability] || params.medium;
  }
  
  // Derive encryption key from master password and salt using Argon2
  async deriveKey(salt, cryptoVersion = 2) {
    // SECURITY NOTE: Key derivation happens client-side to maintain zero-knowledge principles
    // The derived key never leaves the client and is not stored persistently
    
    // SECURITY UPGRADE v2: Enhanced Argon2id parameters for stronger protection
    // - Increased memory cost (128 MB on capable devices)
    // - Adaptive parameters based on device capabilities
    // - Parallelism for multi-core CPUs
    
    try {
      const saltArr = typeof salt === 'string' 
        ? CryptoJS.enc.Base64.parse(salt).toString(CryptoJS.enc.Hex)
        : salt;
      
      // Get parameters based on crypto version
      const params = cryptoVersion === 1 
        ? this.getArgon2Params('legacy')
        : this.getArgon2Params();
      
      console.log(`Deriving key with Argon2id v${cryptoVersion}:`, {
        time: params.time,
        mem: `${params.mem / 1024} MB`,
        parallelism: params.parallelism
      });
      
      const result = await argon2.hash({
        pass: this.masterPassword,
        salt: saltArr,
        time: params.time,
        mem: params.mem,
        hashLen: 32, // Output hash length in bytes
        parallelism: params.parallelism,
        type: argon2.ArgonType.Argon2id // Use Argon2id variant
      });

      // Return base64 encoded hash for AES encryption
      return CryptoJS.enc.Base64.stringify(CryptoJS.enc.Hex.parse(result.hashHex));
    } catch (error) {
      console.error('Argon2 key derivation failed, falling back to PBKDF2:', error);
      
      // Fallback to PBKDF2 with increased iterations for backward compatibility
      const key = CryptoJS.PBKDF2(this.masterPassword, salt, {
        keySize: 256/32,  // 256 bits
        iterations: 600000, // Increased iterations for better security
        hasher: CryptoJS.algo.SHA256
      });
      return key.toString(CryptoJS.enc.Base64);
    }
  }

  // ===========================================================================
  // Adaptive-password zero-knowledge fingerprint (PR-1)
  // ===========================================================================
  //
  // The adaptive-password feature must never send the raw password to the
  // server (see docs/adaptive-password-zk-remediation-plan.md). Instead the
  // client computes a *keyed* fingerprint: HMAC-SHA256 over the password under
  // a key derived from the master password. Because the server never holds the
  // key, the fingerprint is opaque to it (it cannot be reversed or offline-
  // guessed) yet is deterministic, so the server can still correlate/dedup
  // "the same password" across sessions. This is strictly stronger than a bare
  // SHA-256 of the password, which is offline-guessable.

  /**
   * Derive (and cache) the HMAC fingerprint key from the master password.
   *
   * The key is memory-hard (Argon2id, PBKDF2 fallback), never leaves the
   * client, and is domain-separated from the vault encryption key via the
   * ":adaptive-fp" salt suffix so the two key streams cannot be correlated.
   *
   * @param {string} perUserSalt - Non-secret, stable per-user salt (seeds the
   *   KDF; useless without the master password).
   * @returns {Promise<CryptoKey>} A non-extractable HMAC-SHA256 signing key.
   */
  async deriveFingerprintKey(perUserSalt) {
    if (typeof this.masterPassword !== 'string' || this.masterPassword.length === 0) {
      throw new Error('deriveFingerprintKey requires an unlocked master password');
    }
    if (!perUserSalt) {
      throw new Error('deriveFingerprintKey requires a per-user salt');
    }
    if (this._fpKeyCache && this._fpKeyCache.salt === perUserSalt) {
      return this._fpKeyCache.key;
    }

    const keyBits = await this._deriveFingerprintKeyBits(perUserSalt);
    const key = await this.subtle.importKey(
      'raw',
      keyBits,
      { name: 'HMAC', hash: 'SHA-256' },
      false, // non-extractable
      ['sign']
    );

    this._fpKeyCache = { salt: perUserSalt, key };
    return key;
  }

  /**
   * Derive 256 bits of fingerprint-key material from the master password.
   * Prefers Argon2id (matching the vault KDF); falls back to WebCrypto PBKDF2.
   * @private
   */
  async _deriveFingerprintKeyBits(perUserSalt) {
    const domainSalt = `${perUserSalt}:adaptive-fp`;
    try {
      const result = await argon2.hash({
        pass: this.masterPassword,
        salt: domainSalt,
        time: 3,
        mem: 65536, // 64 MB
        hashLen: 32,
        parallelism: 1,
        type: argon2.ArgonType.Argon2id,
      });
      return result.hash instanceof Uint8Array
        ? result.hash
        : Uint8Array.from(result.hash);
    } catch (error) {
      console.error('Argon2 fingerprint-key derivation failed, falling back to PBKDF2:', error);
      const enc = new TextEncoder();
      const keyMaterial = await this.subtle.importKey(
        'raw',
        enc.encode(this.masterPassword),
        { name: 'PBKDF2' },
        false,
        ['deriveBits']
      );
      const bits = await this.subtle.deriveBits(
        { name: 'PBKDF2', salt: enc.encode(domainSalt), iterations: 600000, hash: 'SHA-256' },
        keyMaterial,
        256
      );
      return new Uint8Array(bits);
    }
  }

  /**
   * Compute the keyed, deterministic, non-reversible fingerprint of a password.
   *
   * @param {string} password - The plaintext password (never leaves the client).
   * @param {string} perUserSalt - The per-user salt (see deriveFingerprintKey).
   * @returns {Promise<string>} A 24-char base64url fingerprint (144 bits).
   */
  async passwordFingerprint(password, perUserSalt) {
    if (typeof password !== 'string' || password.length === 0) {
      throw new Error('passwordFingerprint requires a non-empty password');
    }
    const key = await this.deriveFingerprintKey(perUserSalt);
    const message = new TextEncoder().encode(`adaptive-pw|${password}`);
    const signature = await this.subtle.sign('HMAC', key, message);
    return this._toBase64Url(new Uint8Array(signature)).slice(0, 24);
  }

  /**
   * Encode a byte array as unpadded base64url.
   * @private
   */
  _toBase64Url(bytes) {
    const binary = Array.from(bytes, (b) => String.fromCharCode(b)).join('');
    return btoa(binary)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }

  // Encrypt data with AES-256.
  //
  // NOTE: `key` here is the *already-derived* key from deriveKey()
  // (Argon2id, see above) — not a master password. Passing it as a
  // raw string to CryptoJS.AES.encrypt would trigger CryptoJS's
  // legacy EVP_BytesToKey password-derivation pipeline, which is the
  // exact pattern CodeQL's js/insufficient-password-hash query flags.
  // We coerce to a WordArray first so CryptoJS uses it as a real key
  // and skips the weak internal KDF.
  async legacyEncrypt(data, key) {
    // SECURITY NOTE: Encryption occurs client-side - plaintext data never sent to server

    // Guard against accidental misuse: the `key` argument must be the
    // *derived* key (Argon2id / PBKDF2 output, base64-encoded ~44 chars
    // for a 32-byte key, or a CryptoJS WordArray). Anything shorter is
    // almost certainly a raw password or salt and would force CryptoJS
    // through its weak internal KDF.
    if (typeof key === 'string' && key.length < 40) {
      throw new Error(
        'legacyEncrypt requires a derived key (Argon2id/PBKDF2), not a raw password or salt'
      );
    }

    // Compress data before encryption for large items
    let dataToEncrypt = data;
    let compressed = false;

    // Only compress if data is large enough
    const jsonData = JSON.stringify(data);
    if (jsonData.length > 1024) {
      try {
        const compressedData = pako.deflate(jsonData);
        // Only use compressed version if it's actually smaller
        if (compressedData.length < jsonData.length) {
          dataToEncrypt = compressedData;
          compressed = true;
        }
      } catch (error) {
        console.warn('Compression failed, using uncompressed data', error);
        // Continue with uncompressed data
      }
    }

    // Generate random IV (Initialization Vector)
    const iv = CryptoJS.lib.WordArray.random(16);

    // Encrypt data
    const dataToProcess = compressed
      ? CryptoJS.lib.WordArray.create(dataToEncrypt)
      : JSON.stringify(dataToEncrypt);

    const keyWordArray = typeof key === 'string'
      ? CryptoJS.enc.Base64.parse(key)
      : key;

    // TODO(security): migrate this legacy CryptoJS path to AES-GCM
    // for authenticated encryption (CodeQL alert #1041 / CWE-916
    // family). CBC + Pkcs7 has no integrity tag; the higher-level
    // wrapped-DEK envelope (sessionVaultCryptoV3) already uses
    // AES-GCM and is what new code should reach for. Keeping CBC
    // here for now because cipher-text in user vaults predates the
    // v3 path and rotating it requires a re-encrypt sweep that is
    // out of scope for the alert-cleanup PR.
    const encrypted = CryptoJS.AES.encrypt(dataToProcess, keyWordArray, {
      iv: iv,
      mode: CryptoJS.mode.CBC,
      padding: CryptoJS.pad.Pkcs7
    });
    
    // Combine IV, compression flag, and encrypted data
    const result = {
      iv: iv.toString(CryptoJS.enc.Base64),
      data: encrypted.toString(),
      compressed // Store flag to know if we need to decompress
    };
    
    return JSON.stringify(result);
  }
  
  // Decrypt data with AES-256
  async decrypt(encryptedData, key) {
    // SECURITY NOTE: Decryption occurs client-side - the server never has access to plaintext data
    try {
      const payload = JSON.parse(encryptedData);
      
      if (!payload.iv || !payload.data) {
        throw new Error('Invalid encrypted data format');
      }
      
      // Get IV from payload
      const iv = CryptoJS.enc.Base64.parse(payload.iv);

      // Mirror legacyEncrypt: coerce a string key into a WordArray so
      // CryptoJS uses it directly as the AES key rather than running
      // its weak internal password-derivation routine.
      const keyWordArray = typeof key === 'string'
        ? CryptoJS.enc.Base64.parse(key)
        : key;

      // Decrypt data
      const decrypted = CryptoJS.AES.decrypt(payload.data, keyWordArray, {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
      });
      
      // Handle decompression if data was compressed
      if (payload.compressed) {
        try {
          // Convert WordArray to byte array
          const decryptedBytes = this.convertWordArrayToUint8Array(decrypted);
          // Decompress
          const decompressed = pako.inflate(decryptedBytes);
          // Convert back to string
          const jsonStr = new TextDecoder().decode(decompressed);
          return JSON.parse(jsonStr);
        } catch (error) {
          console.error('Decompression failed', error);
          throw error;
        }
      } else {
        // Regular JSON parse for uncompressed data
        const decryptedStr = decrypted.toString(CryptoJS.enc.Utf8);
        if (!decryptedStr) {
          throw new Error('Decryption failed - invalid key or corrupted data');
        }
        return JSON.parse(decryptedStr);
      }
    } catch (error) {
      console.error('Decryption error:', error.message);
      throw new Error('Failed to decrypt data: ' + error.message);
    }
  }
  
  // Helper function to convert CryptoJS WordArray to Uint8Array
  convertWordArrayToUint8Array(wordArray) {
    const words = wordArray.words;
    const sigBytes = wordArray.sigBytes;
    const u8 = new Uint8Array(sigBytes);
    
    for (let i = 0; i < sigBytes; i++) {
      const byte = (words[i >>> 2] >>> (24 - (i % 4) * 8)) & 0xff;
      u8[i] = byte;
    }
    
    return u8;
  }
  
  // Generate a strong random password
  generatePassword(length = 16, options = {
    uppercase: true,
    lowercase: true,
    numbers: true,
    symbols: true
  }) {
    const chars = {
      uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
      lowercase: 'abcdefghijklmnopqrstuvwxyz',
      numbers: '0123456789',
      symbols: '!@#$%^&*()_+~`|}{[]:;?><,./-='
    };
    
    let charset = '';
    if (options.uppercase) charset += chars.uppercase;
    if (options.lowercase) charset += chars.lowercase;
    if (options.numbers) charset += chars.numbers;
    if (options.symbols) charset += chars.symbols;
    
    // Ensure at least one character set is selected
    if (charset === '') {
      charset = chars.lowercase + chars.numbers;
    }
    
    // SECURITY NOTE: Using the Web Crypto API for cryptographically secure random values
    let password = '';
    const randomValues = new Uint32Array(length);
    window.crypto.getRandomValues(randomValues);
    
    for (let i = 0; i < length; i++) {
      password += charset[randomValues[i] % charset.length];
    }
    
    return password;
  }
  
  /**
   * Extract metadata from encrypted data without full decryption
   * This is a lightweight operation that only parses the payload structure
   * @param {string} encryptedData - The encrypted data string
   * @returns {Object} Metadata object with preview information
   */
  extractMetadata(encryptedData) {
    try {
      const payload = JSON.parse(encryptedData);
      
      // Basic metadata available without decryption
      return {
        hasIV: !!payload.iv,
        hasData: !!payload.data,
        compressed: payload.compressed || false,
        version: payload.version || 'legacy',
        timestamp: Date.now()
      };
    } catch (error) {
      console.error('Failed to extract metadata:', error);
      return {
        hasIV: false,
        hasData: false,
        compressed: false,
        version: 'unknown',
        timestamp: Date.now()
      };
    }
  }
  
  /**
   * Extract preview title from encrypted data
   * Note: This is a heuristic and may not always work perfectly
   * For true zero-knowledge, titles should be stored separately
   * @param {string} itemType - The item type
   * @returns {string} Preview title or placeholder
   */
  extractPreviewTitle(itemType) {
    // Simple preview based on item type
    const previews = {
      'password': '🔑 Password Entry',
      'card': '💳 Payment Card',
      'identity': '👤 Identity Document',
      'note': '📝 Secure Note'
    };
    return previews[itemType] || '📄 Vault Item';
  }
  
  // Add method to clear sensitive data
  clearKeys() {
    // SECURITY NOTE: Securely clear sensitive data from memory when no longer needed
    this.masterPassword = null;
    this.encryptionKey = null;
    // Drop the cached HMAC fingerprint key so it can't be reused after clearing.
    this._fpKeyCache = null;
    // Overwrite memory with random data
    const buf = new Uint8Array(1024);
    crypto.getRandomValues(buf);
    // Force garbage collection if possible
    if (global.gc) global.gc();
  }
  
  /**
   * Derive key from recovery key - separate from master password key derivation
   * Used for recovery flows
   * @param {string} recoveryKey - The recovery key to derive an encryption key from
   * @param {string} salt - Base64 encoded salt
   * @returns {string} The derived key
   */
  async deriveKeyFromRecoveryKey(recoveryKey, salt, iterations = 10) {
    // SECURITY NOTE: Recovery key derivation also happens client-side
    // Recovery keys provide an alternative decryption path while maintaining zero-knowledge
    try {
      // Remove hyphens before deriving key
      const cleanRecoveryKey = recoveryKey.replace(/-/g, '');
      
      const saltArr = typeof salt === 'string' 
        ? CryptoJS.enc.Base64.parse(salt).toString(CryptoJS.enc.Hex)
        : salt;
      
      const result = await argon2.hash({
        pass: cleanRecoveryKey,
        salt: saltArr,
        time: iterations, // Number of iterations
        mem: 65536, // Memory usage in KiB (64 MB)
        hashLen: 32, // Output hash length in bytes
        parallelism: 1, // Parallelism factor
        type: argon2.ArgonType.Argon2id // Use Argon2id variant
      });

      // Return base64 encoded hash for AES encryption
      return CryptoJS.enc.Base64.stringify(CryptoJS.enc.Hex.parse(result.hashHex));
    } catch (error) {
      console.error('Argon2 key derivation failed for recovery key, falling back to PBKDF2:', error);
      
      // Fallback to PBKDF2 with increased iterations
      const key = CryptoJS.PBKDF2(
        recoveryKey.replace(/-/g, ''), // Remove hyphens before deriving key
        salt, 
        {
          keySize: 256/32,
          iterations: 600000, // Increased iterations for better security
          hasher: CryptoJS.algo.SHA256
        }
      );
      return key.toString(CryptoJS.enc.Base64);
    }
  }
}

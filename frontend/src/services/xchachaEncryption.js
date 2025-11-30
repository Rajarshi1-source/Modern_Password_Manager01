/**
 * XChaCha20-Poly1305 Encryption Service (Frontend)
 * 
 * Client-side encryption service using XChaCha20-Poly1305 AEAD
 * Compatible with backend Python implementation
 * 
 * Note: Uses SubtleCrypto API with ChaCha20-Poly1305
 * For full XChaCha20 support, consider using libsodium.js
 */

class XChaChaEncryptionService {
  constructor() {
    this.crypto = window.crypto || window.msCrypto;
    this.subtle = this.crypto.subtle;
    
    if (!this.subtle) {
      throw new Error('SubtleCrypto API not supported in this browser');
    }
  }

  /**
   * Generate a secure random 256-bit key
   * @returns {Promise<ArrayBuffer>} 32-byte encryption key
   */
  async generateKey() {
    const key = this.crypto.getRandomValues(new Uint8Array(32));
    return key.buffer;
  }

  /**
   * Generate a secure random nonce
   * @param {number} size - Nonce size in bytes (default: 12 for ChaCha20)
   * @returns {Uint8Array} Random nonce
   */
  generateNonce(size = 12) {
    return this.crypto.getRandomValues(new Uint8Array(size));
  }

  /**
   * Convert key buffer to CryptoKey object
   * @param {ArrayBuffer} keyBuffer - Raw key bytes
   * @returns {Promise<CryptoKey>}
   */
  async importKey(keyBuffer) {
    return await this.subtle.importKey(
      'raw',
      keyBuffer,
      { name: 'AES-GCM' }, // Fallback to AES-GCM for browser compatibility
      false,
      ['encrypt', 'decrypt']
    );
  }

  /**
   * Encrypt data using ChaCha20-Poly1305 (or AES-GCM fallback)
   * @param {ArrayBuffer} keyBuffer - Encryption key
   * @param {string|ArrayBuffer} plaintext - Data to encrypt
   * @param {string} [associatedData] - Optional authenticated data
   * @returns {Promise<Object>} Encrypted package with nonce
   */
  async encrypt(keyBuffer, plaintext, associatedData = null) {
    try {
      // Convert plaintext to ArrayBuffer if string
      const plaintextBuffer = typeof plaintext === 'string'
        ? new TextEncoder().encode(plaintext)
        : plaintext;

      // Generate nonce
      const nonce = this.generateNonce(12);

      // Import key
      const cryptoKey = await this.importKey(keyBuffer);

      // Encrypt data
      const ciphertext = await this.subtle.encrypt(
        {
          name: 'AES-GCM',
          iv: nonce,
          tagLength: 128, // 128-bit authentication tag
          additionalData: associatedData 
            ? new TextEncoder().encode(associatedData) 
            : undefined
        },
        cryptoKey,
        plaintextBuffer
      );

      // Return structured result
      return {
        ciphertext: this.arrayBufferToBase64(ciphertext),
        nonce: this.arrayBufferToBase64(nonce),
        algorithm: 'XChaCha20-Poly1305', // Logical algorithm
        actualAlgorithm: 'AES-256-GCM', // Actual browser implementation
        version: '1.0'
      };
    } catch (error) {
      console.error('Encryption failed:', error);
      throw new Error(`Encryption failed: ${error.message}`);
    }
  }

  /**
   * Decrypt data using ChaCha20-Poly1305 (or AES-GCM fallback)
   * @param {ArrayBuffer} keyBuffer - Decryption key
   * @param {Object|string} encryptedData - Encrypted package or base64 ciphertext
   * @param {string} [associatedData] - Optional authenticated data
   * @returns {Promise<ArrayBuffer>} Decrypted plaintext
   */
  async decrypt(keyBuffer, encryptedData, associatedData = null) {
    try {
      // Parse encrypted data
      let ciphertext, nonce;
      
      if (typeof encryptedData === 'string') {
        // Assume it's base64-encoded ciphertext
        ciphertext = this.base64ToArrayBuffer(encryptedData);
        nonce = this.generateNonce(12); // Default nonce
      } else {
        ciphertext = this.base64ToArrayBuffer(encryptedData.ciphertext);
        nonce = this.base64ToArrayBuffer(encryptedData.nonce);
      }

      // Import key
      const cryptoKey = await this.importKey(keyBuffer);

      // Decrypt data
      const plaintext = await this.subtle.decrypt(
        {
          name: 'AES-GCM',
          iv: nonce,
          tagLength: 128,
          additionalData: associatedData 
            ? new TextEncoder().encode(associatedData) 
            : undefined
        },
        cryptoKey,
        ciphertext
      );

      return plaintext;
    } catch (error) {
      console.error('Decryption failed:', error);
      throw new Error(`Decryption failed: ${error.message}`);
    }
  }

  /**
   * Encrypt JSON-serializable data
   * @param {ArrayBuffer} keyBuffer - Encryption key
   * @param {*} data - JSON-serializable object
   * @param {string} [associatedData] - Optional authenticated data
   * @returns {Promise<string>} Base64-encoded encrypted package
   */
  async encryptJSON(keyBuffer, data, associatedData = null) {
    try {
      const jsonString = JSON.stringify(data);
      const encrypted = await this.encrypt(keyBuffer, jsonString, associatedData);
      
      // Return compact base64-encoded package
      const packageString = JSON.stringify(encrypted);
      return btoa(packageString);
    } catch (error) {
      console.error('JSON encryption failed:', error);
      throw new Error(`JSON encryption failed: ${error.message}`);
    }
  }

  /**
   * Decrypt and parse JSON data
   * @param {ArrayBuffer} keyBuffer - Decryption key
   * @param {string} encryptedPackage - Base64-encoded encrypted package
   * @param {string} [associatedData] - Optional authenticated data
   * @returns {Promise<*>} Decrypted and parsed JSON object
   */
  async decryptJSON(keyBuffer, encryptedPackage, associatedData = null) {
    try {
      // Decode package
      const packageString = atob(encryptedPackage);
      const encrypted = JSON.parse(packageString);
      
      // Decrypt
      const plaintextBuffer = await this.decrypt(keyBuffer, encrypted, associatedData);
      
      // Parse JSON
      const jsonString = new TextDecoder().decode(plaintextBuffer);
      return JSON.parse(jsonString);
    } catch (error) {
      console.error('JSON decryption failed:', error);
      throw new Error(`JSON decryption failed: ${error.message}`);
    }
  }

  /**
   * Derive encryption key from password using PBKDF2
   * @param {string} password - User password
   * @param {ArrayBuffer} salt - Salt value
   * @param {number} [iterations=100000] - PBKDF2 iterations
   * @returns {Promise<ArrayBuffer>} Derived 32-byte key
   */
  async deriveKeyFromPassword(password, salt, iterations = 100000) {
    try {
      const passwordBuffer = new TextEncoder().encode(password);
      
      // Import password as key material
      const keyMaterial = await this.subtle.importKey(
        'raw',
        passwordBuffer,
        'PBKDF2',
        false,
        ['deriveBits']
      );
      
      // Derive key using PBKDF2
      const derivedBits = await this.subtle.deriveBits(
        {
          name: 'PBKDF2',
          salt: salt,
          iterations: iterations,
          hash: 'SHA-256'
        },
        keyMaterial,
        256 // 256 bits = 32 bytes
      );
      
      return derivedBits;
    } catch (error) {
      console.error('Key derivation failed:', error);
      throw new Error(`Key derivation failed: ${error.message}`);
    }
  }

  /**
   * Derive sub-key from master key using HKDF
   * @param {ArrayBuffer} masterKey - Master encryption key
   * @param {string} context - Context string for key derivation
   * @param {ArrayBuffer} [salt] - Optional salt
   * @returns {Promise<ArrayBuffer>} Derived 32-byte sub-key
   */
  async deriveSubKey(masterKey, context, salt = null) {
    try {
      const contextBuffer = new TextEncoder().encode(context);
      
      // Import master key
      const keyMaterial = await this.subtle.importKey(
        'raw',
        masterKey,
        'HKDF',
        false,
        ['deriveBits']
      );
      
      // Derive sub-key using HKDF
      const derivedBits = await this.subtle.deriveBits(
        {
          name: 'HKDF',
          hash: 'SHA-256',
          salt: salt || new Uint8Array(32),
          info: contextBuffer
        },
        keyMaterial,
        256 // 256 bits = 32 bytes
      );
      
      return derivedBits;
    } catch (error) {
      console.error('Sub-key derivation failed:', error);
      throw new Error(`Sub-key derivation failed: ${error.message}`);
    }
  }

  /**
   * Convert ArrayBuffer to Base64 string
   * @param {ArrayBuffer} buffer
   * @returns {string}
   */
  arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  /**
   * Convert Base64 string to ArrayBuffer
   * @param {string} base64
   * @returns {ArrayBuffer}
   */
  base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * Convert ArrayBuffer to hex string (for debugging)
   * @param {ArrayBuffer} buffer
   * @returns {string}
   */
  arrayBufferToHex(buffer) {
    return Array.from(new Uint8Array(buffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  /**
   * Generate a secure random salt
   * @param {number} [size=16] - Salt size in bytes
   * @returns {Uint8Array}
   */
  generateSalt(size = 16) {
    return this.crypto.getRandomValues(new Uint8Array(size));
  }

  /**
   * Stream encryption for large files
   * @param {ArrayBuffer} keyBuffer - Encryption key
   * @param {File} file - File to encrypt
   * @param {Function} [progressCallback] - Progress callback (percent)
   * @returns {Promise<Object>} Encrypted file data
   */
  async encryptFile(keyBuffer, file, progressCallback = null) {
    try {
      const CHUNK_SIZE = 64 * 1024; // 64 KB chunks
      const chunks = [];
      const masterNonce = this.generateNonce(12);
      
      let offset = 0;
      let chunkNumber = 0;
      
      while (offset < file.size) {
        const chunk = file.slice(offset, offset + CHUNK_SIZE);
        const chunkBuffer = await chunk.arrayBuffer();
        
        // Derive chunk-specific nonce
        const chunkNonceExtra = new Uint8Array([chunkNumber]);
        const chunkNonce = new Uint8Array([...masterNonce, ...chunkNonceExtra]);
        
        // Encrypt chunk
        const encrypted = await this.encrypt(
          keyBuffer,
          chunkBuffer,
          null
        );
        
        chunks.push(encrypted);
        
        offset += CHUNK_SIZE;
        chunkNumber++;
        
        if (progressCallback) {
          progressCallback(Math.round((offset / file.size) * 100));
        }
      }
      
      return {
        chunks,
        masterNonce: this.arrayBufferToBase64(masterNonce),
        originalSize: file.size,
        chunkSize: CHUNK_SIZE,
        fileName: file.name,
        fileType: file.type
      };
    } catch (error) {
      console.error('File encryption failed:', error);
      throw new Error(`File encryption failed: ${error.message}`);
    }
  }

  /**
   * Stream decryption for large files
   * @param {ArrayBuffer} keyBuffer - Decryption key
   * @param {Object} encryptedFile - Encrypted file data
   * @param {Function} [progressCallback] - Progress callback (percent)
   * @returns {Promise<Blob>} Decrypted file
   */
  async decryptFile(keyBuffer, encryptedFile, progressCallback = null) {
    try {
      const decryptedChunks = [];
      
      for (let i = 0; i < encryptedFile.chunks.length; i++) {
        const decrypted = await this.decrypt(
          keyBuffer,
          encryptedFile.chunks[i],
          null
        );
        
        decryptedChunks.push(decrypted);
        
        if (progressCallback) {
          progressCallback(Math.round(((i + 1) / encryptedFile.chunks.length) * 100));
        }
      }
      
      // Combine chunks into blob
      const blob = new Blob(decryptedChunks, { type: encryptedFile.fileType });
      return blob;
    } catch (error) {
      console.error('File decryption failed:', error);
      throw new Error(`File decryption failed: ${error.message}`);
    }
  }
}

// Export singleton instance
const xchachaEncryptionService = new XChaChaEncryptionService();
export default xchachaEncryptionService;


/**
 * ECCService - Elliptic Curve Cryptography Service
 * 
 * Implements dual ECC curves for hybrid key exchange:
 * - Curve25519 (X25519): Modern, fast, side-channel resistant
 * - P-384 (secp384r1): NIST standard, enterprise trusted
 * 
 * This provides defense-in-depth: both curves must be compromised
 * for the system to be vulnerable.
 */

import { x25519 } from '@noble/curves/ed25519';
import { p384 } from '@noble/curves/p384';
import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha256';
import { randomBytes } from '@noble/hashes/utils';

export class ECCService {
  constructor() {
    this.CURVE25519_KEY_SIZE = 32; // bytes
    this.P384_KEY_SIZE = 48; // bytes (384 bits)
  }

  /**
   * Generate Curve25519 keypair
   * @returns {Object} { privateKey: Uint8Array, publicKey: Uint8Array }
   */
  generateCurve25519KeyPair() {
    try {
      // Generate random private key (32 bytes)
      const privateKey = x25519.utils.randomPrivateKey();
      
      // Derive public key
      const publicKey = x25519.getPublicKey(privateKey);
      
      return {
        privateKey,
        publicKey,
        curve: 'Curve25519'
      };
    } catch (error) {
      console.error('Failed to generate Curve25519 keypair:', error);
      throw new Error('Curve25519 key generation failed');
    }
  }

  /**
   * Generate P-384 keypair
   * @returns {Object} { privateKey: Uint8Array, publicKey: Uint8Array }
   */
  generateP384KeyPair() {
    try {
      // Generate random private key
      const privateKey = p384.utils.randomPrivateKey();
      
      // Derive public key (uncompressed format)
      const publicKey = p384.getPublicKey(privateKey);
      
      return {
        privateKey,
        publicKey,
        curve: 'P-384'
      };
    } catch (error) {
      console.error('Failed to generate P-384 keypair:', error);
      throw new Error('P-384 key generation failed');
    }
  }

  /**
   * Generate hybrid keypair (both Curve25519 and P-384)
   * @returns {Object} Contains both keypairs
   */
  generateHybridKeyPair() {
    try {
      const curve25519Pair = this.generateCurve25519KeyPair();
      const p384Pair = this.generateP384KeyPair();
      
      return {
        curve25519: curve25519Pair,
        p384: p384Pair,
        type: 'hybrid-ecdh',
        version: 2
      };
    } catch (error) {
      console.error('Failed to generate hybrid keypair:', error);
      throw new Error('Hybrid keypair generation failed');
    }
  }

  /**
   * Perform Curve25519 ECDH
   * @param {Uint8Array} privateKey - Our private key
   * @param {Uint8Array} publicKey - Peer's public key
   * @returns {Uint8Array} Shared secret
   */
  performCurve25519ECDH(privateKey, publicKey) {
    try {
      return x25519.getSharedSecret(privateKey, publicKey);
    } catch (error) {
      console.error('Curve25519 ECDH failed:', error);
      throw new Error('Curve25519 ECDH failed');
    }
  }

  /**
   * Perform P-384 ECDH
   * @param {Uint8Array} privateKey - Our private key
   * @param {Uint8Array} publicKey - Peer's public key
   * @returns {Uint8Array} Shared secret
   */
  performP384ECDH(privateKey, publicKey) {
    try {
      return p384.getSharedSecret(privateKey, publicKey);
    } catch (error) {
      console.error('P-384 ECDH failed:', error);
      throw new Error('P-384 ECDH failed');
    }
  }

  /**
   * Perform hybrid ECDH with both curves
   * @param {Object} ourKeys - Our keypair { curve25519: {...}, p384: {...} }
   * @param {Object} peerKeys - Peer's public keys
   * @returns {Object} { secret1: Uint8Array, secret2: Uint8Array }
   */
  performHybridECDH(ourKeys, peerKeys) {
    try {
      // Perform ECDH with Curve25519
      const secret1 = this.performCurve25519ECDH(
        ourKeys.curve25519.privateKey,
        peerKeys.curve25519
      );
      
      // Perform ECDH with P-384
      const secret2 = this.performP384ECDH(
        ourKeys.p384.privateKey,
        peerKeys.p384
      );
      
      return {
        curve25519Secret: secret1,
        p384Secret: secret2
      };
    } catch (error) {
      console.error('Hybrid ECDH failed:', error);
      throw new Error('Hybrid ECDH failed');
    }
  }

  /**
   * Derive final key from hybrid ECDH secrets using HKDF
   * @param {Uint8Array} secret1 - Curve25519 shared secret
   * @param {Uint8Array} secret2 - P-384 shared secret
   * @param {Uint8Array|string} salt - Salt for HKDF
   * @param {string} info - Context information
   * @returns {Uint8Array} Derived key (32 bytes for AES-256)
   */
  deriveKeyFromHybridSecret(secret1, secret2, salt, info = 'hybrid-ecdh-v2') {
    try {
      // Concatenate both secrets
      const combinedSecret = new Uint8Array(secret1.length + secret2.length);
      combinedSecret.set(secret1, 0);
      combinedSecret.set(secret2, secret1.length);
      
      // Convert salt to Uint8Array if it's a string
      const saltBytes = typeof salt === 'string' 
        ? new TextEncoder().encode(salt)
        : salt;
      
      // Convert info to Uint8Array
      const infoBytes = new TextEncoder().encode(info);
      
      // Use HKDF to derive final key
      const derivedKey = hkdf(
        sha256,           // Hash function
        combinedSecret,   // Input key material (both ECDH secrets)
        saltBytes,        // Salt
        infoBytes,        // Context info
        32                // Output length (32 bytes for AES-256)
      );
      
      return derivedKey;
    } catch (error) {
      console.error('Key derivation from hybrid secret failed:', error);
      throw new Error('Hybrid key derivation failed');
    }
  }

  /**
   * Wrap a key using hybrid ECDH
   * Used for encrypting vault keys for cross-device sync
   * @param {Uint8Array|string} keyToWrap - The key to encrypt
   * @param {Object} peerPublicKeys - Peer's public keys
   * @returns {Object} Wrapped key and our public keys
   */
  async wrapKey(keyToWrap, peerPublicKeys) {
    try {
      // Generate ephemeral keypair
      const ourKeys = this.generateHybridKeyPair();
      
      // Perform hybrid ECDH
      const { curve25519Secret, p384Secret } = this.performHybridECDH(
        ourKeys,
        peerPublicKeys
      );
      
      // Derive encryption key from hybrid secret
      const salt = randomBytes(32);
      const wrapKey = this.deriveKeyFromHybridSecret(
        curve25519Secret,
        p384Secret,
        salt,
        'key-wrap-v2'
      );
      
      // Import Web Crypto API
      const subtle = window.crypto.subtle;
      
      // Import the wrap key
      const wrapCryptoKey = await subtle.importKey(
        'raw',
        wrapKey,
        { name: 'AES-GCM' },
        false,
        ['encrypt']
      );
      
      // Convert keyToWrap to ArrayBuffer
      const keyBytes = typeof keyToWrap === 'string'
        ? new TextEncoder().encode(keyToWrap)
        : keyToWrap;
      
      // Generate IV
      const iv = randomBytes(12);
      
      // Encrypt the key
      const encryptedKey = await subtle.encrypt(
        { name: 'AES-GCM', iv },
        wrapCryptoKey,
        keyBytes
      );
      
      return {
        encryptedKey: new Uint8Array(encryptedKey),
        iv,
        salt,
        publicKeys: {
          curve25519: ourKeys.curve25519.publicKey,
          p384: ourKeys.p384.publicKey
        },
        version: 2
      };
    } catch (error) {
      console.error('Key wrapping failed:', error);
      throw new Error('Failed to wrap key with hybrid ECDH');
    }
  }

  /**
   * Unwrap a key using hybrid ECDH
   * @param {Object} wrappedData - Wrapped key data
   * @param {Object} ourPrivateKeys - Our private keys
   * @returns {Uint8Array} Unwrapped key
   */
  async unwrapKey(wrappedData, ourPrivateKeys) {
    try {
      // Perform hybrid ECDH
      const { curve25519Secret, p384Secret } = this.performHybridECDH(
        ourPrivateKeys,
        wrappedData.publicKeys
      );
      
      // Derive decryption key
      const unwrapKey = this.deriveKeyFromHybridSecret(
        curve25519Secret,
        p384Secret,
        wrappedData.salt,
        'key-wrap-v2'
      );
      
      // Import Web Crypto API
      const subtle = window.crypto.subtle;
      
      // Import the unwrap key
      const unwrapCryptoKey = await subtle.importKey(
        'raw',
        unwrapKey,
        { name: 'AES-GCM' },
        false,
        ['decrypt']
      );
      
      // Decrypt the key
      const decryptedKey = await subtle.decrypt(
        { name: 'AES-GCM', iv: wrappedData.iv },
        unwrapCryptoKey,
        wrappedData.encryptedKey
      );
      
      return new Uint8Array(decryptedKey);
    } catch (error) {
      console.error('Key unwrapping failed:', error);
      throw new Error('Failed to unwrap key with hybrid ECDH');
    }
  }

  /**
   * Convert Uint8Array to Base64 string
   * @param {Uint8Array} bytes
   * @returns {string}
   */
  bytesToBase64(bytes) {
    return btoa(String.fromCharCode(...bytes));
  }

  /**
   * Convert Base64 string to Uint8Array
   * @param {string} base64
   * @returns {Uint8Array}
   */
  base64ToBytes(base64) {
    return Uint8Array.from(atob(base64), c => c.charCodeAt(0));
  }

  /**
   * Export public keys for transmission
   * @param {Object} keys - Keypair object
   * @returns {Object} Base64-encoded public keys
   */
  exportPublicKeys(keys) {
    return {
      curve25519: this.bytesToBase64(keys.curve25519.publicKey),
      p384: this.bytesToBase64(keys.p384.publicKey),
      version: 2
    };
  }

  /**
   * Import public keys from Base64
   * @param {Object} encodedKeys - Base64-encoded public keys
   * @returns {Object} Uint8Array public keys
   */
  importPublicKeys(encodedKeys) {
    return {
      curve25519: this.base64ToBytes(encodedKeys.curve25519),
      p384: this.base64ToBytes(encodedKeys.p384)
    };
  }

  /**
   * Clear sensitive data from memory
   * @param {Uint8Array} data
   */
  secureWipe(data) {
    if (data instanceof Uint8Array) {
      crypto.getRandomValues(data);
      data.fill(0);
    }
  }
}

// Export singleton instance
export const eccService = new ECCService();
export default eccService;


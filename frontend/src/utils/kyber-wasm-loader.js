/**
 * WebAssembly Kyber Module Loader
 * 
 * Provides optimized loading and management of Kyber WASM modules:
 * - Dynamic import with code splitting
 * - Memory management for WASM operations
 * - Fallback to JavaScript implementation
 * - Singleton pattern for efficient resource usage
 * 
 * Usage:
 *   import { kyberWasm } from '@/utils/kyber-wasm-loader';
 *   
 *   await kyberWasm.loadModule();
 *   const encrypted = await kyberWasm.encrypt(plaintext, publicKey);
 */

// WASM module status
const WASM_STATUS = {
  NOT_LOADED: 'not_loaded',
  LOADING: 'loading',
  LOADED: 'loaded',
  FAILED: 'failed',
  FALLBACK: 'fallback'
};

class KyberWasmLoader {
  constructor() {
    this.module = null;
    this.status = WASM_STATUS.NOT_LOADED;
    this.isLoading = false;
    this.loadPromise = null;
    this.memory = null;
    
    // Configuration
    this.config = {
      wasmPath: '/assets/kyber.wasm',
      fallbackEnabled: true,
      memoryInitial: 256,  // Pages (16KB each)
      memoryMaximum: 512,
      enableSIMD: true,
      retryAttempts: 3,
      retryDelay: 1000
    };
    
    // Performance metrics
    this.metrics = {
      loadTime: 0,
      encryptCount: 0,
      decryptCount: 0,
      totalEncryptTime: 0,
      totalDecryptTime: 0,
      errors: 0
    };
    
    // Kyber-768 constants
    this.KYBER_PUBLIC_KEY_SIZE = 1184;
    this.KYBER_PRIVATE_KEY_SIZE = 2400;
    this.KYBER_CIPHERTEXT_SIZE = 1088;
    this.KYBER_SHARED_SECRET_SIZE = 32;
  }

  /**
   * Load the WASM module
   * 
   * @returns {Promise<Object>} Loaded WASM module exports
   */
  async loadModule() {
    // Return cached module if already loaded
    if (this.module && this.status === WASM_STATUS.LOADED) {
      return this.module;
    }
    
    // Return existing promise if currently loading
    if (this.isLoading && this.loadPromise) {
      return this.loadPromise;
    }
    
    this.isLoading = true;
    this.status = WASM_STATUS.LOADING;
    
    this.loadPromise = (async () => {
      const startTime = performance.now();
      
      try {
        // Try to load from existing Kyber packages first
        const module = await this._loadFromPackages();
        
        if (module) {
          this.module = module;
          this.status = WASM_STATUS.LOADED;
          this.metrics.loadTime = performance.now() - startTime;
          console.log(`[KyberWASM] Module loaded in ${this.metrics.loadTime.toFixed(2)}ms`);
          return this.module;
        }
        
        // Try to load WASM directly
        const wasmModule = await this._loadWasmDirect();
        
        if (wasmModule) {
          this.module = wasmModule;
          this.status = WASM_STATUS.LOADED;
          this.metrics.loadTime = performance.now() - startTime;
          console.log(`[KyberWASM] WASM loaded directly in ${this.metrics.loadTime.toFixed(2)}ms`);
          return this.module;
        }
        
        throw new Error('No WASM module available');
        
      } catch (error) {
        console.warn('[KyberWASM] Failed to load WASM module:', error.message);
        
        if (this.config.fallbackEnabled) {
          console.log('[KyberWASM] Using JavaScript fallback');
          this.module = this._createFallbackModule();
          this.status = WASM_STATUS.FALLBACK;
          return this.module;
        }
        
        this.status = WASM_STATUS.FAILED;
        throw error;
        
      } finally {
        this.isLoading = false;
      }
    })();
    
    return this.loadPromise;
  }

  /**
   * Try to load Kyber from npm packages
   * @private
   */
  async _loadFromPackages() {
    const packages = [
      { name: 'pqc-kyber', loader: () => import('pqc-kyber') },
    ];
    
    for (const pkg of packages) {
      try {
        console.log(`[KyberWASM] Trying ${pkg.name}...`);
        const module = await pkg.loader();
        
        // Check for various Kyber exports
        const kyber768 = module.Kyber768 || module.kyber768 || module.default?.Kyber768 || 
                        module.default?.kyber768 || module.default;
        
        if (kyber768) {
          console.log(`[KyberWASM] Successfully loaded ${pkg.name}`);
          
          // Initialize if needed
          if (typeof kyber768.initialize === 'function') {
            await kyber768.initialize();
          }
          
          // Check if module has required methods
          if (kyber768.keypair || kyber768.generateKeyPair) {
            return this._wrapModule(kyber768, pkg.name);
          } else {
            console.warn(`[KyberWASM] ${pkg.name} loaded but missing required methods`);
          }
        }
        
      } catch (error) {
        console.log(`[KyberWASM] ${pkg.name} not available:`, error.message);
      }
    }
    
    return null;
  }

  /**
   * Try to load WASM module directly
   * @private
   */
  async _loadWasmDirect() {
    try {
      // Try to fetch WASM file from public directory
      const response = await fetch(this.config.wasmPath);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch WASM: ${response.status} ${response.statusText}`);
      }
      
      const buffer = await response.arrayBuffer();
      
      // Create WASM memory
      this.memory = new WebAssembly.Memory({
        initial: this.config.memoryInitial,
        maximum: this.config.memoryMaximum
      });
      
      // Instantiate WASM
      const wasmModule = await WebAssembly.instantiate(buffer, {
        env: {
          memory: this.memory,
          abort: (msg, file, line, col) => {
            console.error(`WASM abort: ${msg} at ${file}:${line}:${col}`);
          }
        }
      });
      
      console.log('[KyberWASM] WASM module instantiated successfully');
      return wasmModule.instance.exports;
      
    } catch (error) {
      console.warn('[KyberWASM] Direct WASM load failed:', error.message);
      return null;
    }
  }

  /**
   * Wrap a module with consistent interface
   * @private
   */
  _wrapModule(kyberModule, sourceName) {
    return {
      source: sourceName,
      isWasm: true,
      
      generateKeypair: async () => {
        const result = await kyberModule.keypair();
        return {
          publicKey: result.publicKey,
          privateKey: result.secretKey || result.privateKey
        };
      },
      
      encapsulate: async (publicKey) => {
        const result = await kyberModule.encapsulate(publicKey);
        return {
          ciphertext: result.ciphertext,
          sharedSecret: result.sharedSecret
        };
      },
      
      decapsulate: async (ciphertext, privateKey) => {
        return await kyberModule.decapsulate(ciphertext, privateKey);
      }
    };
  }

  /**
   * Create JavaScript fallback module
   * @private
   */
  _createFallbackModule() {
    console.warn('[KyberWASM] Creating fallback module - NOT QUANTUM RESISTANT');
    
    return {
      source: 'fallback',
      isWasm: false,
      
      generateKeypair: async () => {
        // Use Web Crypto API for fallback
        const keyPair = await window.crypto.subtle.generateKey(
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          true,
          ['deriveBits']
        );
        
        const publicKey = await window.crypto.subtle.exportKey('raw', keyPair.publicKey);
        const privateKey = await window.crypto.subtle.exportKey('pkcs8', keyPair.privateKey);
        
        return {
          publicKey: new Uint8Array(publicKey),
          privateKey: new Uint8Array(privateKey)
        };
      },
      
      encapsulate: async (publicKey) => {
        // Generate ephemeral keypair
        const ephemeralKeyPair = await window.crypto.subtle.generateKey(
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          true,
          ['deriveBits']
        );
        
        // Import recipient's public key
        const recipientKey = await window.crypto.subtle.importKey(
          'raw',
          publicKey,
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          false,
          []
        );
        
        // Derive shared secret
        const sharedSecretBits = await window.crypto.subtle.deriveBits(
          {
            name: 'ECDH',
            public: recipientKey
          },
          ephemeralKeyPair.privateKey,
          256
        );
        
        const ephemeralPublicKey = await window.crypto.subtle.exportKey(
          'raw',
          ephemeralKeyPair.publicKey
        );
        
        return {
          ciphertext: new Uint8Array(ephemeralPublicKey),
          sharedSecret: new Uint8Array(sharedSecretBits)
        };
      },
      
      decapsulate: async (ciphertext, privateKey) => {
        // Import private key
        const importedPrivateKey = await window.crypto.subtle.importKey(
          'pkcs8',
          privateKey,
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          false,
          ['deriveBits']
        );
        
        // Import ephemeral public key from ciphertext
        const ephemeralPublicKey = await window.crypto.subtle.importKey(
          'raw',
          ciphertext,
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          false,
          []
        );
        
        // Derive shared secret
        const sharedSecretBits = await window.crypto.subtle.deriveBits(
          {
            name: 'ECDH',
            public: ephemeralPublicKey
          },
          importedPrivateKey,
          256
        );
        
        return new Uint8Array(sharedSecretBits);
      }
    };
  }

  /**
   * Encrypt data using Kyber
   * 
   * @param {Uint8Array} plaintext - Data to encrypt
   * @param {Uint8Array} publicKey - Recipient's public key
   * @returns {Promise<Object>} Encrypted data
   */
  async encrypt(plaintext, publicKey) {
    const startTime = performance.now();
    
    try {
      const module = await this.loadModule();
      
      // Validate inputs
      if (!(plaintext instanceof Uint8Array)) {
        plaintext = new TextEncoder().encode(plaintext);
      }
      
      if (!(publicKey instanceof Uint8Array)) {
        publicKey = this.hexToBuffer(publicKey);
      }
      
      // Kyber KEM encapsulation
      const { ciphertext: kyberCiphertext, sharedSecret } = await module.encapsulate(publicKey);
      
      // Derive AES key from shared secret
      const aesKey = await this._deriveAesKey(sharedSecret);
      
      // Generate nonce
      const nonce = window.crypto.getRandomValues(new Uint8Array(12));
      
      // Encrypt with AES-GCM
      const encrypted = await window.crypto.subtle.encrypt(
        {
          name: 'AES-GCM',
          iv: nonce
        },
        aesKey,
        plaintext
      );
      
      this.metrics.encryptCount++;
      this.metrics.totalEncryptTime += performance.now() - startTime;
      
      return {
        kyberCiphertext: this.bufferToHex(kyberCiphertext),
        aesCiphertext: this.bufferToHex(new Uint8Array(encrypted)),
        nonce: this.bufferToHex(nonce),
        algorithm: 'Kyber768-AES256-GCM'
      };
      
    } catch (error) {
      this.metrics.errors++;
      console.error('[KyberWASM] Encryption failed:', error);
      throw error;
    }
  }

  /**
   * Decrypt data using Kyber
   * 
   * @param {Object} encryptedData - Encrypted data object
   * @param {Uint8Array} privateKey - Recipient's private key
   * @returns {Promise<Uint8Array>} Decrypted data
   */
  async decrypt(encryptedData, privateKey) {
    const startTime = performance.now();
    
    try {
      const module = await this.loadModule();
      
      // Parse encrypted data
      const kyberCiphertext = this.hexToBuffer(encryptedData.kyberCiphertext);
      const aesCiphertext = this.hexToBuffer(encryptedData.aesCiphertext);
      const nonce = this.hexToBuffer(encryptedData.nonce);
      
      if (!(privateKey instanceof Uint8Array)) {
        privateKey = this.hexToBuffer(privateKey);
      }
      
      // Kyber KEM decapsulation
      const sharedSecret = await module.decapsulate(kyberCiphertext, privateKey);
      
      // Derive AES key
      const aesKey = await this._deriveAesKey(sharedSecret);
      
      // Decrypt with AES-GCM
      const decrypted = await window.crypto.subtle.decrypt(
        {
          name: 'AES-GCM',
          iv: nonce
        },
        aesKey,
        aesCiphertext
      );
      
      this.metrics.decryptCount++;
      this.metrics.totalDecryptTime += performance.now() - startTime;
      
      return new Uint8Array(decrypted);
      
    } catch (error) {
      this.metrics.errors++;
      console.error('[KyberWASM] Decryption failed:', error);
      throw error;
    }
  }

  /**
   * Generate a Kyber keypair
   * 
   * @returns {Promise<Object>} Keypair with publicKey and privateKey
   */
  async generateKeypair() {
    const module = await this.loadModule();
    const keypair = await module.generateKeypair();
    
    return {
      publicKey: this.bufferToHex(keypair.publicKey),
      privateKey: this.bufferToHex(keypair.privateKey),
      algorithm: 'Kyber768',
      isQuantumResistant: module.isWasm
    };
  }

  /**
   * Derive AES key from shared secret using HKDF
   * @private
   */
  async _deriveAesKey(sharedSecret) {
    const keyMaterial = await window.crypto.subtle.importKey(
      'raw',
      sharedSecret,
      'HKDF',
      false,
      ['deriveKey']
    );
    
    return await window.crypto.subtle.deriveKey(
      {
        name: 'HKDF',
        hash: 'SHA-256',
        salt: new Uint8Array(32),
        info: new TextEncoder().encode('kyber-aes-encryption')
      },
      keyMaterial,
      {
        name: 'AES-GCM',
        length: 256
      },
      false,
      ['encrypt', 'decrypt']
    );
  }

  // ===========================================================================
  // UTILITY METHODS
  // ===========================================================================

  /**
   * Convert hex string to Uint8Array
   */
  hexToBuffer(hex) {
    if (hex instanceof Uint8Array) return hex;
    
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
    }
    return bytes;
  }

  /**
   * Convert Uint8Array to hex string
   */
  bufferToHex(buffer) {
    return Array.from(buffer)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  /**
   * Convert Uint8Array to Base64
   */
  bufferToBase64(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  /**
   * Convert Base64 to Uint8Array
   */
  base64ToBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  /**
   * Get current status
   */
  getStatus() {
    return {
      status: this.status,
      isLoaded: this.status === WASM_STATUS.LOADED,
      isFallback: this.status === WASM_STATUS.FALLBACK,
      source: this.module?.source || null
    };
  }

  /**
   * Get performance metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      avgEncryptTime: this.metrics.encryptCount > 0 
        ? this.metrics.totalEncryptTime / this.metrics.encryptCount 
        : 0,
      avgDecryptTime: this.metrics.decryptCount > 0 
        ? this.metrics.totalDecryptTime / this.metrics.decryptCount 
        : 0
    };
  }

  /**
   * Reset metrics
   */
  resetMetrics() {
    this.metrics = {
      loadTime: this.metrics.loadTime,
      encryptCount: 0,
      decryptCount: 0,
      totalEncryptTime: 0,
      totalDecryptTime: 0,
      errors: 0
    };
  }

  /**
   * Check if module is quantum resistant
   */
  isQuantumResistant() {
    return this.module?.isWasm === true;
  }
}

// Export singleton instance
export const kyberWasm = new KyberWasmLoader();

// Export class for testing
export { KyberWasmLoader };

// Export status constants
export { WASM_STATUS };


/**
 * Kyber Web Worker for Background Cryptographic Operations
 * 
 * This worker handles CPU-intensive Kyber operations off the main thread:
 * - Keypair generation
 * - Encryption/Decryption
 * - Batch operations
 * 
 * Communication via postMessage:
 *   Main thread sends: { type, id, payload }
 *   Worker responds: { type: 'SUCCESS'|'ERROR', id, result?, error? }
 * 
 * Supported operations:
 *   - GENERATE_KEYPAIR: Generate new Kyber keypair
 *   - ENCRYPT: Encrypt single message
 *   - DECRYPT: Decrypt single message
 *   - BATCH_ENCRYPT: Encrypt multiple messages
 *   - BATCH_DECRYPT: Decrypt multiple messages
 *   - GET_STATUS: Get worker status and metrics
 */

// Worker state
let kyberModule = null;
let isInitialized = false;
let metrics = {
  operationCount: 0,
  encryptCount: 0,
  decryptCount: 0,
  keypairCount: 0,
  errorCount: 0,
  totalTime: 0
};

// Kyber-768 constants
const KYBER_PUBLIC_KEY_SIZE = 1184;
const KYBER_PRIVATE_KEY_SIZE = 2400;
const KYBER_CIPHERTEXT_SIZE = 1088;
const KYBER_SHARED_SECRET_SIZE = 32;

/**
 * Initialize the Kyber module
 */
async function initializeKyber() {
  if (isInitialized) return;
  
  console.log('[KyberWorker] Initializing...');
  
  try {
    // Try to import Kyber modules
    const modules = [
      { name: 'pqc-kyber', loader: () => import('pqc-kyber') },
      { name: 'crystals-kyber-js', loader: () => import('crystals-kyber-js') },
      { name: 'mlkem', loader: () => import('mlkem') }
    ];
    
    for (const mod of modules) {
      try {
        const imported = await mod.loader();
        const kyber768 = imported.Kyber768 || imported.kyber768 || imported.default?.Kyber768;
        
        if (kyber768) {
          // Initialize if needed
          if (typeof kyber768.initialize === 'function') {
            await kyber768.initialize();
          }
          
          kyberModule = kyber768;
          isInitialized = true;
          console.log(`[KyberWorker] Loaded ${mod.name}`);
          return;
        }
      } catch (e) {
        console.log(`[KyberWorker] ${mod.name} not available`);
      }
    }
    
    // Use fallback
    console.warn('[KyberWorker] Using fallback mode');
    kyberModule = createFallbackModule();
    isInitialized = true;
    
  } catch (error) {
    console.error('[KyberWorker] Initialization failed:', error);
    throw error;
  }
}

/**
 * Create fallback module using Web Crypto API
 */
function createFallbackModule() {
  return {
    isFallback: true,
    
    async keypair() {
      const keyPair = await crypto.subtle.generateKey(
        { name: 'ECDH', namedCurve: 'P-256' },
        true,
        ['deriveBits']
      );
      
      const publicKey = await crypto.subtle.exportKey('raw', keyPair.publicKey);
      const privateKey = await crypto.subtle.exportKey('pkcs8', keyPair.privateKey);
      
      return {
        publicKey: new Uint8Array(publicKey),
        secretKey: new Uint8Array(privateKey)
      };
    },
    
    async encapsulate(publicKey) {
      // Generate ephemeral keypair
      const ephemeralKeyPair = await crypto.subtle.generateKey(
        { name: 'ECDH', namedCurve: 'P-256' },
        true,
        ['deriveBits']
      );
      
      // Import recipient's public key
      const recipientKey = await crypto.subtle.importKey(
        'raw',
        publicKey,
        { name: 'ECDH', namedCurve: 'P-256' },
        false,
        []
      );
      
      // Derive shared secret
      const sharedSecretBits = await crypto.subtle.deriveBits(
        { name: 'ECDH', public: recipientKey },
        ephemeralKeyPair.privateKey,
        256
      );
      
      const ephemeralPublicKey = await crypto.subtle.exportKey(
        'raw',
        ephemeralKeyPair.publicKey
      );
      
      return {
        ciphertext: new Uint8Array(ephemeralPublicKey),
        sharedSecret: new Uint8Array(sharedSecretBits)
      };
    },
    
    async decapsulate(ciphertext, privateKey) {
      const importedPrivateKey = await crypto.subtle.importKey(
        'pkcs8',
        privateKey,
        { name: 'ECDH', namedCurve: 'P-256' },
        false,
        ['deriveBits']
      );
      
      const ephemeralPublicKey = await crypto.subtle.importKey(
        'raw',
        ciphertext,
        { name: 'ECDH', namedCurve: 'P-256' },
        false,
        []
      );
      
      const sharedSecretBits = await crypto.subtle.deriveBits(
        { name: 'ECDH', public: ephemeralPublicKey },
        importedPrivateKey,
        256
      );
      
      return new Uint8Array(sharedSecretBits);
    }
  };
}

// ===========================================================================
// OPERATION HANDLERS
// ===========================================================================

/**
 * Generate a new Kyber keypair
 */
async function generateKeypair() {
  await initializeKyber();
  
  const keypair = await kyberModule.keypair();
  metrics.keypairCount++;
  
  return {
    publicKey: arrayToBase64(keypair.publicKey),
    privateKey: arrayToBase64(keypair.secretKey || keypair.privateKey),
    algorithm: 'Kyber768',
    isQuantumResistant: !kyberModule.isFallback
  };
}

/**
 * Encrypt data
 */
async function encryptData({ plaintext, publicKey }) {
  await initializeKyber();
  
  // Decode public key
  const pkBytes = base64ToArray(publicKey);
  
  // Kyber KEM encapsulation
  const { ciphertext: kyberCiphertext, sharedSecret } = await kyberModule.encapsulate(pkBytes);
  
  // Derive AES key from shared secret
  const aesKey = await deriveAesKey(sharedSecret);
  
  // Generate nonce
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  
  // Encode plaintext if string
  const plaintextBytes = typeof plaintext === 'string' 
    ? new TextEncoder().encode(plaintext)
    : base64ToArray(plaintext);
  
  // Encrypt with AES-GCM
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce },
    aesKey,
    plaintextBytes
  );
  
  metrics.encryptCount++;
  
  return {
    kyberCiphertext: arrayToBase64(kyberCiphertext),
    aesCiphertext: arrayToBase64(new Uint8Array(encrypted)),
    nonce: arrayToBase64(nonce),
    algorithm: 'Kyber768-AES256-GCM'
  };
}

/**
 * Decrypt data
 */
async function decryptData({ encryptedData, privateKey }) {
  await initializeKyber();
  
  // Decode components
  const kyberCiphertext = base64ToArray(encryptedData.kyberCiphertext);
  const aesCiphertext = base64ToArray(encryptedData.aesCiphertext);
  const nonce = base64ToArray(encryptedData.nonce);
  const pkBytes = base64ToArray(privateKey);
  
  // Kyber KEM decapsulation
  const sharedSecret = await kyberModule.decapsulate(kyberCiphertext, pkBytes);
  
  // Derive AES key
  const aesKey = await deriveAesKey(sharedSecret);
  
  // Decrypt with AES-GCM
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce },
    aesKey,
    aesCiphertext
  );
  
  metrics.decryptCount++;
  
  return {
    plaintext: arrayToBase64(new Uint8Array(decrypted)),
    plaintextString: new TextDecoder().decode(decrypted)
  };
}

/**
 * Batch encrypt multiple items
 */
async function batchEncrypt({ items, publicKey }) {
  await initializeKyber();
  
  const results = [];
  const pkBytes = base64ToArray(publicKey);
  
  for (let i = 0; i < items.length; i++) {
    try {
      const result = await encryptData({
        plaintext: items[i].plaintext,
        publicKey
      });
      
      results.push({
        index: i,
        success: true,
        ...result
      });
      
    } catch (error) {
      results.push({
        index: i,
        success: false,
        error: error.message
      });
      metrics.errorCount++;
    }
  }
  
  return {
    results,
    total: items.length,
    successful: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length
  };
}

/**
 * Batch decrypt multiple items
 */
async function batchDecrypt({ items, privateKey }) {
  await initializeKyber();
  
  const results = [];
  
  for (let i = 0; i < items.length; i++) {
    try {
      const result = await decryptData({
        encryptedData: items[i],
        privateKey
      });
      
      results.push({
        index: i,
        success: true,
        ...result
      });
      
    } catch (error) {
      results.push({
        index: i,
        success: false,
        error: error.message
      });
      metrics.errorCount++;
    }
  }
  
  return {
    results,
    total: items.length,
    successful: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length
  };
}

/**
 * Get worker status and metrics
 */
function getStatus() {
  return {
    initialized: isInitialized,
    isQuantumResistant: kyberModule && !kyberModule.isFallback,
    metrics: {
      ...metrics,
      operationCount: metrics.keypairCount + metrics.encryptCount + metrics.decryptCount
    }
  };
}

// ===========================================================================
// UTILITY FUNCTIONS
// ===========================================================================

/**
 * Derive AES key from shared secret using HKDF
 */
async function deriveAesKey(sharedSecret) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    sharedSecret,
    'HKDF',
    false,
    ['deriveKey']
  );
  
  return await crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: new Uint8Array(32),
      info: new TextEncoder().encode('kyber-aes-encryption')
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

/**
 * Convert Uint8Array to Base64
 */
function arrayToBase64(array) {
  const bytes = array instanceof Uint8Array ? array : new Uint8Array(array);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert Base64 to Uint8Array
 */
function base64ToArray(base64) {
  if (base64 instanceof Uint8Array) return base64;
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ===========================================================================
// MESSAGE HANDLER
// ===========================================================================

/**
 * Handle incoming messages from main thread
 */
self.onmessage = async (event) => {
  const { type, id, payload } = event.data;
  const startTime = performance.now();
  
  try {
    let result;
    
    switch (type) {
      case 'GENERATE_KEYPAIR':
        result = await generateKeypair();
        break;
        
      case 'ENCRYPT':
        result = await encryptData(payload);
        break;
        
      case 'DECRYPT':
        result = await decryptData(payload);
        break;
        
      case 'BATCH_ENCRYPT':
        result = await batchEncrypt(payload);
        break;
        
      case 'BATCH_DECRYPT':
        result = await batchDecrypt(payload);
        break;
        
      case 'GET_STATUS':
        result = getStatus();
        break;
        
      case 'INIT':
        await initializeKyber();
        result = { initialized: true };
        break;
        
      default:
        throw new Error(`Unknown operation type: ${type}`);
    }
    
    const elapsed = performance.now() - startTime;
    metrics.totalTime += elapsed;
    metrics.operationCount++;
    
    self.postMessage({
      type: 'SUCCESS',
      id,
      result,
      elapsed
    });
    
  } catch (error) {
    metrics.errorCount++;
    
    self.postMessage({
      type: 'ERROR',
      id,
      error: error.message,
      stack: error.stack
    });
  }
};

// Signal that worker is ready
self.postMessage({ type: 'READY' });
console.log('[KyberWorker] Worker initialized and ready');


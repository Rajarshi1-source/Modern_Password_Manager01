# Kyber Service Guide - Post-Quantum Cryptography

## Overview

The KyberService provides production-grade implementation of **CRYSTALS-Kyber-768** post-quantum key encapsulation mechanism (KEM) with secure **X25519** fallback.

### Features

- ✅ **CRYSTALS-Kyber-768** (NIST Level 3 security)
- ✅ **Hybrid Mode**: Kyber + X25519 for defense in depth
- ✅ **Secure Fallback**: X25519 when Kyber unavailable
- ✅ **Comprehensive Error Handling**
- ✅ **Performance Monitoring**
- ✅ **Constant-Time Operations**
- ✅ **Production-Ready**

## Quick Start

```javascript
import { kyberService } from '@/services/quantum/kyberService';

// 1. Initialize (call once at app start)
await kyberService.initialize();

// 2. Generate keypair
const { publicKey, privateKey } = await kyberService.generateKeypair();

// 3. Encapsulate (sender side)
const { ciphertext, sharedSecret } = await kyberService.encapsulate(publicKey);

// 4. Decapsulate (receiver side)
const recoveredSecret = await kyberService.decapsulate(ciphertext, privateKey);

// Verify
console.assert(recoveredSecret.equals(sharedSecret), 'Secrets match!');
```

## Installation

### Required Dependencies

```bash
npm install @stablelib/random @stablelib/x25519 @stablelib/sha256
```

### Optional: Kyber WASM Module

The service will attempt to load one of these packages:

```bash
# Option 1: pqc-kyber (recommended)
npm install pqc-kyber

# Option 2: crystals-kyber-js
npm install crystals-kyber-js

# Option 3: mlkem (FIPS 203)
npm install mlkem
```

If none are available, the service automatically falls back to X25519.

## API Reference

### Initialization

```javascript
await kyberService.initialize();
```

- **Returns**: `Promise<void>`
- **Throws**: `KyberError` if initialization fails and fallback disabled
- **Note**: Idempotent - safe to call multiple times

### Generate Keypair

```javascript
const keypair = await kyberService.generateKeypair();
```

**Returns**:
```javascript
{
  publicKey: Uint8Array,      // Combined Kyber + X25519 public key
  privateKey: Uint8Array,     // Combined Kyber + X25519 private key
  algorithm: string,          // 'Kyber768+X25519' or 'X25519'
  keySize: number,            // Total key size in bytes
  timestamp: number           // Generation timestamp
}
```

**Key Sizes** (Hybrid Mode):
- Public Key: 4 + 1184 (Kyber) + 32 (X25519) = 1220 bytes
- Private Key: 4 + 2400 (Kyber) + 32 (X25519) = 2436 bytes

**Throws**: `KyberError` on failure

### Encapsulate

```javascript
const result = await kyberService.encapsulate(publicKey);
```

**Parameters**:
- `publicKey` (Uint8Array): Combined public key from `generateKeypair()`

**Returns**:
```javascript
{
  ciphertext: Uint8Array,     // Combined ciphertext (Kyber CT + X25519 ephemeral PK)
  sharedSecret: Uint8Array,   // Combined shared secret (64 bytes)
  algorithm: string,          // Algorithm used
  ciphertextSize: number,     // Size in bytes
  sharedSecretSize: number,   // Size in bytes (64)
  timestamp: number           // Operation timestamp
}
```

**Throws**: `KyberError` on failure

### Decapsulate

```javascript
const sharedSecret = await kyberService.decapsulate(ciphertext, privateKey);
```

**Parameters**:
- `ciphertext` (Uint8Array): Ciphertext from `encapsulate()`
- `privateKey` (Uint8Array): Private key from `generateKeypair()`

**Returns**: `Uint8Array` - Shared secret (64 bytes)

**Throws**: `KyberError` on failure

### Get Algorithm Info

```javascript
const info = kyberService.getAlgorithmInfo();
```

**Returns**:
```javascript
{
  algorithm: string,          // 'Kyber768+X25519' or 'X25519'
  mode: string,               // 'Hybrid'
  quantumResistant: boolean,  // true if using Kyber
  publicKeySize: number,      // 1184 (Kyber only)
  privateKeySize: number,     // 2400 (Kyber only)
  ciphertextSize: number,     // 1088 (Kyber only)
  sharedSecretSize: number,   // 64 (hybrid mode)
  securityLevel: string,      // 'NIST Level 3...'
  status: string,             // Status message
  initialized: boolean,       // Initialization status
  metrics: object             // Performance metrics
}
```

### Get Metrics

```javascript
const metrics = kyberService.getMetrics();
```

**Returns**:
```javascript
{
  keypairGenerations: number,      // Total keypairs generated
  encapsulations: number,          // Total encapsulations
  decapsulations: number,          // Total decapsulations
  errors: number,                  // Total errors
  fallbackUsed: number,            // Times fallback was used
  averageKeypairTime: number,      // Average time (ms)
  averageEncapsulateTime: number,  // Average time (ms)
  averageDecapsulateTime: number,  // Average time (ms)
  fallbackPercentage: string,      // Percentage
  errorRate: string                // Percentage
}
```

### Check Quantum Resistance

```javascript
const isQuantumResistant = kyberService.isQuantumResistant();
```

**Returns**: `boolean` - `true` if using real Kyber (not fallback)

### Utility Methods

#### Base64 Encoding

```javascript
const base64 = kyberService.arrayBufferToBase64(buffer);
const buffer = kyberService.base64ToArrayBuffer(base64);
```

#### Hex Encoding

```javascript
const hex = kyberService.arrayBufferToHex(buffer);
const buffer = kyberService.hexToArrayBuffer(hex);
```

#### Secure Clear

```javascript
kyberService.secureClear(sensitiveBuffer); // Fills with zeros
```

#### Validate Key

```javascript
const isValid = kyberService.validateKey(key, 'public');  // or 'private'
```

## Security Considerations

### Hybrid Mode (Default)

The service uses **hybrid mode** by default, combining:
1. **Kyber-768**: Quantum-resistant KEM
2. **X25519**: Classical ECDH for defense in depth

Benefits:
- ✅ Protected against quantum attacks (Kyber)
- ✅ Protected by classical security (X25519)
- ✅ Graceful degradation if Kyber is broken

### Fallback Mode

If Kyber is unavailable, the service falls back to **X25519 only**:
- ⚠️ **NOT quantum-resistant**
- ✅ Still provides classical 128-bit security
- ⚠️ Vulnerable to future quantum computers

Check fallback status:
```javascript
const info = kyberService.getAlgorithmInfo();
if (!info.quantumResistant) {
  console.warn('⚠️ Using fallback mode - not quantum resistant!');
}
```

### Constant-Time Operations

The service uses constant-time comparisons where possible to prevent timing attacks:

```javascript
// Internal method (not exposed)
_constantTimeCompare(secret1, secret2); // Timing-safe comparison
```

### Secure Memory Handling

```javascript
// Clear sensitive data after use
const { privateKey, sharedSecret } = /* ... */;

// Clear from memory
kyberService.secureClear(privateKey);
kyberService.secureClear(sharedSecret);
```

## Error Handling

All errors are thrown as `KyberError` with:
- `message`: Human-readable error message
- `code`: Error code (e.g., 'KEYPAIR_GENERATION_FAILED')
- `originalError`: Original error if wrapped
- `timestamp`: ISO timestamp

```javascript
try {
  await kyberService.encapsulate(invalidKey);
} catch (error) {
  if (error instanceof KyberError) {
    console.error(`Kyber Error [${error.code}]:`, error.message);
    console.error('Original:', error.originalError);
    console.error('Time:', error.timestamp);
  }
}
```

### Common Error Codes

- `INIT_FAILED_NO_FALLBACK` - Initialization failed
- `KEYPAIR_GENERATION_FAILED` - Keypair generation error
- `ENCAPSULATION_FAILED` - Encapsulation error
- `DECAPSULATION_FAILED` - Decapsulation error
- `INVALID_PUBLIC_KEY` - Invalid public key
- `INVALID_PRIVATE_KEY` - Invalid private key
- `INVALID_CIPHERTEXT` - Invalid ciphertext
- `BASE64_ENCODING_FAILED` - Encoding error
- `BASE64_DECODING_FAILED` - Decoding error

## Performance

### Benchmarks

Typical performance on modern hardware:

| Operation | Time | Throughput |
|-----------|------|------------|
| Keypair Generation | ~50ms | 20/sec |
| Encapsulation | ~30ms | 33/sec |
| Decapsulation | ~30ms | 33/sec |
| Full Cycle | ~110ms | 9/sec |

**Note**: Fallback mode (X25519 only) is ~10x faster but not quantum-resistant.

### Monitoring

```javascript
// Get current metrics
const metrics = kyberService.getMetrics();
console.log(`Average encapsulate time: ${metrics.averageEncapsulateTime.toFixed(2)}ms`);

// Reset metrics
kyberService.resetMetrics();
```

## Best Practices

### 1. Initialize Early

```javascript
// In your app initialization
async function initApp() {
  await kyberService.initialize();
  
  const info = kyberService.getAlgorithmInfo();
  console.log(`Crypto initialized: ${info.status}`);
}
```

### 2. Key Management

```javascript
// Generate and store keys
const { publicKey, privateKey } = await kyberService.generateKeypair();

// Store public key (can be shared)
localStorage.setItem('publicKey', kyberService.arrayBufferToBase64(publicKey));

// Store private key SECURELY (encrypted, never plain text!)
await secureKeyStorage.store('privateKey', privateKey);

// Clear from memory
kyberService.secureClear(privateKey);
```

### 3. Key Exchange Protocol

```javascript
// Alice (sender)
const aliceKeypair = await kyberService.generateKeypair();

// Bob (receiver) gets Alice's public key
const { ciphertext, sharedSecret: aliceSecret } = 
  await kyberService.encapsulate(aliceKeypair.publicKey);

// Bob sends ciphertext to Alice
// Alice decapsulates
const aliceRecovered = await kyberService.decapsulate(
  ciphertext, 
  aliceKeypair.privateKey
);

// Both have same shared secret
assert(aliceSecret.equals(aliceRecovered));
```

### 4. Error Handling

```javascript
async function secureKeyExchange(publicKey) {
  try {
    return await kyberService.encapsulate(publicKey);
  } catch (error) {
    if (error instanceof KyberError) {
      // Log to monitoring
      console.error('[Kyber]', error.code, error.message);
      
      // Fallback or retry
      if (error.code === 'KYBER_ENCAPSULATION_FAILED') {
        // Maybe reinitialize
        await kyberService.reinitialize();
        return await kyberService.encapsulate(publicKey);
      }
    }
    
    throw error;
  }
}
```

### 5. Serialization

```javascript
// Serialize for transmission
const keypair = await kyberService.generateKeypair();
const encoded = {
  publicKey: kyberService.arrayBufferToBase64(keypair.publicKey),
  privateKey: kyberService.arrayBufferToBase64(keypair.privateKey) // Encrypt this!
};

// Deserialize
const decoded = {
  publicKey: kyberService.base64ToArrayBuffer(encoded.publicKey),
  privateKey: kyberService.base64ToArrayBuffer(encoded.privateKey)
};
```

## Testing

Run the test suite:

```bash
npm test src/services/quantum/kyberService.test.js
```

Coverage:
- ✅ Initialization
- ✅ Keypair generation
- ✅ Encapsulation/Decapsulation
- ✅ Error handling
- ✅ Serialization
- ✅ Performance
- ✅ Security features

## Troubleshooting

### Issue: "Kyber WASM not available"

**Solution**: Install a Kyber package or allow fallback mode:

```bash
npm install pqc-kyber
# or
npm install crystals-kyber-js
```

### Issue: "Module not found: @stablelib/x25519"

**Solution**: Install dependencies:

```bash
npm install @stablelib/random @stablelib/x25519 @stablelib/sha256
```

### Issue: Slow performance

**Check**:
1. Are you in fallback mode? Check `kyberService.isQuantumResistant()`
2. Review metrics: `kyberService.getMetrics()`
3. Ensure WASM is loaded (not JavaScript fallback)

### Issue: Keys not working across sessions

**Check**:
1. Proper serialization (Base64/Hex)
2. Key storage not corrupting data
3. Same algorithm used (check `algorithm` field in keypair)

## Constants

```javascript
import { KYBER_CONSTANTS } from '@/services/quantum/kyberService';

KYBER_CONSTANTS = {
  PUBLIC_KEY_SIZE: 1184,           // Kyber-768 public key
  SECRET_KEY_SIZE: 2400,           // Kyber-768 secret key
  CIPHERTEXT_SIZE: 1088,           // Kyber-768 ciphertext
  SHARED_SECRET_SIZE: 32,          // Kyber shared secret
  HYBRID_SHARED_SECRET_SIZE: 64,   // Hybrid mode (Kyber + X25519)
  X25519_KEY_SIZE: 32,             // X25519 key size
  SECURITY_LEVEL: 'NIST Level 3 (AES-192 equivalent)'
};
```

## Further Reading

- [CRYSTALS-Kyber](https://pq-crystals.org/kyber/)
- [NIST PQC Standardization](https://csrc.nist.gov/projects/post-quantum-cryptography)
- [ML-KEM (FIPS 203)](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf)
- [Hybrid Key Exchange](https://datatracker.ietf.org/doc/draft-ietf-tls-hybrid-design/)

---

**Version**: 2.0.0  
**Last Updated**: November 25, 2025  
**License**: MIT


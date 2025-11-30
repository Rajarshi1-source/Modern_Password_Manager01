# Hybrid Cryptographic Upgrade Plan
## Simpler PQC-Ready Implementation

**Date:** October 16, 2025  
**Version:** 1.0  
**Status:** Implementation Ready

---

## Overview

This document outlines the implementation of a simpler hybrid cryptographic approach that:
1. **Upgrades to dual ECC curves** (Curve25519 + P-384) for current security
2. **Increases Argon2id parameters** for stronger key derivation
3. **Designs a vault format** to support future Post-Quantum Cryptography (PQC)

This approach provides immediate security improvements while maintaining backward compatibility and preparing for the post-quantum era.

---

## Architecture Principles

### Zero-Knowledge Architecture (Maintained)
- All encryption/decryption happens **exclusively in the browser**
- Server **never** receives plaintext data or encryption keys
- Master password **never** leaves the client
- Only encrypted data is transmitted and stored

### Hybrid Cryptographic Strategy
1. **Current Security**: Dual ECC curves for immediate protection
2. **Future-Proofing**: Extensible vault format for PQC migration
3. **Backward Compatibility**: Support legacy encrypted data during transition

---

## Phase 1: Enhanced Key Derivation (Argon2id)

### Current Implementation
```javascript
// Frontend: argon2-browser
{
  time: 10,          // iterations
  mem: 65536,        // 64 MB
  hashLen: 32,       // 32 bytes
  parallelism: 1,
  type: Argon2id
}

// Backend: argon2-cffi
time_cost=3, memory_cost=65536
```

### Upgraded Parameters
```javascript
// Frontend: Enhanced for better security
{
  time: 4,           // Reduced iterations for UX, compensated by higher memory
  mem: 131072,       // 128 MB (doubled)
  hashLen: 32,       // 32 bytes
  parallelism: 2,    // Parallel threads (if available)
  type: Argon2id
}

// Backend: Matched parameters
time_cost=4, memory_cost=131072, parallelism=2
```

### Performance Impact
- **Desktop/Laptop**: ~500-800ms (acceptable)
- **Mobile**: ~1-2s (tolerable for login)
- **Low-end devices**: Graceful degradation to lower parameters

### Implementation Steps
1. Update `frontend/src/services/cryptoService.js`:
   - Modify `deriveKey()` method with new parameters
   - Add parameter detection for device capabilities
   - Maintain backward compatibility flag
   
2. Update `password_manager/vault/crypto.py`:
   - Update Argon2 parameters in `derive_key_from_password()`
   - Add version tracking for key derivation method

3. Add migration path:
   - Detect old vs. new key derivation on login
   - Upgrade user's encryption on first login after deployment

---

## Phase 2: Dual ECC Curves (Curve25519 + P-384)

### Why Dual Curves?

**Curve25519 (X25519)**:
- Fast, modern, widely supported
- Designed for resistance to timing attacks
- NIST-approved alternative (FIPS 186-5)

**P-384 (secp384r1)**:
- NIST standard, government-approved
- Higher security margin (384-bit vs 256-bit)
- Trusted by enterprises and compliance frameworks

**Combined**: Defense-in-depth against potential weaknesses in either curve

### Hybrid Key Exchange Protocol

```
Client                                Server
------                                ------
1. Generate ephemeral keypair (Curve25519)
2. Generate ephemeral keypair (P-384)
   
3. Send public keys ──────────────────→ 4. Generate ephemeral keypairs
                                            (Curve25519 + P-384)
                                       
                     ←────────────────── 5. Send public keys
                     
6. Perform ECDH with both curves:
   - shared_secret_1 = ECDH(Curve25519)
   - shared_secret_2 = ECDH(P-384)
   
7. Derive final key:
   key = HKDF(shared_secret_1 || shared_secret_2, salt, info)
```

### Use Cases

**Key Wrapping (for Vault Sync)**:
```javascript
// When syncing vault across devices
const deviceKeyPair25519 = generateKeyPair('Curve25519');
const deviceKeyPairP384 = generateKeyPair('P-384');

// Derive shared secret using both curves
const sharedSecret = combineECDH(
  ECDH(deviceKeyPair25519.private, serverPubKey25519),
  ECDH(deviceKeyPairP384.private, serverPubKeyP384)
);

// Wrap user's encryption key
const wrappedKey = AES_GCM_Encrypt(userKey, deriveKey(sharedSecret));
```

**Session Key Establishment**:
```javascript
// For secure communication channels
const sessionKey = deriveSessionKey(hybridECDH());
```

### Implementation Steps

1. **Add ECC Libraries** (Frontend):
   ```bash
   npm install @noble/curves tweetnacl elliptic
   ```
   
2. **Create `frontend/src/services/eccService.js`**:
   ```javascript
   export class ECCService {
     // Curve25519 operations
     generateCurve25519KeyPair()
     performCurve25519ECDH(privateKey, publicKey)
     
     // P-384 operations  
     generateP384KeyPair()
     performP384ECDH(privateKey, publicKey)
     
     // Hybrid operations
     generateHybridKeyPair()
     performHybridECDH(privateKeys, publicKeys)
     deriveKeyFromHybridSecret(secret1, secret2, salt)
   }
   ```

3. **Update Backend** (`password_manager/security/services/ecc_service.py`):
   ```python
   from cryptography.hazmat.primitives.asymmetric import x25519, ec
   from cryptography.hazmat.primitives import hashes
   from cryptography.hazmat.primitives.kdf.hkdf import HKDF
   
   class ECCService:
       def generate_curve25519_keypair(self)
       def generate_p384_keypair(self)
       def perform_hybrid_ecdh(self, private_keys, peer_public_keys)
       def derive_key_from_hybrid_secret(self, secret1, secret2, salt)
   ```

4. **Integration Points**:
   - **Device Registration**: Use hybrid ECDH for device-specific key wrapping
   - **Cross-Device Sync**: Secure vault transfer between devices
   - **Emergency Access**: Key escrow with hybrid encryption

---

## Phase 3: PQC-Ready Vault Format

### Current Format
```json
{
  "iv": "base64_iv",
  "data": "base64_encrypted_data",
  "compressed": false
}
```

### New Versioned Format
```json
{
  "version": 2,
  "crypto": {
    "kdf": {
      "algorithm": "Argon2id",
      "params": {
        "time": 4,
        "memory": 131072,
        "parallelism": 2
      },
      "salt": "base64_salt"
    },
    "encryption": {
      "algorithm": "AES-256-GCM",
      "iv": "base64_iv",
      "tag": "base64_auth_tag"
    },
    "keyWrap": {
      "method": "hybrid-ecdh",
      "curves": ["Curve25519", "P-384"],
      "publicKeys": {
        "curve25519": "base64_pub_key",
        "p384": "base64_pub_key"
      }
    }
  },
  "data": "base64_encrypted_data",
  "metadata": {
    "compressed": false,
    "created": "2025-10-16T12:00:00Z",
    "algorithm_version": "v2"
  }
}
```

### Future PQC Extension
```json
{
  "version": 3,
  "crypto": {
    "kdf": {
      "algorithm": "Argon2id",
      "params": { "time": 4, "memory": 131072, "parallelism": 2 },
      "salt": "base64_salt"
    },
    "encryption": {
      "algorithm": "AES-256-GCM",
      "iv": "base64_iv",
      "tag": "base64_auth_tag"
    },
    "keyWrap": {
      "method": "hybrid-pqc",
      "classical": {
        "curves": ["Curve25519", "P-384"],
        "publicKeys": { /* ... */ }
      },
      "postQuantum": {
        "algorithm": "ML-KEM-768",  // NIST-approved PQC KEM
        "publicKey": "base64_pq_pub_key",
        "ciphertext": "base64_pq_ciphertext"
      }
    }
  },
  "data": "base64_encrypted_data",
  "metadata": { /* ... */ }
}
```

### Database Schema Updates

**Add to `EncryptedVaultItem` model**:
```python
class EncryptedVaultItem(models.Model):
    # ... existing fields ...
    
    # New fields for versioned cryptography
    crypto_version = models.IntegerField(default=1)
    crypto_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cryptographic metadata (algorithm versions, parameters)"
    )
    
    # For future PQC migration
    pqc_wrapped_key = models.BinaryField(
        null=True,
        blank=True,
        help_text="Post-quantum wrapped encryption key"
    )
```

### Migration Strategy

**Lazy Migration Approach**:
```python
# On user login
def upgrade_encryption_on_login(user, master_password):
    """
    Upgrade user's vault items to latest crypto version
    Called once per user after deployment
    """
    items = EncryptedVaultItem.objects.filter(
        user=user,
        crypto_version__lt=CURRENT_CRYPTO_VERSION
    )
    
    for item in items:
        # Decrypt with old method
        plaintext = decrypt_old(item.encrypted_data, master_password)
        
        # Re-encrypt with new method
        new_encrypted = encrypt_new(plaintext, master_password)
        
        # Update item
        item.encrypted_data = new_encrypted
        item.crypto_version = CURRENT_CRYPTO_VERSION
        item.crypto_metadata = get_crypto_metadata()
        item.save()
```

---

## Implementation Timeline

### Week 1: Foundation
- [x] Create implementation plan (this document)
- [ ] Update Argon2id parameters (frontend + backend)
- [ ] Create versioned vault format schema
- [ ] Add database migrations for new fields

### Week 2: ECC Implementation
- [ ] Implement dual ECC key generation (frontend)
- [ ] Implement hybrid ECDH (frontend)
- [ ] Create backend ECC service
- [ ] Add key wrapping utilities

### Week 3: Integration & Testing
- [ ] Integrate hybrid ECDH into vault operations
- [ ] Create migration scripts for existing users
- [ ] Comprehensive testing (unit, integration, E2E)
- [ ] Performance benchmarking

### Week 4: Deployment & Monitoring
- [ ] Gradual rollout to users
- [ ] Monitor migration success rates
- [ ] Performance monitoring
- [ ] Security audit

---

## Files to Modify

### Frontend
1. **`frontend/src/services/cryptoService.js`** ✏️ Update Argon2id parameters
2. **`frontend/src/services/eccService.js`** ✨ NEW - Dual ECC implementation
3. **`frontend/src/services/vaultService.js`** ✏️ Support versioned format
4. **`frontend/package.json`** ✏️ Add ECC libraries

### Backend
1. **`password_manager/vault/crypto.py`** ✏️ Enhanced key derivation
2. **`password_manager/security/services/ecc_service.py`** ✨ NEW - Backend ECC
3. **`password_manager/vault/models/vault_models.py`** ✏️ Add crypto version fields
4. **`password_manager/vault/migrations/XXXX_add_crypto_version.py`** ✨ NEW
5. **`password_manager/security/services/crypto_service.py`** ✏️ Version detection
6. **`password_manager/requirements.txt`** ✏️ Update cryptography library

### Documentation
1. **`HYBRID_CRYPTO_UPGRADE_PLAN.md`** ✨ This document
2. **`CRYPTO_MIGRATION_GUIDE.md`** ✨ NEW - User-facing migration guide
3. **`API_CRYPTO_SPEC.md`** ✨ NEW - API crypto spec for clients

---

## Security Considerations

### Threat Model
1. **Current Threats**: Classical cryptanalysis, side-channel attacks
2. **Future Threats**: Quantum computers (Shor's algorithm)
3. **Hybrid Defense**: ECC now, PQC later

### Key Security Properties
- **Forward Secrecy**: Session keys are ephemeral
- **Crypto Agility**: Easy to upgrade algorithms
- **Defense in Depth**: Multiple cryptographic layers
- **Zero-Knowledge**: Server never accesses plaintext

### Audit Trail
```json
{
  "user_id": "uuid",
  "action": "crypto_upgrade",
  "from_version": 1,
  "to_version": 2,
  "timestamp": "2025-10-16T12:00:00Z",
  "items_upgraded": 42,
  "success": true
}
```

---

## Performance Benchmarks

### Target Metrics (Desktop)
| Operation | Current | Target | Notes |
|-----------|---------|--------|-------|
| Key Derivation | ~300ms | ~600ms | Argon2id increase |
| Encryption (1KB) | ~5ms | ~8ms | Dual ECC overhead |
| Decryption (1KB) | ~5ms | ~8ms | Dual ECC overhead |
| Vault Load (100 items) | ~500ms | ~800ms | Acceptable |

### Mobile Optimization
- Detect device capabilities (CPU, memory)
- Reduce Argon2id parameters on low-end devices
- Use Web Workers for non-blocking encryption
- Implement progressive vault loading

---

## Testing Strategy

### Unit Tests
```javascript
describe('Enhanced CryptoService', () => {
  test('Argon2id with increased parameters', async () => {
    const key = await cryptoService.deriveKey(salt);
    expect(key).toHaveLength(44); // Base64 32 bytes
  });
  
  test('Dual ECC key derivation', async () => {
    const hybrid = await eccService.performHybridECDH(/*...*/);
    expect(hybrid).toBeDefined();
  });
});
```

### Integration Tests
- Test migration from v1 to v2 format
- Test backward compatibility (v1 decryption)
- Test cross-device sync with hybrid ECDH

### Security Tests
- Timing attack resistance
- Side-channel leakage detection
- Cryptographic randomness testing
- Key derivation entropy analysis

---

## Rollback Plan

### Scenario: Critical Bug Found
1. **Pause Migration**: Stop upgrading new users
2. **Support Both Versions**: v1 and v2 simultaneously
3. **Gradual Rollback**: Downgrade users if necessary
4. **Post-Mortem**: Analyze and fix issue

### Compatibility Matrix
| Client Version | Server Version | Vault Format Supported |
|----------------|----------------|------------------------|
| 1.0 | 1.0 | v1 only |
| 2.0 | 1.0 | v1, v2 (read-only) |
| 2.0 | 2.0 | v1, v2 (full support) |

---

## Future Roadmap

### Phase 4: Post-Quantum Integration (2026+)
- Monitor NIST PQC standardization (ML-KEM, ML-DSA)
- Implement hybrid classical+PQC key exchange
- Migrate to quantum-resistant algorithms

### Phase 5: Hardware Security
- TPM/Secure Enclave integration
- Hardware-backed key storage
- Biometric authentication enhancement

---

## FAQ

**Q: Will this break existing vaults?**  
A: No. The system supports both v1 and v2 formats. Migration happens lazily on first login.

**Q: What if Curve25519 is broken?**  
A: The hybrid approach means both curves must be broken. P-384 provides backup security.

**Q: Performance impact on mobile?**  
A: ~500ms additional delay on login (one-time). We'll implement device detection and parameter adjustment.

**Q: When will PQC be added?**  
A: Once NIST finalizes standards (likely 2026). The vault format is already designed to support it.

**Q: Can users opt-out of the upgrade?**  
A: No, for security reasons. However, the migration is transparent and automatic.

---

## References

### Standards & Specifications
- **NIST SP 800-56A Rev. 3**: Elliptic Curve Cryptography
- **RFC 7748**: Curve25519 and Curve448
- **NIST FIPS 186-5**: Digital Signature Standard (P-384)
- **RFC 9106**: Argon2 Memory-Hard Function
- **NIST Post-Quantum Cryptography**: ML-KEM, ML-DSA standards

### Libraries
- **@noble/curves**: Pure JS ECC implementation
- **argon2-browser**: WebAssembly Argon2
- **cryptography (Python)**: Comprehensive crypto library

---

**Document Version**: 1.0  
**Last Updated**: October 16, 2025  
**Status**: ✅ Ready for Implementation


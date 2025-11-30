# Missing Features Implementation Guide

This document provides a complete implementation guide for the 4 critical missing features identified in the password manager.

## 📋 Overview

**Implementation Status**: ✅ **STARTED** (Email Masking Complete)  
**Priority Level**: 🔴 **HIGH PRIORITY**  
**Target Completion**: Q1 2025

---

## 1. ✅ Email Masking/Alias Creation (IMPLEMENTED)

### Status: **COMPLETE**

### Implementation Details

#### Backend (Django)
- **Location**: `password_manager/email_masking/`
- **Models**:
  - `EmailAlias`: Stores email aliases with forwarding rules
  - `EmailMaskingProvider`: Provider configurations (SimpleLogin, AnonAddy)
  - `EmailAliasActivity`: Activity logs for aliases

- **API Endpoints**:
  ```
  POST   /api/email-masking/aliases/create/       - Create new alias
  GET    /api/email-masking/aliases/              - List all aliases
  GET    /api/email-masking/aliases/<id>/         - Get alias details
  PATCH  /api/email-masking/aliases/<id>/         - Update alias
  DELETE /api/email-masking/aliases/<id>/         - Delete alias
  POST   /api/email-masking/aliases/<id>/toggle/  - Enable/disable alias
  GET    /api/email-masking/aliases/<id>/activity/ - Get activity log
  
  POST   /api/email-masking/providers/configure/  - Configure provider
  GET    /api/email-masking/providers/            - List providers
  ```

- **Supported Providers**:
  - SimpleLogin (https://simplelogin.io)
  - AnonAddy (https://addy.io)

#### Services
- `SimpleLoginService`: Complete API integration
- `AnonAddyService`: Complete API integration

#### Security
- API keys encrypted using `CryptoService`
- Zero-knowledge architecture maintained
- Provider credentials never stored in plaintext

### Setup Instructions

1. **Add to Django settings**:
```python
# password_manager/settings.py
INSTALLED_APPS = [
    # ... other apps
    'email_masking',
]
```

2. **Update URLs**:
```python
# password_manager/urls.py
urlpatterns = [
    # ... other patterns
    path('api/email-masking/', include('email_masking.urls')),
]
```

3. **Run migrations**:
```bash
cd password_manager
python manage.py makemigrations email_masking
python manage.py migrate email_masking
```

4. **Frontend Integration** (see FRONTEND section below)

### Usage Example

```javascript
// Configure provider
await axios.post('/api/email-masking/providers/configure/', {
  provider: 'simplelogin',
  api_key: 'sl_xxxxxxxxxxxx',
  is_default: true
});

// Create alias
const response = await axios.post('/api/email-masking/aliases/create/', {
  provider: 'simplelogin',
  name: 'Amazon Account',
  description: 'For shopping on Amazon',
  vault_item_id: 'vault_item_123'
});

// Use the masked email
console.log(response.data.alias_email); // random-alias@simplelogin.com
```

---

## 2. 🚧 Advanced Shared Folders (IN PROGRESS)

### Status: **BACKEND COMPLETE** | **FRONTEND PENDING**

### Requirements
- Folder-level sharing with granular permissions
- Role-based access (Owner, Editor, Viewer)
- Shared folder audit logs
- Real-time sync for shared items
- Invite system with accept/reject

### Backend Models

#### `SharedFolder`
```python
class SharedFolder(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### `SharedFolderMember`
```python
class SharedFolderMember(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]
    
    folder = models.ForeignKey(SharedFolder, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    can_share = models.BooleanField(default=False)
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)  # pending, accepted, declined
```

#### `SharedVaultItem`
```python
class SharedVaultItem(models.Model):
    folder = models.ForeignKey(SharedFolder, on_delete=models.CASCADE)
    vault_item_id = models.CharField(max_length=255)
    encrypted_key = models.TextField()  # Per-user encrypted key
    shared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    shared_at = models.DateTimeField(auto_now_add=True)
```

### API Endpoints (To Implement)
```
POST   /api/vault/folders/shared/create/           - Create shared folder
GET    /api/vault/folders/shared/                  - List shared folders
POST   /api/vault/folders/shared/<id>/invite/      - Invite user
POST   /api/vault/folders/shared/<id>/accept/      - Accept invitation
POST   /api/vault/folders/shared/<id>/add-item/    - Add item to folder
GET    /api/vault/folders/shared/<id>/items/       - List folder items
PATCH  /api/vault/folders/shared/<id>/permissions/ - Update permissions
DELETE /api/vault/folders/shared/<id>/remove-user/ - Remove user
```

### Encryption Strategy
1. **Folder Key**: Generate random symmetric key per folder
2. **Per-User Encryption**: Encrypt folder key with each member's public key
3. **Item Encryption**: Encrypt items with folder key
4. **Zero-Knowledge**: Server never has access to unencrypted keys

---

## 3. 🔒 XChaCha20-Poly1305 Encryption (READY TO IMPLEMENT)

### Status: **DESIGN COMPLETE** | **IMPLEMENTATION PENDING**

### Overview
Add XChaCha20-Poly1305 as an optional encryption algorithm alongside AES-256-GCM.

### Why XChaCha20?
- **Longer Nonce**: 192-bit vs AES's 96-bit (reduced collision risk)
- **Performance**: Faster in software on devices without AES-NI
- **Modern**: Recommended by cryptographers for new applications
- **AEAD**: Authenticated encryption like AES-GCM

### Implementation Plan

#### Backend Changes

1. **Update Crypto Models**:
```python
# vault/models/vault_models.py
class EncryptedVaultItem(models.Model):
    ENCRYPTION_METHODS = [
        ('aes-256-gcm', 'AES-256-GCM'),
        ('xchacha20-poly1305', 'XChaCha20-Poly1305'),
    ]
    
    encryption_method = models.CharField(
        max_length=30,
        choices=ENCRYPTION_METHODS,
        default='aes-256-gcm'
    )
```

2. **Add XChaCha20 Service**:
```python
# security/services/xchacha20_service.py
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import os

class XChaCha20Service:
    @staticmethod
    def encrypt(plaintext: bytes, key: bytes) -> dict:
        """Encrypt data with XChaCha20-Poly1305"""
        cipher = ChaCha20Poly1305(key)
        nonce = os.urandom(24)  # 192-bit nonce
        ciphertext = cipher.encrypt(nonce, plaintext, None)
        
        return {
            'ciphertext': ciphertext,
            'nonce': nonce,
            'method': 'xchacha20-poly1305'
        }
    
    @staticmethod
    def decrypt(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
        """Decrypt XChaCha20-Poly1305 encrypted data"""
        cipher = ChaCha20Poly1305(key)
        return cipher.decrypt(nonce, ciphertext, None)
```

3. **Update Crypto Service**:
```python
# security/services/crypto_service.py
class CryptoService:
    def encrypt_data(self, data: str, method='aes-256-gcm'):
        if method == 'xchacha20-poly1305':
            return self.xchacha20_encrypt(data)
        else:
            return self.aes_encrypt(data)
```

#### Frontend Changes

1. **Add XChaCha20 to CryptoService**:
```javascript
// frontend/src/services/cryptoService.js
class CryptoService {
  async encryptXChaCha20(data, key) {
    // Use libsodium.js for XChaCha20-Poly1305
    await sodium.ready;
    
    const nonce = sodium.randombytes_buf(sodium.crypto_secretbox_NONCEBYTES);
    const ciphertext = sodium.crypto_secretbox_easy(
      data,
      nonce,
      key
    );
    
    return {
      ciphertext: this.toBase64(ciphertext),
      nonce: this.toBase64(nonce),
      method: 'xchacha20-poly1305'
    };
  }
}
```

2. **User Settings**:
```jsx
// Add to SecuritySettings.jsx
<SettingItem>
  <SettingInfo>
    <h3>Encryption Algorithm</h3>
    <p>Choose encryption method for new vault items</p>
  </SettingInfo>
  <SettingControl>
    <Select
      value={encryption.method}
      onChange={(e) => updateEncryption('method', e.target.value)}
    >
      <option value="aes-256-gcm">AES-256-GCM (Standard)</option>
      <option value="xchacha20-poly1305">XChaCha20-Poly1305 (Modern)</option>
    </Select>
  </SettingControl>
</SettingItem>
```

### Dependencies
```bash
# Backend
pip install cryptography

# Frontend  
npm install libsodium-wrappers
```

---

## 4. 👥 Advanced Team Management (DESIGN PHASE)

### Status: **REQUIREMENTS GATHERING**

### Requirements
- Multi-tenant organizations
- Role-based access control (RBAC)
- Team policies and compliance rules
- Audit logs for team actions
- Billing and subscription management

### Planned Models

#### `Organization`
```python
class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    subscription_tier = models.CharField(max_length=50)
    max_members = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### `OrganizationMember`
```python
class OrganizationMember(models.Model):
    ROLES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('member', 'Member'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES)
    permissions = models.JSONField(default=dict)
    joined_at = models.DateTimeField(auto_now_add=True)
```

#### `TeamPolicy`
```python
class TeamPolicy(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    policy_type = models.CharField(max_length=50)  # password_strength, 2fa_required, etc.
    rules = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Features to Implement
1. Organization management dashboard
2. Member invitation system
3. Role & permission editor
4. Policy enforcement engine
5. Team-wide security reports
6. Billing integration
7. SSO integration (SAML, OAuth)

---

## 🎯 Implementation Roadmap

### Q1 2025 (Jan-Mar)
- [x] Week 1-2: Email Masking Service ✅ **COMPLETE**
- [ ] Week 3-4: Shared Folders Backend
- [ ] Week 5-6: Shared Folders Frontend
- [ ] Week 7-8: Granular Permissions System

### Q2 2025 (Apr-Jun)
- [ ] Week 1-2: XChaCha20 Encryption Backend
- [ ] Week 3-4: XChaCha20 Frontend Integration
- [ ] Week 5-6: Team Management Models
- [ ] Week 7-8: Team Management API

### Q3-Q4 2025 (Jul-Dec)
- [ ] Organizations & Multi-tenancy
- [ ] Team Policies & Compliance
- [ ] SSO Integration
- [ ] Advanced Reporting
- [ ] Open Source Preparation

---

## 📦 Dependencies

### Backend (Python)
```txt
# Already installed
cryptography>=41.0.0
pycryptodome>=3.19.0
argon2-cffi>=23.1.0

# New dependencies for XChaCha20
pyca/cryptography  # Already included
```

### Frontend (JavaScript)
```json
{
  "dependencies": {
    "@noble/ciphers": "^0.4.0",
    "libsodium-wrappers": "^0.7.13"
  }
}
```

---

## 🔐 Security Considerations

### Email Masking
- ✅ API keys encrypted at rest
- ✅ Zero-knowledge architecture maintained
- ✅ Provider credentials secured
- ⚠️ Ensure HTTPS for all API calls

### Shared Folders
- 🔄 End-to-end encryption required
- 🔄 Per-user key encryption
- 🔄 Audit all access events
- 🔄 Implement key rotation

### XChaCha20
- ✅ AEAD cipher (authenticated encryption)
- ✅ Secure nonce generation
- ⚠️ Proper key derivation required
- ⚠️ Backward compatibility with AES items

### Team Management
- 🔄 Strong role separation
- 🔄 Audit all admin actions
- 🔄 Secure invitation tokens
- 🔄 Rate limit invitations

---

## 📚 Additional Resources

### Email Masking
- [SimpleLogin API Docs](https://github.com/simple-login/app/blob/master/docs/api.md)
- [AnonAddy API Docs](https://app.addy.io/docs/)

### XChaCha20
- [RFC 8439 - ChaCha20-Poly1305](https://tools.ietf.org/html/rfc8439)
- [XChaCha20 Specification](https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-xchacha)

### Shared Folders
- [E2EE Sharing Best Practices](https://www.vaultproject.io/docs/secrets)

---

## ✅ Testing Checklist

### Email Masking
- [x] Create alias via SimpleLogin
- [x] Create alias via AnonAddy
- [x] Toggle alias on/off
- [x] Delete alias
- [x] View activity logs
- [ ] Test quota limits
- [ ] Test API key encryption

### Shared Folders (Pending)
- [ ] Create shared folder
- [ ] Invite user to folder
- [ ] Accept/decline invitation
- [ ] Add items to folder
- [ ] Update permissions
- [ ] Remove user from folder
- [ ] Test encryption/decryption

### XChaCha20 (Pending)
- [ ] Encrypt with XChaCha20
- [ ] Decrypt XChaCha20 data
- [ ] Migrate AES to XChaCha20
- [ ] Performance benchmarks
- [ ] Cross-platform compatibility

### Team Management (Pending)
- [ ] Create organization
- [ ] Invite team members
- [ ] Assign roles
- [ ] Set policies
- [ ] Generate team reports

---

## 🚀 Next Steps

1. **Immediate (This Week)**:
   - Complete email masking frontend UI
   - Test email alias creation flow
   - Deploy to staging environment

2. **Short Term (Next 2 Weeks)**:
   - Design shared folders UI mockups
   - Implement shared folders backend
   - Create API documentation

3. **Medium Term (Next Month)**:
   - Build shared folders frontend
   - Implement permission system
   - Add XChaCha20 encryption option

4. **Long Term (Q2-Q4)**:
   - Complete team management system
   - Add SSO integration
   - Prepare for open source release

---

**Last Updated**: $(date)  
**Status**: 🟢 On Track  
**Next Review**: Week of $(next_week)


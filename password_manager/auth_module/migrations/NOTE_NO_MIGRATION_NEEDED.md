# Passkey Model Migration Note

## No Migration Required

The `UserPasskey` model in `auth_module/models.py` already has all the correct fields:

```python
class UserPasskey(models.Model):
    """Model for storing WebAuthn/passkey credentials"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    credential_id = models.BinaryField(unique=True)  # ✅ Already BinaryField
    public_key = models.BinaryField()  # ✅ Correct
    sign_count = models.IntegerField(default=0)  # ✅ Correct
    rp_id = models.CharField(max_length=253)  # ✅ Already exists
    created_at = models.DateTimeField(auto_now_add=True)  # ✅ Correct field name
    last_used_at = models.DateTimeField(null=True, blank=True)  # ✅ Correct field name
    device_type = models.CharField(max_length=255, null=True, blank=True)  # ✅ Already exists
```

## What Was Fixed

The issues were in the **code** (passkey_views.py), not the model:

1. ✅ **Fixed code to use correct field names**: 
   - Changed `registered_on` → `created_at` in code
   - Changed `last_used` → `last_used_at` in code

2. ✅ **Fixed credential_id handling**:
   - Now stores as bytes: `credential_id=websafe_decode(credential_id)`
   - Lookups use bytes: `credential_id_bytes = websafe_decode(credential_id)`
   - List view converts to base64: `websafe_encode(passkey.credential_id)`

3. ✅ **Fixed rp_id population**:
   - Now sets: `rp_id=RP_ID` during registration

## If You Need to Migrate

If your existing database has old passkeys with incorrect data, run:

```bash
cd password_manager
python manage.py shell
```

Then in the shell:

```python
from auth_module.models import UserPasskey
from fido2.utils import websafe_encode, websafe_decode

# Check if any passkeys exist
count = UserPasskey.objects.count()
print(f"Found {count} passkeys")

# If you need to fix credential_id format (only if they're stored as text)
for passkey in UserPasskey.objects.all():
    # Check if credential_id is stored as text
    if isinstance(passkey.credential_id, str):
        # Convert from base64 string to bytes
        passkey.credential_id = websafe_decode(passkey.credential_id)
        passkey.save()
        print(f"Fixed passkey {passkey.id}")
```

## Verification

To verify your passkeys are stored correctly:

```python
from auth_module.models import UserPasskey

for passkey in UserPasskey.objects.all():
    print(f"Passkey {passkey.id}:")
    print(f"  User: {passkey.user.username}")
    print(f"  credential_id type: {type(passkey.credential_id)}")  # Should be 'bytes'
    print(f"  credential_id length: {len(passkey.credential_id)}")  # Should be > 0
    print(f"  rp_id: {passkey.rp_id}")  # Should match PASSKEY_RP_ID setting
    print(f"  device_type: {passkey.device_type}")
    print(f"  sign_count: {passkey.sign_count}")
    print(f"  created_at: {passkey.created_at}")
    print(f"  last_used_at: {passkey.last_used_at}")
    print()
```

Expected output:
```
Passkey 1:
  User: testuser
  credential_id type: <class 'bytes'>
  credential_id length: 64
  rp_id: localhost
  device_type: Chrome on Windows
  sign_count: 5
  created_at: 2025-10-11 12:30:00
  last_used_at: 2025-10-11 14:45:00
```

## Conclusion

**No database migration is needed.** The model schema was already correct. All fixes were applied to the Python code in `passkey_views.py`.


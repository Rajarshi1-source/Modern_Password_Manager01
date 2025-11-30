# Quantum Crypto Migration Guide

**Migrating Behavioral Commitments from Classical to Quantum Encryption**

---

## Overview

This guide explains how to migrate existing behavioral commitments from classical Base64 encoding to quantum-resistant Kyber-768 + AES-256-GCM encryption.

**Migration is NON-DESTRUCTIVE**: Original encrypted data is preserved in `legacy_encrypted_embedding` field.

---

## Pre-Migration Checklist

Before migrating:

- [ ] Backup database
- [ ] Install liboqs-python (`pip install liboqs-python`)
- [ ] Run database migrations (`python manage.py migrate behavioral_recovery`)
- [ ] Test on dev environment first
- [ ] Run dry-run migration
- [ ] Verify tests pass

---

## Migration Methods

### Method 1: Management Command (Recommended)

#### Step 1: Dry Run

```bash
cd password_manager

# Simulate migration (no changes made)
python manage.py upgrade_to_quantum --dry-run
```

Expected output:
```
==========================================
Behavioral Commitment Quantum Migration
==========================================
Found 50 commitments to upgrade

⚠️  DRY RUN MODE - No changes will be made

✅ Using Kyber768
.................................................. [50/50]
==========================================

✅ Migration simulated!

Total commitments: 50
Upgraded: 50
Skipped (already quantum): 0
Failed: 0
```

#### Step 2: Actual Migration

```bash
# Migrate all commitments
python manage.py upgrade_to_quantum
```

#### Step 3: Verify

```bash
python manage.py shell
```

```python
>>> from behavioral_recovery.models import BehavioralCommitment
>>> quantum = BehavioralCommitment.objects.filter(is_quantum_protected=True).count()
>>> total = BehavioralCommitment.objects.count()
>>> print(f"✅ {quantum}/{total} commitments are quantum-protected")
```

### Method 2: Async Background Migration

For large datasets (1000+ commitments):

```bash
python manage.py shell
```

```python
>>> from behavioral_recovery.tasks import async_migrate_commitments_to_quantum
>>> 
>>> # Migrate in batches of 100
>>> task = async_migrate_commitments_to_quantum.delay(batch_size=100)
>>> 
>>> # Check task status
>>> print(task.status)  # PENDING, STARTED, SUCCESS, FAILURE
>>> 
>>> # Get result
>>> result = task.get(timeout=300)  # Wait up to 5 minutes
>>> print(f"Migrated {result} commitments")
```

### Method 3: Gradual Migration

Migrate incrementally:

```python
# Migrate one user at a time
python manage.py upgrade_to_quantum --user-id 1
python manage.py upgrade_to_quantum --user-id 2
# ... etc
```

or

```bash
# Migrate in small batches
python manage.py upgrade_to_quantum --batch-size 10
# Run multiple times until all migrated
```

---

## Migration Process Details

### What Happens During Migration

For each classical commitment:

1. **Decrypt old format** (Base64 decoding)
2. **Generate new Kyber keypair**
3. **Encrypt with Kyber + AES**
4. **Preserve original** in `legacy_encrypted_embedding`
5. **Update fields**:
   - `quantum_encrypted_embedding` = new encrypted data
   - `kyber_public_key` = public key
   - `encryption_algorithm` = 'kyber768-aes256gcm'
   - `is_quantum_protected` = True
   - `migrated_to_quantum` = current timestamp
6. **Clear legacy field** `encrypted_embedding` = b''

### Rollback Procedure

If migration fails or issues arise:

```python
from behavioral_recovery.models import BehavioralCommitment

# Revert to legacy encryption for a commitment
commitment = BehavioralCommitment.objects.get(commitment_id='...')

# Restore from legacy
commitment.encrypted_embedding = commitment.legacy_encrypted_embedding
commitment.quantum_encrypted_embedding = None
commitment.kyber_public_key = None
commitment.is_quantum_protected = False
commitment.encryption_algorithm = 'base64'
commitment.save()
```

---

## Verification

### Verify Quantum Protection

**Django Admin**: http://localhost:8000/admin/behavioral_recovery/behavioralcommitment/

Filter by `is_quantum_protected = True`

Check that:
- `encryption_algorithm` shows "kyber768-aes256gcm"
- `kyber_public_key` is not empty (1184 bytes)
- `quantum_encrypted_embedding` contains encrypted dict
- `migrated_to_quantum` shows migration timestamp

### Verify Functionality

**Test Recovery Flow**:

1. Initiate recovery for user with quantum commitment
2. Complete challenges
3. Verify similarity calculation works
4. Confirm password reset succeeds

**Expected**: No difference in user experience, but commitments are now quantum-resistant!

---

## Performance Considerations

### Migration Time Estimates

| Commitments | Time (Serial) | Time (Async) |
|------------|---------------|--------------|
| 10 | ~5 seconds | ~2 seconds |
| 100 | ~50 seconds | ~15 seconds |
| 1,000 | ~8 minutes | ~2 minutes |
| 10,000 | ~1.5 hours | ~20 minutes |

**Recommendation**: Use async migration for > 100 commitments

### Database Growth

Quantum commitments require more storage:

- Classical: ~200 bytes per commitment
- Quantum: ~2,500 bytes per commitment (12.5x larger)

**Example**: 1,000 commitments = ~2.5 MB (quantum) vs ~200 KB (classical)

Still very manageable for modern databases.

---

## Monitoring

### Track Migration Progress

```python
from behavioral_recovery.models import BehavioralCommitment
from django.db.models import Count, Q

# Get counts
stats = BehavioralCommitment.objects.aggregate(
    total=Count('id'),
    quantum=Count('id', filter=Q(is_quantum_protected=True)),
    classical=Count('id', filter=Q(is_quantum_protected=False))
)

print(f"Total: {stats['total']}")
print(f"Quantum: {stats['quantum']} ({stats['quantum']/stats['total']*100:.1f}%)")
print(f"Classical: {stats['classical']} ({stats['classical']/stats['total']*100:.1f}%)")
```

### Set Up Alerts

```python
# Celery periodic task to monitor migration
from celery import shared_task

@shared_task
def check_quantum_migration_status():
    from behavioral_recovery.models import BehavioralCommitment
    
    classical_count = BehavioralCommitment.objects.filter(is_quantum_protected=False).count()
    
    if classical_count > 0:
        logger.warning(f"{classical_count} commitments still need quantum upgrade")
        # Send alert email
    
    return classical_count
```

---

## Best Practices

### Before Migration

1. **Backup**: Always backup database first
2. **Test**: Run dry-run migration
3. **Verify**: Check liboqs is installed
4. **Timing**: Migrate during low-traffic period

### During Migration

1. **Monitor**: Watch logs for errors
2. **Batch**: Use appropriate batch size
3. **Progress**: Track completion percentage
4. **Patience**: Large migrations take time

### After Migration

1. **Verify**: Check all commitments migrated
2. **Test**: Run quantum crypto tests
3. **Monitor**: Watch for any issues
4. **Document**: Note migration completion date

---

## FAQ

**Q: Will migration break existing commitments?**  
A: No, original data is preserved in `legacy_encrypted_embedding`.

**Q: Can I rollback if something goes wrong?**  
A: Yes, original data is still available. Can be restored.

**Q: Do users need to do anything?**  
A: No, migration is transparent to users.

**Q: What if liboqs isn't available?**  
A: System automatically uses fallback encryption (not quantum-resistant).

**Q: How long does migration take?**  
A: ~0.5 seconds per commitment (serial), ~0.15 seconds (async).

**Q: Is there downtime during migration?**  
A: No, migration can run while system is live.

---

**Migration Status**: ✅ Ready  
**Safety**: Non-destructive  
**Complexity**: Low-Medium  
**Recommended**: Yes (for quantum protection)


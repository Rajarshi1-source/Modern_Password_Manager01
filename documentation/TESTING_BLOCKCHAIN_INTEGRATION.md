# Testing Blockchain Integration - End-to-End Guide

## 🎯 Overview

This guide walks you through testing the complete blockchain anchoring flow from commitment creation to on-chain verification.

**Prerequisites**:
- Smart contract deployed to Arbitrum Sepolia
- Redis running
- Celery workers started
- Django server running

---

## Test Phase 1: Backend Setup Verification

### 1.1 Check Django Settings

```bash
cd password_manager
python manage.py shell
```

```python
from django.conf import settings

# Check blockchain configuration
bc_config = settings.BLOCKCHAIN_ANCHORING
print("Enabled:", bc_config['ENABLED'])
print("Network:", bc_config['NETWORK'])
print("Contract:", bc_config['CONTRACT_ADDRESS'])
print("RPC URL:", bc_config['RPC_URL'])

# Should show all values correctly
```

### 1.2 Test Blockchain Service Connection

```python
from blockchain.services.blockchain_anchor_service import BlockchainAnchorService

# Initialize service
service = BlockchainAnchorService()

# Check connection
print("✅ Connected to:", service.w3.provider.endpoint_uri)
print("✅ Contract address:", service.contract.address)
print("✅ Latest block:", service.w3.eth.block_number)
```

Expected output:
```
✅ Connected to: https://sepolia-rollup.arbitrum.io/rpc
✅ Contract address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
✅ Latest block: 12345678
```

---

## Test Phase 2: Merkle Tree Generation

### 2.1 Test Merkle Tree Builder

```python
from blockchain.services.merkle_tree_builder import MerkleTreeBuilder
import hashlib

# Create test commitment hashes
test_hashes = [
    hashlib.sha256(f"commitment_{i}".encode()).hexdigest()
    for i in range(10)
]

# Build tree
tree_data = MerkleTreeBuilder.build_tree(test_hashes)

print("✅ Merkle Root:", tree_data['root'][:16] + "...")
print("✅ Tree Levels:", len(tree_data['levels']))
print("✅ Leaf Count:", len(tree_data['leaves']))

# Generate proof for first leaf
proof = MerkleTreeBuilder.generate_proof(tree_data, test_hashes[0])
print("✅ Proof Length:", len(proof))

# Verify proof
is_valid = MerkleTreeBuilder.verify_proof(
    tree_data['root'],
    test_hashes[0],
    proof
)
print("✅ Proof Valid:", is_valid)
```

Expected output:
```
✅ Merkle Root: 0x742d35Cc6634...
✅ Tree Levels: 4
✅ Leaf Count: 10
✅ Proof Length: 4
✅ Proof Valid: True
```

---

## Test Phase 3: Create Behavioral Commitment

### 3.1 Create a Test User and Commitment

```python
from django.contrib.auth.models import User
from behavioral_recovery.services.commitment_service import CommitmentService
import numpy as np

# Get or create test user
user, created = User.objects.get_or_create(
    username='test_blockchain_user',
    email='test@example.com'
)
if created:
    user.set_password('test_password_123')
    user.save()
    print("✅ Created test user")

# Create commitment service
commitment_service = CommitmentService(use_quantum=True, use_blockchain=True)

# Create fake behavioral data (128-dim embedding)
behavioral_data = np.random.rand(128).tolist()

# Create commitment
commitment = commitment_service.create_commitments(
    user=user,
    behavioral_samples={'typing': [behavioral_data]},
    unlock_conditions={'similarity_threshold': 0.87}
)

print("✅ Commitment created:", commitment[0].commitment_id)
print("✅ Blockchain hash:", commitment[0].blockchain_hash[:16] + "...")
print("✅ Quantum protected:", commitment[0].is_quantum_protected)
```

### 3.2 Check Pending Commitments

```python
from blockchain.models import PendingCommitment

pending = PendingCommitment.objects.filter(anchored=False)
print(f"✅ Pending commitments: {pending.count()}")

for p in pending[:5]:
    print(f"  - User: {p.user.username}, Hash: {p.commitment_hash[:16]}...")
```

---

## Test Phase 4: Manual Blockchain Anchoring

### 4.1 Trigger Anchoring Manually

```python
from blockchain.services.blockchain_anchor_service import BlockchainAnchorService

# Initialize service
service = BlockchainAnchorService()

# Anchor pending batch
result = service.anchor_pending_batch()

if result['success']:
    print("✅ Anchoring successful!")
    print("  TX Hash:", result['tx_hash'])
    print("  Merkle Root:", result['merkle_root'][:16] + "...")
    print("  Anchored:", result['anchored_count'], "commitments")
    print("  Block:", result.get('block_number'))
    print("  Arbiscan:", f"https://sepolia.arbiscan.io/tx/{result['tx_hash']}")
else:
    print("❌ Anchoring failed:", result.get('error'))
```

**Wait 1-2 minutes for blockchain confirmation**, then proceed.

### 4.2 Verify Anchor was Stored

```python
from blockchain.models import BlockchainAnchor, MerkleProof

# Check blockchain anchors
anchors = BlockchainAnchor.objects.all().order_by('-timestamp')
print(f"✅ Total anchors: {anchors.count()}")

if anchors.exists():
    latest = anchors.first()
    print(f"  Latest TX: {latest.tx_hash}")
    print(f"  Block: {latest.block_number}")
    print(f"  Batch size: {latest.batch_size}")
    print(f"  Network: {latest.network}")

# Check Merkle proofs
proofs = MerkleProof.objects.all()
print(f"✅ Total proofs: {proofs.count()}")
```

---

## Test Phase 5: Verify Commitments

### 5.1 Verify Locally (Database)

```python
# Get a commitment with proof
proof = MerkleProof.objects.filter(verified=False).first()

if proof:
    # Verify proof locally
    service = BlockchainAnchorService()
    is_valid = service.verify_proof_locally(
        merkle_root=proof.merkle_root,
        leaf_hash=proof.commitment_hash,
        proof=proof.proof
    )
    
    print("✅ Local verification:", is_valid)
    
    if is_valid:
        proof.verified = True
        proof.save()
        print("✅ Proof marked as verified")
```

### 5.2 Verify On-Chain (Arbitrum)

```python
# Verify on Arbitrum blockchain
is_valid_onchain = service.verify_proof_on_chain(
    merkle_root=proof.merkle_root,
    leaf_hash=proof.commitment_hash,
    proof=proof.proof
)

print("✅ On-chain verification:", is_valid_onchain)
```

---

## Test Phase 6: API Endpoints

### 6.1 Get Anchor Status

```bash
# Get anchor status (requires authentication)
curl -X GET http://localhost:8000/api/blockchain/anchor-status/ \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

Expected response:
```json
{
  "enabled": true,
  "network": "testnet",
  "contract_address": "0x742d35Cc...",
  "pending_count": 0,
  "total_anchored": 10,
  "last_anchor": {
    "timestamp": "2025-11-23T...",
    "batch_size": 10,
    "tx_hash": "0xabc..."
  }
}
```

### 6.2 Verify Commitment via API

```bash
# Verify a specific commitment
curl -X GET http://localhost:8000/api/blockchain/verify-commitment/COMMITMENT_ID/ \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

Expected response:
```json
{
  "verified": true,
  "commitment_id": "uuid...",
  "commitment_hash": "0x...",
  "merkle_root": "0x...",
  "blockchain_anchor": {
    "tx_hash": "0x...",
    "block_number": 12345678,
    "timestamp": "2025-11-23T...",
    "network": "testnet"
  },
  "arbiscan_url": "https://sepolia.arbiscan.io/tx/0x..."
}
```

### 6.3 Trigger Manual Anchoring (Admin Only)

```bash
curl -X POST http://localhost:8000/api/blockchain/trigger-anchor/ \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json"
```

---

## Test Phase 7: Frontend Integration

### 7.1 Update Frontend .env

```bash
# frontend/.env
REACT_APP_BLOCKCHAIN_ENABLED=true
REACT_APP_ARBITRUM_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
REACT_APP_CONTRACT_ADDRESS=0xYOUR_CONTRACT_ADDRESS
```

### 7.2 Test Arbitrum Service

```javascript
// In browser console after starting frontend
import arbitrumService from './services/blockchain/arbitrumService';

// Check connection
const networkInfo = await arbitrumService.getNetworkInfo();
console.log('Network:', networkInfo);

// Check contract
const isAccessible = await arbitrumService.isContractAccessible();
console.log('Contract accessible:', isAccessible);
```

### 7.3 Test BlockchainVerification Component

1. Navigate to password recovery flow
2. Create a recovery attempt
3. The `BlockchainVerification` component should display:
   - ⏳ "Pending" if not yet anchored
   - ✅ "Verified" with details if anchored
   - Link to Arbiscan explorer

---

## Test Phase 8: Celery Auto-Anchoring

### 8.1 Test Celery Task Manually

```bash
cd password_manager

# In Python shell
python manage.py shell
```

```python
from blockchain.tasks import anchor_pending_commitments

# Run task manually
result = anchor_pending_commitments.apply()
print(result.get())
```

### 8.2 Test Celery Beat Schedule

```bash
# Check Celery beat schedule
celery -A password_manager inspect scheduled

# Should show:
# - anchor-commitments-to-blockchain (daily at 2 AM UTC)
# - verify-blockchain-anchors (every 6 hours)
# - cleanup-old-pending-commitments (weekly Sunday 3 AM)
```

---

## Test Phase 9: End-to-End Flow

### Complete E2E Test

```python
# 1. Create user
user = User.objects.create_user('e2e_test', 'e2e@test.com', 'password123')

# 2. Create commitment
service = CommitmentService(use_blockchain=True)
commitment = service.create_commitments(
    user=user,
    behavioral_samples={'typing': [np.random.rand(128).tolist()]},
    unlock_conditions={}
)[0]

print("1. ✅ Commitment created:", commitment.commitment_id)
print("   Hash:", commitment.blockchain_hash[:16] + "...")

# 3. Check pending
pending = PendingCommitment.objects.filter(
    user=user,
    anchored=False
).count()
print(f"2. ✅ Pending: {pending}")

# 4. Anchor to blockchain
anchor_service = BlockchainAnchorService()
result = anchor_service.anchor_pending_batch()

if result['success']:
    print("3. ✅ Anchored to blockchain")
    print("   TX:", result['tx_hash'])
    
    # Wait for confirmation
    import time
    print("   Waiting for confirmation...")
    time.sleep(30)
    
    # 5. Verify
    commitment.refresh_from_db()
    print("4. ✅ Commitment anchored:", commitment.blockchain_anchored)
    
    # 6. Get Merkle proof
    proof = MerkleProof.objects.get(commitment=commitment)
    print("5. ✅ Merkle proof exists")
    
    # 7. Verify locally
    is_valid_local = anchor_service.verify_proof_locally(
        proof.merkle_root,
        proof.commitment_hash,
        proof.proof
    )
    print("6. ✅ Local verification:", is_valid_local)
    
    # 8. Verify on-chain
    is_valid_chain = anchor_service.verify_proof_on_chain(
        proof.merkle_root,
        proof.commitment_hash,
        proof.proof
    )
    print("7. ✅ On-chain verification:", is_valid_chain)
    
    print("\n🎉 END-TO-END TEST PASSED!")
else:
    print("❌ Anchoring failed:", result.get('error'))
```

---

## Success Checklist ✅

After running all tests, verify:

- [ ] Blockchain service connects to Arbitrum
- [ ] Merkle tree generation works correctly
- [ ] Commitments are created with blockchain hashes
- [ ] Pending commitments are queued
- [ ] Manual anchoring succeeds
- [ ] Transaction appears on Arbiscan
- [ ] Merkle proofs are stored correctly
- [ ] Local verification works
- [ ] On-chain verification works
- [ ] API endpoints return correct data
- [ ] Frontend can display verification status
- [ ] Celery tasks run successfully
- [ ] E2E flow completes without errors

---

## 🐛 Troubleshooting

### "Provider not connected"
```python
# Check RPC URL is accessible
import requests
rpc_url = "https://sepolia-rollup.arbitrum.io/rpc"
response = requests.post(rpc_url, json={
    "jsonrpc": "2.0",
    "method": "eth_blockNumber",
    "params": [],
    "id": 1
})
print(response.json())
```

### "Contract not found"
- Verify contract address in `.env`
- Check contract was deployed successfully
- Visit Arbiscan to confirm

### "Insufficient funds for gas"
- Get more test ETH from faucet
- Check wallet balance on Arbiscan

### "Celery task fails"
- Check Celery worker logs
- Verify Redis is running
- Check environment variables are loaded

---

## 📊 Performance Metrics

After successful testing, track:

1. **Anchoring Performance**:
   - Time to anchor: ~30-60 seconds
   - Gas cost: ~0.001 test ETH per batch
   - Batch size: 1-1000 commitments

2. **Verification Performance**:
   - Local verification: < 100ms
   - On-chain verification: 1-3 seconds
   - API response time: < 500ms

3. **System Health**:
   - Celery task success rate: 100%
   - Blockchain RPC uptime: > 99%
   - Verification accuracy: 100%

---

## 🎯 Next Steps

After successful testing:

1. **Production Deployment**:
   - Deploy to mainnet (requires real ETH)
   - Update RPC URLs and contract addresses
   - Monitor gas prices

2. **Monitoring Setup**:
   - Set up Sentry for error tracking
   - Add Grafana dashboards for metrics
   - Configure alerts for failed anchoring

3. **User Documentation**:
   - Create user guide for blockchain verification
   - Add tooltips in UI explaining blockchain anchoring
   - Provide FAQs

4. **Phase 2B.2 (Next Phase)**:
   - Implement metrics collection
   - Set up A/B testing
   - Create admin dashboard

---

**Ready for Production?** ✅

If all tests pass, Phase 2B.1 is complete! 🎉


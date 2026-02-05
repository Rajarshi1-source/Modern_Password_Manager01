# Next Steps: Complete Phase 2B.1 Deployment

## Required Actions

### 1. Install Dependencies

```bash
# Backend
cd password_manager
pip install celery redis web3 eth-account

# Smart contract
cd ../contracts
npm install
```

### 2. Install and Start Redis

**Windows**:
- Download from: https://redis.io/download
- Or use WSL: `sudo apt-get install redis-server`

**Linux/macOS**:
```bash
# Linux
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

**Verify Redis**:
```bash
redis-cli ping
# Should return: PONG
```

### 3. Get Test ETH (Arbitrum Sepolia)

1. Create a test wallet or use existing
2. Visit: https://faucet.quicknode.com/arbitrum/sepolia
3. Enter your wallet address
4. Receive test ETH (~0.1 ETH for gas fees)

### 4. Deploy Smart Contract

```bash
cd contracts

# Deploy to Arbitrum Sepolia testnet
npx hardhat run scripts/deploy.js --network arbitrumSepolia
```

**Copy the deployed contract address** (example: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`)

### 5. Update Environment Variables

Edit `password_manager/.env`:
```bash
# Enable blockchain
BLOCKCHAIN_ENABLED=True
BLOCKCHAIN_NETWORK=testnet

# Add contract address from step 4
COMMITMENT_REGISTRY_ADDRESS_TESTNET=0xYOUR_CONTRACT_ADDRESS

# Add deployer private key
BLOCKCHAIN_PRIVATE_KEY=<YOUR_PRIVATE_KEY>_PRIVATE_KEY

# Celery configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# RPC URL (default is fine)
ARBITRUM_TESTNET_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
```

### 6. Run Migrations

```bash
cd password_manager
python manage.py migrate
```

### 7. Start Services

**Terminal 1 - Redis** (if not running as service):
```bash
redis-server
```

**Terminal 2 - Django**:
```bash
python manage.py runserver
```

**Terminal 3 - Celery Worker**:
```bash
celery -A password_manager worker --loglevel=info
```

**Terminal 4 - Celery Beat** (scheduler):
```bash
celery -A password_manager beat --loglevel=info
```

### 8. Verify Setup

1. **Check Django Admin**: http://localhost:8000/admin/
   - Navigate to Blockchain → Pending Commitments
   - Should be empty initially

2. **Create a Test Commitment**:
   - Sign up for an account
   - Interact with the app to build behavioral profile
   - System will auto-create commitments

3. **Trigger Manual Anchoring** (optional):
   ```bash
   python manage.py shell
   ```
   ```python
   from blockchain.tasks import anchor_pending_commitments
   result = anchor_pending_commitments()
   print(result)
   ```

4. **Check Blockchain**:
   - Django Admin → Blockchain → Blockchain Anchors
   - Click "View on Arbiscan" to verify transaction

### 9. Verify Contract on Arbiscan (Optional but Recommended)

```bash
cd contracts
npx hardhat verify --network arbitrumSepolia <CONTRACT_ADDRESS>
```

This makes your contract source code viewable on Arbiscan.

---

## Optional: Frontend Integration

If you want to add blockchain verification UI:

### 1. Install Frontend Dependencies

```bash
cd frontend
npm install ethers@^6.8.0 merkletreejs@^0.3.11
```

### 2. Update Frontend `.env`

```bash
REACT_APP_BLOCKCHAIN_ENABLED=true
REACT_APP_ARBITRUM_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
REACT_APP_CONTRACT_ADDRESS=0xYOUR_CONTRACT_ADDRESS
```

### 3. Create Arbitrum Service

See `PHASE_2B1_BLOCKCHAIN_INTEGRATION_COMPLETE.md` for frontend code examples.

---

## Troubleshooting

### "Connection to Redis failed"
```bash
# Check if Redis is running
redis-cli ping

# Start Redis if not running
redis-server
```

### "Insufficient funds for gas"
- Get more test ETH from faucet
- Check your wallet balance on Arbiscan

### "Contract deployment failed"
- Check your private key is correct
- Verify you have test ETH
- Check RPC URL is correct

### "Module 'celery' not found"
```bash
pip install celery redis
```

---

## Cost Estimate

**Testnet (FREE)**:
- Uses test ETH (no real cost)
- Perfect for development

**Mainnet (if deployed later)**:
- Contract deployment: ~$2-5 USD (one-time)
- Per batch (1000 commitments): ~$0.02 USD
- Monthly (30 batches): ~$0.60 USD

---

## Next Phase: Phase 2B.2 (Evaluation Framework)

After blockchain is working:
1. Implement metrics collection
2. Set up A/B testing framework
3. Create admin dashboard
4. Build Go/No-Go decision tool

See `Neur.plan.md` for Phase 2B.2 details.

---

**Questions?** Check `PHASE_2B1_BLOCKCHAIN_INTEGRATION_COMPLETE.md` for full documentation.


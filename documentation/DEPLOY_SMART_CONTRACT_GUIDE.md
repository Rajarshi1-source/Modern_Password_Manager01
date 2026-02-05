# Smart Contract Deployment Guide - Step by Step

## 🎯 Goal
Deploy the `CommitmentRegistry` smart contract to Arbitrum Sepolia testnet and configure your application.

---

## Step 1: Get a Wallet and Test ETH

### Option A: Use MetaMask (Recommended)

1. **Install MetaMask**:
   - Visit: https://metamask.io/
   - Install browser extension
   - Create a new wallet (SAVE YOUR SEED PHRASE!)

2. **Add Arbitrum Sepolia Network**:
   - Open MetaMask
   - Click network dropdown (top)
   - Click "Add Network"
   - Fill in:
     - **Network Name**: Arbitrum Sepolia
     - **RPC URL**: `https://sepolia-rollup.arbitrum.io/rpc`
     - **Chain ID**: `421614`
     - **Currency Symbol**: `ETH`
     - **Block Explorer**: `https://sepolia.arbiscan.io`
   - Click "Save"

3. **Get Your Wallet Address**:
   - Click on your account name in MetaMask
   - Click to copy address (e.g., `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`)

4. **Get Your Private Key** (for deployment):
   - Click three dots → Account Details → Export Private Key
   - Enter password
   - **⚠️ KEEP THIS PRIVATE! Never share or commit to Git!**
   - Copy it (e.g., `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80`)

### Option B: Use Hardhat Test Account (Quick Start)

Hardhat comes with test accounts. Use this for quick testing:
```javascript
// Account #0: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
// Private Key: <YOUR_PRIVATE_KEY>
```

---

## Step 2: Get Test ETH from Faucets

You need test ETH on **Arbitrum Sepolia** (not regular Sepolia!).

### Method 1: QuickNode Faucet (Easiest) ⭐

1. Visit: https://faucet.quicknode.com/arbitrum/sepolia
2. Connect your MetaMask wallet
3. Click "Continue"
4. Complete any verification (if required)
5. Receive 0.01-0.1 ETH (~$0 real value, for testing only)
6. Wait 1-2 minutes for confirmation

### Method 2: Alchemy Faucet

1. Visit: https://www.alchemy.com/faucets/arbitrum-sepolia
2. Sign up for free Alchemy account
3. Enter your wallet address
4. Receive test ETH

### Method 3: Bridge from Sepolia (If you have Sepolia ETH)

1. Get Sepolia ETH first: https://sepoliafaucet.com/
2. Bridge to Arbitrum Sepolia: https://bridge.arbitrum.io/
3. Select Sepolia → Arbitrum Sepolia
4. Bridge your test ETH

### Verify You Have Test ETH:

- Check on Arbiscan: https://sepolia.arbiscan.io/address/YOUR_ADDRESS
- Or check MetaMask balance (switch to Arbitrum Sepolia network)
- You should see ~0.01-0.1 ETH

---

## Step 3: Prepare Environment

1. **Update `.env` file** in `password_manager` directory:

```bash
# Add these lines (or update if they exist)

# Blockchain Configuration
BLOCKCHAIN_ENABLED=True
BLOCKCHAIN_NETWORK=testnet

# Arbitrum RPC
ARBITRUM_TESTNET_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc

# Your wallet private key (from Step 1)
BLOCKCHAIN_PRIVATE_KEY=<YOUR_PRIVATE_KEY>_PRIVATE_KEY_HERE

# Contract address (leave empty for now, will update after deployment)
COMMITMENT_REGISTRY_ADDRESS_TESTNET=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**⚠️ IMPORTANT**: Add `.env` to `.gitignore` to prevent committing your private key!

2. **Create `.env` for contracts directory**:

Create `contracts/.env`:
```bash
# Arbitrum Sepolia
ARBITRUM_TESTNET_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
BLOCKCHAIN_PRIVATE_KEY=<YOUR_PRIVATE_KEY>_PRIVATE_KEY_HERE

# Optional: For contract verification on Arbiscan
ARBISCAN_API_KEY=
```

---

## Step 4: Install Dependencies

```bash
# Navigate to contracts directory
cd contracts

# Install dependencies (if not already done)
npm install

# Verify installation
npx hardhat --version
# Should show: 2.x.x or similar
```

---

## Step 5: Compile Smart Contract

```bash
# Still in contracts directory
npx hardhat compile
```

Expected output:
```
Compiling 1 file with 0.8.20
Compilation finished successfully
```

---

## Step 6: Deploy to Arbitrum Sepolia

```bash
# Deploy the contract
npx hardhat run scripts/deploy.js --network arbitrumSepolia
```

Expected output:
```
Deploying CommitmentRegistry...
CommitmentRegistry deployed to: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
Transaction hash: 0xabc123...
Block number: 12345678
Gas used: 1234567
```

**✅ COPY THE CONTRACT ADDRESS!** (e.g., `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`)

---

## Step 7: Update Configuration with Contract Address

1. **Update `password_manager/.env`**:
```bash
COMMITMENT_REGISTRY_ADDRESS_TESTNET=0xYOUR_CONTRACT_ADDRESS
```

2. **Verify on Arbiscan**:
   - Visit: `https://sepolia.arbiscan.io/address/YOUR_CONTRACT_ADDRESS`
   - You should see your deployed contract!

---

## Step 8: Verify Contract on Arbiscan (Recommended)

This makes your contract source code public and verifiable:

```bash
# In contracts directory
npx hardhat verify --network arbitrumSepolia YOUR_CONTRACT_ADDRESS
```

Expected output:
```
Successfully verified contract CommitmentRegistry on Arbiscan.
https://sepolia.arbiscan.io/address/YOUR_CONTRACT_ADDRESS#code
```

Now anyone can view your contract source code on Arbiscan!

---

## Step 9: Test the Contract

Create a test script to verify the contract works:

```bash
# In contracts directory
npx hardhat test
```

Expected output:
```
  CommitmentRegistry
    ✓ Should deploy successfully
    ✓ Should anchor commitment
    ✓ Should verify Merkle proof
    
  3 passing (2s)
```

---

## Step 10: Configure Backend

1. **Run Django migrations**:
```bash
cd ../password_manager
python manage.py migrate
```

2. **Test blockchain service**:
```bash
python manage.py shell
```

```python
from blockchain.services.blockchain_anchor_service import BlockchainAnchorService

# Initialize service
service = BlockchainAnchorService()

# Check connection
print(f"Connected to: {service.w3.provider.endpoint_uri}")
print(f"Contract address: {service.contract.address}")
print("✅ Blockchain service initialized!")
```

---

## 🎉 Success Checklist

- [ ] Wallet created with test ETH (0.01+ ETH)
- [ ] Contract compiled successfully
- [ ] Contract deployed to Arbitrum Sepolia
- [ ] Contract address copied
- [ ] `.env` updated with contract address
- [ ] Contract verified on Arbiscan (optional but recommended)
- [ ] Tests passing
- [ ] Backend can connect to contract

---

## 💰 Cost Estimate

**You just deployed for FREE!** ✨
- Test ETH has no real value
- Deployment cost: ~0.001 test ETH (~$0)
- Future anchoring: ~0.00001 test ETH per batch (~$0)

**Mainnet would cost**:
- Deployment: ~$2-5 USD (one-time)
- Anchoring: ~$0.02 per 1000 commitments

---

## 🐛 Troubleshooting

### Error: "Insufficient funds for gas"
- **Solution**: Get more test ETH from faucet (Step 2)

### Error: "Cannot find module '@nomicfoundation/hardhat-toolbox'"
- **Solution**: Run `npm install` in contracts directory

### Error: "Network arbitrumSepolia not found"
- **Solution**: Check `hardhat.config.js` has arbitrumSepolia network configured
- Verify ARBITRUM_TESTNET_RPC_URL in contracts/.env

### Error: "Invalid nonce"
- **Solution**: Reset MetaMask account (Settings → Advanced → Reset Account)

### Contract deployed but not showing on Arbiscan
- **Wait**: Give it 1-2 minutes to propagate
- **Check**: Verify you're on https://sepolia.arbiscan.io (not mainnet)

---

## 📝 What's Next?

After successful deployment:
1. ✅ Test API endpoints (we'll create these next)
2. ✅ Start Celery workers for auto-anchoring
3. ✅ Create behavioral commitments
4. ✅ Trigger blockchain anchoring
5. ✅ Verify on blockchain

Ready to proceed? Let me know when you've deployed and I'll help you with the API endpoints! 🚀


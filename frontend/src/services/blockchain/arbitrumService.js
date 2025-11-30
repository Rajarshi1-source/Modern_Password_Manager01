/**
 * Arbitrum Blockchain Service
 * 
 * Service for interacting with Arbitrum L2 blockchain to verify
 * behavioral commitments anchored via CommitmentRegistry smart contract.
 * 
 * Phase 2B.1: Blockchain Anchoring
 */

import { ethers } from 'ethers';
import COMMITMENT_REGISTRY_ABI from './abi/CommitmentRegistry.json';

class ArbitrumService {
  constructor() {
    // Initialize provider
    const rpcUrl = process.env.REACT_APP_ARBITRUM_RPC_URL || 'https://sepolia-rollup.arbitrum.io/rpc';
    this.provider = new ethers.JsonRpcProvider(rpcUrl);
    
    // Initialize contract
    const contractAddress = process.env.REACT_APP_CONTRACT_ADDRESS;
    if (contractAddress && contractAddress !== '') {
      this.contract = new ethers.Contract(
        contractAddress,
        COMMITMENT_REGISTRY_ABI,
        this.provider
      );
      console.log('✅ Arbitrum service initialized:', { rpcUrl, contractAddress });
    } else {
      console.warn('⚠️ Contract address not configured. On-chain verification disabled.');
      this.contract = null;
    }
    
    this.network = this.determineNetwork(rpcUrl);
  }
  
  /**
   * Determine network from RPC URL
   */
  determineNetwork(rpcUrl) {
    if (rpcUrl.includes('sepolia')) {
      return 'testnet';
    } else if (rpcUrl.includes('arb1') || rpcUrl.includes('mainnet')) {
      return 'mainnet';
    }
    return 'unknown';
  }
  
  /**
   * Get Arbiscan explorer URL for a transaction
   */
  getExplorerUrl(txHash) {
    const baseUrl = this.network === 'testnet' 
      ? 'https://sepolia.arbiscan.io' 
      : 'https://arbiscan.io';
    return `${baseUrl}/tx/${txHash}`;
  }
  
  /**
   * Get Arbiscan explorer URL for the contract
   */
  getContractUrl() {
    if (!this.contract) return null;
    const baseUrl = this.network === 'testnet' 
      ? 'https://sepolia.arbiscan.io' 
      : 'https://arbiscan.io';
    return `${baseUrl}/address/${this.contract.address}`;
  }
  
  /**
   * Verify a commitment on-chain using Merkle proof
   * 
   * @param {string} merkleRoot - The Merkle root (0x...)
   * @param {string} leafHash - The leaf hash (commitment hash)
   * @param {Array<string>} proof - Array of Merkle proof hashes
   * @returns {Promise<boolean>} - True if valid, false otherwise
   */
  async verifyCommitment(merkleRoot, leafHash, proof) {
    if (!this.contract) {
      throw new Error('Contract not initialized. Check REACT_APP_CONTRACT_ADDRESS.');
    }
    
    try {
      console.log('Verifying commitment on Arbitrum:', {
        merkleRoot: merkleRoot.substring(0, 10) + '...',
        leafHash: leafHash.substring(0, 10) + '...',
        proofLength: proof.length
      });
      
      const isValid = await this.contract.verifyCommitment(
        merkleRoot,
        leafHash,
        proof
      );
      
      console.log('✅ On-chain verification result:', isValid);
      return isValid;
      
    } catch (error) {
      console.error('❌ On-chain verification failed:', error);
      throw error;
    }
  }
  
  /**
   * Get commitment metadata from blockchain
   * 
   * @param {string} merkleRoot - The Merkle root
   * @returns {Promise<Object>} - Commitment data
   */
  async getCommitment(merkleRoot) {
    if (!this.contract) {
      throw new Error('Contract not initialized');
    }
    
    try {
      const commitment = await this.contract.getCommitment(merkleRoot);
      
      return {
        merkleRoot: commitment.merkleRoot,
        timestamp: Number(commitment.timestamp),
        timestampDate: new Date(Number(commitment.timestamp) * 1000),
        batchSize: Number(commitment.batchSize),
        submitter: commitment.submitter,
        exists: commitment.exists
      };
      
    } catch (error) {
      console.error('Error getting commitment from blockchain:', error);
      throw error;
    }
  }
  
  /**
   * Get commitment timestamp
   * 
   * @param {string} merkleRoot - The Merkle root
   * @returns {Promise<number>} - Unix timestamp
   */
  async getCommitmentTimestamp(merkleRoot) {
    const commitment = await this.getCommitment(merkleRoot);
    return commitment.timestamp;
  }
  
  /**
   * Check if contract is deployed and accessible
   * 
   * @returns {Promise<boolean>}
   */
  async isContractAccessible() {
    if (!this.contract) return false;
    
    try {
      // Try to read contract code
      const code = await this.provider.getCode(this.contract.address);
      return code !== '0x';
    } catch (error) {
      console.error('Contract accessibility check failed:', error);
      return false;
    }
  }
  
  /**
   * Get current network information
   * 
   * @returns {Promise<Object>}
   */
  async getNetworkInfo() {
    try {
      const network = await this.provider.getNetwork();
      const blockNumber = await this.provider.getBlockNumber();
      
      return {
        name: network.name,
        chainId: Number(network.chainId),
        blockNumber: blockNumber,
        rpcUrl: this.provider.connection.url,
        contractAddress: this.contract?.address,
        explorerUrl: this.getContractUrl()
      };
    } catch (error) {
      console.error('Error getting network info:', error);
      throw error;
    }
  }
}

// Export singleton instance
export default new ArbitrumService();


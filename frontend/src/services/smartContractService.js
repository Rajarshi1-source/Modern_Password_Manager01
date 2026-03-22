/**
 * Smart Contract Service
 * 
 * API client for the smart contract automation feature.
 * Wraps all backend endpoints for vault CRUD, condition evaluation,
 * multi-sig, DAO voting, escrow, and oracle.
 */

import api from './api';

const BASE_URL = '/api/smart-contracts';

const smartContractService = {
  // ============================
  // Configuration
  // ============================
  
  getConfig: () => api.get(`${BASE_URL}/config/`),

  // ============================
  // Vault CRUD
  // ============================
  
  listVaults: (params = {}) => api.get(`${BASE_URL}/vaults/`, { params }),
  
  createVault: (data) => api.post(`${BASE_URL}/vaults/`, data),
  
  getVault: (vaultId) => api.get(`${BASE_URL}/vaults/${vaultId}/`),
  
  deleteVault: (vaultId) => api.delete(`${BASE_URL}/vaults/${vaultId}/`),

  // ============================
  // Condition Evaluation
  // ============================
  
  getConditions: (vaultId, verifyOnchain = false) =>
    api.get(`${BASE_URL}/vaults/${vaultId}/conditions/`, {
      params: { verify_onchain: verifyOnchain }
    }),
  
  unlockVault: (vaultId) => api.post(`${BASE_URL}/vaults/${vaultId}/unlock/`),

  // ============================
  // Dead Man's Switch
  // ============================
  
  checkIn: (vaultId) => api.post(`${BASE_URL}/vaults/${vaultId}/check-in/`),

  // ============================
  // Multi-Sig
  // ============================
  
  approveMultiSig: (vaultId) => api.post(`${BASE_URL}/multi-sig/${vaultId}/approve/`),
  
  getMultiSigStatus: (vaultId) => api.get(`${BASE_URL}/multi-sig/${vaultId}/status/`),

  // ============================
  // DAO Voting
  // ============================
  
  castVote: (vaultId, approve) => api.post(`${BASE_URL}/dao/${vaultId}/vote/`, { approve }),
  
  getDAOResults: (vaultId) => api.get(`${BASE_URL}/dao/${vaultId}/results/`),

  // ============================
  // Escrow
  // ============================
  
  releaseEscrow: (vaultId) => api.post(`${BASE_URL}/escrow/${vaultId}/release/`),
  
  getEscrowStatus: (vaultId) => api.get(`${BASE_URL}/escrow/${vaultId}/status/`),

  // ============================
  // Inheritance
  // ============================
  
  getInheritanceStatus: (vaultId) => api.get(`${BASE_URL}/inheritance/${vaultId}/`),

  // ============================
  // Oracle
  // ============================
  
  getOraclePrice: () => api.get(`${BASE_URL}/oracle/price/`),
};

export default smartContractService;

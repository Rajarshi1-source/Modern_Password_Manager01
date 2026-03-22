/**
 * SmartContractService (Mobile)
 * 
 * API client for smart contract vault feature on mobile.
 */

import { Platform } from 'react-native';

const API_BASE = Platform.select({
  ios: 'http://localhost:8000/api/smart-contracts',
  android: 'http://10.0.2.2:8000/api/smart-contracts',
});

class SmartContractService {
  constructor() {
    this.token = null;
  }

  setToken(token) {
    this.token = token;
  }

  async _request(method, path, body = null) {
    const url = `${API_BASE}${path}`;
    const headers = {
      'Content-Type': 'application/json',
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const options = { method, headers };
    if (body) {
      options.body = JSON.stringify(body);
    }

    const res = await fetch(url, options);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed: ${res.status}`);
    }
    return data;
  }

  // Config
  getConfig() {
    return this._request('GET', '/config/');
  }

  // Vault CRUD
  listVaults(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this._request('GET', `/vaults/${query ? '?' + query : ''}`);
  }

  createVault(data) {
    return this._request('POST', '/vaults/', data);
  }

  getVault(vaultId) {
    return this._request('GET', `/vaults/${vaultId}/`);
  }

  deleteVault(vaultId) {
    return this._request('DELETE', `/vaults/${vaultId}/`);
  }

  // Conditions
  getConditions(vaultId) {
    return this._request('GET', `/vaults/${vaultId}/conditions/`);
  }

  unlockVault(vaultId) {
    return this._request('POST', `/vaults/${vaultId}/unlock/`);
  }

  // Dead Man's Switch
  checkIn(vaultId) {
    return this._request('POST', `/vaults/${vaultId}/check-in/`);
  }

  // Multi-Sig
  approveMultiSig(vaultId) {
    return this._request('POST', `/multi-sig/${vaultId}/approve/`);
  }

  getMultiSigStatus(vaultId) {
    return this._request('GET', `/multi-sig/${vaultId}/status/`);
  }

  // DAO Voting
  castVote(vaultId, approve) {
    return this._request('POST', `/dao/${vaultId}/vote/`, { approve });
  }

  getDAOResults(vaultId) {
    return this._request('GET', `/dao/${vaultId}/results/`);
  }

  // Escrow
  releaseEscrow(vaultId) {
    return this._request('POST', `/escrow/${vaultId}/release/`);
  }

  getEscrowStatus(vaultId) {
    return this._request('GET', `/escrow/${vaultId}/status/`);
  }

  // Inheritance
  getInheritanceStatus(vaultId) {
    return this._request('GET', `/inheritance/${vaultId}/`);
  }

  // Oracle
  getOraclePrice() {
    return this._request('GET', '/oracle/price/');
  }
}

export default new SmartContractService();

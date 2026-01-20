/**
 * EntanglementService.js
 * 
 * Mobile API client for quantum entanglement operations.
 * Handles device pairing, key sync, and revocation.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_URL } from '../config';

class EntanglementService {
  constructor() {
    this.baseUrl = `${API_URL}/api/security/entanglement`;
  }

  /**
   * Get authorization headers
   */
  async getHeaders() {
    const token = await AsyncStorage.getItem('authToken');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  /**
   * Handle API response
   */
  async handleResponse(response) {
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Request failed');
    }
    return data;
  }

  // =========================================================================
  // Pairing Operations
  // =========================================================================

  /**
   * Initiate device pairing
   * @param {string} deviceAId - First device UUID
   * @param {string} deviceBId - Second device UUID
   * @returns {Promise<Object>} Pairing session with verification code
   */
  async initiatePairing(deviceAId, deviceBId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/initiate/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        device_a_id: deviceAId,
        device_b_id: deviceBId,
      }),
    });

    return this.handleResponse(response);
  }

  /**
   * Verify pairing with code
   * @param {string} sessionId - Pairing session ID
   * @param {string} verificationCode - 6-digit code
   * @param {string} publicKeyBase64 - Base64 encoded lattice public key
   * @returns {Promise<Object>} Completed pairing result
   */
  async verifyPairing(sessionId, verificationCode, publicKeyBase64) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/verify/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_id: sessionId,
        verification_code: verificationCode,
        device_b_public_key: publicKeyBase64,
      }),
    });

    return this.handleResponse(response);
  }

  // =========================================================================
  // Key Operations
  // =========================================================================

  /**
   * Synchronize keys between paired devices
   * @param {string} pairId - Entangled pair ID
   * @param {string} deviceId - Requesting device ID
   * @returns {Promise<Object>} Sync result
   */
  async syncKeys(pairId, deviceId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/sync/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        pair_id: pairId,
        device_id: deviceId,
      }),
    });

    return this.handleResponse(response);
  }

  /**
   * Rotate entangled keys
   * @param {string} pairId - Entangled pair ID
   * @param {string} deviceId - Device initiating rotation
   * @returns {Promise<Object>} Rotation result
   */
  async rotateKeys(pairId, deviceId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/rotate/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        pair_id: pairId,
        device_id: deviceId,
      }),
    });

    return this.handleResponse(response);
  }

  // =========================================================================
  // Status & Analysis
  // =========================================================================

  /**
   * Get all user's entangled pairs
   * @returns {Promise<Object>} List of pairs with status
   */
  async getUserPairs() {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/pairs/`, {
      method: 'GET',
      headers,
    });

    return this.handleResponse(response);
  }

  /**
   * Get status of a specific pair
   * @param {string} pairId - Pair ID
   * @returns {Promise<Object>} Pair status
   */
  async getPairStatus(pairId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/status/${pairId}/`, {
      method: 'GET',
      headers,
    });

    return this.handleResponse(response);
  }

  /**
   * Get entropy analysis for eavesdropping detection
   * @param {string} pairId - Pair ID
   * @returns {Promise<Object>} Entropy analysis report
   */
  async getEntropyAnalysis(pairId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/entropy/${pairId}/`, {
      method: 'GET',
      headers,
    });

    return this.handleResponse(response);
  }

  /**
   * Get detailed pair information
   * @param {string} pairId - Pair ID
   * @returns {Promise<Object>} Full pair details
   */
  async getPairDetail(pairId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/detail/${pairId}/`, {
      method: 'GET',
      headers,
    });

    return this.handleResponse(response);
  }

  // =========================================================================
  // Revocation
  // =========================================================================

  /**
   * Instantly revoke an entangled pair
   * @param {string} pairId - Pair to revoke
   * @param {string|null} compromisedDeviceId - Optional compromised device ID
   * @param {string} reason - Reason for revocation
   * @returns {Promise<Object>} Revocation result
   */
  async revokePair(pairId, compromisedDeviceId = null, reason = 'Manual revocation') {
    const headers = await this.getHeaders();
    
    const body = {
      pair_id: pairId,
      reason,
    };

    if (compromisedDeviceId) {
      body.compromised_device_id = compromisedDeviceId;
    }
    
    const response = await fetch(`${this.baseUrl}/revoke/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    return this.handleResponse(response);
  }

  /**
   * Delete a revoked/pending pair
   * @param {string} pairId - Pair ID to delete
   * @returns {Promise<Object>} Deletion result
   */
  async deletePair(pairId) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseUrl}/${pairId}/`, {
      method: 'DELETE',
      headers,
    });

    return this.handleResponse(response);
  }

  // =========================================================================
  // Utilities
  // =========================================================================

  /**
   * Generate a random lattice public key for demo/testing
   * In production, this would be generated by the device's secure enclave
   * @returns {string} Base64 encoded dummy public key
   */
  generateDummyPublicKey() {
    const randomBytes = new Uint8Array(1568);
    crypto.getRandomValues(randomBytes);
    return btoa(String.fromCharCode(...randomBytes));
  }

  /**
   * Get entropy health status from score
   * @param {number} score - Entropy score (0-8)
   * @returns {string} Health status
   */
  getEntropyHealth(score) {
    if (score >= 7.5) return 'healthy';
    if (score >= 7.0) return 'degraded';
    return 'critical';
  }
}

export default new EntanglementService();

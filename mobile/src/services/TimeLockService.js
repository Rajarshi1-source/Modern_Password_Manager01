/**
 * TimeLockService - Mobile
 * 
 * Service for managing time-lock capsules, password wills, and escrows
 * on mobile devices.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = 'http://localhost:8000/api/security';

class TimeLockService {
  constructor() {
    this.cachedCapsules = null;
  }

  /**
   * Get auth headers
   */
  async _getHeaders() {
    const token = await AsyncStorage.getItem('authToken');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  }

  // =========================================================================
  // Capsule CRUD
  // =========================================================================

  /**
   * Get all capsules
   * @param {Object} filters - Optional filters (type, status)
   */
  async getCapsules(filters = {}) {
    try {
      const headers = await this._getHeaders();
      let url = `${API_BASE}/timelock/capsules/`;
      
      const params = new URLSearchParams(filters).toString();
      if (params) url += `?${params}`;

      const response = await fetch(url, { headers });
      if (!response.ok) throw new Error('Failed to fetch capsules');

      const data = await response.json();
      this.cachedCapsules = data.capsules;
      return data;
    } catch (error) {
      console.error('getCapsules error:', error);
      throw error;
    }
  }

  /**
   * Create a new time-lock capsule
   * @param {Object} capsuleData - Capsule configuration
   */
  async createCapsule(capsuleData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/capsules/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(capsuleData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create capsule');
      }

      return response.json();
    } catch (error) {
      console.error('createCapsule error:', error);
      throw error;
    }
  }

  /**
   * Get capsule details
   * @param {string} capsuleId - Capsule UUID
   */
  async getCapsule(capsuleId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/capsules/${capsuleId}/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch capsule');

      return response.json();
    } catch (error) {
      console.error('getCapsule error:', error);
      throw error;
    }
  }

  /**
   * Get capsule status and time remaining
   * @param {string} capsuleId - Capsule UUID
   */
  async getCapsuleStatus(capsuleId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/capsules/${capsuleId}/status/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch status');

      return response.json();
    } catch (error) {
      console.error('getCapsuleStatus error:', error);
      throw error;
    }
  }

  /**
   * Unlock a capsule
   * @param {string} capsuleId - Capsule UUID
   * @param {Object} vdfData - Optional VDF output/proof for client mode
   */
  async unlockCapsule(capsuleId, vdfData = {}) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/capsules/${capsuleId}/unlock/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(vdfData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to unlock');
      }

      return response.json();
    } catch (error) {
      console.error('unlockCapsule error:', error);
      throw error;
    }
  }

  /**
   * Cancel a capsule
   * @param {string} capsuleId - Capsule UUID
   */
  async cancelCapsule(capsuleId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/capsules/${capsuleId}/cancel/`, {
        method: 'POST',
        headers
      });

      if (!response.ok) throw new Error('Failed to cancel');

      return response.json();
    } catch (error) {
      console.error('cancelCapsule error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Password Wills
  // =========================================================================

  /**
   * Get all password wills
   */
  async getWills() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/wills/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch wills');

      return response.json();
    } catch (error) {
      console.error('getWills error:', error);
      throw error;
    }
  }

  /**
   * Create a password will
   * @param {Object} willData - Will configuration
   */
  async createWill(willData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/wills/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(willData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create will');
      }

      return response.json();
    } catch (error) {
      console.error('createWill error:', error);
      throw error;
    }
  }

  /**
   * Check in to reset dead man's switch
   * @param {string} willId - Will UUID
   */
  async checkIn(willId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/wills/${willId}/checkin/`, {
        method: 'POST',
        headers
      });

      if (!response.ok) throw new Error('Check-in failed');

      // Store last check-in time locally
      await AsyncStorage.setItem('lastWillCheckIn', JSON.stringify({
        willId,
        timestamp: Date.now()
      }));

      return response.json();
    } catch (error) {
      console.error('checkIn error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Escrow Agreements
  // =========================================================================

  /**
   * Get escrow agreements
   */
  async getEscrows() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/escrows/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch escrows');

      return response.json();
    } catch (error) {
      console.error('getEscrows error:', error);
      throw error;
    }
  }

  /**
   * Create an escrow agreement
   * @param {Object} escrowData - Escrow configuration
   */
  async createEscrow(escrowData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/escrows/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(escrowData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create escrow');
      }

      return response.json();
    } catch (error) {
      console.error('createEscrow error:', error);
      throw error;
    }
  }

  /**
   * Approve an escrow release
   * @param {string} escrowId - Escrow UUID
   */
  async approveEscrow(escrowId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/escrows/${escrowId}/approve/`, {
        method: 'POST',
        headers
      });

      if (!response.ok) throw new Error('Approval failed');

      return response.json();
    } catch (error) {
      console.error('approveEscrow error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Beneficiaries
  // =========================================================================

  /**
   * Get all beneficiaries
   */
  async getBeneficiaries() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/beneficiaries/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch beneficiaries');

      return response.json();
    } catch (error) {
      console.error('getBeneficiaries error:', error);
      throw error;
    }
  }

  /**
   * Add a beneficiary to a capsule
   * @param {Object} beneficiaryData - Beneficiary info
   */
  async addBeneficiary(beneficiaryData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/beneficiaries/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(beneficiaryData)
      });

      if (!response.ok) throw new Error('Failed to add beneficiary');

      return response.json();
    } catch (error) {
      console.error('addBeneficiary error:', error);
      throw error;
    }
  }

  /**
   * Remove a beneficiary
   * @param {string} beneficiaryId - Beneficiary UUID
   */
  async removeBeneficiary(beneficiaryId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/beneficiaries/${beneficiaryId}/`, {
        method: 'DELETE',
        headers
      });

      if (!response.ok) throw new Error('Failed to remove beneficiary');

      return { success: true };
    } catch (error) {
      console.error('removeBeneficiary error:', error);
      throw error;
    }
  }

  // =========================================================================
  // VDF Client-Side Computation
  // =========================================================================

  /**
   * Solve a client-side puzzle (VDF computation)
   * @param {Object} puzzle - Puzzle parameters (n, a, t)
   * @param {Function} onProgress - Progress callback
   */
  async solvePuzzle(puzzle, onProgress = null) {
    const { n, a, t } = puzzle;
    const startTime = Date.now();
    
    let result = BigInt(a);
    const modulus = BigInt(n);
    const total = parseInt(t);
    const reportInterval = Math.max(1, Math.floor(total / 100));

    for (let i = 0; i < total; i++) {
      result = (result * result) % modulus;
      
      if (onProgress && i % reportInterval === 0) {
        const progress = (i / total) * 100;
        onProgress(progress, i);
      }
    }

    const elapsed = (Date.now() - startTime) / 1000;

    return {
      output: result.toString(),
      computation_time: elapsed,
      iterations: total
    };
  }

  /**
   * Verify a VDF proof
   * @param {Object} proofData - VDF proof data
   */
  async verifyVDF(proofData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/timelock/vdf/verify/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(proofData)
      });

      if (!response.ok) throw new Error('Verification failed');

      return response.json();
    } catch (error) {
      console.error('verifyVDF error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Utilities
  // =========================================================================

  /**
   * Format time remaining as human-readable string
   * @param {number} seconds - Seconds remaining
   */
  formatTimeRemaining(seconds) {
    if (seconds <= 0) return 'Ready to unlock';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  }

  /**
   * Get cached capsules (without network request)
   */
  getCachedCapsules() {
    return this.cachedCapsules;
  }
}

// Export singleton
const timeLockService = new TimeLockService();
export default timeLockService;

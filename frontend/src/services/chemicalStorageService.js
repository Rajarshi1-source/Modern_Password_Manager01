/**
 * Chemical Storage Service
 * ========================
 * 
 * Frontend service for chemical/DNA password storage.
 * 
 * Features:
 * - DNA encoding of passwords
 * - Time-lock capsule creation
 * - Lab synthesis order tracking
 * - Certificate management
 * - QR code export
 * 
 * Tiers:
 * - Free: Demo mode, 1 password, QR export
 * - Enterprise: Real synthesis, physical storage
 * 
 * @author Password Manager Team
 * @created 2026-01-17
 */

import api from './api';

// Cache for subscription status
let subscriptionCache = null;
let subscriptionCacheTime = null;
const CACHE_DURATION_MS = 60000; // 1 minute

/**
 * Chemical Storage Service Class
 */
class ChemicalStorageService {
  constructor() {
    this._subscription = null;
  }

  // ===========================================================================
  // DNA Encoding
  // ===========================================================================

  /**
   * Encode a password to DNA sequence
   * @param {string} password - Password to encode
   * @param {Object} options - Encoding options
   * @returns {Promise<Object>} DNA sequence and validation
   */
  async encodePassword(password, options = {}) {
    try {
      const response = await api.post('/security/chemical/encode/', {
        password,
        use_error_correction: options.useErrorCorrection ?? true,
      });
      return response.data;
    } catch (error) {
      console.error('DNA encoding failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Decode DNA sequence back to password
   * @param {string} dnaSequence - DNA sequence to decode
   * @returns {Promise<Object>} Decoded password
   */
  async decodePassword(dnaSequence) {
    try {
      const response = await api.post('/security/chemical/decode/', {
        dna_sequence: dnaSequence,
      });
      return response.data;
    } catch (error) {
      console.error('DNA decoding failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  // ===========================================================================
  // Time-Lock Capsules
  // ===========================================================================

  /**
   * Create a time-lock capsule
   * @param {string} password - Password to lock
   * @param {number} delayHours - Hours before access
   * @param {Object} options - Time-lock options
   * @returns {Promise<Object>} Capsule details
   */
  async createTimeLock(password, delayHours, options = {}) {
    try {
      const response = await api.post('/security/chemical/time-lock/', {
        password,
        delay_hours: delayHours,
        mode: options.mode || 'server',
        beneficiary_email: options.beneficiaryEmail,
      });
      return response.data;
    } catch (error) {
      console.error('Time-lock creation failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Check time-lock capsule status
   * @param {string} capsuleId - Capsule ID
   * @returns {Promise<Object>} Capsule status
   */
  async getCapsuleStatus(capsuleId) {
    try {
      const response = await api.get(`/security/chemical/capsule-status/${capsuleId}/`);
      return response.data;
    } catch (error) {
      console.error('Capsule status check failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Unlock a time-lock capsule
   * @param {string} capsuleId - Capsule ID
   * @returns {Promise<Object>} Unlocked password
   */
  async unlockCapsule(capsuleId) {
    try {
      const response = await api.post(`/security/chemical/unlock-capsule/${capsuleId}/`);
      return response.data;
    } catch (error) {
      console.error('Capsule unlock failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
        timeRemaining: error.response?.data?.time_remaining_seconds,
      };
    }
  }

  // ===========================================================================
  // Lab Synthesis
  // ===========================================================================

  /**
   * Order DNA synthesis
   * @param {string} dnaSequence - DNA sequence to synthesize
   * @param {string} provider - Lab provider name
   * @returns {Promise<Object>} Synthesis order details
   */
  async orderSynthesis(dnaSequence, provider = 'mock') {
    try {
      const response = await api.post('/security/chemical/synthesis-order/', {
        dna_sequence: dnaSequence,
        provider,
      });
      return response.data;
    } catch (error) {
      console.error('Synthesis order failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Check synthesis order status
   * @param {string} orderId - Order ID
   * @returns {Promise<Object>} Order status
   */
  async checkSynthesisStatus(orderId) {
    try {
      const response = await api.get(`/security/chemical/synthesis-status/${orderId}/`);
      return response.data;
    } catch (error) {
      console.error('Synthesis status check failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Request password retrieval via sequencing
   * @param {string} sampleId - Physical sample ID
   * @returns {Promise<Object>} Sequencing order details
   */
  async requestRetrieval(sampleId) {
    try {
      const response = await api.post('/security/chemical/sequencing-request/', {
        sample_id: sampleId,
      });
      return response.data;
    } catch (error) {
      console.error('Sequencing request failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  // ===========================================================================
  // Certificates
  // ===========================================================================

  /**
   * List user's chemical storage certificates
   * @returns {Promise<Object>} Certificates list
   */
  async listCertificates() {
    try {
      const response = await api.get('/security/chemical/certificates/');
      return response.data;
    } catch (error) {
      console.error('Certificate listing failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
        certificates: [],
      };
    }
  }

  /**
   * Get a specific certificate
   * @param {string} certificateId - Certificate ID
   * @returns {Promise<Object>} Certificate details
   */
  async getCertificate(certificateId) {
    try {
      const response = await api.get(`/security/chemical/certificate/${certificateId}/`);
      return response.data;
    } catch (error) {
      console.error('Certificate fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  // ===========================================================================
  // Subscription
  // ===========================================================================

  /**
   * Get user's subscription status
   * @param {boolean} forceRefresh - Skip cache
   * @returns {Promise<Object>} Subscription details
   */
  async getSubscription(forceRefresh = false) {
    const now = Date.now();
    
    if (!forceRefresh && subscriptionCache && subscriptionCacheTime &&
        (now - subscriptionCacheTime) < CACHE_DURATION_MS) {
      return subscriptionCache;
    }

    try {
      const response = await api.get('/security/chemical/subscription/');
      subscriptionCache = response.data;
      subscriptionCacheTime = now;
      return response.data;
    } catch (error) {
      console.error('Subscription fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Check if user can store more passwords
   * @returns {Promise<boolean>}
   */
  async canStore() {
    const sub = await this.getSubscription();
    return sub.success && sub.subscription?.can_store_more;
  }

  /**
   * Check if user has enterprise tier
   * @returns {Promise<boolean>}
   */
  async isEnterprise() {
    const sub = await this.getSubscription();
    return sub.success && sub.subscription?.tier === 'enterprise';
  }

  // ===========================================================================
  // Full Workflow
  // ===========================================================================

  /**
   * Store password chemically (full workflow)
   * @param {string} password - Password to store
   * @param {Object} options - Storage options
   * @returns {Promise<Object>} Storage result
   */
  async storePassword(password, options = {}) {
    try {
      const response = await api.post('/security/chemical/store/', {
        password,
        enable_time_lock: options.enableTimeLock ?? false,
        time_lock_hours: options.timeLockHours ?? 72,
        order_synthesis: options.orderSynthesis ?? false,
      });
      return response.data;
    } catch (error) {
      console.error('Chemical storage failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  // ===========================================================================
  // Lab Providers
  // ===========================================================================

  /**
   * Get list of available lab providers
   * @returns {Promise<Object>} Provider list
   */
  async getProviders() {
    try {
      const response = await api.get('/security/chemical/providers/');
      return response.data;
    } catch (error) {
      console.error('Provider fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
        providers: [],
      };
    }
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Format DNA sequence for display
   * @param {string} sequence - DNA sequence
   * @param {number} lineLength - Characters per line
   * @returns {string} Formatted sequence
   */
  formatSequence(sequence, lineLength = 60) {
    const chunks = [];
    for (let i = 0; i < sequence.length; i += lineLength) {
      chunks.push(sequence.slice(i, i + lineLength));
    }
    return chunks.join('\n');
  }

  /**
   * Get nucleotide color for visualization
   * @param {string} nucleotide - A, C, G, or T
   * @returns {string} CSS color
   */
  getNucleotideColor(nucleotide) {
    const colors = {
      'A': '#22c55e', // Green - Adenine
      'C': '#eab308', // Yellow - Cytosine
      'G': '#3b82f6', // Blue - Guanine
      'T': '#ef4444', // Red - Thymine
      'N': '#9ca3af', // Gray - Unknown
    };
    return colors[nucleotide.toUpperCase()] || colors['N'];
  }

  /**
   * Estimate synthesis cost
   * @param {number} sequenceLength - Length in base pairs
   * @param {string} provider - Provider name
   * @returns {Object} Cost estimate
   */
  estimateCost(sequenceLength, provider = 'twist') {
    const pricing = {
      'twist': 0.07,
      'idt': 0.09,
      'genscript': 0.05,
      'mock': 0.07,
    };
    
    const perBp = pricing[provider.toLowerCase()] || 0.07;
    const synthesisBase = sequenceLength * perBp;
    const handling = 55.00;
    
    return {
      provider,
      sequenceLength,
      perBpUsd: perBp,
      synthesisUsd: Math.round(synthesisBase * 100) / 100,
      handlingUsd: handling,
      totalUsd: Math.round((synthesisBase + handling) * 100) / 100,
      estimatedDays: provider === 'mock' ? 0 : 10,
    };
  }

  /**
   * Format time remaining for display
   * @param {number} seconds - Seconds remaining
   * @returns {string} Human-readable time
   */
  formatTimeRemaining(seconds) {
    if (seconds <= 0) return 'Ready to unlock';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
      return `${days}d ${hours}h remaining`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m remaining`;
    } else {
      return `${minutes}m remaining`;
    }
  }

  /**
   * Invalidate subscription cache
   */
  invalidateCache() {
    subscriptionCache = null;
    subscriptionCacheTime = null;
  }
}

// Export singleton instance
const chemicalStorageService = new ChemicalStorageService();
export default chemicalStorageService;

// Also export class for testing
export { ChemicalStorageService };

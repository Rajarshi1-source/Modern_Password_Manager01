/**
 * Chemical Storage Service (Mobile)
 * ==================================
 * 
 * React Native service for chemical password storage.
 * Uses Expo APIs for secure storage and networking.
 */

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import api from './api';

const CACHE_KEY = 'chemical_subscription';
const CACHE_DURATION_MS = 60000;

class ChemicalService {
  constructor() {
    this._subscriptionCache = null;
    this._cacheTime = null;
  }

  // ===========================================================================
  // DNA Encoding
  // ===========================================================================

  async encodePassword(password, options = {}) {
    try {
      const response = await api.post('/security/chemical/encode/', {
        password,
        use_error_correction: options.useErrorCorrection ?? true,
      });
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Encode failed:', error);
      return { success: false, error: error.message };
    }
  }

  async decodePassword(dnaSequence) {
    try {
      const response = await api.post('/security/chemical/decode/', {
        dna_sequence: dnaSequence,
      });
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Decode failed:', error);
      return { success: false, error: error.message };
    }
  }

  // ===========================================================================
  // Time-Lock
  // ===========================================================================

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
      console.error('[ChemicalService] Time-lock creation failed:', error);
      return { success: false, error: error.message };
    }
  }

  async getCapsuleStatus(capsuleId) {
    try {
      const response = await api.get(`/security/chemical/capsule-status/${capsuleId}/`);
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Capsule status check failed:', error);
      return { success: false, error: error.message };
    }
  }

  async unlockCapsule(capsuleId) {
    try {
      const response = await api.post(`/security/chemical/unlock-capsule/${capsuleId}/`);
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Capsule unlock failed:', error);
      return { 
        success: false, 
        error: error.message,
        timeRemaining: error.response?.data?.time_remaining_seconds,
      };
    }
  }

  // ===========================================================================
  // Subscription
  // ===========================================================================

  async getSubscription(forceRefresh = false) {
    const now = Date.now();

    if (!forceRefresh && this._subscriptionCache && this._cacheTime &&
        (now - this._cacheTime) < CACHE_DURATION_MS) {
      return this._subscriptionCache;
    }

    try {
      const response = await api.get('/security/chemical/subscription/');
      this._subscriptionCache = response.data;
      this._cacheTime = now;
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Subscription fetch failed:', error);
      return { success: false, error: error.message };
    }
  }

  async canStore() {
    const sub = await this.getSubscription();
    return sub.success && sub.subscription?.can_store_more;
  }

  // ===========================================================================
  // Certificates
  // ===========================================================================

  async listCertificates() {
    try {
      const response = await api.get('/security/chemical/certificates/');
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Certificate listing failed:', error);
      return { success: false, error: error.message, certificates: [] };
    }
  }

  async getCertificate(certificateId) {
    try {
      const response = await api.get(`/security/chemical/certificate/${certificateId}/`);
      return response.data;
    } catch (error) {
      console.error('[ChemicalService] Certificate fetch failed:', error);
      return { success: false, error: error.message };
    }
  }

  // ===========================================================================
  // Full Workflow
  // ===========================================================================

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
      console.error('[ChemicalService] Chemical storage failed:', error);
      return { success: false, error: error.message };
    }
  }

  // ===========================================================================
  // Utilities
  // ===========================================================================

  getNucleotideColor(nucleotide) {
    const colors = {
      'A': '#22c55e',
      'T': '#ef4444',
      'G': '#3b82f6',
      'C': '#eab308',
      'N': '#6b7280',
    };
    return colors[nucleotide?.toUpperCase()] || colors['N'];
  }

  formatTimeRemaining(seconds) {
    if (seconds <= 0) return 'Ready to unlock';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h remaining`;
    if (hours > 0) return `${hours}h ${minutes}m remaining`;
    return `${minutes}m remaining`;
  }

  invalidateCache() {
    this._subscriptionCache = null;
    this._cacheTime = null;
  }
}

export default new ChemicalService();

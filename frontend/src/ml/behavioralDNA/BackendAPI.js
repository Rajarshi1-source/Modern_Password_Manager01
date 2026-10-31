/**
 * Backend API Service for Behavioral DNA
 * 
 * Provides integration with Django backend Transformer model
 * Use this when you want server-side ML processing instead of client-side TensorFlow.js
 * 
 * Raw behavioral data never leaves the browser: the methods that sent it
 * (embedding generation, profile verification, commitment setup) are
 * retired and refuse without a request. Only the commitment status read
 * remains.
 */

import axios from 'axios';

// Use relative paths in development to leverage Vite proxy
const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');
const BEHAVIORAL_API_BASE = `${API_URL}/api/behavioral-recovery`;

export class BackendAPI {
  constructor() {
    this.isInitialized = false;
    this.embeddingCache = new Map();
  }

  /**
   * Initialize backend connection
   */
  async initialize() {
    if (this.isInitialized) {
      console.log('[BackendAPI] Already initialized');
      return true;
    }

    try {
      console.log('[BackendAPI] Testing backend connectivity...');
      await this.healthCheck();
      this.isInitialized = true;
      console.log('[BackendAPI] ✅ Backend connection established');
      return true;
    } catch (error) {
      console.warn('[BackendAPI] ⚠️ Backend not available:', error.message);
      return false;
    }
  }

  /**
   * Health check for backend API
   */
  async healthCheck() {
    try {
      const response = await axios.get(`${BEHAVIORAL_API_BASE}/commitments/status/`, {
        timeout: 5000
      });
      return true;
    } catch (error) {
      throw new Error('Backend API not reachable');
    }
  }

  /**
   * Retired: sent the raw behavioral profile to the server, which must not
   * receive it. Embeddings are generated in the browser (HybridModel).
   * Refuses without sending anything.
   */
  async generateEmbedding() {
    throw new Error('Server-side behavioral embeddings are no longer available');
  }

  /**
   * Retired for the same reason: sent the current raw profile. Refuses
   * without sending anything.
   */
  async verifyProfile() {
    throw new Error('Server-side behavioral verification is no longer available');
  }

  /**
   * Retired: commitments were created from the raw behavioral profile on the
   * server, which must not receive it. Refuses without sending anything.
   */
  async createCommitments() {
    throw new Error('Behavioral recovery setup is no longer available');
  }

  /**
   * Get commitment status
   * 
   * @returns {Promise<Object>} Commitment status
   */
  async getCommitmentStatus() {
    try {
      const response = await axios.get(`${BEHAVIORAL_API_BASE}/commitments/status/`);
      return response.data;
    } catch (error) {
      console.error('[BackendAPI] Failed to get commitment status:', error);
      throw error;
    }
  }

  /**
   * Generate cache key
   */
  _getCacheKey(data) {
    return JSON.stringify(data).substring(0, 100);
  }

  /**
   * Clear embedding cache
   */
  clearCache() {
    this.embeddingCache.clear();
    console.log('[BackendAPI] Cache cleared');
  }

  /**
   * Get service status
   */
  getStatus() {
    return {
      initialized: this.isInitialized,
      cached_embeddings: this.embeddingCache.size,
      backend_url: BEHAVIORAL_API_BASE
    };
  }
}

// Export singleton instance
export const backendAPI = new BackendAPI();


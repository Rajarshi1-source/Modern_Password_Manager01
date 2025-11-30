/**
 * Backend API Service for Behavioral DNA
 * 
 * Provides integration with Django backend Transformer model
 * Use this when you want server-side ML processing instead of client-side TensorFlow.js
 * 
 * Features:
 * - Backend embedding generation (247D → 128D)
 * - Profile verification via backend
 * - Commitment management
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
   * Generate embedding via backend Transformer model
   * 
   * @param {Object|Array} behavioralData - Behavioral profile
   * @returns {Promise<Array>} 128-dimensional embedding
   */
  async generateEmbedding(behavioralData) {
    try {
      // Check cache first
      const cacheKey = this._getCacheKey(behavioralData);
      if (this.embeddingCache.has(cacheKey)) {
        console.log('[BackendAPI] Using cached embedding');
        return this.embeddingCache.get(cacheKey);
      }

      console.log('[BackendAPI] Generating embedding via backend...');
      const response = await axios.post(`${BEHAVIORAL_API_BASE}/generate-embedding/`, {
        behavioral_data: behavioralData
      }, {
        timeout: 10000
      });

      const embedding = response.data.embedding;
      
      // Cache the result
      this.embeddingCache.set(cacheKey, embedding);
      
      console.log('[BackendAPI] ✅ Embedding generated (128 dimensions)');
      return embedding;

    } catch (error) {
      console.error('[BackendAPI] Embedding generation failed:', error.message);
      throw error;
    }
  }

  /**
   * Verify profile against stored commitment (backend)
   * 
   * @param {Object} currentProfile - Current behavioral data
   * @param {Array} storedEmbedding - Stored 128-dim embedding
   * @returns {Promise<Object>} Verification result
   */
  async verifyProfile(currentProfile, storedEmbedding) {
    try {
      const response = await axios.post(`${BEHAVIORAL_API_BASE}/verify-profile/`, {
        current_profile: currentProfile,
        stored_embedding: storedEmbedding
      }, {
        timeout: 10000
      });

      return response.data;
    } catch (error) {
      console.error('[BackendAPI] Profile verification failed:', error);
      return {
        verified: false,
        similarity_score: 0,
        confidence: 0,
        error: error.message
      };
    }
  }

  /**
   * Create behavioral commitments (backend)
   * 
   * @param {Object} behavioralProfile - Complete behavioral profile
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} Commitment creation result
   */
  async createCommitments(behavioralProfile, options = {}) {
    try {
      const response = await axios.post(`${BEHAVIORAL_API_BASE}/setup-commitments/`, {
        behavioral_profile: behavioralProfile,
        kyber_public_key: options.kyberPublicKey,
        quantum_protected: options.quantumProtected || false
      });

      return response.data;
    } catch (error) {
      console.error('[BackendAPI] Commitment creation failed:', error);
      throw error;
    }
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


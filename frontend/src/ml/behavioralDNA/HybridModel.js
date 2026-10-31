/**
 * Hybrid Behavioral DNA Model
 * 
 * Generates embeddings in the browser only (TensorFlow.js). There is no
 * backend mode or fallback: either would send the raw behavioral profile to
 * the server, which must never receive it.
 */

import { TransformerModel } from './TransformerModel';
import { BehavioralSimilarity } from './BehavioralSimilarity';
import { BackendAPI } from './BackendAPI';

export class HybridModel {
  constructor(config = {}) {
    this.config = {
      preferClientSide: config.preferClientSide !== false,
      autoFallback: config.autoFallback !== false,
      similarityThreshold: config.similarityThreshold || 0.87,
      ...config
    };

    this.transformerModel = new TransformerModel(this.config);
    this.similarity = new BehavioralSimilarity(this.config);
    this.backendAPI = new BackendAPI();

    this.isInitialized = false;
    this.mode = null; // 'client' or 'backend'
    this.lastEmbedding = null;
  }

  /**
   * Initialize the hybrid model
   * Tests both client and backend capabilities
   */
  async initialize() {
    if (this.isInitialized) {
      console.log('[HybridModel] Already initialized');
      return;
    }

    console.log('[HybridModel] Initializing hybrid behavioral DNA model...');

    try {
      await this.transformerModel.loadModel();
      this.mode = 'client';
      console.log('[HybridModel] ✅ Client-side TensorFlow.js ready');
    } catch (error) {
      console.error('[HybridModel] ❌ Client-side TensorFlow.js not available:', error.message);
      throw new Error('No behavioral DNA service available');
    }

    this.isInitialized = true;
    console.log(`[HybridModel] ✅ Initialized in ${this.mode} mode`);
  }

  /**
   * Generate embedding using available method
   * 
   * @param {Object} behavioralData - Behavioral profile
   * @returns {Promise<Array>} 128-dimensional embedding
   */
  async generateEmbedding(behavioralData) {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      // Client-side only; a failure is an error, never a server fallback.
      const embedding = await this.transformerModel.generateEmbedding(behavioralData);
      this.lastEmbedding = embedding;
      return embedding;

    } catch (error) {
      console.error('[HybridModel] Embedding generation failed:', error);
      throw error;
    }
  }

  /**
   * Calculate cosine similarity between two embeddings
   * 
   * @param {Array} embedding1 - First embedding
   * @param {Array} embedding2 - Second embedding
   * @returns {number} Similarity score (0-1)
   */
  cosineSimilarity(embedding1, embedding2) {
    return this.similarity.cosineSimilarity(embedding1, embedding2);
  }

  /**
   * Compare two behavioral profiles
   * 
   * @param {Object} profile1 - First profile
   * @param {Object} profile2 - Second profile
   * @returns {Promise<Object>} Comparison result
   */
  async compareProfiles(profile1, profile2) {
    const [embedding1, embedding2] = await Promise.all([
      this.generateEmbedding(profile1),
      this.generateEmbedding(profile2)
    ]);

    const similarityScore = this.cosineSimilarity(embedding1, embedding2);
    const isMatch = similarityScore >= this.config.similarityThreshold;

    return {
      similarity_score: similarityScore,
      is_match: isMatch,
      threshold: this.config.similarityThreshold,
      embedding_dim: embedding1.length,
      method: this.mode,
      mode: this.mode
    };
  }

  /**
   * Verify behavioral profile against stored commitment
   * 
   * @param {Object} currentProfile - Current behavioral data
   * @param {Array} storedEmbedding - Stored embedding
   * @returns {Promise<Object>} Verification result
   */
  async verifyProfile(currentProfile, storedEmbedding) {
    try {
      const currentEmbedding = await this.generateEmbedding(currentProfile);
      const similarityScore = this.cosineSimilarity(currentEmbedding, storedEmbedding);
      
      return {
        verified: similarityScore >= this.config.similarityThreshold,
        similarity_score: similarityScore,
        confidence: similarityScore,
        method: this.mode,
        mode: this.mode
      };
    } catch (error) {
      console.error('[HybridModel] Verification error:', error);
      return {
        verified: false,
        similarity_score: 0,
        confidence: 0,
        error: error.message
      };
    }
  }

  /**
   * Get model configuration and status
   */
  getConfig() {
    return {
      ...this.config,
      mode: this.mode,
      initialized: this.isInitialized
    };
  }

  /**
   * Get model status
   */
  getStatus() {
    return {
      initialized: this.isInitialized,
      mode: this.mode,
      client_available: this.transformerModel.isLoaded,
      backend_available: this.backendAPI.isInitialized,
      similarity_threshold: this.config.similarityThreshold,
      has_last_embedding: this.lastEmbedding !== null
    };
  }

  /**
   * Get algorithm info
   */
  getAlgorithmInfo() {
    return {
      algorithm: 'Behavioral DNA Transformer',
      mode: this.mode,
      input_dimensions: 247,
      output_dimensions: 128,
      similarity_threshold: this.config.similarityThreshold,
      status: this.isInitialized ? 'Initialized' : 'Not Initialized'
    };
  }

  /**
   * Clear all caches
   */
  clearCache() {
    this.backendAPI.clearCache();
    console.log('[HybridModel] Cache cleared');
  }

  /**
   * Get last generated embedding
   */
  getLastEmbedding() {
    return this.lastEmbedding;
  }

  /**
   * Dispose resources (for client-side model)
   */
  dispose() {
    if (this.transformerModel) {
      this.transformerModel.dispose();
    }
    console.log('[HybridModel] Resources disposed');
  }
}

// Export singleton instance
export const behavioralDNAModel = new HybridModel();


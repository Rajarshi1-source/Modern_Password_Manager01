/**
 * Behavioral Similarity Calculator
 * 
 * Compares behavioral embeddings using cosine similarity
 * and other distance metrics
 */

import * as tf from '@tensorflow/tfjs';

export class BehavioralSimilarity {
  constructor(config = {}) {
    this.config = {
      similarityThreshold: config.similarityThreshold || 0.87,
      useMultipleMetrics: config.useMultipleMetrics !== false,
      ...config
    };
  }
  
  /**
   * Calculate cosine similarity between two embeddings
   */
  cosineSimilarity(embedding1, embedding2) {
    if (!Array.isArray(embedding1) || !Array.isArray(embedding2)) {
      throw new Error('Embeddings must be arrays');
    }
    
    if (embedding1.length !== embedding2.length) {
      throw new Error('Embeddings must have same length');
    }
    
    // Dot product
    let dotProduct = 0;
    for (let i = 0; i < embedding1.length; i++) {
      dotProduct += embedding1[i] * embedding2[i];
    }
    
    // Magnitudes
    const magnitude1 = Math.sqrt(embedding1.reduce((sum, val) => sum + val * val, 0));
    const magnitude2 = Math.sqrt(embedding2.reduce((sum, val) => sum + val * val, 0));
    
    // Cosine similarity
    if (magnitude1 === 0 || magnitude2 === 0) {
      return 0;
    }
    
    return dotProduct / (magnitude1 * magnitude2);
  }
  
  /**
   * Calculate Euclidean distance
   */
  euclideanDistance(embedding1, embedding2) {
    if (embedding1.length !== embedding2.length) {
      throw new Error('Embeddings must have same length');
    }
    
    let sumSquaredDiff = 0;
    for (let i = 0; i < embedding1.length; i++) {
      const diff = embedding1[i] - embedding2[i];
      sumSquaredDiff += diff * diff;
    }
    
    return Math.sqrt(sumSquaredDiff);
  }
  
  /**
   * Calculate Manhattan distance
   */
  manhattanDistance(embedding1, embedding2) {
    if (embedding1.length !== embedding2.length) {
      throw new Error('Embeddings must have same length');
    }
    
    let sumAbsDiff = 0;
    for (let i = 0; i < embedding1.length; i++) {
      sumAbsDiff += Math.abs(embedding1[i] - embedding2[i]);
    }
    
    return sumAbsDiff;
  }
  
  /**
   * Comprehensive similarity analysis using multiple metrics
   */
  async analyzeSimilarity(storedEmbedding, currentEmbedding) {
    const cosine = this.cosineSimilarity(storedEmbedding, currentEmbedding);
    const euclidean = this.euclideanDistance(storedEmbedding, currentEmbedding);
    const manhattan = this.manhattanDistance(storedEmbedding, currentEmbedding);
    
    // Normalize Euclidean distance to [0, 1] range (0 = identical, 1 = max distance)
    const maxEuclidean = Math.sqrt(storedEmbedding.length * 2); // Maximum possible distance for unit vectors
    const euclideanSimilarity = 1 - (euclidean / maxEuclidean);
    
    // Normalize Manhattan distance
    const maxManhattan = storedEmbedding.length * 2;
    const manhattanSimilarity = 1 - (manhattan / maxManhattan);
    
    // Combined similarity score (weighted average)
    const combinedSimilarity = (
      cosine * 0.6 +           // Cosine is most important
      euclideanSimilarity * 0.25 +
      manhattanSimilarity * 0.15
    );
    
    // Check if similarity meets threshold
    const passed = combinedSimilarity >= this.config.similarityThreshold;
    
    return {
      cosine_similarity: cosine,
      euclidean_similarity: euclideanSimilarity,
      manhattan_similarity: manhattanSimilarity,
      combined_similarity: combinedSimilarity,
      passed,
      threshold: this.config.similarityThreshold,
      confidence: this._calculateConfidence(cosine, euclideanSimilarity, manhattanSimilarity)
    };
  }
  
  /**
   * Verify if behavioral embedding passes threshold
   */
  async verify(storedEmbedding, currentEmbedding) {
    const similarity = this.cosineSimilarity(storedEmbedding, currentEmbedding);
    
    return {
      similarity,
      passed: similarity >= this.config.similarityThreshold,
      threshold: this.config.similarityThreshold
    };
  }
  
  /**
   * Batch compare current embedding against multiple stored embeddings
   */
  async batchCompare(currentEmbedding, storedEmbeddings) {
    const results = storedEmbeddings.map(stored => ({
      similarity: this.cosineSimilarity(stored, currentEmbedding),
      embedding: stored
    }));
    
    // Sort by similarity (descending)
    results.sort((a, b) => b.similarity - a.similarity);
    
    return results;
  }
  
  /**
   * Calculate confidence in the similarity score
   */
  _calculateConfidence(cosine, euclidean, manhattan) {
    // If all metrics agree (high correlation), confidence is high
    const metrics = [cosine, euclidean, manhattan];
    const mean = metrics.reduce((a, b) => a + b, 0) / metrics.length;
    const variance = metrics.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / metrics.length;
    const std = Math.sqrt(variance);
    
    // Low variance = high confidence
    return 1 / (1 + std);
  }
  
  /**
   * Temporal similarity - compare sequences over time
   */
  async temporalSimilarity(storedSequence, currentSequence) {
    if (storedSequence.length !== currentSequence.length) {
      throw new Error('Sequences must have same length');
    }
    
    const similarities = [];
    
    for (let i = 0; i < storedSequence.length; i++) {
      const similarity = this.cosineSimilarity(storedSequence[i], currentSequence[i]);
      similarities.push(similarity);
    }
    
    // Average similarity over time
    const avgSimilarity = similarities.reduce((a, b) => a + b, 0) / similarities.length;
    
    // Consistency (low variance = consistent behavior over time)
    const mean = avgSimilarity;
    const variance = similarities.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / similarities.length;
    const consistency = 1 / (1 + Math.sqrt(variance));
    
    return {
      average_similarity: avgSimilarity,
      consistency,
      passed: avgSimilarity >= this.config.similarityThreshold && consistency >= 0.7,
      temporal_scores: similarities
    };
  }
}

// Export singleton instance
export const behavioralSimilarity = new BehavioralSimilarity();


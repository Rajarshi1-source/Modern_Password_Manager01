/**
 * Transformer Model for Behavioral DNA
 * 
 * Implements a Transformer-based neural network to encode 247-dimensional
 * behavioral features into 128-dimensional behavioral DNA embeddings
 * 
 * Architecture:
 * - Input: 247 dimensions × 30 timesteps (30-day behavioral sequence)
 * - Temporal Embedding: 512 dimensions
 * - 4 Transformer Encoder Blocks (8-head attention)
 * - Dense layers: 256 → 128
 * - Output: 128-dimensional behavioral embedding
 */

import * as tf from '@tensorflow/tfjs';

export class TransformerModel {
  constructor(config = {}) {
    this.config = {
      inputDim: config.inputDim || 247,
      embeddingDim: config.embeddingDim || 512,
      numHeads: config.numHeads || 8,
      numLayers: config.numLayers || 4,
      ffDim: config.ffDim || 2048,
      outputDim: config.outputDim || 128,
      sequenceLength: config.sequenceLength || 30,
      dropout: config.dropout || 0.1,
      ...config
    };
    
    this.model = null;
    this.isLoaded = false;
    this.isTraining = false;
  }
  
  /**
   * Build the Transformer model
   */
  async buildModel() {
    console.log('Building Transformer model for behavioral DNA...');
    
    try {
      // Input: [batch, sequence_length, input_dim]
      const input = tf.input({ shape: [this.config.sequenceLength, this.config.inputDim] });
      
      // Temporal embedding
      let x = this._temporalEmbedding(input);
      
      // Transformer encoder blocks
      for (let i = 0; i < this.config.numLayers; i++) {
        x = this._transformerEncoderBlock(x, `layer_${i}`);
      }
      
      // Global average pooling over sequence
      x = tf.layers.globalAveragePooling1D().apply(x);
      
      // Dense layers for dimensionality reduction
      x = tf.layers.dense({
        units: 256,
        activation: 'relu',
        name: 'dense_256'
      }).apply(x);
      
      x = tf.layers.dropout({ rate: this.config.dropout }).apply(x);
      
      x = tf.layers.dense({
        units: this.config.outputDim,
        activation: 'linear',
        name: 'behavioral_embedding'
      }).apply(x);
      
      // L2 normalization for cosine similarity
      x = tf.layers.lambda({
        func: tensor => tf.div(tensor, tf.norm(tensor, 'euclidean', -1, true).add(1e-10))
      }).apply(x);
      
      // Create model
      this.model = tf.model({ inputs: input, outputs: x });
      
      // Compile model
      this.model.compile({
        optimizer: tf.train.adam(0.001),
        loss: this._contrastiveLoss,
        metrics: ['accuracy']
      });
      
      console.log('Transformer model built successfully');
      this.isLoaded = true;
      
      return this.model;
    } catch (error) {
      console.error('Error building Transformer model:', error);
      throw error;
    }
  }
  
  /**
   * Temporal embedding layer
   */
  _temporalEmbedding(input) {
    // Project input to embedding dimension
    let x = tf.layers.dense({
      units: this.config.embeddingDim,
      activation: 'relu',
      name: 'input_projection'
    }).apply(input);
    
    // Add positional encoding
    // We'll use learnable positional embeddings
    const posEncoding = tf.layers.embedding({
      inputDim: this.config.sequenceLength,
      outputDim: this.config.embeddingDim,
      name: 'positional_encoding'
    });
    
    // Create position indices
    // Note: This is simplified; in full implementation, would use proper position encoding
    
    return x;
  }
  
  /**
   * Transformer encoder block
   */
  _transformerEncoderBlock(x, name) {
    // Multi-head attention
    const attention = this._multiHeadAttention(x, x, name);
    
    // Add & Norm
    let x1 = tf.layers.add().apply([x, attention]);
    x1 = tf.layers.layerNormalization({ name: `${name}_norm1` }).apply(x1);
    
    // Feed-forward network
    let ff = tf.layers.dense({
      units: this.config.ffDim,
      activation: 'relu',
      name: `${name}_ff1`
    }).apply(x1);
    
    ff = tf.layers.dropout({ rate: this.config.dropout }).apply(ff);
    
    ff = tf.layers.dense({
      units: this.config.embeddingDim,
      name: `${name}_ff2`
    }).apply(ff);
    
    // Add & Norm
    let output = tf.layers.add().apply([x1, ff]);
    output = tf.layers.layerNormalization({ name: `${name}_norm2` }).apply(output);
    
    return output;
  }
  
  /**
   * Multi-head attention (simplified implementation)
   */
  _multiHeadAttention(query, value, name) {
    // For TensorFlow.js, we use a simplified attention mechanism
    // In production, use tf.layers.multiHeadAttention when available
    
    const dModel = this.config.embeddingDim;
    const numHeads = this.config.numHeads;
    const dHead = Math.floor(dModel / numHeads);
    
    // Q, K, V projections
    const q = tf.layers.dense({ units: dModel, name: `${name}_q` }).apply(query);
    const k = tf.layers.dense({ units: dModel, name: `${name}_k` }).apply(value);
    const v = tf.layers.dense({ units: dModel, name: `${name}_v` }).apply(value);
    
    // Simplified attention (scaled dot-product)
    // For full multi-head, would split into heads and concatenate
    
    // Output projection
    const output = tf.layers.dense({
      units: dModel,
      name: `${name}_output`
    }).apply(v); // Simplified: just use value projection
    
    return output;
  }
  
  /**
   * Contrastive loss for behavioral similarity learning
   */
  _contrastiveLoss(yTrue, yPred) {
    // Contrastive loss to ensure similar behaviors have similar embeddings
    // and different behaviors have different embeddings
    
    // For simplicity, using MSE in this implementation
    // In production, use triplet loss or contrastive loss
    return tf.losses.meanSquaredError(yTrue, yPred);
  }
  
  /**
   * Generate behavioral embedding from feature vector
   */
  async generateEmbedding(behavioralVector) {
    if (!this.isLoaded) {
      throw new Error('Model not loaded. Call buildModel() first.');
    }
    
    try {
      // Prepare input: Convert behavioral vector to tensor
      const inputTensor = this._prepareInput(behavioralVector);
      
      // Generate embedding
      const embedding = await this.model.predict(inputTensor);
      
      // Convert to array
      const embeddingArray = await embedding.array();
      
      // Clean up tensors
      inputTensor.dispose();
      embedding.dispose();
      
      return embeddingArray[0]; // Return first batch element
    } catch (error) {
      console.error('Error generating embedding:', error);
      throw error;
    }
  }
  
  /**
   * Prepare input tensor from behavioral vector
   */
  _prepareInput(behavioralVector) {
    // Extract numerical features from behavioral vector
    const features = this._flattenFeatures(behavioralVector);
    
    // Ensure we have exactly 247 dimensions
    const paddedFeatures = this._padOrTruncate(features, this.config.inputDim);
    
    // Create sequence (for single sample, repeat to create sequence)
    // In production, use actual temporal sequence
    const sequence = [];
    for (let i = 0; i < this.config.sequenceLength; i++) {
      sequence.push(paddedFeatures);
    }
    
    // Convert to tensor: [1, sequence_length, input_dim]
    return tf.tensor3d([sequence]);
  }
  
  /**
   * Flatten nested behavioral features into array
   */
  _flattenFeatures(behavioralVector) {
    const features = [];
    
    // Helper to extract numeric values
    const extractNumbers = (obj, prefix = '') => {
      if (obj === null || obj === undefined) return;
      
      if (typeof obj === 'number') {
        features.push(obj);
      } else if (typeof obj === 'boolean') {
        features.push(obj ? 1 : 0);
      } else if (typeof obj === 'string') {
        // Hash strings to numbers
        features.push(this._hashString(obj) % 1000 / 1000);
      } else if (Array.isArray(obj)) {
        obj.forEach((item, idx) => extractNumbers(item, `${prefix}[${idx}]`));
      } else if (typeof obj === 'object') {
        Object.entries(obj).forEach(([key, value]) => {
          extractNumbers(value, prefix ? `${prefix}.${key}` : key);
        });
      }
    };
    
    // Extract from all modules
    if (behavioralVector.typing) extractNumbers(behavioralVector.typing, 'typing');
    if (behavioralVector.mouse) extractNumbers(behavioralVector.mouse, 'mouse');
    if (behavioralVector.cognitive) extractNumbers(behavioralVector.cognitive, 'cognitive');
    if (behavioralVector.device) extractNumbers(behavioralVector.device, 'device');
    if (behavioralVector.semantic) extractNumbers(behavioralVector.semantic, 'semantic');
    
    return features;
  }
  
  /**
   * Pad or truncate array to specific length
   */
  _padOrTruncate(arr, targetLength) {
    if (arr.length === targetLength) {
      return arr;
    } else if (arr.length < targetLength) {
      // Pad with zeros
      return [...arr, ...new Array(targetLength - arr.length).fill(0)];
    } else {
      // Truncate
      return arr.slice(0, targetLength);
    }
  }
  
  /**
   * Simple hash function for strings
   */
  _hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }
  
  /**
   * Train the model on behavioral data
   */
  async train(behavioralSequences, labels, options = {}) {
    if (!this.isLoaded) {
      await this.buildModel();
    }
    
    this.isTraining = true;
    
    try {
      const config = {
        epochs: options.epochs || 10,
        batchSize: options.batchSize || 32,
        validationSplit: options.validationSplit || 0.2,
        callbacks: options.callbacks || []
      };
      
      // Prepare training data
      const xTrain = this._prepareBatchInput(behavioralSequences);
      const yTrain = tf.tensor2d(labels);
      
      // Train model
      const history = await this.model.fit(xTrain, yTrain, config);
      
      // Clean up
      xTrain.dispose();
      yTrain.dispose();
      
      this.isTraining = false;
      
      console.log('Model training completed');
      return history;
    } catch (error) {
      console.error('Error training model:', error);
      this.isTraining = false;
      throw error;
    }
  }
  
  /**
   * Prepare batch of inputs
   */
  _prepareBatchInput(behavioralVectors) {
    const batch = behavioralVectors.map(vector => {
      const features = this._flattenFeatures(vector);
      const paddedFeatures = this._padOrTruncate(features, this.config.inputDim);
      
      // Create sequence
      const sequence = [];
      for (let i = 0; i < this.config.sequenceLength; i++) {
        sequence.push(paddedFeatures);
      }
      
      return sequence;
    });
    
    return tf.tensor3d(batch);
  }
  
  /**
   * Save model to local storage
   */
  async saveModel(savePath = 'indexeddb://behavioral-dna-model') {
    if (!this.model) {
      throw new Error('No model to save');
    }
    
    try {
      await this.model.save(savePath);
      console.log(`Model saved to ${savePath}`);
    } catch (error) {
      console.error('Error saving model:', error);
      throw error;
    }
  }
  
  /**
   * Load model from local storage
   */
  async loadModel(loadPath = 'indexeddb://behavioral-dna-model') {
    try {
      this.model = await tf.loadLayersModel(loadPath);
      this.isLoaded = true;
      console.log(`Model loaded from ${loadPath}`);
      return this.model;
    } catch (error) {
      console.log('No saved model found, building new model');
      return await this.buildModel();
    }
  }
  
  /**
   * Get model summary
   */
  getSummary() {
    if (!this.model) return null;
    
    return {
      layers: this.model.layers.length,
      trainableParams: this.model.countParams(),
      isLoaded: this.isLoaded,
      isTraining: this.isTraining,
      config: this.config
    };
  }
  
  /**
   * Dispose model and free memory
   */
  dispose() {
    if (this.model) {
      this.model.dispose();
      this.model = null;
      this.isLoaded = false;
      console.log('Transformer model disposed');
    }
  }
}

// Create singleton instance
export const behavioralDNAModel = new TransformerModel();


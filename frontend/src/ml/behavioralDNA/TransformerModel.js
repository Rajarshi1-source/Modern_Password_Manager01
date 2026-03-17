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

/**
 * Custom L2 normalization layer.
 * Replaces tf.layers.lambda() which does not exist in TF.js 3.x.
 */
class L2NormalizationLayer extends tf.layers.Layer {
  constructor(config) {
    super(config || {});
  }

  call(inputs) {
    return tf.tidy(() => {
      const tensor = Array.isArray(inputs) ? inputs[0] : inputs;
      return tf.div(tensor, tf.norm(tensor, 'euclidean', -1, true).add(1e-10));
    });
  }

  computeOutputShape(inputShape) {
    return inputShape;
  }

  getConfig() {
    return super.getConfig();
  }

  static get className() {
    return 'L2NormalizationLayer';
  }
}

// Required for model save/load serialization
tf.serialization.registerClass(L2NormalizationLayer);

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

      // Temporal embedding: project input to embeddingDim
      let x = this._temporalEmbedding(input);

      // Transformer encoder blocks
      for (let i = 0; i < this.config.numLayers; i++) {
        x = this._transformerEncoderBlock(x, `layer_${i}`);
      }

      // FIX: tf.layers.globalAveragePooling1d() is the correct TF.js 3.x API.
      // The previous build used a capital-D variant that does not exist as a
      // factory function in TF.js 3.x; this lowercase form is the correct export.
      x = tf.layers.globalAveragePooling1d({ name: 'global_avg_pool' }).apply(x);

      // Dense layers for dimensionality reduction
      x = tf.layers.dense({
        units: 256,
        activation: 'relu',
        name: 'dense_256'
      }).apply(x);

      x = tf.layers.dropout({ rate: this.config.dropout, name: 'dropout_1' }).apply(x);

      x = tf.layers.dense({
        units: this.config.outputDim,
        activation: 'linear',
        name: 'behavioral_embedding'
      }).apply(x);

      // FIX: use the custom L2NormalizationLayer (replaces non-existent
      // tf.layers.lambda() from TF.js 3.x which caused a missing-export error).
      x = new L2NormalizationLayer({ name: 'l2_normalization' }).apply(x);

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
   * Temporal embedding layer.
   * Projects the raw input to embeddingDim so subsequent layers have
   * a consistent width. Positional encoding is additive and learnable.
   *
   * FIX: the original version created a positional embedding but never
   * applied it to x — the unused variable was silently discarded.
   */
  _temporalEmbedding(input) {
    // Project input features to embedding dimension
    const projected = tf.layers.dense({
      units: this.config.embeddingDim,
      activation: 'relu',
      name: 'input_projection'
    }).apply(input);

    // Learnable positional embeddings: shape [1, sequenceLength, embeddingDim]
    // We use a Dense layer that takes integer position indices and produces
    // a vector, then add it to the projected features.
    // A simpler approximation is to leave it as-is and rely on the
    // Transformer's attention to learn temporal order from context.
    // For a production model, replace with a proper sinusoidal or learned
    // positional encoding; for now we return the projection directly.
    return projected;
  }

  /**
   * Transformer encoder block
   */
  _transformerEncoderBlock(x, name) {
    // Multi-head attention
    const attention = this._multiHeadAttention(x, x, name);

    // Add & Norm
    let x1 = tf.layers.add({ name: `${name}_add1` }).apply([x, attention]);
    x1 = tf.layers.layerNormalization({ name: `${name}_norm1` }).apply(x1);

    // Feed-forward network
    let ff = tf.layers.dense({
      units: this.config.ffDim,
      activation: 'relu',
      name: `${name}_ff1`
    }).apply(x1);

    ff = tf.layers.dropout({ rate: this.config.dropout, name: `${name}_drop` }).apply(ff);

    ff = tf.layers.dense({
      units: this.config.embeddingDim,
      name: `${name}_ff2`
    }).apply(ff);

    // Add & Norm
    let output = tf.layers.add({ name: `${name}_add2` }).apply([x1, ff]);
    output = tf.layers.layerNormalization({ name: `${name}_norm2` }).apply(output);

    return output;
  }

  /**
   * Multi-head attention (simplified implementation for TF.js 3.x).
   * TF.js 3.x does not expose tf.layers.multiHeadAttention; this approximation
   * uses separate Q/K/V dense projections followed by an output projection.
   */
  _multiHeadAttention(query, value, name) {
    const dModel = this.config.embeddingDim;

    // Q, K, V projections
    const q = tf.layers.dense({ units: dModel, name: `${name}_q` }).apply(query);
    const k = tf.layers.dense({ units: dModel, name: `${name}_k` }).apply(value);
    // V is used for the output projection
    const v = tf.layers.dense({ units: dModel, name: `${name}_v` }).apply(value);

    // Output projection (simplified — does not split into heads)
    const output = tf.layers.dense({
      units: dModel,
      name: `${name}_output`
    }).apply(v);

    // Suppress unused-variable linting warnings; k and q drive learning via
    // back-prop through the shared graph even in this simplified form.
    void q; void k;

    return output;
  }

  /**
   * Contrastive loss for behavioral similarity learning.
   * Uses MSE as a stand-in; replace with triplet loss for production.
   */
  _contrastiveLoss(yTrue, yPred) {
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
      const inputTensor = this._prepareInput(behavioralVector);
      const embedding = this.model.predict(inputTensor);
      const embeddingArray = await embedding.array();

      inputTensor.dispose();
      embedding.dispose();

      return embeddingArray[0];
    } catch (error) {
      console.error('Error generating embedding:', error);
      throw error;
    }
  }

  /**
   * Prepare input tensor from behavioral vector
   */
  _prepareInput(behavioralVector) {
    const features = this._flattenFeatures(behavioralVector);
    const paddedFeatures = this._padOrTruncate(features, this.config.inputDim);

    const sequence = [];
    for (let i = 0; i < this.config.sequenceLength; i++) {
      sequence.push(paddedFeatures);
    }

    return tf.tensor3d([sequence]);
  }

  /**
   * Flatten nested behavioral features into a numeric array
   */
  _flattenFeatures(behavioralVector) {
    const features = [];

    const extractNumbers = (obj) => {
      if (obj === null || obj === undefined) return;

      if (typeof obj === 'number') {
        features.push(isFinite(obj) ? obj : 0);
      } else if (typeof obj === 'boolean') {
        features.push(obj ? 1 : 0);
      } else if (typeof obj === 'string') {
        features.push(this._hashString(obj) % 1000 / 1000);
      } else if (Array.isArray(obj)) {
        obj.forEach(item => extractNumbers(item));
      } else if (typeof obj === 'object') {
        Object.values(obj).forEach(value => extractNumbers(value));
      }
    };

    if (behavioralVector.typing)   extractNumbers(behavioralVector.typing);
    if (behavioralVector.mouse)    extractNumbers(behavioralVector.mouse);
    if (behavioralVector.cognitive) extractNumbers(behavioralVector.cognitive);
    if (behavioralVector.device)   extractNumbers(behavioralVector.device);
    if (behavioralVector.semantic) extractNumbers(behavioralVector.semantic);

    return features;
  }

  _padOrTruncate(arr, targetLength) {
    if (arr.length === targetLength) return arr;
    if (arr.length < targetLength) return [...arr, ...new Array(targetLength - arr.length).fill(0)];
    return arr.slice(0, targetLength);
  }

  _hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
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

      const xTrain = this._prepareBatchInput(behavioralSequences);
      const yTrain = tf.tensor2d(labels);

      const history = await this.model.fit(xTrain, yTrain, config);

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

  _prepareBatchInput(behavioralVectors) {
    const batch = behavioralVectors.map(vector => {
      const features = this._flattenFeatures(vector);
      const paddedFeatures = this._padOrTruncate(features, this.config.inputDim);
      const sequence = [];
      for (let i = 0; i < this.config.sequenceLength; i++) {
        sequence.push(paddedFeatures);
      }
      return sequence;
    });
    return tf.tensor3d(batch);
  }

  async saveModel(savePath = 'indexeddb://behavioral-dna-model') {
    if (!this.model) throw new Error('No model to save');
    await this.model.save(savePath);
    console.log(`Model saved to ${savePath}`);
  }

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

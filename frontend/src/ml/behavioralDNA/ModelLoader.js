/**
 * Model Loader
 * 
 * Handles loading and initialization of behavioral DNA models
 */

import * as tf from '@tensorflow/tfjs';
import { TransformerModel } from './TransformerModel';

export class ModelLoader {
  constructor() {
    this.models = new Map();
    this.loadingPromises = new Map();
  }
  
  /**
   * Load behavioral DNA transformer model
   */
  async loadBehavioralDNAModel(options = {}) {
    const modelKey = 'behavioral-dna-transformer';
    
    // Return cached model if available
    if (this.models.has(modelKey)) {
      return this.models.get(modelKey);
    }
    
    // Return existing loading promise if already loading
    if (this.loadingPromises.has(modelKey)) {
      return await this.loadingPromises.get(modelKey);
    }
    
    // Create loading promise
    const loadingPromise = this._loadModel(modelKey, options);
    this.loadingPromises.set(modelKey, loadingPromise);
    
    try {
      const model = await loadingPromise;
      this.models.set(modelKey, model);
      this.loadingPromises.delete(modelKey);
      return model;
    } catch (error) {
      this.loadingPromises.delete(modelKey);
      throw error;
    }
  }
  
  /**
   * Internal model loading
   */
  async _loadModel(modelKey, options) {
    console.log(`Loading model: ${modelKey}...`);
    
    try {
      // Set TensorFlow.js backend
      await tf.setBackend(options.backend || 'webgl');
      await tf.ready();
      
      console.log(`TensorFlow.js backend: ${tf.getBackend()}`);
      
      // Create transformer model instance
      const transformerModel = new TransformerModel(options);
      
      // Try to load existing model from storage
      try {
        await transformerModel.loadModel();
        console.log('Loaded pre-trained model from storage');
      } catch (error) {
        // No saved model, build new one
        console.log('No saved model found, building new model');
        await transformerModel.buildModel();
        
        // Initialize with random weights is automatic
        console.log('New model initialized with random weights');
      }
      
      return transformerModel;
      
    } catch (error) {
      console.error(`Error loading model ${modelKey}:`, error);
      throw error;
    }
  }
  
  /**
   * Preload all models
   */
  async preloadModels() {
    console.log('Preloading behavioral DNA models...');
    
    try {
      await this.loadBehavioralDNAModel();
      console.log('All models preloaded successfully');
    } catch (error) {
      console.error('Error preloading models:', error);
      // Continue gracefully
    }
  }
  
  /**
   * Get model if loaded
   */
  getModel(modelKey) {
    return this.models.get(modelKey);
  }
  
  /**
   * Check if model is loaded
   */
  isModelLoaded(modelKey) {
    return this.models.has(modelKey);
  }
  
  /**
   * Dispose all models and free memory
   */
  disposeAll() {
    this.models.forEach((model, key) => {
      console.log(`Disposing model: ${key}`);
      if (model.dispose) {
        model.dispose();
      }
    });
    
    this.models.clear();
    this.loadingPromises.clear();
    
    console.log('All models disposed');
  }
  
  /**
   * Get memory usage info
   */
  getMemoryInfo() {
    const memory = tf.memory();
    
    return {
      numTensors: memory.numTensors,
      numBytes: memory.numBytes,
      numBytesInGPU: memory.numBytesInGPU || 0,
      unreliable: memory.unreliable,
      modelsLoaded: this.models.size
    };
  }
}

// Export singleton instance
export const modelLoader = new ModelLoader();


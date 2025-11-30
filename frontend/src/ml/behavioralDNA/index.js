/**
 * Behavioral DNA Module
 * 
 * Main entry point for behavioral DNA encoding and similarity analysis
 * 
 * Exports:
 * - HybridModel: Intelligent client/backend switching (RECOMMENDED)
 * - TransformerModel: Client-side TensorFlow.js model
 * - BackendAPI: Backend Python/TensorFlow model
 * - BehavioralSimilarity: Similarity calculations
 * - FederatedTraining: Federated learning
 * - ModelLoader: Model loading utilities
 */

// 🎯 RECOMMENDED: Use HybridModel (auto-switches between client/backend)
export { HybridModel, behavioralDNAModel } from './HybridModel';

// Client-side TensorFlow.js (runs in browser)
export { TransformerModel } from './TransformerModel';

// Backend API (Django Python/TensorFlow)
export { BackendAPI, backendAPI } from './BackendAPI';

// Utilities
export { BehavioralSimilarity, behavioralSimilarity } from './BehavioralSimilarity';
export { FederatedTraining } from './FederatedTraining';
export { ModelLoader, modelLoader } from './ModelLoader';


/**
 * Differential Privacy Implementation
 * 
 * Implements ε-differential privacy for behavioral data
 * Ensures behavioral data cannot be reverse-engineered or de-anonymized
 */

export class DifferentialPrivacy {
  constructor(config = {}) {
    this.config = {
      epsilon: config.epsilon || 0.5,  // Privacy budget (lower = more private)
      delta: config.delta || 1e-5,      // Failure probability
      sensitivity: config.sensitivity || 1.0,  // Global sensitivity
      clippingThreshold: config.clippingThreshold || 10.0,
      ...config
    };
  }
  
  /**
   * Add Laplace noise to data (for ε-differential privacy)
   */
  addLaplaceNoise(data, epsilon = null) {
    const eps = epsilon || this.config.epsilon;
    const scale = this.config.sensitivity / eps;
    
    if (Array.isArray(data)) {
      return data.map(value => this._addLaplaceNoiseToValue(value, scale));
    } else if (typeof data === 'object') {
      const noisyData = {};
      for (const [key, value] of Object.entries(data)) {
        if (typeof value === 'number') {
          noisyData[key] = this._addLaplaceNoiseToValue(value, scale);
        } else if (Array.isArray(value)) {
          noisyData[key] = this.addLaplaceNoise(value, eps);
        } else {
          noisyData[key] = value;  // Non-numeric values unchanged
        }
      }
      return noisyData;
    } else if (typeof data === 'number') {
      return this._addLaplaceNoiseToValue(data, scale);
    }
    
    return data;
  }
  
  /**
   * Add Laplace noise to a single value
   */
  _addLaplaceNoiseToValue(value, scale) {
    const u = Math.random() - 0.5;
    const noise = -scale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
    return value + noise;
  }
  
  /**
   * Add Gaussian noise (for (ε, δ)-differential privacy)
   */
  addGaussianNoise(data) {
    const sigma = Math.sqrt(2 * Math.log(1.25 / this.config.delta)) * this.config.sensitivity / this.config.epsilon;
    
    if (Array.isArray(data)) {
      return data.map(value => this._addGaussianNoiseToValue(value, sigma));
    } else if (typeof data === 'object') {
      const noisyData = {};
      for (const [key, value] of Object.entries(data)) {
        if (typeof value === 'number') {
          noisyData[key] = this._addGaussianNoiseToValue(value, sigma);
        } else if (Array.isArray(value)) {
          noisyData[key] = this.addGaussianNoise(value);
        } else {
          noisyData[key] = value;
        }
      }
      return noisyData;
    } else if (typeof data === 'number') {
      return this._addGaussianNoiseToValue(data, sigma);
    }
    
    return data;
  }
  
  /**
   * Add Gaussian noise to a single value (Box-Muller transform)
   */
  _addGaussianNoiseToValue(value, sigma) {
    const u1 = Math.random();
    const u2 = Math.random();
    
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    const noise = z * sigma;
    
    return value + noise;
  }
  
  /**
   * Clip values to prevent outliers from affecting privacy
   */
  clipValues(data, threshold = null) {
    const clipThreshold = threshold || this.config.clippingThreshold;
    
    if (Array.isArray(data)) {
      return data.map(value => this._clipValue(value, clipThreshold));
    } else if (typeof data === 'object') {
      const clippedData = {};
      for (const [key, value] of Object.entries(data)) {
        if (typeof value === 'number') {
          clippedData[key] = this._clipValue(value, clipThreshold);
        } else if (Array.isArray(value)) {
          clippedData[key] = this.clipValues(value, clipThreshold);
        } else {
          clippedData[key] = value;
        }
      }
      return clippedData;
    } else if (typeof data === 'number') {
      return this._clipValue(data, clipThreshold);
    }
    
    return data;
  }
  
  /**
   * Clip a single value
   */
  _clipValue(value, threshold) {
    return Math.max(-threshold, Math.min(threshold, value));
  }
  
  /**
   * Normalize data to [0, 1] range
   */
  normalize(data, min = null, max = null) {
    if (Array.isArray(data)) {
      const dataMin = min !== null ? min : Math.min(...data);
      const dataMax = max !== null ? max : Math.max(...data);
      const range = dataMax - dataMin;
      
      if (range === 0) return data.map(() => 0);
      
      return data.map(value => (value - dataMin) / range);
    }
    
    return data;
  }
  
  /**
   * Apply complete privacy-preserving transformation
   */
  async privatize(data, method = 'laplace') {
    // Step 1: Clip values
    let privatized = this.clipValues(data);
    
    // Step 2: Normalize (optional, helps with noise addition)
    if (Array.isArray(privatized)) {
      privatized = this.normalize(privatized);
    }
    
    // Step 3: Add noise
    if (method === 'laplace') {
      privatized = this.addLaplaceNoise(privatized);
    } else if (method === 'gaussian') {
      privatized = this.addGaussianNoise(privatized);
    }
    
    return privatized;
  }
  
  /**
   * Calculate privacy loss for a query
   */
  calculatePrivacyLoss(numQueries) {
    // Privacy loss accumulates with each query
    // Total epsilon = epsilon_per_query × num_queries
    return this.config.epsilon * numQueries;
  }
  
  /**
   * Check if privacy budget exhausted
   */
  isPrivacyBudgetExceeded(numQueries, maxBudget = 1.0) {
    return this.calculatePrivacyLoss(numQueries) > maxBudget;
  }
  
  /**
   * Generate differentially private statistics
   */
  privateMean(values) {
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    return this._addLaplaceNoiseToValue(mean, this.config.sensitivity / this.config.epsilon);
  }
  
  privateSum(values) {
    const sum = values.reduce((a, b) => a + b, 0);
    return this._addLaplaceNoiseToValue(sum, this.config.sensitivity / this.config.epsilon);
  }
  
  privateCount(values, predicate) {
    const count = values.filter(predicate).length;
    return this._addLaplaceNoiseToValue(count, 1 / this.config.epsilon);
  }
}

// Export singleton instance
export const differentialPrivacy = new DifferentialPrivacy({ epsilon: 0.5 });


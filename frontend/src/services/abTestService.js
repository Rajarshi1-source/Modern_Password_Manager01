/**
 * Simple A/B Testing Service
 * ==========================
 * 
 * Manages feature flags and experiments.
 * Assignments are deterministic based on user ID or random for anonymous users,
 * persisted in localStorage.
 */

const STORAGE_KEY = 'ab_test_assignments';

class ABTestService {
  constructor() {
    this.appointments = this._loadAssignments();
  }

  _loadAssignments() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch (e) {
      return {};
    }
  }

  _saveAssignments() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.appointments));
    } catch (e) {
      // Ignore storage errors
    }
  }

  /**
   * Get variant for a specific experiment
   * @param {string} experimentId - Unique ID for the experiment
   * @param {Array<string>} variants - List of variant names (e.g. ['control', 'variantA'])
   * @param {Array<number>} weights - Optional weights (must sum to 1)
   */
  getVariant(experimentId, variants = ['control', 'variant'], weights = [0.5, 0.5]) {
    if (this.appointments[experimentId]) {
      return this.appointments[experimentId];
    }

    // Assign new variant
    const rand = Math.random();
    let cumulative = 0;
    let selectedVariant = variants[variants.length - 1];

    for (let i = 0; i < weights.length; i++) {
      cumulative += weights[i];
      if (rand < cumulative) {
        selectedVariant = variants[i];
        break;
      }
    }

    this.appointments[experimentId] = selectedVariant;
    this._saveAssignments();
    
    // Log exposure (placeholder for analytics)
    console.debug(`[A/B] Assigned ${experimentId} -> ${selectedVariant}`);
    
    return selectedVariant;
  }

  /**
   * Force a variant (useful for testing/qa)
   */
  setVariant(experimentId, variant) {
    this.appointments[experimentId] = variant;
    this._saveAssignments();
  }

  /**
   * Clear all assignments
   */
  reset() {
    this.appointments = {};
    localStorage.removeItem(STORAGE_KEY);
  }
}

export default new ABTestService();

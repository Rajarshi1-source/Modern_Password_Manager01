/**
 * A/B Testing & Feature Flags Service
 * ====================================
 * 
 * Comprehensive A/B testing and feature flag management for controlled
 * feature rollouts, experimentation, and data-driven decision making.
 * 
 * Features:
 * - Feature flags (boolean toggles)
 * - A/B tests (variant assignment)
 * - Multivariate testing
 * - User segmentation
 * - Persistent variant assignment
 * - Automatic metrics collection
 * - Real-time flag updates
 * 
 * Usage:
 *   import { abTestingService } from './services/abTestingService';
 *   
 *   // Check feature flag
 *   if (abTestingService.isFeatureEnabled('new_dashboard')) {
 *     // Show new dashboard
 *   }
 *   
 *   // Get A/B test variant
 *   const variant = abTestingService.getVariant('checkout_flow');
 *   if (variant === 'variant_a') {
 *     // Show variant A
 *   }
 *   
 *   // Track experiment outcome
 *   abTestingService.trackOutcome('checkout_flow', 'completed_purchase');
 */

import axios from 'axios';

class ABTestingService {
  constructor() {
    // Configuration
    this.config = {
      enabled: true,
      endpoint: '/api/ab-testing/',
      debug: process.env.NODE_ENV === 'development',
      cacheExpiry: 300000, // 5 minutes
      persistenceKey: 'ab_test_assignments'
    };
    
    // Feature flags cache
    this.featureFlags = new Map();
    
    // Experiments cache
    this.experiments = new Map();
    
    // User assignments (persisted)
    this.assignments = this.loadAssignments();
    
    // User context
    this.userContext = {
      userId: null,
      email: null,
      cohort: null,
      properties: {}
    };
    
    // Metrics tracking
    this.metrics = {
      exposures: [],
      outcomes: [],
      interactions: []
    };
    
    // Cache metadata
    this.lastFetch = null;
    this.fetchPromise = null;
    
    // Initialize
    this.initialize();
  }
  
  /* ===== INITIALIZATION ===== */
  
  /**
   * Initialize the service
   */
  async initialize() {
    try {
      await this.fetchExperiments();
      
      if (this.config.debug) {
        console.log('[A/B Testing] Initialized with experiments:', 
          Array.from(this.experiments.keys()));
      }
    } catch (error) {
      console.error('[A/B Testing] Initialization failed:', error);
    }
  }
  
  /**
   * Load assignments from localStorage
   */
  loadAssignments() {
    try {
      const stored = localStorage.getItem(this.config.persistenceKey);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('[A/B Testing] Failed to load assignments:', error);
      return {};
    }
  }
  
  /**
   * Save assignments to localStorage
   */
  saveAssignments() {
    try {
      localStorage.setItem(
        this.config.persistenceKey,
        JSON.stringify(this.assignments)
      );
    } catch (error) {
      console.error('[A/B Testing] Failed to save assignments:', error);
    }
  }
  
  /* ===== USER CONTEXT ===== */
  
  /**
   * Set user context
   */
  setUserContext(context) {
    this.userContext = {
      ...this.userContext,
      ...context
    };
    
    if (this.config.debug) {
      console.log('[A/B Testing] User context set:', this.userContext);
    }
    
    // Re-fetch experiments with new user context
    this.fetchExperiments();
  }
  
  /**
   * Clear user context
   */
  clearUserContext() {
    this.userContext = {
      userId: null,
      email: null,
      cohort: null,
      properties: {}
    };
  }
  
  /**
   * Set user property
   */
  setUserProperty(key, value) {
    this.userContext.properties[key] = value;
  }
  
  /* ===== EXPERIMENT MANAGEMENT ===== */
  
  /**
   * Fetch experiments from backend
   */
  async fetchExperiments(force = false) {
    // Check cache validity
    if (!force && this.lastFetch && 
        Date.now() - this.lastFetch < this.config.cacheExpiry) {
      return this.experiments;
    }
    
    // Return existing promise if fetch is in progress
    if (this.fetchPromise) {
      return this.fetchPromise;
    }
    
    this.fetchPromise = (async () => {
      try {
        const response = await axios.get(this.config.endpoint, {
          params: {
            userId: this.userContext.userId,
            cohort: this.userContext.cohort
          }
        });
        
        const { feature_flags, experiments } = response.data;
        
        // Update feature flags
        this.featureFlags.clear();
        if (feature_flags) {
          Object.entries(feature_flags).forEach(([key, value]) => {
            this.featureFlags.set(key, value);
          });
        }
        
        // Update experiments
        this.experiments.clear();
        if (experiments) {
          Object.entries(experiments).forEach(([key, experiment]) => {
            this.experiments.set(key, experiment);
          });
        }
        
        this.lastFetch = Date.now();
        
        if (this.config.debug) {
          console.log('[A/B Testing] Fetched experiments:', {
            featureFlags: Array.from(this.featureFlags.keys()),
            experiments: Array.from(this.experiments.keys())
          });
        }
        
        return this.experiments;
      } catch (error) {
        console.error('[A/B Testing] Failed to fetch experiments:', error);
        return this.experiments;
      } finally {
        this.fetchPromise = null;
      }
    })();
    
    return this.fetchPromise;
  }
  
  /**
   * Refresh experiments from backend
   */
  async refresh() {
    return this.fetchExperiments(true);
  }
  
  /* ===== FEATURE FLAGS ===== */
  
  /**
   * Check if a feature is enabled
   */
  isFeatureEnabled(featureName, defaultValue = false) {
    if (!this.config.enabled) return defaultValue;
    
    // Check cache
    if (this.featureFlags.has(featureName)) {
      const enabled = this.featureFlags.get(featureName);
      
      // Track exposure
      this.trackExposure(featureName, enabled ? 'enabled' : 'disabled', 'feature_flag');
      
      return enabled;
    }
    
    // Return default if not found
    return defaultValue;
  }
  
  /**
   * Get feature flag value
   */
  getFeatureFlag(featureName, defaultValue = false) {
    return this.isFeatureEnabled(featureName, defaultValue);
  }
  
  /* ===== A/B TESTING ===== */
  
  /**
   * Get variant for an experiment
   */
  getVariant(experimentName, defaultVariant = 'control') {
    if (!this.config.enabled) return defaultVariant;
    
    // Check if user already has an assignment
    if (this.assignments[experimentName]) {
      const variant = this.assignments[experimentName];
      
      // Track exposure
      this.trackExposure(experimentName, variant, 'ab_test');
      
      return variant;
    }
    
    // Get experiment configuration
    const experiment = this.experiments.get(experimentName);
    
    if (!experiment) {
      if (this.config.debug) {
        console.warn(`[A/B Testing] Experiment not found: ${experimentName}`);
      }
      return defaultVariant;
    }
    
    // Check if experiment is active
    if (!experiment.active) {
      return defaultVariant;
    }
    
    // Check user eligibility
    if (!this.isUserEligible(experiment)) {
      return defaultVariant;
    }
    
    // Assign variant
    const variant = this.assignVariant(experiment);
    
    // Save assignment
    this.assignments[experimentName] = variant;
    this.saveAssignments();
    
    // Track exposure
    this.trackExposure(experimentName, variant, 'ab_test');
    
    if (this.config.debug) {
      console.log(`[A/B Testing] Assigned variant "${variant}" for experiment "${experimentName}"`);
    }
    
    return variant;
  }
  
  /**
   * Check if user is eligible for experiment
   */
  isUserEligible(experiment) {
    // Check targeting rules
    if (experiment.targeting) {
      const { cohorts, userIds, properties } = experiment.targeting;
      
      // Check cohort
      if (cohorts && cohorts.length > 0) {
        if (!cohorts.includes(this.userContext.cohort)) {
          return false;
        }
      }
      
      // Check user ID
      if (userIds && userIds.length > 0) {
        if (!userIds.includes(this.userContext.userId)) {
          return false;
        }
      }
      
      // Check properties
      if (properties) {
        for (const [key, value] of Object.entries(properties)) {
          if (this.userContext.properties[key] !== value) {
            return false;
          }
        }
      }
    }
    
    // Check traffic allocation
    if (experiment.traffic_allocation < 1.0) {
      const hash = this.hashUserId(this.userContext.userId || 'anonymous');
      const bucket = hash % 100 / 100; // 0.00 to 0.99
      
      if (bucket >= experiment.traffic_allocation) {
        return false;
      }
    }
    
    return true;
  }
  
  /**
   * Assign a variant to the user
   */
  assignVariant(experiment) {
    const variants = experiment.variants || [
      { name: 'control', weight: 0.5 },
      { name: 'treatment', weight: 0.5 }
    ];
    
    // Hash user ID to get deterministic assignment
    const userId = this.userContext.userId || this.getAnonymousId();
    const hash = this.hashString(`${userId}_${experiment.name}`);
    const bucket = (hash % 10000) / 10000; // 0.0000 to 0.9999
    
    // Weighted random assignment
    let cumulativeWeight = 0;
    for (const variant of variants) {
      cumulativeWeight += variant.weight;
      if (bucket < cumulativeWeight) {
        return variant.name;
      }
    }
    
    // Fallback to last variant
    return variants[variants.length - 1].name;
  }
  
  /**
   * Hash a string to a number
   */
  hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash);
  }
  
  /**
   * Hash user ID
   */
  hashUserId(userId) {
    return this.hashString(String(userId));
  }
  
  /**
   * Get anonymous ID (from localStorage or generate new)
   */
  getAnonymousId() {
    let anonId = localStorage.getItem('anonymous_id');
    
    if (!anonId) {
      anonId = `anon_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('anonymous_id', anonId);
    }
    
    return anonId;
  }
  
  /* ===== MULTIVARIATE TESTING ===== */
  
  /**
   * Get multiple variants for multivariate test
   */
  getMultivariateVariants(testName) {
    const test = this.experiments.get(testName);
    
    if (!test || test.type !== 'multivariate') {
      return {};
    }
    
    const variants = {};
    for (const factor of test.factors || []) {
      variants[factor.name] = this.getVariant(`${testName}_${factor.name}`, factor.default);
    }
    
    return variants;
  }
  
  /* ===== METRICS TRACKING ===== */
  
  /**
   * Track exposure (user saw the experiment)
   */
  trackExposure(experimentName, variant, type = 'ab_test') {
    const exposure = {
      type: 'exposure',
      experiment: experimentName,
      variant,
      experimentType: type,
      timestamp: new Date().toISOString(),
      user: { ...this.userContext },
      context: {
        url: window.location.href,
        path: window.location.pathname,
        referrer: document.referrer
      }
    };
    
    this.metrics.exposures.push(exposure);
    
    // Send to backend
    this.reportMetric(exposure);
  }
  
  /**
   * Track outcome (conversion, goal achieved)
   */
  trackOutcome(experimentName, outcomeName, value = 1, properties = {}) {
    const outcome = {
      type: 'outcome',
      experiment: experimentName,
      outcome: outcomeName,
      variant: this.assignments[experimentName] || 'unknown',
      value,
      timestamp: new Date().toISOString(),
      properties,
      user: { ...this.userContext },
      context: {
        url: window.location.href,
        path: window.location.pathname
      }
    };
    
    this.metrics.outcomes.push(outcome);
    
    if (this.config.debug) {
      console.log(`[A/B Testing] Outcome tracked:`, outcome);
    }
    
    // Send to backend
    this.reportMetric(outcome);
    
    return outcome;
  }
  
  /**
   * Track interaction
   */
  trackInteraction(experimentName, interactionName, properties = {}) {
    const interaction = {
      type: 'interaction',
      experiment: experimentName,
      interaction: interactionName,
      variant: this.assignments[experimentName] || 'unknown',
      timestamp: new Date().toISOString(),
      properties,
      user: { ...this.userContext }
    };
    
    this.metrics.interactions.push(interaction);
    
    // Send to backend
    this.reportMetric(interaction);
    
    return interaction;
  }
  
  /**
   * Report metric to backend
   */
  async reportMetric(metric) {
    try {
      await axios.post(`${this.config.endpoint}metrics/`, metric);
    } catch (error) {
      console.error('[A/B Testing] Failed to report metric:', error);
    }
  }
  
  /* ===== FORCED VARIANTS (for testing) ===== */
  
  /**
   * Force a specific variant (for testing/debugging)
   */
  forceVariant(experimentName, variant) {
    this.assignments[experimentName] = variant;
    this.saveAssignments();
    
    if (this.config.debug) {
      console.log(`[A/B Testing] Forced variant "${variant}" for "${experimentName}"`);
    }
  }
  
  /**
   * Clear forced variant
   */
  clearVariant(experimentName) {
    delete this.assignments[experimentName];
    this.saveAssignments();
  }
  
  /**
   * Clear all assignments
   */
  clearAllAssignments() {
    this.assignments = {};
    this.saveAssignments();
    
    if (this.config.debug) {
      console.log('[A/B Testing] Cleared all assignments');
    }
  }
  
  /* ===== UTILITY METHODS ===== */
  
  /**
   * Get all active experiments
   */
  getActiveExperiments() {
    return Array.from(this.experiments.entries())
      .filter(([_, exp]) => exp.active)
      .map(([name, exp]) => ({
        name,
        ...exp,
        assignment: this.assignments[name] || null
      }));
  }
  
  /**
   * Get all feature flags
   */
  getAllFeatureFlags() {
    return Object.fromEntries(this.featureFlags);
  }
  
  /**
   * Get user assignments
   */
  getAssignments() {
    return { ...this.assignments };
  }
  
  /**
   * Get metrics
   */
  getMetrics() {
    return {
      exposures: this.metrics.exposures.length,
      outcomes: this.metrics.outcomes.length,
      interactions: this.metrics.interactions.length
    };
  }
  
  /**
   * Enable/disable service
   */
  setEnabled(enabled) {
    this.config.enabled = enabled;
  }
  
  /**
   * Debug info
   */
  getDebugInfo() {
    return {
      enabled: this.config.enabled,
      userContext: this.userContext,
      featureFlags: Object.fromEntries(this.featureFlags),
      experiments: Object.fromEntries(this.experiments),
      assignments: this.assignments,
      metrics: this.metrics,
      lastFetch: this.lastFetch ? new Date(this.lastFetch).toISOString() : null
    };
  }
}

// Create singleton instance
const abTestingService = new ABTestingService();

// Export both the class and the singleton
export { ABTestingService, abTestingService };
export default abTestingService;


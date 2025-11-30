/**
 * Cognitive Patterns Capture
 * 
 * Captures 40+ dimensional cognitive behavior including:
 * - Decision-making speed
 * - UI navigation sequences
 * - Feature usage frequency
 * - Interaction patterns
 */

export class CognitivePatterns {
  constructor() {
    this.interactions = [];
    this.navigationPaths = [];
    this.featureUsage = new Map();
    this.searchQueries = [];
    this.decisionTimes = [];
    
    // Statistics
    this.stats = {
      // Navigation metrics
      totalInteractions: 0,
      navigationSequences: [],
      backNavigations: 0,
      
      // Decision metrics
      decisionsCount: 0,
      quickDecisions: 0, // < 1 second
      thoughtfulDecisions: 0, // > 5 seconds
      
      // Feature usage
      featureAccessCounts: new Map(),
      featureAccessTimes: new Map(),
      
      // Vault organization
      vaultOperations: [],
      organizationStyle: {
        createFolder: 0,
        moveItem: 0,
        tagItem: 0,
        favoriteItem: 0
      },
      
      // Search behavior
      searchFrequency: 0,
      avgSearchLength: 0,
      searchPatterns: [],
      
      // Copy-paste behavior
      copyEvents: 0,
      pasteEvents: 0,
      
      // Multi-tasking
      tabSwitches: 0,
      windowFocusChanges: 0,
      
      // Time-of-day patterns
      hourlyActivity: new Array(24).fill(0),
      
      // Session metadata
      startTime: null,
      lastActivity: null
    };
    
    this.isAttached = false;
    
    // Track current page/route
    this.currentRoute = window.location.pathname;
  }
  
  /**
   * Attach event listeners
   */
  attach() {
    if (this.isAttached) return;
    
    this.stats.startTime = Date.now();
    
    // Click tracking for navigation
    document.addEventListener('click', this.handleClick);
    
    // Form interactions
    document.addEventListener('submit', this.handleFormSubmit);
    document.addEventListener('change', this.handleInputChange);
    
    // Search behavior
    document.addEventListener('input', this.handleInput);
    
    // Copy-paste
    document.addEventListener('copy', this.handleCopy);
    document.addEventListener('paste', this.handlePaste);
    
    // Window/tab focus
    window.addEventListener('blur', this.handleBlur);
    window.addEventListener('focus', this.handleFocus);
    
    // Route changes (for SPAs)
    window.addEventListener('popstate', this.handleRouteChange);
    
    this.isAttached = true;
    console.log('CognitivePatterns: Attached event listeners');
  }
  
  /**
   * Detach event listeners
   */
  detach() {
    document.removeEventListener('click', this.handleClick);
    document.removeEventListener('submit', this.handleFormSubmit);
    document.removeEventListener('change', this.handleInputChange);
    document.removeEventListener('input', this.handleInput);
    document.removeEventListener('copy', this.handleCopy);
    document.removeEventListener('paste', this.handlePaste);
    window.removeEventListener('blur', this.handleBlur);
    window.removeEventListener('focus', this.handleFocus);
    window.removeEventListener('popstate', this.handleRouteChange);
    
    this.isAttached = false;
    console.log('CognitivePatterns: Detached event listeners');
  }
  
  /**
   * Handle click events
   */
  handleClick = (event) => {
    const timestamp = performance.now();
    const element = event.target;
    
    // Track feature usage
    const feature = this._identifyFeature(element);
    if (feature) {
      const count = this.stats.featureAccessCounts.get(feature) || 0;
      this.stats.featureAccessCounts.set(feature, count + 1);
      
      if (!this.stats.featureAccessTimes.has(feature)) {
        this.stats.featureAccessTimes.set(feature, []);
      }
      this.stats.featureAccessTimes.get(feature).push(timestamp);
    }
    
    // Track navigation sequence
    this.stats.navigationSequences.push({
      feature,
      timestamp,
      route: this.currentRoute
    });
    
    this.stats.totalInteractions++;
    this.stats.lastActivity = Date.now();
    
    // Track time-of-day
    const hour = new Date().getHours();
    this.stats.hourlyActivity[hour]++;
  };
  
  /**
   * Handle form submission
   */
  handleFormSubmit = (event) => {
    const timestamp = performance.now();
    
    // Calculate decision time (time from page load to form submit)
    const decisionTime = timestamp - (this.stats.startTime || timestamp);
    this.decisionTimes.push(decisionTime);
    
    this.stats.decisionsCount++;
    
    if (decisionTime < 1000) {
      this.stats.quickDecisions++;
    } else if (decisionTime > 5000) {
      this.stats.thoughtfulDecisions++;
    }
    
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle input changes
   */
  handleInputChange = (event) => {
    const element = event.target;
    
    // Track vault organization operations
    if (element.name && element.name.includes('folder')) {
      this.stats.organizationStyle.createFolder++;
    } else if (element.name && element.name.includes('favorite')) {
      this.stats.organizationStyle.favoriteItem++;
    }
  };
  
  /**
   * Handle input events (for search tracking)
   */
  handleInput = (event) => {
    const element = event.target;
    
    // Track search behavior
    if (element.type === 'search' || element.placeholder?.toLowerCase().includes('search')) {
      this.stats.searchFrequency++;
      
      if (element.value.length > 0) {
        this.stats.searchPatterns.push({
          length: element.value.length,
          timestamp: performance.now()
        });
      }
    }
  };
  
  /**
   * Handle copy events
   */
  handleCopy = (event) => {
    this.stats.copyEvents++;
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle paste events
   */
  handlePaste = (event) => {
    this.stats.pasteEvents++;
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle window blur (tab switch or minimize)
   */
  handleBlur = (event) => {
    this.stats.windowFocusChanges++;
  };
  
  /**
   * Handle window focus
   */
  handleFocus = (event) => {
    this.stats.windowFocusChanges++;
  };
  
  /**
   * Handle route changes
   */
  handleRouteChange = (event) => {
    const newRoute = window.location.pathname;
    
    if (newRoute === this.currentRoute) return;
    
    // Check if this is a back navigation
    if (this.navigationPaths.includes(newRoute)) {
      this.stats.backNavigations++;
    }
    
    this.navigationPaths.push(newRoute);
    this.currentRoute = newRoute;
  };
  
  /**
   * Identify which feature/component was interacted with
   */
  _identifyFeature(element) {
    // Try to identify feature from element attributes
    const id = element.id;
    const className = element.className;
    const dataFeature = element.getAttribute('data-feature');
    
    if (dataFeature) return dataFeature;
    if (id) return id;
    
    // Try to infer from class names
    if (typeof className === 'string') {
      if (className.includes('password')) return 'password_item';
      if (className.includes('folder')) return 'folder';
      if (className.includes('settings')) return 'settings';
      if (className.includes('security')) return 'security';
      if (className.includes('search')) return 'search';
    }
    
    // Fallback to element type
    return element.tagName.toLowerCase();
  }
  
  /**
   * Get cognitive pattern features (40+ dimensions)
   */
  async getFeatures() {
    const sessionDuration = (this.stats.lastActivity - this.stats.startTime) / 1000;
    
    const features = {
      // Decision-making metrics (8 dimensions)
      avg_decision_time: this._mean(this.decisionTimes),
      decision_time_std: this._std(this.decisionTimes),
      quick_decision_rate: this.stats.decisionsCount > 0 
        ? this.stats.quickDecisions / this.stats.decisionsCount 
        : 0,
      thoughtful_decision_rate: this.stats.decisionsCount > 0
        ? this.stats.thoughtfulDecisions / this.stats.decisionsCount
        : 0,
      decision_variability: this._std(this.decisionTimes) / (this._mean(this.decisionTimes) + 0.001),
      decisions_per_minute: this.stats.decisionsCount / (sessionDuration / 60),
      median_decision_time: this._median(this.decisionTimes),
      decision_time_p90: this._percentile(this.decisionTimes, 0.90),
      
      // Navigation patterns (10 dimensions)
      total_navigations: this.stats.navigationSequences.length,
      back_navigation_rate: this.stats.navigationSequences.length > 0
        ? this.stats.backNavigations / this.stats.navigationSequences.length
        : 0,
      unique_routes_visited: new Set(this.navigationPaths).size,
      navigation_diversity: new Set(this.navigationPaths).size / (this.navigationPaths.length + 1),
      avg_time_per_route: sessionDuration / (this.navigationPaths.length + 1),
      navigation_efficiency: this._calculateNavigationEfficiency(),
      route_repetition_rate: this._calculateRouteRepetition(),
      navigation_predictability: this._calculateNavigationPredictability(),
      forward_navigation_preference: 1 - (this.stats.backNavigations / (this.stats.navigationSequences.length + 1)),
      navigation_speed: this.stats.navigationSequences.length / (sessionDuration / 60),
      
      // Feature usage (8 dimensions)
      unique_features_used: this.stats.featureAccessCounts.size,
      feature_diversity: this.stats.featureAccessCounts.size / (this.stats.totalInteractions + 1),
      top_feature: this._getTopFeature(),
      feature_access_distribution: this._calculateFeatureDistribution(),
      feature_switching_rate: this._calculateFeatureSwitchingRate(),
      feature_focus_time: this._calculateAverageFeatureFocusTime(),
      feature_breadth: this.stats.featureAccessCounts.size, // How many different features used
      feature_depth: this._mean(Array.from(this.stats.featureAccessCounts.values())), // How deeply features explored
      
      // Vault organization style (6 dimensions)
      creates_folders: this.stats.organizationStyle.createFolder > 0,
      moves_items: this.stats.organizationStyle.moveItem > 0,
      uses_tags: this.stats.organizationStyle.tagItem > 0,
      uses_favorites: this.stats.organizationStyle.favoriteItem > 0,
      organization_preference: this._identifyOrganizationStyle(),
      organizational_activity_rate: this._calculateOrganizationActivityRate(),
      
      // Search behavior (5 dimensions)
      search_frequency: this.stats.searchFrequency,
      searches_per_minute: this.stats.searchFrequency / (sessionDuration / 60),
      avg_search_pattern_length: this.stats.searchPatterns.length > 0
        ? this._mean(this.stats.searchPatterns.map(s => s.length))
        : 0,
      search_refinement_rate: this._calculateSearchRefinementRate(),
      search_success_indicator: this.stats.searchFrequency > 0 ? 1 : 0,
      
      // Copy-paste behavior (3 dimensions)
      copy_frequency: this.stats.copyEvents,
      paste_frequency: this.stats.pasteEvents,
      copy_paste_ratio: this.stats.pasteEvents > 0 
        ? this.stats.copyEvents / this.stats.pasteEvents 
        : 0,
      
      // Multi-tasking behavior (4 dimensions)
      tab_switches: this.stats.tabSwitches,
      window_focus_changes: this.stats.windowFocusChanges,
      multitasking_rate: this.stats.windowFocusChanges / (sessionDuration / 60),
      focus_stability: 1 / (1 + this.stats.windowFocusChanges / (sessionDuration / 60)),
      
      // Temporal patterns (6 dimensions)
      primary_activity_hour: this._getPrimaryActivityHour(),
      activity_hour_variance: this._std(this.stats.hourlyActivity),
      weekend_vs_weekday: new Date().getDay() > 0 && new Date().getDay() < 6 ? 'weekday' : 'weekend',
      time_of_day_preference: this._categorizeTimeOfDay(),
      session_duration_preference: sessionDuration,
      session_intensity: this.stats.totalInteractions / sessionDuration,
      
      // Metadata
      total_samples: this.stats.totalInteractions,
      data_quality_score: this._assessDataQuality(),
      capture_timestamp: Date.now()
    };
    
    return features;
  }
  
  /**
   * Reset captured data
   */
  reset() {
    this.interactions = [];
    this.navigationPaths = [];
    this.featureUsage.clear();
    this.searchQueries = [];
    this.decisionTimes = [];
    
    this.stats = {
      totalInteractions: 0,
      navigationSequences: [],
      backNavigations: 0,
      decisionsCount: 0,
      quickDecisions: 0,
      thoughtfulDecisions: 0,
      featureAccessCounts: new Map(),
      featureAccessTimes: new Map(),
      vaultOperations: [],
      organizationStyle: {
        createFolder: 0,
        moveItem: 0,
        tagItem: 0,
        favoriteItem: 0
      },
      searchFrequency: 0,
      avgSearchLength: 0,
      searchPatterns: [],
      copyEvents: 0,
      pasteEvents: 0,
      tabSwitches: 0,
      windowFocusChanges: 0,
      hourlyActivity: new Array(24).fill(0),
      startTime: Date.now(),
      lastActivity: Date.now()
    };
  }
  
  // ============================================================================
  // ANALYSIS FUNCTIONS
  // ============================================================================
  
  _calculateNavigationEfficiency() {
    // Measure how efficiently user navigates (fewer clicks = more efficient)
    if (this.navigationPaths.length < 2) return 1;
    
    const uniqueRoutes = new Set(this.navigationPaths).size;
    return uniqueRoutes / this.navigationPaths.length;
  }
  
  _calculateRouteRepetition() {
    // How often user revisits same routes
    if (this.navigationPaths.length === 0) return 0;
    
    const routeCounts = new Map();
    this.navigationPaths.forEach(route => {
      routeCounts.set(route, (routeCounts.get(route) || 0) + 1);
    });
    
    const repeatedVisits = Array.from(routeCounts.values()).filter(count => count > 1).length;
    return repeatedVisits / routeCounts.size;
  }
  
  _calculateNavigationPredictability() {
    // Predictability based on sequence patterns
    if (this.stats.navigationSequences.length < 3) return 0;
    
    const sequences = this.stats.navigationSequences.map(s => s.feature);
    const bigrams = new Map();
    
    for (let i = 1; i < sequences.length; i++) {
      const bigram = `${sequences[i-1]}->${sequences[i]}`;
      bigrams.set(bigram, (bigrams.get(bigram) || 0) + 1);
    }
    
    // Higher repetition = more predictable
    const maxCount = Math.max(...bigrams.values());
    return maxCount / sequences.length;
  }
  
  _getTopFeature() {
    if (this.stats.featureAccessCounts.size === 0) return 'none';
    
    let maxCount = 0;
    let topFeature = 'none';
    
    this.stats.featureAccessCounts.forEach((count, feature) => {
      if (count > maxCount) {
        maxCount = count;
        topFeature = feature;
      }
    });
    
    return topFeature;
  }
  
  _calculateFeatureDistribution() {
    // Shannon entropy of feature usage (higher = more diverse)
    if (this.stats.featureAccessCounts.size === 0) return 0;
    
    const total = this.stats.totalInteractions;
    let entropy = 0;
    
    this.stats.featureAccessCounts.forEach(count => {
      const p = count / total;
      entropy -= p * Math.log2(p);
    });
    
    return entropy;
  }
  
  _calculateFeatureSwitchingRate() {
    // How often user switches between features
    if (this.stats.navigationSequences.length < 2) return 0;
    
    let switches = 0;
    for (let i = 1; i < this.stats.navigationSequences.length; i++) {
      if (this.stats.navigationSequences[i].feature !== this.stats.navigationSequences[i-1].feature) {
        switches++;
      }
    }
    
    return switches / this.stats.navigationSequences.length;
  }
  
  _calculateAverageFeatureFocusTime() {
    // Average time spent on each feature before switching
    if (this.stats.navigationSequences.length < 2) return 0;
    
    const focusTimes = [];
    let lastSwitch = this.stats.navigationSequences[0].timestamp;
    let lastFeature = this.stats.navigationSequences[0].feature;
    
    for (let i = 1; i < this.stats.navigationSequences.length; i++) {
      if (this.stats.navigationSequences[i].feature !== lastFeature) {
        const focusTime = this.stats.navigationSequences[i].timestamp - lastSwitch;
        focusTimes.push(focusTime);
        lastSwitch = this.stats.navigationSequences[i].timestamp;
        lastFeature = this.stats.navigationSequences[i].feature;
      }
    }
    
    return this._mean(focusTimes);
  }
  
  _identifyOrganizationStyle() {
    // Identify user's preferred organization method
    const styles = this.stats.organizationStyle;
    const total = styles.createFolder + styles.moveItem + styles.tagItem + styles.favoriteItem;
    
    if (total === 0) return 'none';
    
    const maxStyle = Object.keys(styles).reduce((a, b) => 
      styles[a] > styles[b] ? a : b
    );
    
    return maxStyle;
  }
  
  _calculateOrganizationActivityRate() {
    const total = Object.values(this.stats.organizationStyle).reduce((a, b) => a + b, 0);
    const sessionMinutes = (this.stats.lastActivity - this.stats.startTime) / 60000;
    
    return total / sessionMinutes;
  }
  
  _calculateSearchRefinementRate() {
    // How often user refines search queries
    if (this.stats.searchPatterns.length < 2) return 0;
    
    let refinements = 0;
    for (let i = 1; i < this.stats.searchPatterns.length; i++) {
      const timeDiff = this.stats.searchPatterns[i].timestamp - this.stats.searchPatterns[i-1].timestamp;
      // If searches are close together (< 5 seconds), likely a refinement
      if (timeDiff < 5000) {
        refinements++;
      }
    }
    
    return refinements / this.stats.searchPatterns.length;
  }
  
  _getPrimaryActivityHour() {
    const maxActivity = Math.max(...this.stats.hourlyActivity);
    return this.stats.hourlyActivity.indexOf(maxActivity);
  }
  
  _categorizeTimeOfDay() {
    const hour = new Date().getHours();
    
    if (hour >= 5 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';
    if (hour >= 17 && hour < 21) return 'evening';
    return 'night';
  }
  
  _mean(arr) {
    if (!arr || arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }
  
  _std(arr) {
    if (!arr || arr.length === 0) return 0;
    const mean = this._mean(arr);
    const squaredDiffs = arr.map(x => Math.pow(x - mean, 2));
    return Math.sqrt(this._mean(squaredDiffs));
  }
  
  _median(arr) {
    if (!arr || arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  }
  
  _percentile(arr, p) {
    if (!arr || arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const index = Math.ceil(sorted.length * p) - 1;
    return sorted[Math.max(0, index)];
  }
  
  _assessDataQuality() {
    let quality = 0;
    
    // Sufficient interactions
    if (this.stats.totalInteractions >= 20) quality += 0.3;
    else quality += (this.stats.totalInteractions / 20) * 0.3;
    
    // Navigation diversity
    const uniqueRoutes = new Set(this.navigationPaths).size;
    if (uniqueRoutes >= 3) quality += 0.2;
    else quality += (uniqueRoutes / 3) * 0.2;
    
    // Feature usage diversity
    if (this.stats.featureAccessCounts.size >= 5) quality += 0.2;
    else quality += (this.stats.featureAccessCounts.size / 5) * 0.2;
    
    // Decision samples
    if (this.decisionTimes.length >= 3) quality += 0.2;
    else quality += (this.decisionTimes.length / 3) * 0.2;
    
    // Session duration
    const sessionMinutes = (this.stats.lastActivity - this.stats.startTime) / 60000;
    if (sessionMinutes >= 2) quality += 0.1;
    else quality += (sessionMinutes / 2) * 0.1;
    
    return Math.min(quality, 1.0);
  }
}


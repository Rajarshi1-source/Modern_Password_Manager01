/**
 * Keystroke Dynamics Capture
 * 
 * Captures 80+ dimensional typing biometrics including:
 * - Key press duration (dwell time)
 * - Inter-key latency (flight time)
 * - Typing rhythm patterns
 * - Error correction behavior
 * - Shift/modifier key usage
 */

export class KeystrokeDynamics {
  constructor() {
    this.keyEvents = [];
    this.currentSequence = [];
    this.maxSequenceLength = 1000; // Keep last 1000 key events
    
    // Track key states
    this.keyDownTimes = new Map();
    this.lastKeyUp = null;
    
    // Statistics accumulators
    this.stats = {
      totalKeys: 0,
      pressDurations: [],
      flightTimes: [],
      errorCorrections: 0,
      shiftUsage: 0,
      capsLockUsage: 0,
      backspaceCount: 0,
      
      // N-gram timings
      bigrams: new Map(),
      trigrams: new Map(),
      
      // Key-specific timings
      keyTimings: new Map(),
      
      // Session metadata
      startTime: null,
      lastActivity: null
    };
    
    this.isAttached = false;
  }
  
  /**
   * Attach event listeners to capture typing behavior
   */
  attach() {
    if (this.isAttached) return;
    
    this.stats.startTime = Date.now();
    
    document.addEventListener('keydown', this.handleKeyDown);
    document.addEventListener('keyup', this.handleKeyUp);
    document.addEventListener('keypress', this.handleKeyPress);
    
    this.isAttached = true;
    console.log('KeystrokeDynamics: Attached event listeners');
  }
  
  /**
   * Detach event listeners
   */
  detach() {
    document.removeEventListener('keydown', this.handleKeyDown);
    document.removeEventListener('keyup', this.handleKeyUp);
    document.removeEventListener('keypress', this.handleKeyPress);
    
    this.isAttached = false;
    console.log('KeystrokeDynamics: Detached event listeners');
  }
  
  /**
   * Handle keydown event
   */
  handleKeyDown = (event) => {
    const timestamp = performance.now();
    const key = event.key;
    
    // Store keydown time
    this.keyDownTimes.set(key, timestamp);
    
    // Track special keys
    if (key === 'Shift') this.stats.shiftUsage++;
    if (key === 'CapsLock') this.stats.capsLockUsage++;
    if (key === 'Backspace') {
      this.stats.backspaceCount++;
      this.stats.errorCorrections++;
    }
    
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle keyup event
   */
  handleKeyUp = (event) => {
    const timestamp = performance.now();
    const key = event.key;
    
    // Calculate press duration (dwell time)
    if (this.keyDownTimes.has(key)) {
      const downTime = this.keyDownTimes.get(key);
      const pressDuration = timestamp - downTime;
      
      this.stats.pressDurations.push(pressDuration);
      
      // Track per-key statistics
      if (!this.stats.keyTimings.has(key)) {
        this.stats.keyTimings.set(key, []);
      }
      this.stats.keyTimings.get(key).push(pressDuration);
      
      this.keyDownTimes.delete(key);
    }
    
    // Calculate flight time (inter-key latency)
    if (this.lastKeyUp) {
      const flightTime = timestamp - this.lastKeyUp;
      this.stats.flightTimes.push(flightTime);
      
      // Track bigrams and trigrams
      this._trackNgrams(key);
    }
    
    this.lastKeyUp = timestamp;
    this.stats.totalKeys++;
    
    // Add to sequence
    this.currentSequence.push({
      key,
      timestamp,
      pressDuration: timestamp - (this.keyDownTimes.get(key) || timestamp),
      isModifier: ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(key)
    });
    
    // Maintain sequence size
    if (this.currentSequence.length > this.maxSequenceLength) {
      this.currentSequence.shift();
    }
  };
  
  /**
   * Handle keypress event
   */
  handleKeyPress = (event) => {
    // Additional capture if needed
  };
  
  /**
   * Track n-gram patterns
   */
  _trackNgrams(key) {
    const recentKeys = this.currentSequence.slice(-3).map(e => e.key);
    
    if (recentKeys.length >= 2) {
      const bigram = recentKeys.slice(-2).join('');
      const count = this.stats.bigrams.get(bigram) || 0;
      this.stats.bigrams.set(bigram, count + 1);
    }
    
    if (recentKeys.length >= 3) {
      const trigram = recentKeys.join('');
      const count = this.stats.trigrams.get(trigram) || 0;
      this.stats.trigrams.set(trigram, count + 1);
    }
  }
  
  /**
   * Calculate statistical features from collected data
   */
  _calculateStatistics() {
    const features = {};
    
    // Press duration statistics
    if (this.stats.pressDurations.length > 0) {
      features.press_duration_mean = this._mean(this.stats.pressDurations);
      features.press_duration_std = this._std(this.stats.pressDurations);
      features.press_duration_median = this._median(this.stats.pressDurations);
      features.press_duration_min = Math.min(...this.stats.pressDurations);
      features.press_duration_max = Math.max(...this.stats.pressDurations);
      features.press_duration_range = features.press_duration_max - features.press_duration_min;
      features.press_duration_cv = features.press_duration_std / features.press_duration_mean; // Coefficient of variation
    }
    
    // Flight time statistics
    if (this.stats.flightTimes.length > 0) {
      features.flight_time_mean = this._mean(this.stats.flightTimes);
      features.flight_time_std = this._std(this.stats.flightTimes);
      features.flight_time_median = this._median(this.stats.flightTimes);
      features.flight_time_min = Math.min(...this.stats.flightTimes);
      features.flight_time_max = Math.max(...this.stats.flightTimes);
      features.flight_time_cv = features.flight_time_std / features.flight_time_mean;
    }
    
    // Typing speed
    if (this.stats.startTime) {
      const elapsedSeconds = (this.stats.lastActivity - this.stats.startTime) / 1000;
      features.typing_speed_cps = this.stats.totalKeys / elapsedSeconds; // Characters per second
      features.typing_speed_wpm = (this.stats.totalKeys / 5) / (elapsedSeconds / 60); // Words per minute
    }
    
    // Error rates
    features.error_rate = this.stats.totalKeys > 0 
      ? this.stats.errorCorrections / this.stats.totalKeys 
      : 0;
    features.backspace_frequency = this.stats.totalKeys > 0
      ? this.stats.backspaceCount / this.stats.totalKeys
      : 0;
    
    // Modifier key usage
    features.shift_usage_rate = this.stats.totalKeys > 0
      ? this.stats.shiftUsage / this.stats.totalKeys
      : 0;
    features.capslock_usage_rate = this.stats.totalKeys > 0
      ? this.stats.capsLockUsage / this.stats.totalKeys
      : 0;
    
    // Rhythm patterns (variance in timing)
    if (this.stats.flightTimes.length > 1) {
      features.rhythm_regularity = 1 / (1 + features.flight_time_cv); // Inverse CV (higher = more regular)
      features.rhythm_variability = features.flight_time_cv;
    }
    
    // N-gram diversity
    features.bigram_diversity = this.stats.bigrams.size;
    features.trigram_diversity = this.stats.trigrams.size;
    
    // Top bigrams/trigrams (most common patterns)
    const topBigrams = this._getTopN(this.stats.bigrams, 5);
    const topTrigrams = this._getTopN(this.stats.trigrams, 5);
    
    features.top_bigrams = topBigrams;
    features.top_trigrams = topTrigrams;
    
    // Pause patterns (gaps in typing)
    const pauseCounts = this._analyzePauses(this.stats.flightTimes);
    features.short_pauses = pauseCounts.short; // < 200ms
    features.medium_pauses = pauseCounts.medium; // 200-500ms
    features.long_pauses = pauseCounts.long; // > 500ms
    
    // Key-specific timing patterns
    const commonKeys = ['e', 'a', 't', 'o', 'i', 'n', 's', 'r', 'h', 'l'];
    commonKeys.forEach(key => {
      if (this.stats.keyTimings.has(key)) {
        const timings = this.stats.keyTimings.get(key);
        features[`key_${key}_mean`] = this._mean(timings);
        features[`key_${key}_std`] = this._std(timings);
      }
    });
    
    // Temporal patterns (time of day, etc.)
    const now = new Date();
    features.capture_hour = now.getHours();
    features.capture_day_of_week = now.getDay();
    
    return features;
  }
  
  /**
   * Get 247-dimensional feature vector for current session
   */
  async getFeatures() {
    const basicStats = this._calculateStatistics();
    
    // Extend to 80+ dimensions with additional derived features
    const features = {
      ...basicStats,
      
      // Derived rhythm features
      rhythm_entropy: this._calculateEntropy(this.stats.flightTimes),
      rhythm_autocorrelation: this._autocorrelation(this.stats.flightTimes, 1),
      
      // Typing burst patterns
      burst_count: this._detectBursts(this.stats.flightTimes).length,
      avg_burst_length: this._mean(this._detectBursts(this.stats.flightTimes).map(b => b.length)),
      
      // Consistency metrics
      early_vs_late_consistency: this._earlyVsLateConsistency(),
      
      // Sequence complexity
      sequence_complexity: this._calculateSequenceComplexity(),
      
      // Advanced timing features
      timing_skewness: this._skewness(this.stats.flightTimes),
      timing_kurtosis: this._kurtosis(this.stats.flightTimes),
      
      // Inter-quartile range
      flight_time_iqr: this._iqr(this.stats.flightTimes),
      press_duration_iqr: this._iqr(this.stats.pressDurations),
      
      // Percentiles
      flight_time_p25: this._percentile(this.stats.flightTimes, 0.25),
      flight_time_p75: this._percentile(this.stats.flightTimes, 0.75),
      flight_time_p90: this._percentile(this.stats.flightTimes, 0.90),
      
      // Metadata
      total_samples: this.stats.totalKeys,
      session_duration_seconds: (this.stats.lastActivity - this.stats.startTime) / 1000,
      data_quality_score: this._assessDataQuality()
    };
    
    return features;
  }
  
  /**
   * Reset all captured data
   */
  reset() {
    this.keyEvents = [];
    this.currentSequence = [];
    this.keyDownTimes.clear();
    this.lastKeyUp = null;
    
    this.stats = {
      totalKeys: 0,
      pressDurations: [],
      flightTimes: [],
      errorCorrections: 0,
      shiftUsage: 0,
      capsLockUsage: 0,
      backspaceCount: 0,
      bigrams: new Map(),
      trigrams: new Map(),
      keyTimings: new Map(),
      startTime: Date.now(),
      lastActivity: Date.now()
    };
  }
  
  // ============================================================================
  // STATISTICAL UTILITY FUNCTIONS
  // ============================================================================
  
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
  
  _iqr(arr) {
    return this._percentile(arr, 0.75) - this._percentile(arr, 0.25);
  }
  
  _skewness(arr) {
    if (!arr || arr.length < 3) return 0;
    const mean = this._mean(arr);
    const std = this._std(arr);
    if (std === 0) return 0;
    
    const cubedDiffs = arr.map(x => Math.pow((x - mean) / std, 3));
    return this._mean(cubedDiffs);
  }
  
  _kurtosis(arr) {
    if (!arr || arr.length < 4) return 0;
    const mean = this._mean(arr);
    const std = this._std(arr);
    if (std === 0) return 0;
    
    const fourthPowerDiffs = arr.map(x => Math.pow((x - mean) / std, 4));
    return this._mean(fourthPowerDiffs) - 3; // Excess kurtosis
  }
  
  _calculateEntropy(arr) {
    if (!arr || arr.length === 0) return 0;
    
    // Bin the values
    const bins = 10;
    const min = Math.min(...arr);
    const max = Math.max(...arr);
    const binSize = (max - min) / bins;
    
    const counts = new Array(bins).fill(0);
    arr.forEach(val => {
      const binIndex = Math.min(Math.floor((val - min) / binSize), bins - 1);
      counts[binIndex]++;
    });
    
    // Calculate entropy
    const total = arr.length;
    let entropy = 0;
    counts.forEach(count => {
      if (count > 0) {
        const p = count / total;
        entropy -= p * Math.log2(p);
      }
    });
    
    return entropy;
  }
  
  _autocorrelation(arr, lag) {
    if (!arr || arr.length < lag + 1) return 0;
    
    const mean = this._mean(arr);
    let numerator = 0;
    let denominator = 0;
    
    for (let i = 0; i < arr.length - lag; i++) {
      numerator += (arr[i] - mean) * (arr[i + lag] - mean);
    }
    
    for (let i = 0; i < arr.length; i++) {
      denominator += Math.pow(arr[i] - mean, 2);
    }
    
    return denominator === 0 ? 0 : numerator / denominator;
  }
  
  _getTopN(map, n) {
    const entries = Array.from(map.entries());
    entries.sort((a, b) => b[1] - a[1]);
    return entries.slice(0, n).map(([key, count]) => ({ pattern: key, count }));
  }
  
  _analyzePauses(flightTimes) {
    let short = 0, medium = 0, long = 0;
    
    flightTimes.forEach(time => {
      if (time < 200) short++;
      else if (time < 500) medium++;
      else long++;
    });
    
    return { short, medium, long };
  }
  
  _detectBursts(flightTimes) {
    const burstThreshold = 150; // ms
    const bursts = [];
    let currentBurst = [];
    
    flightTimes.forEach(time => {
      if (time < burstThreshold) {
        currentBurst.push(time);
      } else {
        if (currentBurst.length > 2) {
          bursts.push(currentBurst);
        }
        currentBurst = [];
      }
    });
    
    if (currentBurst.length > 2) {
      bursts.push(currentBurst);
    }
    
    return bursts;
  }
  
  _earlyVsLateConsistency() {
    // Compare early session typing vs late session typing
    const halfPoint = Math.floor(this.stats.flightTimes.length / 2);
    const early = this.stats.flightTimes.slice(0, halfPoint);
    const late = this.stats.flightTimes.slice(halfPoint);
    
    if (early.length === 0 || late.length === 0) return 0;
    
    const earlyMean = this._mean(early);
    const lateMean = this._mean(late);
    
    // Calculate consistency (lower = more consistent)
    return Math.abs(earlyMean - lateMean) / earlyMean;
  }
  
  _calculateSequenceComplexity() {
    // Measure of typing pattern complexity
    if (this.currentSequence.length < 10) return 0;
    
    const transitions = new Set();
    for (let i = 1; i < this.currentSequence.length; i++) {
      const transition = `${this.currentSequence[i-1].key}->${this.currentSequence[i].key}`;
      transitions.add(transition);
    }
    
    return transitions.size / this.currentSequence.length;
  }
  
  _assessDataQuality() {
    // Assess quality of captured data (0-1)
    let quality = 0;
    
    // Sufficient samples
    if (this.stats.totalKeys >= 50) quality += 0.3;
    else quality += (this.stats.totalKeys / 50) * 0.3;
    
    // Variety of keys
    const uniqueKeys = new Set(this.currentSequence.map(e => e.key)).size;
    if (uniqueKeys >= 20) quality += 0.3;
    else quality += (uniqueKeys / 20) * 0.3;
    
    // Time span (prefer longer sessions)
    if (this.stats.startTime) {
      const sessionMinutes = (this.stats.lastActivity - this.stats.startTime) / 60000;
      if (sessionMinutes >= 5) quality += 0.2;
      else quality += (sessionMinutes / 5) * 0.2;
    }
    
    // N-gram diversity
    if (this.stats.bigrams.size >= 10) quality += 0.2;
    else quality += (this.stats.bigrams.size / 10) * 0.2;
    
    return Math.min(quality, 1.0);
  }
}


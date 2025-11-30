/**
 * Mouse Biometrics Capture
 * 
 * Captures 60+ dimensional mouse behavior including:
 * - Velocity and acceleration curves
 * - Movement trajectories
 * - Click timing patterns
 * - Scroll behavior
 * - Hover patterns
 */

export class MouseBiometrics {
  constructor() {
    this.mouseEvents = [];
    this.clickEvents = [];
    this.scrollEvents = [];
    this.maxEvents = 2000; // Keep last 2000 events
    
    // Track current mouse state
    this.lastPosition = { x: 0, y: 0, timestamp: 0 };
    this.hoverStart = null;
    
    // Statistics accumulators
    this.stats = {
      movements: [],
      clicks: [],
      scrolls: [],
      hovers: [],
      
      // Movement metrics
      totalDistance: 0,
      velocities: [],
      accelerations: [],
      directions: [],
      curvatures: [],
      
      // Click metrics
      clickDurations: [],
      doubleClickIntervals: [],
      lastClickTime: null,
      
      // Scroll metrics
      scrollSpeeds: [],
      scrollDirections: [],
      
      // Session metadata
      startTime: null,
      lastActivity: null
    };
    
    this.isAttached = false;
  }
  
  /**
   * Attach event listeners for mouse behavior capture
   */
  attach() {
    if (this.isAttached) return;
    
    this.stats.startTime = Date.now();
    
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mousedown', this.handleMouseDown);
    document.addEventListener('mouseup', this.handleMouseUp);
    document.addEventListener('click', this.handleClick);
    document.addEventListener('wheel', this.handleWheel);
    document.addEventListener('mouseenter', this.handleMouseEnter, true);
    document.addEventListener('mouseleave', this.handleMouseLeave, true);
    
    this.isAttached = true;
    console.log('MouseBiometrics: Attached event listeners');
  }
  
  /**
   * Detach event listeners
   */
  detach() {
    document.removeEventListener('mousemove', this.handleMouseMove);
    document.removeEventListener('mousedown', this.handleMouseDown);
    document.removeEventListener('mouseup', this.handleMouseUp);
    document.removeEventListener('click', this.handleClick);
    document.removeEventListener('wheel', this.handleWheel);
    document.removeEventListener('mouseenter', this.handleMouseEnter, true);
    document.removeEventListener('mouseleave', this.handleMouseLeave, true);
    
    this.isAttached = false;
    console.log('MouseBiometrics: Detached event listeners');
  }
  
  /**
   * Handle mouse move events
   */
  handleMouseMove = (event) => {
    const timestamp = performance.now();
    const { clientX: x, clientY: y } = event;
    
    // Calculate movement metrics
    if (this.lastPosition.timestamp > 0) {
      const dt = timestamp - this.lastPosition.timestamp;
      const dx = x - this.lastPosition.x;
      const dy = y - this.lastPosition.y;
      
      // Distance
      const distance = Math.sqrt(dx * dx + dy * dy);
      this.stats.totalDistance += distance;
      
      // Velocity (pixels per millisecond)
      const velocity = dt > 0 ? distance / dt : 0;
      this.stats.velocities.push(velocity);
      
      // Direction (angle in radians)
      const direction = Math.atan2(dy, dx);
      this.stats.directions.push(direction);
      
      // Acceleration (change in velocity)
      if (this.stats.velocities.length >= 2) {
        const prevVelocity = this.stats.velocities[this.stats.velocities.length - 2];
        const acceleration = (velocity - prevVelocity) / dt;
        this.stats.accelerations.push(acceleration);
      }
      
      // Curvature (change in direction)
      if (this.stats.directions.length >= 2) {
        const prevDirection = this.stats.directions[this.stats.directions.length - 2];
        const curvature = Math.abs(direction - prevDirection);
        this.stats.curvatures.push(curvature);
      }
      
      // Store movement event
      this.stats.movements.push({
        x, y, timestamp, distance, velocity, direction
      });
    }
    
    this.lastPosition = { x, y, timestamp };
    this.stats.lastActivity = Date.now();
    
    // Maintain event limit
    if (this.stats.movements.length > this.maxEvents) {
      this.stats.movements.shift();
    }
  };
  
  /**
   * Handle mouse down events
   */
  handleMouseDown = (event) => {
    const timestamp = performance.now();
    const { clientX: x, clientY: y, button } = event;
    
    this.clickDownTime = timestamp;
    this.clickDownPosition = { x, y };
  };
  
  /**
   * Handle mouse up events
   */
  handleMouseUp = (event) => {
    const timestamp = performance.now();
    
    if (this.clickDownTime) {
      const clickDuration = timestamp - this.clickDownTime;
      this.stats.clickDurations.push(clickDuration);
    }
    
    this.clickDownTime = null;
  };
  
  /**
   * Handle click events
   */
  handleClick = (event) => {
    const timestamp = performance.now();
    const { clientX: x, clientY: y, button } = event;
    
    // Track hover-before-click duration
    if (this.hoverStart) {
      const hoverDuration = timestamp - this.hoverStart;
      this.stats.hovers.push({
        duration: hoverDuration,
        x, y, timestamp
      });
    }
    
    // Track double-click intervals
    if (this.stats.lastClickTime) {
      const doubleClickInterval = timestamp - this.stats.lastClickTime;
      if (doubleClickInterval < 500) {
        this.stats.doubleClickIntervals.push(doubleClickInterval);
      }
    }
    
    this.stats.lastClickTime = timestamp;
    
    this.stats.clicks.push({
      x, y, button, timestamp
    });
    
    // Maintain event limit
    if (this.stats.clicks.length > this.maxEvents) {
      this.stats.clicks.shift();
    }
  };
  
  /**
   * Handle wheel (scroll) events
   */
  handleWheel = (event) => {
    const timestamp = performance.now();
    const { deltaX, deltaY, deltaMode } = event;
    
    // Calculate scroll speed
    const lastScroll = this.stats.scrolls[this.stats.scrolls.length - 1];
    if (lastScroll) {
      const dt = timestamp - lastScroll.timestamp;
      const scrollSpeed = Math.abs(deltaY) / dt;
      this.stats.scrollSpeeds.push(scrollSpeed);
    }
    
    // Track scroll direction
    const scrollDirection = deltaY > 0 ? 'down' : deltaY < 0 ? 'up' : 'none';
    this.stats.scrollDirections.push(scrollDirection);
    
    this.stats.scrolls.push({
      deltaX, deltaY, deltaMode, timestamp, direction: scrollDirection
    });
    
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle mouse enter events (for hover tracking)
   */
  handleMouseEnter = (event) => {
    this.hoverStart = performance.now();
  };
  
  /**
   * Handle mouse leave events
   */
  handleMouseLeave = (event) => {
    if (this.hoverStart) {
      const hoverDuration = performance.now() - this.hoverStart;
      // Don't count very short hovers (< 50ms)
      if (hoverDuration > 50) {
        this.stats.hovers.push({
          duration: hoverDuration,
          element: event.target.tagName,
          timestamp: performance.now()
        });
      }
    }
    this.hoverStart = null;
  };
  
  /**
   * Calculate mouse behavior features (60+ dimensions)
   */
  async getFeatures() {
    const features = {};
    
    // ========================================================================
    // VELOCITY FEATURES (10 dimensions)
    // ========================================================================
    if (this.stats.velocities.length > 0) {
      features.velocity_mean = this._mean(this.stats.velocities);
      features.velocity_std = this._std(this.stats.velocities);
      features.velocity_median = this._median(this.stats.velocities);
      features.velocity_min = Math.min(...this.stats.velocities);
      features.velocity_max = Math.max(...this.stats.velocities);
      features.velocity_range = features.velocity_max - features.velocity_min;
      features.velocity_cv = features.velocity_std / features.velocity_mean;
      features.velocity_skewness = this._skewness(this.stats.velocities);
      features.velocity_kurtosis = this._kurtosis(this.stats.velocities);
      features.velocity_p90 = this._percentile(this.stats.velocities, 0.90);
    }
    
    // ========================================================================
    // ACCELERATION FEATURES (8 dimensions)
    // ========================================================================
    if (this.stats.accelerations.length > 0) {
      features.acceleration_mean = this._mean(this.stats.accelerations);
      features.acceleration_std = this._std(this.stats.accelerations);
      features.acceleration_median = this._median(this.stats.accelerations);
      features.acceleration_max = Math.max(...this.stats.accelerations.map(Math.abs));
      features.acceleration_positive_rate = this.stats.accelerations.filter(a => a > 0).length / this.stats.accelerations.length;
      features.acceleration_negative_rate = this.stats.accelerations.filter(a => a < 0).length / this.stats.accelerations.length;
      features.acceleration_variability = this._std(this.stats.accelerations) / (Math.abs(this._mean(this.stats.accelerations)) + 0.001);
      features.acceleration_changes = this._countDirectionChanges(this.stats.accelerations);
    }
    
    // ========================================================================
    // TRAJECTORY FEATURES (12 dimensions)
    // ========================================================================
    if (this.stats.directions.length > 0) {
      features.direction_mean = this._circularMean(this.stats.directions);
      features.direction_std = this._circularStd(this.stats.directions);
      
      // Directional preferences
      const directionCounts = this._categorizeDirections(this.stats.directions);
      features.direction_horizontal_rate = directionCounts.horizontal;
      features.direction_vertical_rate = directionCounts.vertical;
      features.direction_diagonal_rate = directionCounts.diagonal;
      
      // Movement straightness
      features.movement_straightness = this._calculateStraightness();
      
      // Curvature metrics
      if (this.stats.curvatures.length > 0) {
        features.curvature_mean = this._mean(this.stats.curvatures);
        features.curvature_std = this._std(this.stats.curvatures);
        features.curvature_max = Math.max(...this.stats.curvatures);
        features.curvature_smoothness = 1 / (1 + features.curvature_std); // Inverse of variability
      }
      
      // Jitter (micro-movements)
      features.mouse_jitter = this._calculateJitter();
      features.pause_frequency = this._detectPauses();
    }
    
    // ========================================================================
    // CLICK FEATURES (10 dimensions)
    // ========================================================================
    if (this.stats.clicks.length > 0) {
      features.click_count = this.stats.clicks.length;
      features.clicks_per_minute = this._calculateClickRate();
      
      // Click duration (press time)
      if (this.stats.clickDurations.length > 0) {
        features.click_duration_mean = this._mean(this.stats.clickDurations);
        features.click_duration_std = this._std(this.stats.clickDurations);
        features.click_duration_median = this._median(this.stats.clickDurations);
      }
      
      // Double-click behavior
      if (this.stats.doubleClickIntervals.length > 0) {
        features.double_click_mean = this._mean(this.stats.doubleClickIntervals);
        features.double_click_std = this._std(this.stats.doubleClickIntervals);
        features.double_click_count = this.stats.doubleClickIntervals.length;
      }
      
      // Click location patterns
      features.click_area_spread = this._calculateClickSpread();
      features.click_clustering = this._calculateClickClustering();
    }
    
    // ========================================================================
    // HOVER FEATURES (6 dimensions)
    // ========================================================================
    if (this.stats.hovers.length > 0) {
      const hoverDurations = this.stats.hovers.map(h => h.duration);
      features.hover_duration_mean = this._mean(hoverDurations);
      features.hover_duration_std = this._std(hoverDurations);
      features.hover_duration_median = this._median(hoverDurations);
      features.hover_count = this.stats.hovers.length;
      features.hover_before_click_rate = this.stats.hovers.length / Math.max(this.stats.clicks.length, 1);
      features.hover_patience = this._percentile(hoverDurations, 0.75); // How long user waits before clicking
    }
    
    // ========================================================================
    // SCROLL FEATURES (8 dimensions)
    // ========================================================================
    if (this.stats.scrolls.length > 0) {
      features.scroll_count = this.stats.scrolls.length;
      
      if (this.stats.scrollSpeeds.length > 0) {
        features.scroll_speed_mean = this._mean(this.stats.scrollSpeeds);
        features.scroll_speed_std = this._std(this.stats.scrollSpeeds);
        features.scroll_speed_max = Math.max(...this.stats.scrollSpeeds);
      }
      
      // Scroll direction preferences
      const downScrolls = this.stats.scrollDirections.filter(d => d === 'down').length;
      const upScrolls = this.stats.scrollDirections.filter(d => d === 'up').length;
      features.scroll_down_rate = downScrolls / this.stats.scrollDirections.length;
      features.scroll_up_rate = upScrolls / this.stats.scrollDirections.length;
      features.scroll_rhythm = this._calculateScrollRhythm();
      features.scroll_burst_count = this._detectScrollBursts().length;
    }
    
    // ========================================================================
    // ADVANCED MOVEMENT FEATURES (6+ dimensions)
    // ========================================================================
    features.movement_efficiency = this._calculateMovementEfficiency();
    features.movement_smoothness = this._calculateMovementSmoothness();
    features.pause_pattern_score = this._analyzePausePatterns();
    features.directional_bias = this._calculateDirectionalBias();
    features.movement_predictability = this._calculatePredictability();
    features.micro_movement_count = this._countMicroMovements();
    
    // ========================================================================
    // METADATA (6 dimensions)
    // ========================================================================
    features.total_movements = this.stats.movements.length;
    features.total_distance_pixels = this.stats.totalDistance;
    features.session_duration_seconds = (this.stats.lastActivity - this.stats.startTime) / 1000;
    features.activity_density = this.stats.movements.length / ((this.stats.lastActivity - this.stats.startTime) / 1000);
    features.data_quality_score = this._assessDataQuality();
    features.capture_timestamp = Date.now();
    
    return features;
  }
  
  /**
   * Reset all captured data
   */
  reset() {
    this.mouseEvents = [];
    this.clickEvents = [];
    this.scrollEvents = [];
    
    this.stats = {
      movements: [],
      clicks: [],
      scrolls: [],
      hovers: [],
      totalDistance: 0,
      velocities: [],
      accelerations: [],
      directions: [],
      curvatures: [],
      clickDurations: [],
      doubleClickIntervals: [],
      lastClickTime: null,
      scrollSpeeds: [],
      scrollDirections: [],
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
    return this._mean(fourthPowerDiffs) - 3;
  }
  
  // ============================================================================
  // MOUSE-SPECIFIC ANALYSIS FUNCTIONS
  // ============================================================================
  
  _circularMean(angles) {
    // Mean of circular data (angles)
    if (!angles || angles.length === 0) return 0;
    
    const sinSum = angles.reduce((sum, angle) => sum + Math.sin(angle), 0);
    const cosSum = angles.reduce((sum, angle) => sum + Math.cos(angle), 0);
    
    return Math.atan2(sinSum / angles.length, cosSum / angles.length);
  }
  
  _circularStd(angles) {
    // Standard deviation of circular data
    if (!angles || angles.length === 0) return 0;
    
    const mean = this._circularMean(angles);
    const squaredDiffs = angles.map(angle => {
      let diff = angle - mean;
      // Normalize to [-π, π]
      while (diff > Math.PI) diff -= 2 * Math.PI;
      while (diff < -Math.PI) diff += 2 * Math.PI;
      return diff * diff;
    });
    
    return Math.sqrt(this._mean(squaredDiffs));
  }
  
  _categorizeDirections(directions) {
    let horizontal = 0, vertical = 0, diagonal = 0;
    
    directions.forEach(angle => {
      const normalized = Math.abs(angle) % (Math.PI / 2);
      
      if (normalized < Math.PI / 8) {
        horizontal++;
      } else if (normalized > 3 * Math.PI / 8) {
        vertical++;
      } else {
        diagonal++;
      }
    });
    
    const total = directions.length;
    return {
      horizontal: horizontal / total,
      vertical: vertical / total,
      diagonal: diagonal / total
    };
  }
  
  _calculateStraightness() {
    // Ratio of actual path length to straight-line distance
    if (this.stats.movements.length < 2) return 1;
    
    const first = this.stats.movements[0];
    const last = this.stats.movements[this.stats.movements.length - 1];
    
    const straightLineDistance = Math.sqrt(
      Math.pow(last.x - first.x, 2) + Math.pow(last.y - first.y, 2)
    );
    
    return straightLineDistance / (this.stats.totalDistance + 0.001);
  }
  
  _calculateJitter() {
    // Average micro-movement (small, rapid changes)
    if (this.stats.movements.length < 10) return 0;
    
    let jitterCount = 0;
    for (let i = 1; i < this.stats.movements.length; i++) {
      const distance = this.stats.movements[i].distance;
      if (distance < 5 && distance > 0) {
        jitterCount++;
      }
    }
    
    return jitterCount / this.stats.movements.length;
  }
  
  _detectPauses() {
    // Detect pauses in mouse movement
    const pauseThreshold = 200; // ms
    let pauseCount = 0;
    
    for (let i = 1; i < this.stats.movements.length; i++) {
      const timeDiff = this.stats.movements[i].timestamp - this.stats.movements[i-1].timestamp;
      if (timeDiff > pauseThreshold) {
        pauseCount++;
      }
    }
    
    return this.stats.movements.length > 0 ? pauseCount / this.stats.movements.length : 0;
  }
  
  _calculateClickRate() {
    if (!this.stats.startTime || this.stats.clicks.length === 0) return 0;
    
    const sessionMinutes = (this.stats.lastActivity - this.stats.startTime) / 60000;
    return this.stats.clicks.length / sessionMinutes;
  }
  
  _calculateClickSpread() {
    // Measure of how spread out clicks are across the screen
    if (this.stats.clicks.length < 2) return 0;
    
    const xValues = this.stats.clicks.map(c => c.x);
    const yValues = this.stats.clicks.map(c => c.y);
    
    const xRange = Math.max(...xValues) - Math.min(...xValues);
    const yRange = Math.max(...yValues) - Math.min(...yValues);
    
    return Math.sqrt(xRange * xRange + yRange * yRange);
  }
  
  _calculateClickClustering() {
    // Measure of click clustering (DBSCAN-like)
    if (this.stats.clicks.length < 3) return 0;
    
    const clusters = [];
    const clusterRadius = 100; // pixels
    
    this.stats.clicks.forEach(click => {
      let addedToCluster = false;
      
      for (const cluster of clusters) {
        const distance = Math.sqrt(
          Math.pow(click.x - cluster.centroid.x, 2) +
          Math.pow(click.y - cluster.centroid.y, 2)
        );
        
        if (distance < clusterRadius) {
          cluster.points.push(click);
          addedToCluster = true;
          break;
        }
      }
      
      if (!addedToCluster) {
        clusters.push({
          centroid: { x: click.x, y: click.y },
          points: [click]
        });
      }
    });
    
    // Return clustering coefficient (fewer clusters = more clustered)
    return 1 - (clusters.length / this.stats.clicks.length);
  }
  
  _calculateScrollRhythm() {
    // Measure regularity of scroll events
    if (this.stats.scrolls.length < 3) return 0;
    
    const intervals = [];
    for (let i = 1; i < this.stats.scrolls.length; i++) {
      intervals.push(this.stats.scrolls[i].timestamp - this.stats.scrolls[i-1].timestamp);
    }
    
    const cv = this._std(intervals) / (this._mean(intervals) + 0.001);
    return 1 / (1 + cv); // Higher = more rhythmic
  }
  
  _detectScrollBursts() {
    // Detect rapid scroll bursts
    const burstThreshold = 100; // ms
    const bursts = [];
    let currentBurst = [];
    
    for (let i = 1; i < this.stats.scrolls.length; i++) {
      const interval = this.stats.scrolls[i].timestamp - this.stats.scrolls[i-1].timestamp;
      
      if (interval < burstThreshold) {
        if (currentBurst.length === 0) {
          currentBurst.push(this.stats.scrolls[i-1]);
        }
        currentBurst.push(this.stats.scrolls[i]);
      } else {
        if (currentBurst.length > 2) {
          bursts.push(currentBurst);
        }
        currentBurst = [];
      }
    }
    
    return bursts;
  }
  
  _calculateMovementEfficiency() {
    // Ratio of productive movement to total movement
    if (this.stats.clicks.length < 2 || this.stats.movements.length < 2) return 0;
    
    // Calculate direct distances between clicks
    let directDistance = 0;
    for (let i = 1; i < this.stats.clicks.length; i++) {
      const dx = this.stats.clicks[i].x - this.stats.clicks[i-1].x;
      const dy = this.stats.clicks[i].y - this.stats.clicks[i-1].y;
      directDistance += Math.sqrt(dx * dx + dy * dy);
    }
    
    return directDistance / (this.stats.totalDistance + 0.001);
  }
  
  _calculateMovementSmoothness() {
    // Measure of movement smoothness (low acceleration variance = smooth)
    if (this.stats.accelerations.length < 2) return 0;
    
    const accelStd = this._std(this.stats.accelerations);
    return 1 / (1 + accelStd);
  }
  
  _analyzePausePatterns() {
    // Analyze patterns in movement pauses
    if (this.stats.movements.length < 10) return 0;
    
    const pauses = [];
    const pauseThreshold = 200; // ms
    
    for (let i = 1; i < this.stats.movements.length; i++) {
      const timeDiff = this.stats.movements[i].timestamp - this.stats.movements[i-1].timestamp;
      if (timeDiff > pauseThreshold) {
        pauses.push(timeDiff);
      }
    }
    
    if (pauses.length === 0) return 0;
    
    // Regularity of pauses
    const pauseCV = this._std(pauses) / (this._mean(pauses) + 0.001);
    return 1 / (1 + pauseCV);
  }
  
  _calculateDirectionalBias() {
    // Preference for certain movement directions
    if (this.stats.directions.length < 10) return 0;
    
    const mean = this._circularMean(this.stats.directions);
    const deviations = this.stats.directions.map(d => Math.abs(d - mean));
    
    return this._mean(deviations);
  }
  
  _calculatePredictability() {
    // How predictable are the user's movements
    // Based on autocorrelation of velocities
    if (this.stats.velocities.length < 10) return 0;
    
    let autocorr = 0;
    const mean = this._mean(this.stats.velocities);
    
    for (let i = 1; i < Math.min(10, this.stats.velocities.length); i++) {
      let sum = 0;
      for (let j = 0; j < this.stats.velocities.length - i; j++) {
        sum += (this.stats.velocities[j] - mean) * (this.stats.velocities[j + i] - mean);
      }
      autocorr += sum / (this.stats.velocities.length - i);
    }
    
    return autocorr / 10;
  }
  
  _countMicroMovements() {
    // Count very small movements (< 3 pixels)
    if (this.stats.movements.length === 0) return 0;
    
    let microCount = 0;
    this.stats.movements.forEach(m => {
      if (m.distance > 0 && m.distance < 3) {
        microCount++;
      }
    });
    
    return microCount / this.stats.movements.length;
  }
  
  _countDirectionChanges(arr) {
    let changes = 0;
    for (let i = 1; i < arr.length; i++) {
      if (Math.sign(arr[i]) !== Math.sign(arr[i-1])) {
        changes++;
      }
    }
    return changes;
  }
  
  _assessDataQuality() {
    // Assess quality of captured mouse data (0-1)
    let quality = 0;
    
    // Sufficient movement samples
    if (this.stats.movements.length >= 100) quality += 0.3;
    else quality += (this.stats.movements.length / 100) * 0.3;
    
    // Click samples
    if (this.stats.clicks.length >= 10) quality += 0.2;
    else quality += (this.stats.clicks.length / 10) * 0.2;
    
    // Session duration
    if (this.stats.startTime) {
      const sessionMinutes = (this.stats.lastActivity - this.stats.startTime) / 60000;
      if (sessionMinutes >= 3) quality += 0.2;
      else quality += (sessionMinutes / 3) * 0.2;
    }
    
    // Distance covered
    if (this.stats.totalDistance >= 1000) quality += 0.2;
    else quality += (this.stats.totalDistance / 1000) * 0.2;
    
    // Variety of behaviors
    const hasScrolls = this.stats.scrolls.length > 0;
    const hasHovers = this.stats.hovers.length > 0;
    quality += (hasScrolls ? 0.05 : 0) + (hasHovers ? 0.05 : 0);
    
    return Math.min(quality, 1.0);
  }
}


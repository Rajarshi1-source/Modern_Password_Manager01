/**
 * Device Interaction Capture
 * 
 * Captures 35+ dimensional device interaction patterns including:
 * - Screen interaction (touch, swipe for mobile)
 * - Device orientation
 * - Battery patterns
 * - Network behavior
 * - App switching
 */

export class DeviceInteraction {
  constructor() {
    this.touchEvents = [];
    this.orientationChanges = [];
    this.networkChanges = [];
    this.visibilityChanges = [];
    
    // Statistics
    this.stats = {
      // Touch/mobile metrics
      touches: [],
      swipes: [],
      pinches: [],
      touchPressures: [],
      
      // Orientation metrics
      orientations: [],
      portraitTime: 0,
      landscapeTime: 0,
      orientationChangeCount: 0,
      
      // Device metrics
      deviceType: this._detectDeviceType(),
      screenSize: {
        width: window.screen.width,
        height: window.screen.height
      },
      viewportSize: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      devicePixelRatio: window.devicePixelRatio || 1,
      
      // Battery (if available)
      batteryLevel: null,
      isCharging: null,
      chargingPatterns: [],
      
      // Network
      connectionType: this._getConnectionType(),
      networkChanges: 0,
      offlineEvents: 0,
      
      // Visibility/App switching
      visibilityChanges: 0,
      tabHiddenDuration: 0,
      tabVisibleDuration: 0,
      lastVisibilityChange: null,
      
      // Scroll behavior (device-specific)
      scrollSpeeds: [],
      swipeVelocities: [],
      
      // Location (anonymized)
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      locale: navigator.language,
      
      // Session metadata
      startTime: null,
      lastActivity: null
    };
    
    this.isAttached = false;
    this.lastOrientation = window.screen?.orientation?.type;
  }
  
  /**
   * Attach event listeners
   */
  attach() {
    if (this.isAttached) return;
    
    this.stats.startTime = Date.now();
    
    // Touch events (mobile)
    document.addEventListener('touchstart', this.handleTouchStart, { passive: true });
    document.addEventListener('touchmove', this.handleTouchMove, { passive: true });
    document.addEventListener('touchend', this.handleTouchEnd, { passive: true });
    
    // Orientation changes
    if (window.screen?.orientation) {
      window.screen.orientation.addEventListener('change', this.handleOrientationChange);
    }
    window.addEventListener('orientationchange', this.handleOrientationChange);
    
    // Visibility changes (tab switching)
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
    
    // Network changes
    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);
    
    // Battery API (if supported)
    this._initializeBatteryMonitoring();
    
    this.isAttached = true;
    console.log('DeviceInteraction: Attached event listeners');
  }
  
  /**
   * Detach event listeners
   */
  detach() {
    document.removeEventListener('touchstart', this.handleTouchStart);
    document.removeEventListener('touchmove', this.handleTouchMove);
    document.removeEventListener('touchend', this.handleTouchEnd);
    
    if (window.screen?.orientation) {
      window.screen.orientation.removeEventListener('change', this.handleOrientationChange);
    }
    window.removeEventListener('orientationchange', this.handleOrientationChange);
    
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
    
    this.isAttached = false;
    console.log('DeviceInteraction: Detached event listeners');
  }
  
  /**
   * Handle touch start
   */
  handleTouchStart = (event) => {
    const timestamp = performance.now();
    const touches = Array.from(event.touches).map(touch => ({
      x: touch.clientX,
      y: touch.clientY,
      force: touch.force || 0,
      radiusX: touch.radiusX || 0,
      radiusY: touch.radiusY || 0,
      timestamp
    }));
    
    this.touchStartData = { touches, timestamp };
    
    // Track touch pressure (if available)
    touches.forEach(touch => {
      if (touch.force > 0) {
        this.stats.touchPressures.push(touch.force);
      }
    });
  };
  
  /**
   * Handle touch move
   */
  handleTouchMove = (event) => {
    const timestamp = performance.now();
    
    if (this.touchStartData && event.touches.length === 1) {
      const touch = event.touches[0];
      const startTouch = this.touchStartData.touches[0];
      
      const dx = touch.clientX - startTouch.x;
      const dy = touch.clientY - startTouch.y;
      const dt = timestamp - this.touchStartData.timestamp;
      
      const distance = Math.sqrt(dx * dx + dy * dy);
      const velocity = dt > 0 ? distance / dt : 0;
      
      // Detect swipe
      if (distance > 50) {
        this.stats.swipes.push({
          distance,
          velocity,
          direction: Math.atan2(dy, dx),
          duration: dt
        });
        
        this.stats.swipeVelocities.push(velocity);
      }
    }
    
    this.stats.lastActivity = Date.now();
  };
  
  /**
   * Handle touch end
   */
  handleTouchEnd = (event) => {
    this.touchStartData = null;
  };
  
  /**
   * Handle orientation change
   */
  handleOrientationChange = (event) => {
    const timestamp = performance.now();
    const newOrientation = window.screen?.orientation?.type || 
                          (window.orientation === 0 || window.orientation === 180 ? 'portrait' : 'landscape');
    
    this.stats.orientations.push({
      orientation: newOrientation,
      timestamp
    });
    
    this.stats.orientationChangeCount++;
    this.lastOrientation = newOrientation;
  };
  
  /**
   * Handle visibility change
   */
  handleVisibilityChange = (event) => {
    const timestamp = Date.now();
    const isHidden = document.hidden;
    
    if (this.stats.lastVisibilityChange) {
      const duration = timestamp - this.stats.lastVisibilityChange;
      
      if (isHidden) {
        this.stats.tabVisibleDuration += duration;
      } else {
        this.stats.tabHiddenDuration += duration;
      }
    }
    
    this.stats.visibilityChanges++;
    this.stats.lastVisibilityChange = timestamp;
    
    this.visibilityChanges.push({
      hidden: isHidden,
      timestamp
    });
  };
  
  /**
   * Handle online event
   */
  handleOnline = (event) => {
    this.stats.networkChanges++;
  };
  
  /**
   * Handle offline event
   */
  handleOffline = (event) => {
    this.stats.networkChanges++;
    this.stats.offlineEvents++;
  };
  
  /**
   * Initialize battery monitoring
   */
  async _initializeBatteryMonitoring() {
    if ('getBattery' in navigator) {
      try {
        const battery = await navigator.getBattery();
        
        this.stats.batteryLevel = battery.level;
        this.stats.isCharging = battery.charging;
        
        // Monitor charging changes
        battery.addEventListener('chargingchange', () => {
          this.stats.chargingPatterns.push({
            isCharging: battery.charging,
            level: battery.level,
            timestamp: Date.now()
          });
        });
        
        battery.addEventListener('levelchange', () => {
          this.stats.batteryLevel = battery.level;
        });
      } catch (error) {
        console.log('Battery API not available');
      }
    }
  }
  
  /**
   * Detect device type
   */
  _detectDeviceType() {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (/mobile|android|iphone|ipad|tablet/.test(userAgent)) {
      if (/tablet|ipad/.test(userAgent)) return 'tablet';
      return 'mobile';
    }
    
    return 'desktop';
  }
  
  /**
   * Get connection type
   */
  _getConnectionType() {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    
    if (connection) {
      return connection.effectiveType || connection.type || 'unknown';
    }
    
    return 'unknown';
  }
  
  /**
   * Get device interaction features (35+ dimensions)
   */
  async getFeatures() {
    const sessionDuration = (this.stats.lastActivity - this.stats.startTime) / 1000;
    
    const features = {
      // Device identification (5 dimensions)
      device_type: this.stats.deviceType,
      screen_width: this.stats.screenSize.width,
      screen_height: this.stats.screenSize.height,
      device_pixel_ratio: this.stats.devicePixelRatio,
      viewport_ratio: this.stats.viewportSize.width / this.stats.screenSize.width,
      
      // Touch/Mobile interaction (8 dimensions - if applicable)
      touch_count: this.stats.touches.length,
      swipe_count: this.stats.swipes.length,
      avg_swipe_velocity: this._mean(this.stats.swipeVelocities),
      swipe_velocity_std: this._std(this.stats.swipeVelocities),
      avg_touch_pressure: this._mean(this.stats.touchPressures),
      touch_pressure_variance: this._std(this.stats.touchPressures),
      pinch_count: this.stats.pinches.length,
      touch_interaction_rate: this.stats.touches.length / sessionDuration,
      
      // Orientation patterns (6 dimensions)
      orientation_changes: this.stats.orientationChangeCount,
      portrait_preference: this._calculateOrientationPreference('portrait'),
      landscape_preference: this._calculateOrientationPreference('landscape'),
      orientation_stability: 1 / (1 + this.stats.orientationChangeCount),
      avg_orientation_duration: this._calculateAvgOrientationDuration(),
      current_orientation: this.lastOrientation || 'unknown',
      
      // Battery patterns (4 dimensions - if available)
      battery_level: this.stats.batteryLevel,
      is_charging: this.stats.isCharging,
      charging_event_count: this.stats.chargingPatterns.length,
      typical_battery_level: this._calculateTypicalBatteryLevel(),
      
      // Network patterns (4 dimensions)
      connection_type: this.stats.connectionType,
      network_changes: this.stats.networkChanges,
      offline_events: this.stats.offlineEvents,
      network_stability: 1 / (1 + this.stats.networkChanges),
      
      // App switching / Visibility (5 dimensions)
      visibility_changes: this.stats.visibilityChanges,
      tab_hidden_duration_total: this.stats.tabHiddenDuration,
      tab_visible_duration_total: this.stats.tabVisibleDuration,
      tab_visibility_ratio: this.stats.tabVisibleDuration / (this.stats.tabVisibleDuration + this.stats.tabHiddenDuration + 1),
      app_focus_stability: 1 / (1 + this.stats.visibilityChanges / (sessionDuration / 60)),
      
      // Locale/timezone (3 dimensions)
      timezone: this.stats.timezone,
      locale: this.stats.locale,
      timezone_offset: new Date().getTimezoneOffset(),
      
      // Metadata
      total_device_interactions: this.stats.touches.length + this.stats.orientationChangeCount + this.stats.visibilityChanges,
      data_quality_score: this._assessDataQuality(),
      capture_timestamp: Date.now()
    };
    
    return features;
  }
  
  /**
   * Reset captured data
   */
  reset() {
    this.touchEvents = [];
    this.orientationChanges = [];
    this.networkChanges = [];
    this.visibilityChanges = [];
    
    // Reset most stats but keep device constants
    const deviceType = this.stats.deviceType;
    const screenSize = this.stats.screenSize;
    const devicePixelRatio = this.stats.devicePixelRatio;
    const timezone = this.stats.timezone;
    const locale = this.stats.locale;
    
    this.stats = {
      touches: [],
      swipes: [],
      pinches: [],
      touchPressures: [],
      orientations: [],
      portraitTime: 0,
      landscapeTime: 0,
      orientationChangeCount: 0,
      deviceType,
      screenSize,
      viewportSize: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      devicePixelRatio,
      batteryLevel: null,
      isCharging: null,
      chargingPatterns: [],
      connectionType: this._getConnectionType(),
      networkChanges: 0,
      offlineEvents: 0,
      visibilityChanges: 0,
      tabHiddenDuration: 0,
      tabVisibleDuration: 0,
      lastVisibilityChange: null,
      scrollSpeeds: [],
      swipeVelocities: [],
      timezone,
      locale,
      startTime: Date.now(),
      lastActivity: Date.now()
    };
  }
  
  // ============================================================================
  // ANALYSIS FUNCTIONS
  // ============================================================================
  
  _calculateOrientationPreference(type) {
    const orientations = this.stats.orientations.filter(o => 
      o.orientation.includes(type)
    );
    
    return orientations.length / (this.stats.orientations.length + 1);
  }
  
  _calculateAvgOrientationDuration() {
    if (this.stats.orientations.length < 2) return 0;
    
    const durations = [];
    for (let i = 1; i < this.stats.orientations.length; i++) {
      durations.push(this.stats.orientations[i].timestamp - this.stats.orientations[i-1].timestamp);
    }
    
    return this._mean(durations);
  }
  
  _calculateTypicalBatteryLevel() {
    if (this.stats.chargingPatterns.length === 0) return null;
    
    const levels = this.stats.chargingPatterns.map(p => p.level);
    return this._median(levels);
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
  
  _assessDataQuality() {
    let quality = 0;
    
    // Device identification is always available
    quality += 0.3;
    
    // Touch data (if mobile)
    if (this.stats.deviceType !== 'desktop') {
      if (this.stats.touches.length >= 10) quality += 0.2;
      else quality += (this.stats.touches.length / 10) * 0.2;
    } else {
      quality += 0.2; // Desktop gets credit for not being mobile
    }
    
    // Orientation data
    if (this.stats.orientations.length > 0) quality += 0.15;
    
    // Visibility tracking
    if (this.stats.visibilityChanges > 0) quality += 0.15;
    
    // Network info
    if (this.stats.connectionType !== 'unknown') quality += 0.1;
    
    // Battery info (bonus)
    if (this.stats.batteryLevel !== null) quality += 0.1;
    
    return Math.min(quality, 1.0);
  }
}


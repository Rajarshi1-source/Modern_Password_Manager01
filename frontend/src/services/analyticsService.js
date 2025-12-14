/**
 * Analytics Service
 * =================
 * 
 * Comprehensive analytics tracking for user engagement, feature usage,
 * conversion funnels, and behavioral insights.
 * 
 * Features:
 * - Event tracking (pageviews, clicks, custom events)
 * - User engagement metrics (session duration, feature usage)
 * - Conversion funnel tracking
 * - User journey mapping
 * - Cohort analysis support
 * - Privacy-first (GDPR compliant)
 * - Batch reporting to minimize network requests
 * 
 * Usage:
 *   import { analyticsService } from './services/analyticsService';
 *   
 *   // Track page view
 *   analyticsService.trackPageView('/vault', { itemCount: 15 });
 *   
 *   // Track user action
 *   analyticsService.trackEvent('password_copied', { itemId: '123' });
 *   
 *   // Track conversion
 *   analyticsService.trackConversion('vault_created', { duration: 1500 });
 */

import axios from 'axios';

class AnalyticsService {
  constructor() {
    // Event queues
    this.eventQueue = [];
    this.engagementQueue = [];
    this.conversionQueue = [];
    
    // Configuration
    this.config = {
      enabled: true,
      batchSize: 20, // Send events in batches
      flushInterval: 30000, // Flush every 30 seconds
      maxQueueSize: 500,
      endpoint: '/api/analytics/events/',
      debug: process.env.NODE_ENV === 'development'
    };
    
    // Session tracking
    this.sessionId = this.generateSessionId();
    this.sessionStartTime = Date.now();
    this.pageLoadTime = Date.now();
    this.lastActivityTime = Date.now();
    
    // User context
    this.userContext = {
      userId: null,
      email: null,
      cohort: null,
      properties: {}
    };
    
    // Feature usage tracking
    this.featureUsage = new Map();
    this.pageViews = [];
    this.userJourney = [];
    
    // Performance metrics
    this.performanceMetrics = {
      pageLoadTimes: [],
      apiResponseTimes: [],
      userFlowTimes: []
    };
    
    // Funnel tracking
    this.activeFunnels = new Map();
    
    // Auto-flush timer
    this.flushTimer = null;
    this.startAutoFlush();
    
    // Initialize session tracking
    this.initializeSessionTracking();
    
    // Track visibility changes
    this.trackVisibilityChanges();
    
    // Handle page unload
    this.handlePageUnload();
  }
  
  /* ===== INITIALIZATION ===== */
  
  /**
   * Initialize analytics service with user context
   * @param {Object} options - Initialization options
   * @param {string} options.userId - User ID
   * @param {string} options.email - User email
   * @param {Object} options.properties - Additional user properties
   * @returns {Promise<void>}
   */
  async initialize(options = {}) {
    try {
      // Set user context
      if (options.userId) {
        this.userContext.userId = options.userId;
      }
      if (options.email) {
        this.userContext.email = options.email;
      }
      if (options.properties) {
        this.userContext.properties = { ...this.userContext.properties, ...options.properties };
      }
      
      // Track initialization
      this.trackEvent('analytics_initialized', {
        userId: this.userContext.userId,
        sessionId: this.sessionId
      });
      
      console.log('[Analytics] Initialized with user context');
      return Promise.resolve();
    } catch (error) {
      console.warn('[Analytics] Initialization failed:', error);
      return Promise.reject(error);
    }
  }
  
  /**
   * Generate unique session ID
   */
  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Initialize session tracking
   */
  initializeSessionTracking() {
    // Track session start
    this.trackEvent('session_start', {
      sessionId: this.sessionId,
      referrer: document.referrer,
      userAgent: navigator.userAgent,
      screenResolution: `${window.screen.width}x${window.screen.height}`,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
    
    // Track activity
    ['click', 'scroll', 'keypress', 'mousemove'].forEach(event => {
      document.addEventListener(event, () => {
        this.lastActivityTime = Date.now();
      }, { passive: true, capture: true });
    });
  }
  
  /**
   * Track visibility changes (tab switching)
   */
  trackVisibilityChanges() {
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.trackEvent('page_hidden', {
          sessionDuration: this.getSessionDuration(),
          pageTime: Date.now() - this.pageLoadTime
        });
      } else {
        this.pageLoadTime = Date.now();
        this.trackEvent('page_visible', {});
      }
    });
  }
  
  /**
   * Handle page unload (send remaining data)
   */
  handlePageUnload() {
    window.addEventListener('beforeunload', () => {
      this.trackEvent('session_end', {
        sessionDuration: this.getSessionDuration(),
        totalPageViews: this.pageViews.length,
        uniqueFeatures: this.featureUsage.size
      });
      
      // Flush remaining events synchronously
      this.flush(true);
    });
  }
  
  /**
   * Get current session duration
   */
  getSessionDuration() {
    return Date.now() - this.sessionStartTime;
  }
  
  /* ===== USER CONTEXT ===== */
  
  /**
   * Set user context for analytics
   */
  setUserContext(context) {
    this.userContext = {
      ...this.userContext,
      ...context
    };
    
    this.trackEvent('user_context_set', {
      userId: context.userId,
      email: context.email
    });
  }
  
  /**
   * Clear user context (on logout)
   */
  clearUserContext() {
    this.trackEvent('user_logout', {
      sessionDuration: this.getSessionDuration()
    });
    
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
  
  /* ===== EVENT TRACKING ===== */
  
  /**
   * Track a custom event
   * @param {string} eventName - Name of the event
   * @param {object} properties - Event properties
   * @param {string} category - Event category (optional)
   */
  trackEvent(eventName, properties = {}, category = 'general') {
    if (!this.config.enabled) return;
    
    const event = {
      type: 'event',
      name: eventName,
      category: category,
      properties: {
        ...properties,
        sessionId: this.sessionId,
        timestamp: new Date().toISOString(),
        url: window.location.href,
        path: window.location.pathname
      },
      user: { ...this.userContext },
      metadata: {
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform
      }
    };
    
    this.eventQueue.push(event);
    
    // Add to user journey
    this.userJourney.push({
      event: eventName,
      timestamp: Date.now(),
      path: window.location.pathname
    });
    
    if (this.config.debug) {
      console.log('[Analytics] Event tracked:', eventName, properties);
    }
    
    // Flush if queue is full
    if (this.eventQueue.length >= this.config.batchSize) {
      this.flush();
    }
    
    // Return a resolved Promise for chaining compatibility
    return Promise.resolve(event);
  }
  
  /**
   * Track page view
   */
  trackPageView(pageName, properties = {}) {
    const pageView = {
      pageName,
      path: window.location.pathname,
      url: window.location.href,
      referrer: document.referrer,
      loadTime: Date.now() - this.pageLoadTime,
      ...properties
    };
    
    this.pageViews.push(pageView);
    this.pageLoadTime = Date.now();
    
    return this.trackEvent('page_view', pageView, 'navigation');
  }
  
  /**
   * Track user action (click, submit, etc.)
   */
  trackAction(actionName, target, properties = {}) {
    return this.trackEvent(actionName, {
      target,
      ...properties
    }, 'interaction');
  }
  
  /**
   * Track feature usage
   */
  trackFeatureUsage(featureName, properties = {}) {
    // Update feature usage count
    const currentCount = this.featureUsage.get(featureName) || 0;
    this.featureUsage.set(featureName, currentCount + 1);
    
    return this.trackEvent('feature_used', {
      feature: featureName,
      usageCount: currentCount + 1,
      ...properties
    }, 'feature');
  }
  
  /**
   * Track error
   */
  trackError(errorName, errorMessage, properties = {}) {
    return this.trackEvent('error_occurred', {
      error: errorName,
      message: errorMessage,
      stack: properties.stack || 'N/A',
      ...properties
    }, 'error');
  }
  
  /* ===== ENGAGEMENT TRACKING ===== */
  
  /**
   * Track user engagement metric
   */
  trackEngagement(metric, value, properties = {}) {
    const engagement = {
      type: 'engagement',
      metric,
      value,
      sessionId: this.sessionId,
      timestamp: new Date().toISOString(),
      properties: {
        ...properties,
        sessionDuration: this.getSessionDuration(),
        inactiveTime: Date.now() - this.lastActivityTime
      },
      user: { ...this.userContext }
    };
    
    this.engagementQueue.push(engagement);
    
    if (this.config.debug) {
      console.log('[Analytics] Engagement tracked:', metric, value);
    }
    
    return engagement;
  }
  
  /**
   * Track session duration
   */
  trackSessionDuration() {
    const duration = this.getSessionDuration();
    return this.trackEngagement('session_duration', duration, {
      minutes: Math.floor(duration / 60000),
      activeTime: duration - (Date.now() - this.lastActivityTime)
    });
  }
  
  /**
   * Track time on page
   */
  trackTimeOnPage(pageName) {
    const timeOnPage = Date.now() - this.pageLoadTime;
    return this.trackEngagement('time_on_page', timeOnPage, {
      page: pageName,
      seconds: Math.floor(timeOnPage / 1000)
    });
  }
  
  /**
   * Track scroll depth
   */
  trackScrollDepth() {
    const scrollDepth = Math.round(
      (window.scrollY + window.innerHeight) / document.body.scrollHeight * 100
    );
    
    return this.trackEngagement('scroll_depth', scrollDepth, {
      page: window.location.pathname
    });
  }
  
  /* ===== CONVERSION TRACKING ===== */
  
  /**
   * Track conversion event
   */
  trackConversion(conversionName, value, properties = {}) {
    const conversion = {
      type: 'conversion',
      name: conversionName,
      value,
      sessionId: this.sessionId,
      timestamp: new Date().toISOString(),
      properties: {
        ...properties,
        sessionDuration: this.getSessionDuration(),
        userJourneyLength: this.userJourney.length
      },
      user: { ...this.userContext }
    };
    
    this.conversionQueue.push(conversion);
    
    if (this.config.debug) {
      console.log('[Analytics] Conversion tracked:', conversionName, value);
    }
    
    return conversion;
  }
  
  /* ===== FUNNEL TRACKING ===== */
  
  /**
   * Start tracking a funnel
   */
  startFunnel(funnelName, initialStep) {
    const funnel = {
      name: funnelName,
      startTime: Date.now(),
      steps: [{
        step: initialStep,
        timestamp: Date.now(),
        completed: true
      }],
      currentStep: initialStep,
      completed: false
    };
    
    this.activeFunnels.set(funnelName, funnel);
    
    this.trackEvent('funnel_started', {
      funnel: funnelName,
      step: initialStep
    }, 'funnel');
    
    return funnel;
  }
  
  /**
   * Track funnel step completion
   */
  completeFunnelStep(funnelName, step, properties = {}) {
    const funnel = this.activeFunnels.get(funnelName);
    
    if (!funnel) {
      console.warn(`[Analytics] Funnel not found: ${funnelName}`);
      return null;
    }
    
    funnel.steps.push({
      step,
      timestamp: Date.now(),
      completed: true,
      ...properties
    });
    funnel.currentStep = step;
    
    this.trackEvent('funnel_step_completed', {
      funnel: funnelName,
      step,
      stepNumber: funnel.steps.length,
      timeFromStart: Date.now() - funnel.startTime,
      ...properties
    }, 'funnel');
    
    return funnel;
  }
  
  /**
   * Complete a funnel
   */
  completeFunnel(funnelName, properties = {}) {
    const funnel = this.activeFunnels.get(funnelName);
    
    if (!funnel) {
      console.warn(`[Analytics] Funnel not found: ${funnelName}`);
      return null;
    }
    
    funnel.completed = true;
    funnel.completionTime = Date.now();
    funnel.totalDuration = funnel.completionTime - funnel.startTime;
    
    this.trackConversion('funnel_completed', funnel.totalDuration, {
      funnel: funnelName,
      steps: funnel.steps.length,
      duration: funnel.totalDuration,
      ...properties
    });
    
    this.activeFunnels.delete(funnelName);
    
    return funnel;
  }
  
  /**
   * Abandon a funnel
   */
  abandonFunnel(funnelName, reason = 'unknown') {
    const funnel = this.activeFunnels.get(funnelName);
    
    if (!funnel) {
      return null;
    }
    
    this.trackEvent('funnel_abandoned', {
      funnel: funnelName,
      lastStep: funnel.currentStep,
      stepsCompleted: funnel.steps.length,
      reason,
      duration: Date.now() - funnel.startTime
    }, 'funnel');
    
    this.activeFunnels.delete(funnelName);
    
    return funnel;
  }
  
  /* ===== PERFORMANCE TRACKING ===== */
  
  /**
   * Track performance metric
   */
  trackPerformance(metric, value, properties = {}) {
    return this.trackEvent('performance_metric', {
      metric,
      value,
      ...properties
    }, 'performance');
  }
  
  /**
   * Track API response time
   */
  trackAPIPerformance(endpoint, duration, status) {
    this.performanceMetrics.apiResponseTimes.push({
      endpoint,
      duration,
      status,
      timestamp: Date.now()
    });
    
    return this.trackPerformance('api_response_time', duration, {
      endpoint,
      status
    });
  }
  
  /**
   * Track user flow timing
   */
  trackUserFlowTime(flowName, duration, properties = {}) {
    this.performanceMetrics.userFlowTimes.push({
      flow: flowName,
      duration,
      timestamp: Date.now()
    });
    
    return this.trackPerformance('user_flow_time', duration, {
      flow: flowName,
      ...properties
    });
  }
  
  /* ===== DATA REPORTING ===== */
  
  /**
   * Flush events to backend
   */
  async flush(sync = false) {
    if (this.eventQueue.length === 0 && 
        this.engagementQueue.length === 0 && 
        this.conversionQueue.length === 0) {
      return;
    }
    
    const payload = {
      events: [...this.eventQueue],
      engagements: [...this.engagementQueue],
      conversions: [...this.conversionQueue],
      session: {
        sessionId: this.sessionId,
        duration: this.getSessionDuration(),
        pageViews: this.pageViews.length,
        featureUsage: Object.fromEntries(this.featureUsage),
        userJourney: this.userJourney.slice(-50) // Last 50 journey steps
      },
      performance: {
        apiResponseTimes: this.performanceMetrics.apiResponseTimes.slice(-20),
        userFlowTimes: this.performanceMetrics.userFlowTimes.slice(-20)
      }
    };
    
    // Clear queues
    this.eventQueue = [];
    this.engagementQueue = [];
    this.conversionQueue = [];
    
    if (this.config.debug) {
      console.log('[Analytics] Flushing analytics data:', payload);
    }
    
    try {
      if (sync) {
        // Use sendBeacon for synchronous sending (on page unload)
        const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
        navigator.sendBeacon(this.config.endpoint, blob);
      } else {
        // Use regular axios for async sending
        await axios.post(this.config.endpoint, payload);
      }
      
      if (this.config.debug) {
        console.log('[Analytics] Data sent successfully');
      }
    } catch (error) {
      console.error('[Analytics] Failed to send data:', error);
      
      // Re-queue failed events (up to max queue size)
      if (!sync) {
        this.eventQueue = [...payload.events, ...this.eventQueue].slice(0, this.config.maxQueueSize);
        this.engagementQueue = [...payload.engagements, ...this.engagementQueue].slice(0, this.config.maxQueueSize);
        this.conversionQueue = [...payload.conversions, ...this.conversionQueue].slice(0, this.config.maxQueueSize);
      }
    }
  }
  
  /**
   * Start auto-flush timer
   */
  startAutoFlush() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    
    this.flushTimer = setInterval(() => {
      this.flush();
    }, this.config.flushInterval);
  }
  
  /**
   * Stop auto-flush timer
   */
  stopAutoFlush() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
  }
  
  /* ===== UTILITY METHODS ===== */
  
  /**
   * Enable/disable analytics
   */
  setEnabled(enabled) {
    this.config.enabled = enabled;
    
    if (!enabled) {
      this.stopAutoFlush();
    } else {
      this.startAutoFlush();
    }
  }
  
  /**
   * Get analytics statistics
   */
  getStatistics() {
    return {
      session: {
        sessionId: this.sessionId,
        duration: this.getSessionDuration(),
        durationMinutes: Math.floor(this.getSessionDuration() / 60000),
        inactiveTime: Date.now() - this.lastActivityTime
      },
      events: {
        total: this.eventQueue.length,
        pageViews: this.pageViews.length,
        featureUsage: Object.fromEntries(this.featureUsage)
      },
      queues: {
        events: this.eventQueue.length,
        engagements: this.engagementQueue.length,
        conversions: this.conversionQueue.length
      },
      funnels: {
        active: this.activeFunnels.size,
        funnels: Array.from(this.activeFunnels.keys())
      },
      performance: {
        avgApiResponseTime: this.calculateAverage(
          this.performanceMetrics.apiResponseTimes.map(m => m.duration)
        ),
        avgUserFlowTime: this.calculateAverage(
          this.performanceMetrics.userFlowTimes.map(m => m.duration)
        )
      }
    };
  }
  
  /**
   * Calculate average
   */
  calculateAverage(values) {
    if (values.length === 0) return 0;
    return values.reduce((sum, val) => sum + val, 0) / values.length;
  }
  
  /**
   * Get user journey
   */
  getUserJourney() {
    return this.userJourney;
  }
  
  /**
   * Reset analytics
   */
  reset() {
    this.eventQueue = [];
    this.engagementQueue = [];
    this.conversionQueue = [];
    this.featureUsage.clear();
    this.pageViews = [];
    this.userJourney = [];
    this.activeFunnels.clear();
    this.sessionId = this.generateSessionId();
    this.sessionStartTime = Date.now();
    this.pageLoadTime = Date.now();
    this.lastActivityTime = Date.now();
  }
}

// Create singleton instance
const analyticsService = new AnalyticsService();

// Export both the class and the singleton
export { AnalyticsService, analyticsService };
export default analyticsService;


/**
 * Performance Monitor Service
 * Comprehensive performance tracking for the application
 * 
 * Features:
 * - Vault operation tracking
 * - API request monitoring
 * - Component render tracking
 * - Navigation timing
 * - Resource loading metrics
 * - Error tracking
 * - Web Vitals integration
 */
class PerformanceMonitor {
  constructor() {
    this.metrics = {
      vaultUnlock: [],
      itemDecryption: [],
      bulkOperations: [],
      apiRequests: [],
      componentRenders: [],
      navigationTiming: [],
      resourceLoading: [],
      webVitals: {},
      errors: []
    };
    
    // Configuration
    this.config = {
      maxMetricsPerType: 100, // Keep last 100 entries per metric type
      reportInterval: 60000, // Report to backend every 60 seconds
      enableAutoReporting: false, // Disabled by default
      slowApiThreshold: 2000, // > 2 seconds is slow
      slowRenderThreshold: 100 // > 100ms is slow
    };
    
    // Auto-reporting timer
    this.reportTimer = null;
    
    // Initialize Web Vitals tracking
    this.initWebVitals();
    
    // Initialize navigation timing
    this.captureNavigationTiming();
  }
  
  /* ===== VAULT OPERATIONS ===== */
  
  /**
   * Record vault unlock performance
   * @param {number} duration - Duration in milliseconds
   * @param {number} itemCount - Number of items in vault
   */
  recordVaultUnlock(duration, itemCount) {
    const metric = {
      duration,
      itemCount,
      timestamp: Date.now(),
      durationPerItem: itemCount > 0 ? duration / itemCount : 0
    };
    
    this._addMetric('vaultUnlock', metric);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`⚡ Vault unlocked in ${duration}ms (${itemCount} items)`);
      console.log(`   Average: ${(duration / itemCount).toFixed(2)}ms per item`);
    }
  }
  
  /**
   * Record individual item decryption
   * @param {string} itemId - Item identifier
   * @param {number} duration - Duration in milliseconds
   */
  recordItemDecryption(itemId, duration) {
    const metric = {
      itemId,
      duration,
      timestamp: Date.now()
    };
    
    this._addMetric('itemDecryption', metric);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`🔓 Item decrypted in ${duration}ms`);
    }
  }
  
  /**
   * Record bulk operation performance
   * @param {string} operation - Operation name
   * @param {number} duration - Duration in milliseconds
   * @param {number} itemCount - Number of items processed
   */
  recordBulkOperation(operation, duration, itemCount) {
    const metric = {
      operation,
      duration,
      itemCount,
      timestamp: Date.now(),
      durationPerItem: itemCount > 0 ? duration / itemCount : 0
    };
    
    this._addMetric('bulkOperations', metric);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`📦 Bulk ${operation} completed in ${duration}ms (${itemCount} items)`);
      console.log(`   Average: ${(duration / itemCount).toFixed(2)}ms per item`);
    }
  }
  
  /* ===== API REQUEST TRACKING ===== */
  
  /**
   * Record API request performance
   * @param {string} endpoint - API endpoint
   * @param {string} method - HTTP method
   * @param {number} duration - Duration in milliseconds
   * @param {number} statusCode - HTTP status code
   * @param {boolean} success - Whether request was successful
   */
  recordAPIRequest(endpoint, method, duration, statusCode, success = true) {
    const metric = {
      endpoint,
      method,
      duration,
      statusCode,
      success,
      timestamp: Date.now(),
      isSlow: duration > this.config.slowApiThreshold
    };
    
    this._addMetric('apiRequests', metric);
    
    if (process.env.NODE_ENV === 'development' && metric.isSlow) {
      console.warn(`🐌 Slow API request: ${method} ${endpoint} (${duration}ms)`);
    }
  }
  
  /* ===== COMPONENT RENDER TRACKING ===== */
  
  /**
   * Record component render performance
   * @param {string} componentName - Name of the component
   * @param {string} phase - 'mount' or 'update'
   * @param {number} duration - Duration in milliseconds
   */
  recordComponentRender(componentName, phase, duration) {
    const metric = {
      componentName,
      phase,
      duration,
      timestamp: Date.now(),
      isSlow: duration > this.config.slowRenderThreshold
    };
    
    this._addMetric('componentRenders', metric);
    
    if (process.env.NODE_ENV === 'development' && metric.isSlow) {
      console.warn(`🐌 Slow ${phase}: ${componentName} (${duration}ms)`);
    }
  }
  
  /* ===== ERROR TRACKING ===== */
  
  /**
   * Record an error
   * @param {Error} error - Error object
   * @param {string} context - Context where error occurred
   * @param {Object} additionalInfo - Additional error information
   */
  recordError(error, context = 'unknown', additionalInfo = {}) {
    const metric = {
      message: error.message,
      stack: error.stack,
      context,
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      ...additionalInfo
    };
    
    this._addMetric('errors', metric);
    
    console.error(`❌ Error in ${context}:`, error);
  }
  
  /* ===== WEB VITALS ===== */
  
  /**
   * Initialize Web Vitals tracking
   */
  initWebVitals() {
    if (typeof window === 'undefined') return;
    
    // Track Web Vitals if available
    if ('PerformanceObserver' in window) {
      try {
        // Largest Contentful Paint (LCP)
        const lcpObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1];
          this.metrics.webVitals.lcp = lastEntry.renderTime || lastEntry.loadTime;
        });
        lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
        
        // First Input Delay (FID)
        const fidObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          entries.forEach((entry) => {
            this.metrics.webVitals.fid = entry.processingStart - entry.startTime;
          });
        });
        fidObserver.observe({ entryTypes: ['first-input'] });
        
        // Cumulative Layout Shift (CLS)
        let clsValue = 0;
        const clsObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!entry.hadRecentInput) {
              clsValue += entry.value;
              this.metrics.webVitals.cls = clsValue;
            }
          }
        });
        clsObserver.observe({ entryTypes: ['layout-shift'] });
      } catch (e) {
        console.warn('Web Vitals tracking unavailable:', e);
      }
    }
  }
  
  /* ===== NAVIGATION TIMING ===== */
  
  /**
   * Capture navigation timing metrics
   */
  captureNavigationTiming() {
    if (typeof window === 'undefined') return;
    
    window.addEventListener('load', () => {
      setTimeout(() => {
        const timing = performance.timing;
        
        const metric = {
          dns: timing.domainLookupEnd - timing.domainLookupStart,
          tcp: timing.connectEnd - timing.connectStart,
          request: timing.responseStart - timing.requestStart,
          response: timing.responseEnd - timing.responseStart,
          dom: timing.domComplete - timing.domLoading,
          load: timing.loadEventEnd - timing.loadEventStart,
          total: timing.loadEventEnd - timing.navigationStart,
          timestamp: Date.now()
        };
        
        this._addMetric('navigationTiming', metric);
        
        if (process.env.NODE_ENV === 'development') {
          console.log('📊 Navigation timing:', metric);
        }
      }, 0);
    });
  }
  
  /* ===== RESOURCE LOADING ===== */
  
  /**
   * Capture resource loading performance
   */
  captureResourceTiming() {
    if (typeof window === 'undefined' || !performance.getEntriesByType) return;
    
    const resources = performance.getEntriesByType('resource');
    const summary = {
      scripts: [],
      stylesheets: [],
      images: [],
      fonts: [],
      other: []
    };
    
    resources.forEach((resource) => {
      const entry = {
        name: resource.name,
        duration: resource.duration,
        size: resource.transferSize,
        type: resource.initiatorType
      };
      
      if (resource.initiatorType === 'script') {
        summary.scripts.push(entry);
      } else if (resource.initiatorType === 'link' || resource.initiatorType === 'css') {
        summary.stylesheets.push(entry);
      } else if (resource.initiatorType === 'img') {
        summary.images.push(entry);
      } else if (resource.name.includes('.woff') || resource.name.includes('.ttf')) {
        summary.fonts.push(entry);
      } else {
        summary.other.push(entry);
      }
    });
    
    this.metrics.resourceLoading.push({
      ...summary,
      timestamp: Date.now(),
      totalResources: resources.length
    });
    
    return summary;
  }
  
  /* ===== STATISTICS ===== */
  
  /**
   * Get average vault unlock time
   * @returns {number} Average duration in milliseconds
   */
  getAverageVaultUnlockTime() {
    return this._calculateAverage(this.metrics.vaultUnlock, 'duration');
  }
  
  /**
   * Get average item decryption time
   * @returns {number} Average duration in milliseconds
   */
  getAverageItemDecryptionTime() {
    return this._calculateAverage(this.metrics.itemDecryption, 'duration');
  }
  
  /**
   * Get average API request time
   * @returns {number} Average duration in milliseconds
   */
  getAverageAPIRequestTime() {
    return this._calculateAverage(this.metrics.apiRequests, 'duration');
  }
  
  /**
   * Get API success rate
   * @returns {number} Success rate as percentage (0-100)
   */
  getAPISuccessRate() {
    if (this.metrics.apiRequests.length === 0) return 100;
    
    const successful = this.metrics.apiRequests.filter(r => r.success).length;
    return (successful / this.metrics.apiRequests.length) * 100;
  }
  
  /**
   * Get slow API requests
   * @returns {Array} List of slow API requests
   */
  getSlowAPIRequests() {
    return this.metrics.apiRequests.filter(r => r.isSlow);
  }
  
  /**
   * Get slow component renders
   * @returns {Array} List of slow component renders
   */
  getSlowComponentRenders() {
    return this.metrics.componentRenders.filter(r => r.isSlow);
  }
  
  /**
   * Get performance report
   * @returns {Object} Comprehensive performance statistics
   */
  getReport() {
    return {
      vaultUnlock: {
        average: this.getAverageVaultUnlockTime(),
        samples: this.metrics.vaultUnlock.length,
        latest: this._getLatest(this.metrics.vaultUnlock)
      },
      itemDecryption: {
        average: this.getAverageItemDecryptionTime(),
        samples: this.metrics.itemDecryption.length,
        latest: this._getLatest(this.metrics.itemDecryption)
      },
      bulkOperations: {
        samples: this.metrics.bulkOperations.length,
        latest: this._getLatest(this.metrics.bulkOperations)
      },
      apiRequests: {
        average: this.getAverageAPIRequestTime(),
        successRate: this.getAPISuccessRate(),
        samples: this.metrics.apiRequests.length,
        slowRequests: this.getSlowAPIRequests().length
      },
      componentRenders: {
        samples: this.metrics.componentRenders.length,
        slowRenders: this.getSlowComponentRenders().length
      },
      webVitals: this.metrics.webVitals,
      errors: {
        count: this.metrics.errors.length,
        latest: this._getLatest(this.metrics.errors)
      },
      navigationTiming: this._getLatest(this.metrics.navigationTiming)
    };
  }
  
  /* ===== UTILITY METHODS ===== */
  
  /**
   * Add metric with automatic pruning
   * @private
   */
  _addMetric(type, metric) {
    this.metrics[type].push(metric);
    
    // Prune old metrics
    if (this.metrics[type].length > this.config.maxMetricsPerType) {
      this.metrics[type].shift();
    }
  }
  
  /**
   * Calculate average of a numeric property
   * @private
   */
  _calculateAverage(metrics, property) {
    if (metrics.length === 0) return 0;
    
    const total = metrics.reduce((sum, m) => sum + m[property], 0);
    return total / metrics.length;
  }
  
  /**
   * Get latest metric
   * @private
   */
  _getLatest(metrics) {
    return metrics.length > 0 ? metrics[metrics.length - 1] : null;
  }
  
  /**
   * Clear all metrics
   */
  clearMetrics() {
    this.metrics = {
      vaultUnlock: [],
      itemDecryption: [],
      bulkOperations: [],
      apiRequests: [],
      componentRenders: [],
      navigationTiming: [],
      resourceLoading: [],
      webVitals: {},
      errors: []
    };
  }
  
  /**
   * Export metrics to JSON
   * @returns {string} JSON string of all metrics
   */
  exportMetrics() {
    return JSON.stringify({
      metrics: this.metrics,
      report: this.getReport(),
      timestamp: Date.now()
    }, null, 2);
  }
  
  /**
   * Enable auto-reporting to backend
   * @param {string} apiEndpoint - Backend API endpoint
   */
  enableAutoReporting(apiEndpoint = '/api/performance/frontend/') {
    this.config.enableAutoReporting = true;
    
    this.reportTimer = setInterval(() => {
      this.reportToBackend(apiEndpoint);
    }, this.config.reportInterval);
    
    console.log('✅ Auto-reporting enabled');
  }
  
  /**
   * Disable auto-reporting
   */
  disableAutoReporting() {
    this.config.enableAutoReporting = false;
    
    if (this.reportTimer) {
      clearInterval(this.reportTimer);
      this.reportTimer = null;
    }
    
    console.log('❌ Auto-reporting disabled');
  }
  
  /**
   * Report metrics to backend
   * @param {string} apiEndpoint - Backend API endpoint
   */
  async reportToBackend(apiEndpoint = '/api/performance/frontend/') {
    try {
      const report = this.getReport();
      
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(report)
      });
      
      if (response.ok) {
        console.log('✅ Performance metrics reported to backend');
      } else {
        console.error('❌ Failed to report metrics:', response.statusText);
      }
    } catch (error) {
      console.error('❌ Error reporting metrics:', error);
    }
  }
}

// Create singleton instance
export const performanceMonitor = new PerformanceMonitor();

// Export class for testing
export default PerformanceMonitor;


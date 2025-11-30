/**
 * Error Tracking Service
 * ======================
 * 
 * Centralized error tracking, logging, and reporting for the frontend.
 * 
 * Features:
 * - Error capturing and logging
 * - Error grouping and deduplication
 * - Stack trace analysis
 * - User context tracking
 * - Error reporting to backend
 * - Error rate monitoring
 * 
 * Usage:
 *   import { errorTracker } from './services/errorTracker';
 *   
 *   // Track error
 *   errorTracker.captureError(error, 'ComponentName', { user: 'john' });
 *   
 *   // Track with severity
 *   errorTracker.captureError(error, 'API', { endpoint: '/api/data' }, 'critical');
 *   
 *   // Get error statistics
 *   const stats = errorTracker.getStatistics();
 */

import axios from 'axios';

class ErrorTracker {
  constructor() {
    this.errors = [];
    this.errorGroups = new Map();
    this.maxErrors = 100; // Keep last 100 errors
    this.reportingEnabled = true;
    this.reportingEndpoint = '/api/performance/frontend/';
    this.userContext = {};
    this.sessionId = this.generateSessionId();
    
    // Error rate tracking
    this.errorCounts = {
      total: 0,
      byType: {},
      bySeverity: {},
      byContext: {}
    };
    
    // Initialize global error handlers
    this.initializeGlobalHandlers();
  }

  /**
   * Generate unique session ID
   */
  generateSessionId() {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Initialize global error handlers
   */
  initializeGlobalHandlers() {
    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.captureError(
        new Error(event.reason),
        'UnhandledPromiseRejection',
        {
          promise: true,
          reason: event.reason
        },
        'error'
      );
    });

    // Global errors
    window.addEventListener('error', (event) => {
      this.captureError(
        event.error || new Error(event.message),
        'GlobalError',
        {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno
        },
        'error'
      );
    });

    // Console error override (optional - for capturing console.error calls)
    this.originalConsoleError = console.error;
    console.error = (...args) => {
      // Prevent infinite loop: don't capture errors from errorTracker itself
      const errorString = args.join(' ');
      if (!errorString.includes('[ErrorTracker]')) {
        this.captureError(
          new Error(errorString),
          'ConsoleError',
          { arguments: args },
          'warning'
        );
      }
      this.originalConsoleError.apply(console, args);
    };
  }

  /**
   * Set user context for error tracking
   */
  setUserContext(context) {
    this.userContext = {
      ...this.userContext,
      ...context,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Clear user context (e.g., on logout)
   */
  clearUserContext() {
    this.userContext = {};
  }

  /**
   * Capture and track an error
   */
  captureError(error, context = 'Unknown', metadata = {}, severity = 'error') {
    // Create error entry
    const errorEntry = {
      id: this.generateErrorId(),
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      
      // Error details
      type: error.name || 'Error',
      message: error.message || String(error),
      stack: error.stack || new Error().stack,
      
      // Context
      context: context,
      severity: severity,
      
      // Metadata
      metadata: {
        ...metadata,
        url: window.location.href,
        userAgent: navigator.userAgent,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        }
      },
      
      // User context
      user: { ...this.userContext }
    };

    // Add to errors array
    this.errors.push(errorEntry);

    // Maintain max errors limit
    if (this.errors.length > this.maxErrors) {
      this.errors.shift();
    }

    // Group similar errors
    this.groupError(errorEntry);

    // Update statistics
    this.updateStatistics(errorEntry);

    // Log to console in development (use original to avoid infinite loop)
    if (process.env.NODE_ENV === 'development' && this.originalConsoleError) {
      this.originalConsoleError(`[ErrorTracker] ${severity.toUpperCase()}:`, {
        context,
        message: errorEntry.message,
        metadata,
        error
      });
    }

    // Report to backend if enabled
    if (this.reportingEnabled) {
      this.reportError(errorEntry);
    }

    return errorEntry.id;
  }

  /**
   * Generate unique error ID
   */
  generateErrorId() {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Group similar errors together
   */
  groupError(errorEntry) {
    // Create fingerprint for grouping
    const fingerprint = this.createErrorFingerprint(errorEntry);

    if (this.errorGroups.has(fingerprint)) {
      // Increment count for existing group
      const group = this.errorGroups.get(fingerprint);
      group.count++;
      group.lastSeen = errorEntry.timestamp;
      group.instances.push(errorEntry.id);
    } else {
      // Create new group
      this.errorGroups.set(fingerprint, {
        fingerprint,
        type: errorEntry.type,
        message: errorEntry.message,
        context: errorEntry.context,
        count: 1,
        firstSeen: errorEntry.timestamp,
        lastSeen: errorEntry.timestamp,
        instances: [errorEntry.id]
      });
    }
  }

  /**
   * Create fingerprint for error grouping
   */
  createErrorFingerprint(errorEntry) {
    // Use type, message, and first line of stack for fingerprint
    const stackLine = errorEntry.stack ? errorEntry.stack.split('\n')[1] : '';
    return `${errorEntry.type}:${errorEntry.message}:${stackLine}`.replace(/\s+/g, '');
  }

  /**
   * Update error statistics
   */
  updateStatistics(errorEntry) {
    // Total count
    this.errorCounts.total++;

    // By type
    this.errorCounts.byType[errorEntry.type] = (this.errorCounts.byType[errorEntry.type] || 0) + 1;

    // By severity
    this.errorCounts.bySeverity[errorEntry.severity] = (this.errorCounts.bySeverity[errorEntry.severity] || 0) + 1;

    // By context
    this.errorCounts.byContext[errorEntry.context] = (this.errorCounts.byContext[errorEntry.context] || 0) + 1;
  }

  /**
   * Report error to backend
   */
  async reportError(errorEntry) {
    try {
      await axios.post(this.reportingEndpoint, {
        type: 'error',
        error: {
          id: errorEntry.id,
          type: errorEntry.type,
          message: errorEntry.message,
          stack: errorEntry.stack,
          context: errorEntry.context,
          severity: errorEntry.severity,
          timestamp: errorEntry.timestamp
        },
        metadata: errorEntry.metadata,
        user: errorEntry.user,
        session: this.sessionId
      });
    } catch (error) {
      // Don't let error reporting break the application
      console.warn('Failed to report error to backend:', error);
    }
  }

  /**
   * Get all errors
   */
  getErrors(filters = {}) {
    let filteredErrors = [...this.errors];

    // Filter by severity
    if (filters.severity) {
      filteredErrors = filteredErrors.filter(e => e.severity === filters.severity);
    }

    // Filter by context
    if (filters.context) {
      filteredErrors = filteredErrors.filter(e => e.context === filters.context);
    }

    // Filter by type
    if (filters.type) {
      filteredErrors = filteredErrors.filter(e => e.type === filters.type);
    }

    // Filter by time range
    if (filters.since) {
      const since = new Date(filters.since);
      filteredErrors = filteredErrors.filter(e => new Date(e.timestamp) >= since);
    }

    return filteredErrors;
  }

  /**
   * Get error groups
   */
  getErrorGroups() {
    return Array.from(this.errorGroups.values());
  }

  /**
   * Get error statistics
   */
  getStatistics() {
    const errorRate = this.calculateErrorRate();

    return {
      total: this.errorCounts.total,
      byType: { ...this.errorCounts.byType },
      bySeverity: { ...this.errorCounts.bySeverity },
      byContext: { ...this.errorCounts.byContext },
      errorRate: errorRate,
      totalGroups: this.errorGroups.size,
      sessionId: this.sessionId
    };
  }

  /**
   * Calculate error rate (errors per minute)
   */
  calculateErrorRate() {
    if (this.errors.length === 0) return 0;

    const now = new Date();
    const oneMinuteAgo = new Date(now - 60000);

    const recentErrors = this.errors.filter(e => 
      new Date(e.timestamp) >= oneMinuteAgo
    );

    return recentErrors.length;
  }

  /**
   * Get error by ID
   */
  getErrorById(id) {
    return this.errors.find(e => e.id === id);
  }

  /**
   * Clear all errors
   */
  clearErrors() {
    this.errors = [];
    this.errorGroups.clear();
    this.errorCounts = {
      total: 0,
      byType: {},
      bySeverity: {},
      byContext: {}
    };
  }

  /**
   * Enable error reporting
   */
  enableReporting() {
    this.reportingEnabled = true;
  }

  /**
   * Disable error reporting
   */
  disableReporting() {
    this.reportingEnabled = false;
  }

  /**
   * Set reporting endpoint
   */
  setReportingEndpoint(endpoint) {
    this.reportingEndpoint = endpoint;
  }

  /**
   * Export errors as JSON
   */
  exportErrors() {
    return {
      sessionId: this.sessionId,
      errors: this.errors,
      groups: this.getErrorGroups(),
      statistics: this.getStatistics(),
      exportedAt: new Date().toISOString()
    };
  }

  /**
   * Capture API error
   */
  captureAPIError(error, endpoint, requestData = {}) {
    const metadata = {
      endpoint,
      requestData,
      statusCode: error.response?.status,
      responseData: error.response?.data
    };

    const severity = error.response?.status >= 500 ? 'critical' : 'error';

    return this.captureError(error, 'APIError', metadata, severity);
  }

  /**
   * Capture component error
   */
  captureComponentError(error, componentName, props = {}) {
    return this.captureError(error, `Component:${componentName}`, { props }, 'error');
  }

  /**
   * Capture validation error
   */
  captureValidationError(message, field, value) {
    return this.captureError(
      new Error(message),
      'ValidationError',
      { field, value },
      'warning'
    );
  }

  /**
   * Capture network error
   */
  captureNetworkError(error, url) {
    return this.captureError(
      error,
      'NetworkError',
      { url, online: navigator.onLine },
      'error'
    );
  }
}

// Create singleton instance
export const errorTracker = new ErrorTracker();

// Export class for testing
export { ErrorTracker };

// Export helper functions
export const captureError = (error, context, metadata, severity) => 
  errorTracker.captureError(error, context, metadata, severity);

export const captureAPIError = (error, endpoint, requestData) => 
  errorTracker.captureAPIError(error, endpoint, requestData);

export const captureComponentError = (error, componentName, props) => 
  errorTracker.captureComponentError(error, componentName, props);

export const setUserContext = (context) => 
  errorTracker.setUserContext(context);

export const clearUserContext = () => 
  errorTracker.clearUserContext();

export default errorTracker;


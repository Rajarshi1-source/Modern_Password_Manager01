/**
 * Centralized Error Handler
 * Provides unified error handling, tracking, and reporting
 */

import { performanceMonitor } from '../services/performanceMonitor';

class ErrorHandler {
  constructor() {
    this.errorQueue = [];
    this.maxQueueSize = 50;
    this.reportEndpoint = '/api/errors/report/';
    
    // Initialize global error handlers
    this.initializeGlobalHandlers();
  }
  
  /**
   * Initialize global error handlers
   */
  initializeGlobalHandlers() {
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError(
        new Error(event.reason),
        'unhandledRejection',
        { promise: true }
      );
    });
    
    // Handle global errors
    window.addEventListener('error', (event) => {
      this.handleError(
        event.error || new Error(event.message),
        'globalError',
        {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno
        }
      );
    });
  }
  
  /**
   * Handle an error
   * @param {Error} error - The error object
   * @param {string} context - Context where error occurred
   * @param {Object} additionalInfo - Additional error information
   */
  handleError(error, context = 'unknown', additionalInfo = {}) {
    // Record in performance monitor
    performanceMonitor.recordError(error, context, additionalInfo);
    
    // Create error record
    const errorRecord = {
      message: error.message,
      stack: error.stack,
      context,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      ...additionalInfo
    };
    
    // Add to queue
    this.errorQueue.push(errorRecord);
    
    // Prune queue if too large
    if (this.errorQueue.length > this.maxQueueSize) {
      this.errorQueue.shift();
    }
    
    // Log to console
    console.error(`[${context}] Error:`, error);
    
    // Report to backend (async, non-blocking)
    this.reportError(errorRecord);
  }
  
  /**
   * Handle API errors
   * @param {Response} response - Fetch response object
   * @param {string} endpoint - API endpoint
   * @param {Object} requestData - Request data
   */
  async handleAPIError(response, endpoint, requestData = {}) {
    let errorMessage = 'API request failed';
    let errorData = {};
    
    try {
      const data = await response.json();
      errorMessage = data.message || data.error || errorMessage;
      errorData = data;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    
    const error = new Error(errorMessage);
    
    this.handleError(error, 'apiError', {
      endpoint,
      statusCode: response.status,
      requestData,
      responseData: errorData
    });
    
    return {
      success: false,
      error: errorMessage,
      statusCode: response.status,
      data: errorData
    };
  }
  
  /**
   * Handle validation errors
   * @param {Object} validationErrors - Validation error object
   * @param {string} formName - Name of the form
   */
  handleValidationError(validationErrors, formName = 'form') {
    const error = new Error('Validation failed');
    
    this.handleError(error, 'validationError', {
      formName,
      validationErrors
    });
    
    return {
      success: false,
      errors: validationErrors
    };
  }
  
  /**
   * Handle network errors
   * @param {Error} error - Network error
   * @param {string} endpoint - API endpoint
   */
  handleNetworkError(error, endpoint) {
    this.handleError(error, 'networkError', {
      endpoint,
      isOnline: navigator.onLine
    });
    
    return {
      success: false,
      error: 'Network request failed. Please check your connection.',
      isOffline: !navigator.onLine
    };
  }
  
  /**
   * Handle authentication errors
   * @param {Error} error - Authentication error
   * @param {string} action - Action that failed
   */
  handleAuthError(error, action = 'authentication') {
    this.handleError(error, 'authError', {
      action,
      isAuthenticated: !!localStorage.getItem('access_token')
    });
    
    // Clear auth tokens
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Redirect to login
    window.location.href = '/login';
    
    return {
      success: false,
      error: 'Authentication failed. Please log in again.',
      requiresLogin: true
    };
  }
  
  /**
   * Handle crypto errors
   * @param {Error} error - Cryptography error
   * @param {string} operation - Crypto operation that failed
   */
  handleCryptoError(error, operation) {
    this.handleError(error, 'cryptoError', {
      operation,
      browserSupport: {
        webCrypto: !!window.crypto?.subtle,
        cryptoJS: typeof window.CryptoJS !== 'undefined'
      }
    });
    
    return {
      success: false,
      error: 'Encryption/decryption failed. Please try again.',
      operation
    };
  }
  
  /**
   * Report error to backend
   * @param {Object} errorRecord - Error record
   */
  async reportError(errorRecord) {
    try {
      await fetch(this.reportEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(errorRecord)
      });
    } catch (e) {
      // Silently fail - don't want error reporting to cause more errors
      console.warn('Failed to report error to backend:', e);
    }
  }
  
  /**
   * Get error history
   * @returns {Array} Array of error records
   */
  getErrorHistory() {
    return [...this.errorQueue];
  }
  
  /**
   * Get error summary
   * @returns {Object} Error statistics
   */
  getErrorSummary() {
    const summary = {
      total: this.errorQueue.length,
      byContext: {},
      recent: this.errorQueue.slice(-5)
    };
    
    this.errorQueue.forEach(error => {
      summary.byContext[error.context] = (summary.byContext[error.context] || 0) + 1;
    });
    
    return summary;
  }
  
  /**
   * Clear error history
   */
  clearErrors() {
    this.errorQueue = [];
  }
  
  /**
   * Export errors to JSON
   * @returns {string} JSON string of error history
   */
  exportErrors() {
    return JSON.stringify({
      errors: this.errorQueue,
      summary: this.getErrorSummary(),
      timestamp: new Date().toISOString()
    }, null, 2);
  }
  
  /**
   * Show user-friendly error message
   * @param {string} message - Error message
   * @param {string} type - Message type (error, warning, info)
   */
  showUserMessage(message, type = 'error') {
    // This can be enhanced with a toast notification library
    console[type](`[User Message] ${message}`);
    
    // You can integrate with a UI notification system here
    // For example: toast.error(message);
  }
  
  /**
   * Get user-friendly error message
   * @param {Error} error - Error object
   * @param {string} context - Error context
   * @returns {string} User-friendly message
   */
  getUserFriendlyMessage(error, context) {
    const messages = {
      apiError: 'Failed to connect to the server. Please try again.',
      networkError: 'Network connection failed. Please check your internet connection.',
      authError: 'Your session has expired. Please log in again.',
      cryptoError: 'Security operation failed. Please try again.',
      validationError: 'Please check your input and try again.',
      unknown: 'An unexpected error occurred. Please try again.'
    };
    
    return messages[context] || messages.unknown;
  }
}

// Create singleton instance
export const errorHandler = new ErrorHandler();

// Export class for testing
export default ErrorHandler;

/**
 * React Error Boundary Component
 * Use this to catch React component errors
 */
import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    errorHandler.handleError(error, 'reactError', {
      componentStack: errorInfo.componentStack
    });
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p>We're sorry for the inconvenience. Please try refreshing the page.</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Async error handler wrapper
 * Use this to wrap async functions
 * 
 * @param {Function} fn - Async function to wrap
 * @param {string} context - Error context
 * @returns {Function} Wrapped function
 */
export function withErrorHandler(fn, context = 'async') {
  return async (...args) => {
    try {
      return await fn(...args);
    } catch (error) {
      errorHandler.handleError(error, context);
      throw error;
    }
  };
}

/**
 * Try-catch helper for cleaner error handling
 * 
 * @param {Function} fn - Function to execute
 * @param {string} context - Error context
 * @returns {[any, Error]} Tuple of [result, error]
 */
export async function tryCatch(fn, context = 'tryCatch') {
  try {
    const result = await fn();
    return [result, null];
  } catch (error) {
    errorHandler.handleError(error, context);
    return [null, error];
  }
}


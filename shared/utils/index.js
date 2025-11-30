/**
 * Shared utility functions for cross-platform password manager
 * This module provides common utilities that can be used across different platforms
 */

/**
 * Generate a cryptographically secure random ID
 * @param {number} length - Length of the ID to generate
 * @returns {string} Secure random ID
 */
export const generateSecureId = (length = 32) => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    // Browser/Node.js with crypto support
    const randomBytes = new Uint8Array(length);
    crypto.getRandomValues(randomBytes);
    
    for (let i = 0; i < length; i++) {
      result += chars[randomBytes[i] % chars.length];
    }
  } else {
    // Fallback for environments without crypto
    for (let i = 0; i < length; i++) {
      result += chars[Math.floor(Math.random() * chars.length)];
    }
  }
  
  return result;
};

/**
 * Generate a UUID v4 with proper operator precedence
 * @returns {string} UUID v4 string
 */
export const generateUUID = () => {
  return (([1e7]) + (-1e3) + (-4e3) + (-8e3) + (-1e11)).replace(/[018]/g, c =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
};

/**
 * Validate email address format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid email format
 */
export const isValidEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Sanitize string for safe display
 * @param {string} str - String to sanitize
 * @returns {string} Sanitized string
 */
export const sanitizeString = (str) => {
  if (typeof str !== 'string') return '';
  
  return str
    .replace(/[<>]/g, '') // Remove potential HTML tags
    .replace(/javascript:/gi, '') // Remove javascript: URLs
    .trim();
};

/**
 * Deep clone an object (for simple objects without functions)
 * @param {object} obj - Object to clone
 * @returns {object} Cloned object
 */
export const deepClone = (obj) => {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj.getTime());
  if (obj instanceof Array) return obj.map(item => deepClone(item));
  
  const cloned = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      cloned[key] = deepClone(obj[key]);
    }
  }
  return cloned;
};

/**
 * Format bytes to human readable format
 * @param {number} bytes - Number of bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted string
 */
export const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

/**
 * Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

/**
 * Check if running in browser environment
 * @returns {boolean} True if in browser
 */
export const isBrowser = () => {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
};

/**
 * Check if running in Node.js environment
 * @returns {boolean} True if in Node.js
 */
export const isNode = () => {
  return typeof process !== 'undefined' && process.versions && process.versions.node;
};

/**
 * Safe JSON parse with fallback
 * @param {string} str - JSON string to parse
 * @param {*} fallback - Fallback value if parsing fails
 * @returns {*} Parsed object or fallback
 */
export const safeJsonParse = (str, fallback = null) => {
  try {
    return JSON.parse(str);
  } catch (e) {
    return fallback;
  }
};

/**
 * Sleep/delay function
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise} Promise that resolves after delay
 */
export const sleep = (ms) => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

// Export all utilities as default object as well
export default {
  generateSecureId,
  generateUUID,
  isValidEmail,
  sanitizeString,
  deepClone,
  formatBytes,
  debounce,
  isBrowser,
  isNode,
  safeJsonParse,
  sleep
};

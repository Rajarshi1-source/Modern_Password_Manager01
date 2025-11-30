/**
 * Shared utility functions for the Password Manager desktop application.
 * These utilities provide common functionality across main and renderer processes.
 */

const { app, shell } = require('electron');
const path = require('path');
const fs = require('fs');

/**
 * Platform detection utilities
 */
const Platform = {
  isWindows: () => process.platform === 'win32',
  isMacOS: () => process.platform === 'darwin',
  isLinux: () => process.platform === 'linux',
  
  getCurrentPlatform: () => process.platform,
  
  getArchitecture: () => process.arch,
  
  getOSVersion: () => {
    try {
      const os = require('os');
      return os.release();
    } catch (error) {
      return 'unknown';
    }
  }
};

/**
 * Path utilities for application files and directories
 */
const PathUtils = {
  /**
   * Get the user data directory
   */
  getUserDataPath: () => {
    try {
      return app.getPath('userData');
    } catch (error) {
      return path.join(process.cwd(), 'userData');
    }
  },
  
  /**
   * Get the secure keys storage directory
   */
  getSecureKeysPath: () => {
    const userDataPath = PathUtils.getUserDataPath();
    return path.join(userDataPath, 'secure_keys');
  },
  
  /**
   * Get logs directory
   */
  getLogsPath: () => {
    const userDataPath = PathUtils.getUserDataPath();
    return path.join(userDataPath, 'logs');
  },
  
  /**
   * Get application cache directory
   */
  getCachePath: () => {
    try {
      return app.getPath('temp');
    } catch (error) {
      return path.join(process.cwd(), 'cache');
    }
  },
  
  /**
   * Ensure directory exists, create if it doesn't
   */
  ensureDirectoryExists: (dirPath) => {
    try {
      if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
      }
      return true;
    } catch (error) {
      console.error('Failed to create directory:', dirPath, error);
      return false;
    }
  }
};

/**
 * Security utilities
 */
const SecurityUtils = {
  /**
   * Generate a cryptographically secure random string
   */
  generateSecureId: (length = 32) => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
      const randomBytes = new Uint8Array(length);
      crypto.getRandomValues(randomBytes);
      
      for (let i = 0; i < length; i++) {
        result += chars[randomBytes[i] % chars.length];
      }
    } else {
      // Fallback using Node.js crypto
      const crypto = require('crypto');
      const randomBytes = crypto.randomBytes(length);
      
      for (let i = 0; i < length; i++) {
        result += chars[randomBytes[i] % chars.length];
      }
    }
    
    return result;
  },
  
  /**
   * Generate a UUID v4
   */
  generateUUID: () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    } else {
      // Fallback UUID generation
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    }
  },
  
  /**
   * Hash a string using SHA-256
   */
  hashString: async (input) => {
    try {
      const crypto = require('crypto');
      return crypto.createHash('sha256').update(input).digest('hex');
    } catch (error) {
      console.error('Failed to hash string:', error);
      return null;
    }
  },
  
  /**
   * Validate if a string is a valid email
   */
  isValidEmail: (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }
};

/**
 * Application state utilities
 */
const AppUtils = {
  /**
   * Get application version
   */
  getVersion: () => {
    try {
      return app.getVersion();
    } catch (error) {
      return '1.0.0';
    }
  },
  
  /**
   * Get application name
   */
  getName: () => {
    try {
      return app.getName();
    } catch (error) {
      return 'Password Manager';
    }
  },
  
  /**
   * Open URL in external browser
   */
  openExternal: (url) => {
    try {
      shell.openExternal(url);
      return true;
    } catch (error) {
      console.error('Failed to open external URL:', error);
      return false;
    }
  },
  
  /**
   * Show item in file manager
   */
  showItemInFolder: (fullPath) => {
    try {
      shell.showItemInFolder(fullPath);
      return true;
    } catch (error) {
      console.error('Failed to show item in folder:', error);
      return false;
    }
  }
};

/**
 * Logging utilities
 */
const LogUtils = {
  /**
   * Create a logger with different levels
   */
  createLogger: (name) => {
    const logLevel = process.env.LOG_LEVEL || 'info';
    const logLevels = { error: 0, warn: 1, info: 2, debug: 3 };
    const currentLevel = logLevels[logLevel] || 2;
    
    return {
      error: (message, ...args) => {
        if (currentLevel >= 0) {
          console.error(`[${name}] ERROR:`, message, ...args);
        }
      },
      warn: (message, ...args) => {
        if (currentLevel >= 1) {
          console.warn(`[${name}] WARN:`, message, ...args);
        }
      },
      info: (message, ...args) => {
        if (currentLevel >= 2) {
          console.info(`[${name}] INFO:`, message, ...args);
        }
      },
      debug: (message, ...args) => {
        if (currentLevel >= 3) {
          console.debug(`[${name}] DEBUG:`, message, ...args);
        }
      }
    };
  }
};

/**
 * Time and date utilities
 */
const TimeUtils = {
  /**
   * Format timestamp to human-readable string
   */
  formatTimestamp: (timestamp, options = {}) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        ...options
      });
    } catch (error) {
      return 'Invalid Date';
    }
  },
  
  /**
   * Get time elapsed since timestamp
   */
  getTimeElapsed: (timestamp) => {
    const now = Date.now();
    const elapsed = now - timestamp;
    
    if (elapsed < 60000) { // Less than 1 minute
      return 'Just now';
    } else if (elapsed < 3600000) { // Less than 1 hour
      const minutes = Math.floor(elapsed / 60000);
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else if (elapsed < 86400000) { // Less than 1 day
      const hours = Math.floor(elapsed / 3600000);
      return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    } else {
      const days = Math.floor(elapsed / 86400000);
      return `${days} day${days !== 1 ? 's' : ''} ago`;
    }
  },
  
  /**
   * Sleep for specified milliseconds
   */
  sleep: (ms) => {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
};

/**
 * Validation utilities
 */
const ValidationUtils = {
  /**
   * Validate if a value is not empty
   */
  isNotEmpty: (value) => {
    return value !== null && value !== undefined && value !== '';
  },
  
  /**
   * Validate if a string meets minimum length
   */
  hasMinLength: (value, minLength) => {
    return typeof value === 'string' && value.length >= minLength;
  },
  
  /**
   * Validate if a value is a valid URL
   */
  isValidUrl: (value) => {
    try {
      new URL(value);
      return true;
    } catch (error) {
      return false;
    }
  }
};

module.exports = {
  Platform,
  PathUtils,
  SecurityUtils,
  AppUtils,
  LogUtils,
  TimeUtils,
  ValidationUtils
};

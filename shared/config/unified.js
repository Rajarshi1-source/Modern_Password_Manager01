/**
 * Unified Configuration System for Password Manager
 * Provides consistent configuration across all platforms (desktop, browser, extension, mobile)
 */

/**
 * Detect the current platform/environment
 */
const detectPlatform = () => {
  // Check for Electron
  if (typeof process !== 'undefined' && process.versions && process.versions.electron) {
    return 'electron';
  }
  
  // Check for browser extension
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id) {
    return 'browser-extension';
  }
  
  // Check for React Native
  if (typeof navigator !== 'undefined' && navigator.product === 'ReactNative') {
    return 'mobile';
  }
  
  // Check for browser
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    return 'browser';
  }
  
  // Check for Node.js
  if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    return 'node';
  }
  
  return 'unknown';
};

/**
 * Base configuration that applies to all platforms
 */
const baseConfig = {
  app: {
    name: 'Password Manager',
    version: '1.0.0',
    description: 'Secure cross-platform password manager'
  },
  
  api: {
    version: 'v1',
    timeout: 30000, // 30 seconds
    retryAttempts: 3,
    retryDelay: 1000 // 1 second
  },
  
  security: {
    // Encryption settings
    pbkdf2Iterations: 100000,
    keyLength: 32, // 256 bits
    saltLength: 16, // 128 bits
    
    // Session timeouts (in milliseconds)
    sessionTimeout: 900000, // 15 minutes
    autoLockTimeout: 300000, // 5 minutes
    idleTimeout: 600000, // 10 minutes
    
    // Rate limiting
    maxLoginAttempts: 5,
    lockoutDuration: 1800000, // 30 minutes
    
    // Password requirements
    minMasterPasswordLength: 12,
    maxMasterPasswordLength: 128
  },
  
  sync: {
    enabled: true,
    interval: 300000, // 5 minutes
    maxRetries: 3,
    batchSize: 50
  },
  
  ui: {
    theme: 'system', // 'light', 'dark', 'system'
    language: 'en',
    notifications: true,
    animations: true
  },
  
  storage: {
    encrypted: true,
    compression: true,
    backup: true
  },
  
  features: {
    autoFill: true,
    autoSave: true,
    darkWebMonitoring: true,
    passwordGenerator: true,
    secureNotes: true,
    biometrics: false // Platform dependent
  }
};

/**
 * Environment-specific configurations
 */
const environmentConfigs = {
  development: {
    api: {
      baseUrl: 'http://127.0.0.1:8000/api',
      wsUrl: 'ws://127.0.0.1:8000/ws'
    },
    debug: true,
    logging: {
      level: 'debug',
      console: true
    }
  },
  
  production: {
    api: {
      baseUrl: 'https://api.passwordmanager.com/api',
      wsUrl: 'wss://api.passwordmanager.com/ws'
    },
    debug: false,
    logging: {
      level: 'error',
      console: false
    }
  },
  
  testing: {
    api: {
      baseUrl: 'http://localhost:8001/api',
      wsUrl: 'ws://localhost:8001/ws'
    },
    debug: true,
    logging: {
      level: 'debug',
      console: true
    }
  }
};

/**
 * Platform-specific configurations
 */
const platformConfigs = {
  electron: {
    window: {
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600
    },
    security: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true
    },
    features: {
      biometrics: true, // Platform supports hardware authentication
      systemTray: true,
      autoStart: true,
      globalShortcuts: true
    },
    storage: {
      path: 'userData', // Electron app data directory
      secureStorage: 'hardware' // OS-level secure storage
    }
  },
  
  'browser-extension': {
    permissions: [
      'storage',
      'tabs',
      'activeTab',
      'notifications',
      'contextMenus'
    ],
    features: {
      contextMenu: true,
      tabIntegration: true,
      autoFill: true,
      pageAnalysis: true
    },
    storage: {
      sync: true, // Chrome storage.sync
      local: true, // Chrome storage.local
      secureStorage: 'extension' // Extension storage APIs
    },
    api: {
      proxy: true // Use background script as proxy
    }
  },
  
  browser: {
    features: {
      serviceWorker: true,
      notifications: true,
      clipboard: true
    },
    storage: {
      localStorage: true,
      indexedDB: true,
      secureStorage: 'indexeddb'
    },
    security: {
      csp: true,
      https: true
    }
  },
  
  mobile: {
    features: {
      biometrics: true, // Fingerprint/Face ID
      camera: true, // QR code scanning
      push: true, // Push notifications
      backgroundSync: true
    },
    storage: {
      secureStorage: 'keychain' // iOS Keychain / Android Keystore
    },
    ui: {
      haptics: true,
      statusBar: true
    }
  },
  
  node: {
    features: {
      filesystem: true,
      crypto: true
    },
    storage: {
      filesystem: true,
      secureStorage: 'file'
    }
  }
};

/**
 * Main configuration class
 */
class UnifiedConfig {
  constructor() {
    this.platform = detectPlatform();
    this.environment = this.detectEnvironment();
    this.config = this.buildConfig();
  }
  
  /**
   * Detect the current environment
   */
  detectEnvironment() {
    // Check for explicit environment variable
    if (typeof process !== 'undefined' && process.env) {
      if (process.env.NODE_ENV) {
        return process.env.NODE_ENV;
      }
      if (process.env.REACT_APP_ENV) {
        return process.env.REACT_APP_ENV;
      }
    }
    
    // Check for development indicators
    if (typeof window !== 'undefined') {
      if (window.location.hostname === 'localhost' || 
          window.location.hostname === '127.0.0.1' ||
          window.location.protocol === 'http:') {
        return 'development';
      }
    }
    
    // Default to production for safety
    return 'production';
  }
  
  /**
   * Build the complete configuration by merging base, environment, and platform configs
   */
  buildConfig() {
    const envConfig = environmentConfigs[this.environment] || {};
    const platformConfig = platformConfigs[this.platform] || {};
    
    // Deep merge configurations
    return this.deepMerge(
      baseConfig,
      envConfig,
      platformConfig,
      this.loadUserPreferences()
    );
  }
  
  /**
   * Load user preferences from storage
   */
  loadUserPreferences() {
    try {
      let prefs = {};
      
      if (this.platform === 'electron') {
        // Electron: Use electron-store
        try {
          const Store = require('electron-store');
          const store = new Store({ name: 'preferences' });
          prefs = store.store;
        } catch (e) {
          // Fallback to empty if electron-store not available
        }
      } else if (this.platform === 'browser-extension') {
        // Extension: Use chrome.storage.sync (handled async elsewhere)
        prefs = {}; // Will be loaded separately
      } else if (this.platform === 'browser') {
        // Browser: Use localStorage
        const stored = localStorage.getItem('passwordmanager_preferences');
        if (stored) {
          prefs = JSON.parse(stored);
        }
      }
      
      return prefs;
    } catch (error) {
      console.warn('Failed to load user preferences:', error);
      return {};
    }
  }
  
  /**
   * Save user preferences to storage
   */
  saveUserPreferences(preferences) {
    try {
      if (this.platform === 'electron') {
        try {
          const Store = require('electron-store');
          const store = new Store({ name: 'preferences' });
          Object.keys(preferences).forEach(key => {
            store.set(key, preferences[key]);
          });
          return true;
        } catch (e) {
          return false;
        }
      } else if (this.platform === 'browser-extension') {
        // Extension: Use chrome.storage.sync
        if (typeof chrome !== 'undefined' && chrome.storage) {
          chrome.storage.sync.set(preferences);
          return true;
        }
      } else if (this.platform === 'browser') {
        // Browser: Use localStorage
        localStorage.setItem('passwordmanager_preferences', JSON.stringify(preferences));
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to save user preferences:', error);
      return false;
    }
  }
  
  /**
   * Deep merge multiple objects
   */
  deepMerge(...objects) {
    const result = {};
    
    for (const obj of objects) {
      if (!obj || typeof obj !== 'object') continue;
      
      for (const key in obj) {
        if (!obj.hasOwnProperty(key)) continue;
        
        if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
          result[key] = this.deepMerge(result[key] || {}, obj[key]);
        } else {
          result[key] = obj[key];
        }
      }
    }
    
    return result;
  }
  
  /**
   * Get configuration value by path (e.g., 'api.baseUrl')
   */
  get(path, defaultValue = undefined) {
    const keys = path.split('.');
    let value = this.config;
    
    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return defaultValue;
      }
    }
    
    return value;
  }
  
  /**
   * Set configuration value by path
   */
  set(path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    let obj = this.config;
    
    for (const key of keys) {
      if (!(key in obj) || typeof obj[key] !== 'object') {
        obj[key] = {};
      }
      obj = obj[key];
    }
    
    obj[lastKey] = value;
    
    // Save to user preferences if it's a user-configurable setting
    if (this.isUserConfigurable(path)) {
      const prefs = this.loadUserPreferences();
      this.setByPath(prefs, path, value);
      this.saveUserPreferences(prefs);
    }
  }
  
  /**
   * Check if a configuration path is user-configurable
   */
  isUserConfigurable(path) {
    const userConfigPaths = [
      'ui.theme',
      'ui.language',
      'ui.notifications',
      'ui.animations',
      'security.autoLockTimeout',
      'sync.enabled',
      'sync.interval',
      'features.autoFill',
      'features.autoSave',
      'features.darkWebMonitoring'
    ];
    
    return userConfigPaths.includes(path);
  }
  
  /**
   * Helper to set value by path in object
   */
  setByPath(obj, path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    let current = obj;
    
    for (const key of keys) {
      if (!(key in current) || typeof current[key] !== 'object') {
        current[key] = {};
      }
      current = current[key];
    }
    
    current[lastKey] = value;
  }
  
  /**
   * Get platform information
   */
  getPlatform() {
    return this.platform;
  }
  
  /**
   * Get environment information
   */
  getEnvironment() {
    return this.environment;
  }
  
  /**
   * Check if running in development mode
   */
  isDevelopment() {
    return this.environment === 'development';
  }
  
  /**
   * Check if running in production mode
   */
  isProduction() {
    return this.environment === 'production';
  }
  
  /**
   * Get the complete configuration object
   */
  getAll() {
    return { ...this.config };
  }
}

// Create and export singleton instance
const config = new UnifiedConfig();

// Export both the instance and the class
export default config;
export { UnifiedConfig, detectPlatform };

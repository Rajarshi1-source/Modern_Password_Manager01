/**
 * Unified configuration management for cross-platform password manager
 * Provides environment-based configuration with platform-specific overrides
 */

// Environment detection
const getEnvironment = () => {
  if (typeof process !== 'undefined' && process.env) {
    return process.env.NODE_ENV || 'development';
  }
  if (typeof window !== 'undefined' && window.location) {
    return window.location.hostname === 'localhost' ? 'development' : 'production';
  }
  return 'development';
};

// Platform detection
const getPlatform = () => {
  if (typeof window !== 'undefined') {
    if (typeof chrome !== 'undefined' && chrome.runtime) {
      return 'browser-extension';
    }
    return 'browser';
  } else if (typeof process !== 'undefined' && process.versions && process.versions.electron) {
    return 'electron';
  } else if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    return 'node';
  }
  return 'unknown';
};

// Base configuration
const baseConfig = {
  // API Configuration
  api: {
    timeout: 30000,
    retryAttempts: 3,
    retryDelay: 1000,
  },

  // Security Configuration
  security: {
    sessionTimeout: 15 * 60 * 1000, // 15 minutes in milliseconds
    maxFailedAttempts: 5,
    lockoutDuration: 30 * 60 * 1000, // 30 minutes in milliseconds
    passwordMinLength: 8,
    passwordMaxLength: 128,
    keyDerivationIterations: 100000,
  },

  // Crypto Configuration
  crypto: {
    algorithm: 'AES-GCM',
    keyLength: 256,
    ivLength: 12,
    saltLength: 32,
    tagLength: 16,
  },

  // Storage Configuration
  storage: {
    keyPrefix: 'passwordmanager_',
    encryptStorage: true,
    compressionEnabled: true,
  },

  // Sync Configuration
  sync: {
    interval: 5 * 60 * 1000, // 5 minutes
    maxPendingChanges: 100,
    conflictResolution: 'server-wins', // 'server-wins', 'client-wins', 'merge'
  },

  // Logging Configuration
  logging: {
    level: 'info', // 'debug', 'info', 'warn', 'error'
    maxLogSize: 10 * 1024 * 1024, // 10MB
    enableRemoteLogging: false,
  },

  // Feature Flags
  features: {
    biometricAuth: true,
    darkWebMonitoring: true,
    autoFill: true,
    crossDeviceSync: true,
    emergencyAccess: true,
    twoFactorAuth: true,
  },
};

// Environment-specific configurations
const environmentConfigs = {
  development: {
    api: {
      baseUrl: 'http://localhost:8000/api',
      timeout: 60000, // Longer timeout for development
    },
    logging: {
      level: 'debug',
      enableRemoteLogging: false,
    },
    security: {
      sessionTimeout: 60 * 60 * 1000, // 1 hour for development
    },
  },

  staging: {
    api: {
      baseUrl: 'https://staging-api.passwordmanager.com/api',
    },
    logging: {
      level: 'info',
      enableRemoteLogging: true,
    },
  },

  production: {
    api: {
      baseUrl: 'https://api.passwordmanager.com/api',
    },
    logging: {
      level: 'warn',
      enableRemoteLogging: true,
    },
    security: {
      sessionTimeout: 10 * 60 * 1000, // 10 minutes for production
    },
  },
};

// Platform-specific configurations
const platformConfigs = {
  'browser-extension': {
    api: {
      timeout: 10000, // Shorter timeout for extension
    },
    storage: {
      useChrome: true,
      syncStorage: true,
    },
    features: {
      autoFill: true,
      pageDetection: true,
    },
  },

  browser: {
    storage: {
      useIndexedDB: true,
      useLocalStorage: false,
    },
    features: {
      offlineMode: true,
      serviceWorker: true,
    },
  },

  electron: {
    api: {
      timeout: 20000,
    },
    storage: {
      useFileSystem: true,
      encryptFiles: true,
    },
    features: {
      systemIntegration: true,
      nativeNotifications: true,
      menuIntegration: true,
    },
  },

  node: {
    api: {
      timeout: 30000,
    },
    storage: {
      useFileSystem: true,
      encryptFiles: true,
    },
    features: {
      cliInterface: true,
      batchOperations: true,
    },
  },
};

// Deep merge function
function deepMerge(target, source) {
  const result = { ...target };
  
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(result[key] || {}, source[key]);
    } else {
      result[key] = source[key];
    }
  }
  
  return result;
}

// Configuration class
export class Config {
  constructor() {
    this.environment = getEnvironment();
    this.platform = getPlatform();
    this._config = this._buildConfig();
  }

  _buildConfig() {
    let config = { ...baseConfig };

    // Apply environment-specific config
    const envConfig = environmentConfigs[this.environment];
    if (envConfig) {
      config = deepMerge(config, envConfig);
    }

    // Apply platform-specific config
    const platformConfig = platformConfigs[this.platform];
    if (platformConfig) {
      config = deepMerge(config, platformConfig);
    }

    // Apply environment variables (Node.js only)
    if (typeof process !== 'undefined' && process.env) {
      config = this._applyEnvironmentVariables(config);
    }

    return config;
  }

  _applyEnvironmentVariables(config) {
    const envOverrides = {};

    // API configuration from environment
    if (process.env.API_BASE_URL) {
      envOverrides.api = { baseUrl: process.env.API_BASE_URL };
    }
    if (process.env.API_TIMEOUT) {
      envOverrides.api = { ...envOverrides.api, timeout: parseInt(process.env.API_TIMEOUT) };
    }

    // Security configuration from environment
    if (process.env.SESSION_TIMEOUT) {
      envOverrides.security = { sessionTimeout: parseInt(process.env.SESSION_TIMEOUT) };
    }
    if (process.env.MAX_FAILED_ATTEMPTS) {
      envOverrides.security = { 
        ...envOverrides.security, 
        maxFailedAttempts: parseInt(process.env.MAX_FAILED_ATTEMPTS) 
      };
    }

    // Logging configuration from environment
    if (process.env.LOG_LEVEL) {
      envOverrides.logging = { level: process.env.LOG_LEVEL.toLowerCase() };
    }

    return deepMerge(config, envOverrides);
  }

  get(key) {
    const keys = key.split('.');
    let value = this._config;
    
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        return undefined;
      }
    }
    
    return value;
  }

  set(key, value) {
    const keys = key.split('.');
    let current = this._config;
    
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i];
      if (!(k in current) || typeof current[k] !== 'object') {
        current[k] = {};
      }
      current = current[k];
    }
    
    current[keys[keys.length - 1]] = value;
  }

  getAll() {
    return { ...this._config };
  }

  getEnvironment() {
    return this.environment;
  }

  getPlatform() {
    return this.platform;
  }

  isDevelopment() {
    return this.environment === 'development';
  }

  isProduction() {
    return this.environment === 'production';
  }

  isFeatureEnabled(feature) {
    return this.get(`features.${feature}`) === true;
  }

  // Convenience methods for common configurations
  getApiConfig() {
    return this.get('api');
  }

  getSecurityConfig() {
    return this.get('security');
  }

  getCryptoConfig() {
    return this.get('crypto');
  }

  getStorageConfig() {
    return this.get('storage');
  }

  // Validate configuration
  validate() {
    const errors = [];

    // Validate API configuration
    const apiConfig = this.getApiConfig();
    if (!apiConfig.baseUrl) {
      errors.push('API base URL is required');
    }
    if (apiConfig.timeout <= 0) {
      errors.push('API timeout must be positive');
    }

    // Validate security configuration
    const securityConfig = this.getSecurityConfig();
    if (securityConfig.sessionTimeout <= 0) {
      errors.push('Session timeout must be positive');
    }
    if (securityConfig.passwordMinLength < 1) {
      errors.push('Password minimum length must be at least 1');
    }

    // Validate crypto configuration
    const cryptoConfig = this.getCryptoConfig();
    if (cryptoConfig.keyLength < 128) {
      errors.push('Crypto key length must be at least 128 bits');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Export singleton instance
export const config = new Config();

// Export default
export default config;

// Export utility functions
export { getEnvironment, getPlatform, deepMerge };

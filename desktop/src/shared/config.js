/**
 * Shared configuration for the Password Manager desktop application.
 * This module provides environment-based configuration values and application settings.
 */

const { app } = require('electron');
const path = require('path');

/**
 * Get environment-based configuration
 */
const getDesktopConfig = () => {
  const isDevelopment = process.env.NODE_ENV === 'development' || process.env.DEBUG === 'true';
  
  return {
    // Application info
    appName: 'Password Manager Desktop',
    version: app?.getVersion() || '1.0.0',
    
    // API configuration
    apiBaseUrl: process.env.REACT_APP_API_URL || (isDevelopment 
      ? 'http://127.0.0.1:8000/api'
      : 'https://your-password-manager.com/api'),
    
    // Security settings
    autoLockTimeout: 300000, // 5 minutes in milliseconds
    maxRetries: 3,
    sessionTimeout: 900000, // 15 minutes in milliseconds
    
    // Application behavior
    syncInterval: 300000, // 5 minutes
    enableHardwareAcceleration: true,
    enableAutoUpdater: !isDevelopment,
    
    // Window settings
    defaultWindowSettings: {
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600,
      show: false, // Don't show until ready
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        webSecurity: true,
        preload: path.join(__dirname, '../main/preload.js')
      }
    },
    
    // Storage paths
    userDataPath: app?.getPath('userData') || './userData',
    secureKeysPath: 'secure_keys',
    
    // Development settings
    isDevelopment,
    enableDevTools: isDevelopment,
    enableReactDevServer: isDevelopment,
    reactDevServerUrl: 'http://localhost:3000',
    
    // Logging configuration
    logging: {
      level: isDevelopment ? 'debug' : 'info',
      maxFiles: 5,
      maxSize: '10m'
    },
    
    // Platform-specific settings
    platform: {
      isWindows: process.platform === 'win32',
      isMacOS: process.platform === 'darwin',
      isLinux: process.platform === 'linux'
    }
  };
};

/**
 * Load user preferences from storage
 */
const loadUserPreferences = () => {
  try {
    const Store = require('electron-store');
    const store = new Store({
      name: 'preferences',
      defaults: {
        autoLockTimeout: 300000, // 5 minutes
        syncEnabled: true,
        notificationsEnabled: true,
        autoStartOnBoot: false,
        minimizeToTray: true,
        theme: 'system' // 'light', 'dark', 'system'
      }
    });
    
    return store.store;
  } catch (error) {
    console.warn('Failed to load user preferences:', error);
    return {};
  }
};

/**
 * Save user preferences to storage
 */
const saveUserPreferences = (preferences) => {
  try {
    const Store = require('electron-store');
    const store = new Store({ name: 'preferences' });
    
    Object.keys(preferences).forEach(key => {
      store.set(key, preferences[key]);
    });
    
    return true;
  } catch (error) {
    console.error('Failed to save user preferences:', error);
    return false;
  }
};

/**
 * Get complete configuration including user preferences
 */
const getFullConfig = () => {
  const config = getDesktopConfig();
  const userPrefs = loadUserPreferences();
  
  return {
    ...config,
    userPreferences: userPrefs,
    // Override default settings with user preferences
    autoLockTimeout: userPrefs.autoLockTimeout || config.autoLockTimeout
  };
};

module.exports = {
  getDesktopConfig,
  loadUserPreferences,
  saveUserPreferences,
  getFullConfig,
  
  // Export constants for direct access
  PLATFORMS: {
    WINDOWS: 'win32',
    MACOS: 'darwin',
    LINUX: 'linux'
  },
  
  THEMES: {
    LIGHT: 'light',
    DARK: 'dark',
    SYSTEM: 'system'
  },
  
  WINDOW_STATES: {
    NORMAL: 'normal',
    MINIMIZED: 'minimized',
    MAXIMIZED: 'maximized',
    FULLSCREEN: 'fullscreen'
  }
};

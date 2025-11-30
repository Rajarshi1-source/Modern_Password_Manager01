/**
 * User Preferences Service
 * =========================
 * 
 * Comprehensive user preference management with local storage,
 * backend synchronization, and cross-device support.
 * 
 * Features:
 * - Theme preferences (light, dark, auto)
 * - Notification preferences
 * - Security preferences
 * - UI/UX preferences
 * - Privacy preferences
 * - Accessibility preferences
 * - Export/import preferences
 * - Real-time sync across devices
 * 
 * Usage:
 *   import { preferencesService } from './services/preferencesService';
 *   
 *   // Get preference
 *   const theme = preferencesService.get('theme.mode');
 *   
 *   // Set preference
 *   preferencesService.set('theme.mode', 'dark');
 *   
 *   // Listen to changes
 *   preferencesService.onChange('theme.mode', (value) => {
 *     console.log('Theme changed to:', value);
 *   });
 */

import axios from 'axios';

// Default preferences
const DEFAULT_PREFERENCES = {
  // Theme preferences
  theme: {
    mode: 'auto', // 'light', 'dark', 'auto'
    primaryColor: '#4A6CF7',
    fontSize: 'medium', // 'small', 'medium', 'large', 'xlarge'
    fontFamily: 'system', // 'system', 'serif', 'sans-serif', 'monospace'
    compactMode: false,
    animations: true,
    highContrast: false
  },
  
  // Notification preferences
  notifications: {
    enabled: true,
    browser: true,
    email: true,
    push: false,
    
    // Notification types
    breachAlerts: true,
    securityAlerts: true,
    accountActivity: true,
    marketingEmails: false,
    productUpdates: true,
    
    // Notification schedule
    quietHoursEnabled: false,
    quietHoursStart: '22:00',
    quietHoursEnd: '08:00',
    
    // Sound
    sound: true,
    soundVolume: 0.5
  },
  
  // Security preferences
  security: {
    autoLockEnabled: true,
    autoLockTimeout: 5, // minutes
    biometricAuth: false,
    twoFactorAuth: false,
    
    // Session
    requireReauth: true,
    reauthTimeout: 30, // minutes
    
    // Clipboard
    clearClipboard: true,
    clipboardTimeout: 30, // seconds
    
    // Password generation
    defaultPasswordLength: 16,
    includeSymbols: true,
    includeNumbers: true,
    includeUppercase: true,
    includeLowercase: true,
    
    // Breach monitoring
    breachMonitoring: true,
    darkWebMonitoring: true
  },
  
  // Privacy preferences
  privacy: {
    analytics: true,
    errorReporting: true,
    performanceMonitoring: true,
    crashReports: true,
    usageData: true,
    
    // Data retention
    keepLoginHistory: true,
    loginHistoryDays: 90,
    keepAuditLogs: true,
    auditLogDays: 365
  },
  
  // UI/UX preferences
  ui: {
    language: 'en',
    dateFormat: 'MM/DD/YYYY',
    timeFormat: '12h', // '12h' or '24h'
    timezone: 'auto',
    
    // Vault display
    vaultView: 'grid', // 'grid', 'list', 'compact'
    sortBy: 'name', // 'name', 'dateCreated', 'dateModified', 'type'
    sortOrder: 'asc', // 'asc', 'desc'
    groupBy: 'none', // 'none', 'type', 'folder', 'tags'
    
    // Dashboard
    showRecentItems: true,
    recentItemsCount: 10,
    showFavorites: true,
    showWeakPasswords: true,
    showBreachAlerts: true,
    
    // Sidebar
    sidebarCollapsed: false,
    sidebarPosition: 'left' // 'left', 'right'
  },
  
  // Accessibility preferences
  accessibility: {
    screenReader: false,
    reducedMotion: false,
    largeText: false,
    keyboardNavigation: true,
    focusIndicators: true,
    announceChanges: true
  },
  
  // Advanced preferences
  advanced: {
    developerMode: false,
    debugLogs: false,
    experimentalFeatures: false,
    betaFeatures: false,
    
    // Performance
    lazyLoading: true,
    cacheEnabled: true,
    offlineMode: true,
    
    // Sync
    autoSync: true,
    syncInterval: 60, // seconds
    conflictResolution: 'latest' // 'latest', 'server', 'manual'
  },
  
  // Metadata
  _metadata: {
    version: '1.0.0',
    lastModified: null,
    lastSync: null,
    deviceId: null
  }
};

class PreferencesService {
  constructor() {
    // Configuration
    this.config = {
      enabled: true,
      endpoint: '/api/user/preferences/',
      storageKey: 'user_preferences',
      syncInterval: 60000, // 1 minute
      debug: process.env.NODE_ENV === 'development'
    };
    
    // Preferences cache
    this.preferences = this.loadLocal();
    
    // Change listeners
    this.listeners = new Map();
    
    // Sync state
    this.syncTimer = null;
    this.syncInProgress = false;
    this.pendingChanges = new Set();
    
    // Initialize
    this.initialize();
  }
  
  /* ===== INITIALIZATION ===== */
  
  /**
   * Initialize the service
   */
  async initialize() {
    // Load from backend if authenticated
    if (this.isAuthenticated()) {
      await this.loadFromBackend();
    }
    
    // Start auto-sync
    if (this.get('advanced.autoSync')) {
      this.startAutoSync();
    }
    
    // Apply theme immediately
    this.applyTheme();
    
    // Listen to system theme changes
    this.watchSystemTheme();
    
    if (this.config.debug) {
      console.log('[Preferences] Initialized with:', this.preferences);
    }
  }
  
  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!localStorage.getItem('token');
  }
  
  /* ===== LOCAL STORAGE ===== */
  
  /**
   * Load preferences from localStorage
   */
  loadLocal() {
    try {
      const stored = localStorage.getItem(this.config.storageKey);
      
      if (stored) {
        const parsed = JSON.parse(stored);
        return this.mergeWithDefaults(parsed);
      }
    } catch (error) {
      console.error('[Preferences] Failed to load from localStorage:', error);
    }
    
    return { ...DEFAULT_PREFERENCES };
  }
  
  /**
   * Save preferences to localStorage
   */
  saveLocal() {
    try {
      // Update metadata
      this.preferences._metadata.lastModified = new Date().toISOString();
      
      localStorage.setItem(
        this.config.storageKey,
        JSON.stringify(this.preferences)
      );
      
      if (this.config.debug) {
        console.log('[Preferences] Saved to localStorage');
      }
    } catch (error) {
      console.error('[Preferences] Failed to save to localStorage:', error);
    }
  }
  
  /**
   * Merge preferences with defaults
   */
  mergeWithDefaults(preferences) {
    return this.deepMerge(DEFAULT_PREFERENCES, preferences);
  }
  
  /**
   * Deep merge two objects
   */
  deepMerge(target, source) {
    const result = { ...target };
    
    for (const key in source) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = this.deepMerge(target[key] || {}, source[key]);
      } else {
        result[key] = source[key];
      }
    }
    
    return result;
  }
  
  /* ===== BACKEND SYNC ===== */
  
  /**
   * Load preferences from backend
   */
  async loadFromBackend() {
    if (!this.isAuthenticated()) {
      return;
    }
    
    try {
      const response = await axios.get(this.config.endpoint);
      const backendPrefs = response.data.preferences || response.data;
      
      // Merge with defaults
      this.preferences = this.mergeWithDefaults(backendPrefs);
      
      // Update metadata
      this.preferences._metadata.lastSync = new Date().toISOString();
      
      // Save locally
      this.saveLocal();
      
      // Apply theme
      this.applyTheme();
      
      if (this.config.debug) {
        console.log('[Preferences] Loaded from backend');
      }
      
      // Notify listeners
      this.notifyAll();
      
      return this.preferences;
    } catch (error) {
      console.error('[Preferences] Failed to load from backend:', error);
      return this.preferences;
    }
  }
  
  /**
   * Save preferences to backend
   */
  async saveToBackend() {
    if (!this.isAuthenticated() || this.syncInProgress) {
      return;
    }
    
    if (this.pendingChanges.size === 0) {
      return;
    }
    
    this.syncInProgress = true;
    
    try {
      await axios.put(this.config.endpoint, {
        preferences: this.preferences
      });
      
      // Update metadata
      this.preferences._metadata.lastSync = new Date().toISOString();
      this.saveLocal();
      
      // Clear pending changes
      this.pendingChanges.clear();
      
      if (this.config.debug) {
        console.log('[Preferences] Saved to backend');
      }
    } catch (error) {
      console.error('[Preferences] Failed to save to backend:', error);
    } finally {
      this.syncInProgress = false;
    }
  }
  
  /**
   * Start auto-sync
   */
  startAutoSync() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
    }
    
    const interval = this.get('advanced.syncInterval') * 1000;
    
    this.syncTimer = setInterval(() => {
      this.saveToBackend();
    }, interval);
  }
  
  /**
   * Stop auto-sync
   */
  stopAutoSync() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
  }
  
  /**
   * Force immediate sync
   */
  async sync() {
    await this.saveToBackend();
  }
  
  /* ===== GET/SET PREFERENCES ===== */
  
  /**
   * Get a preference value
   * @param {string} path - Dot-separated path (e.g., 'theme.mode')
   * @param {*} defaultValue - Default value if not found
   */
  get(path, defaultValue = null) {
    const keys = path.split('.');
    let value = this.preferences;
    
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
   * Set a preference value
   * @param {string} path - Dot-separated path
   * @param {*} value - Value to set
   */
  set(path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    let target = this.preferences;
    
    // Navigate to parent object
    for (const key of keys) {
      if (!(key in target) || typeof target[key] !== 'object') {
        target[key] = {};
      }
      target = target[key];
    }
    
    // Set value
    const oldValue = target[lastKey];
    target[lastKey] = value;
    
    // Save locally
    this.saveLocal();
    
    // Mark as pending for backend sync
    this.pendingChanges.add(path);
    
    // Notify listeners
    this.notify(path, value, oldValue);
    
    // Apply special handlers
    this.handleSpecialPreference(path, value);
    
    if (this.config.debug) {
      console.log(`[Preferences] Set ${path} =`, value);
    }
  }
  
  /**
   * Set multiple preferences at once
   */
  setMultiple(changes) {
    Object.entries(changes).forEach(([path, value]) => {
      this.set(path, value);
    });
  }
  
  /**
   * Reset a preference to default
   */
  reset(path) {
    const defaultValue = this.getDefaultValue(path);
    this.set(path, defaultValue);
  }
  
  /**
   * Reset all preferences to defaults
   */
  resetAll() {
    this.preferences = { ...DEFAULT_PREFERENCES };
    this.saveLocal();
    this.notifyAll();
    this.applyTheme();
    
    if (this.config.debug) {
      console.log('[Preferences] Reset all to defaults');
    }
  }
  
  /**
   * Get default value for a preference
   */
  getDefaultValue(path) {
    const keys = path.split('.');
    let value = DEFAULT_PREFERENCES;
    
    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return null;
      }
    }
    
    return value;
  }
  
  /* ===== CHANGE LISTENERS ===== */
  
  /**
   * Listen to preference changes
   * @param {string} path - Dot-separated path (or '*' for all changes)
   * @param {function} callback - Callback function (value, oldValue) => {}
   * @returns {function} Unsubscribe function
   */
  onChange(path, callback) {
    if (!this.listeners.has(path)) {
      this.listeners.set(path, new Set());
    }
    
    this.listeners.get(path).add(callback);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(path);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }
  
  /**
   * Notify listeners of a change
   */
  notify(path, value, oldValue) {
    // Notify specific path listeners
    const callbacks = this.listeners.get(path);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(value, oldValue);
        } catch (error) {
          console.error('[Preferences] Listener error:', error);
        }
      });
    }
    
    // Notify wildcard listeners
    const wildcardCallbacks = this.listeners.get('*');
    if (wildcardCallbacks) {
      wildcardCallbacks.forEach(callback => {
        try {
          callback(path, value, oldValue);
        } catch (error) {
          console.error('[Preferences] Wildcard listener error:', error);
        }
      });
    }
  }
  
  /**
   * Notify all listeners
   */
  notifyAll() {
    this.listeners.forEach((callbacks, path) => {
      if (path !== '*') {
        const value = this.get(path);
        callbacks.forEach(callback => {
          try {
            callback(value, null);
          } catch (error) {
            console.error('[Preferences] Listener error:', error);
          }
        });
      }
    });
  }
  
  /* ===== SPECIAL HANDLERS ===== */
  
  /**
   * Handle special preferences that need immediate action
   */
  handleSpecialPreference(path, value) {
    // Theme changes
    if (path.startsWith('theme.')) {
      this.applyTheme();
    }
    
    // Auto-sync changes
    if (path === 'advanced.autoSync') {
      if (value) {
        this.startAutoSync();
      } else {
        this.stopAutoSync();
      }
    }
    
    // Analytics changes
    if (path === 'privacy.analytics') {
      // Import and toggle analytics service
      import('./analyticsService').then(({ analyticsService }) => {
        analyticsService.setEnabled(value);
      });
    }
  }
  
  /**
   * Apply theme to document
   */
  applyTheme() {
    const themeMode = this.get('theme.mode');
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    let actualTheme = themeMode;
    if (themeMode === 'auto') {
      actualTheme = systemDark ? 'dark' : 'light';
    }
    
    // Apply to document
    document.documentElement.setAttribute('data-theme', actualTheme);
    document.body.classList.toggle('dark-mode', actualTheme === 'dark');
    
    // Apply font size
    const fontSize = this.get('theme.fontSize');
    document.documentElement.style.fontSize = {
      small: '14px',
      medium: '16px',
      large: '18px',
      xlarge: '20px'
    }[fontSize] || '16px';
    
    // Apply animations
    const animations = this.get('theme.animations');
    document.body.classList.toggle('no-animations', !animations);
    
    // Apply reduced motion
    const reducedMotion = this.get('accessibility.reducedMotion');
    document.body.classList.toggle('reduced-motion', reducedMotion);
  }
  
  /**
   * Watch system theme changes
   */
  watchSystemTheme() {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    mediaQuery.addEventListener('change', () => {
      if (this.get('theme.mode') === 'auto') {
        this.applyTheme();
      }
    });
  }
  
  /* ===== EXPORT/IMPORT ===== */
  
  /**
   * Export preferences as JSON
   */
  export() {
    return {
      version: this.preferences._metadata.version,
      exportedAt: new Date().toISOString(),
      preferences: this.preferences
    };
  }
  
  /**
   * Export preferences as downloadable file
   */
  exportAsFile() {
    const data = this.export();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `preferences_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  
  /**
   * Import preferences from JSON
   */
  import(data) {
    try {
      const imported = typeof data === 'string' ? JSON.parse(data) : data;
      const prefs = imported.preferences || imported;
      
      this.preferences = this.mergeWithDefaults(prefs);
      this.saveLocal();
      this.notifyAll();
      this.applyTheme();
      
      if (this.config.debug) {
        console.log('[Preferences] Imported successfully');
      }
      
      return true;
    } catch (error) {
      console.error('[Preferences] Import failed:', error);
      return false;
    }
  }
  
  /**
   * Import preferences from file
   */
  async importFromFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        try {
          const success = this.import(e.target.result);
          resolve(success);
        } catch (error) {
          reject(error);
        }
      };
      
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  }
  
  /* ===== UTILITY METHODS ===== */
  
  /**
   * Get all preferences
   */
  getAll() {
    return { ...this.preferences };
  }
  
  /**
   * Get default preferences
   */
  getDefaults() {
    return { ...DEFAULT_PREFERENCES };
  }
  
  /**
   * Check if preference has been modified from default
   */
  isModified(path) {
    const currentValue = this.get(path);
    const defaultValue = this.getDefaultValue(path);
    return JSON.stringify(currentValue) !== JSON.stringify(defaultValue);
  }
  
  /**
   * Get modified preferences
   */
  getModified() {
    const modified = {};
    
    const checkModified = (obj, defaults, path = '') => {
      Object.keys(obj).forEach(key => {
        const currentPath = path ? `${path}.${key}` : key;
        const value = obj[key];
        const defaultValue = defaults[key];
        
        if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
          checkModified(value, defaultValue || {}, currentPath);
        } else if (JSON.stringify(value) !== JSON.stringify(defaultValue)) {
          modified[currentPath] = value;
        }
      });
    };
    
    checkModified(this.preferences, DEFAULT_PREFERENCES);
    
    return modified;
  }
  
  /**
   * Get sync status
   */
  getSyncStatus() {
    return {
      syncing: this.syncInProgress,
      pendingChanges: this.pendingChanges.size,
      lastSync: this.preferences._metadata.lastSync,
      lastModified: this.preferences._metadata.lastModified,
      autoSyncEnabled: !!this.syncTimer
    };
  }
}

// Create singleton instance
const preferencesService = new PreferencesService();

// Export both the class and the singleton
export { PreferencesService, preferencesService, DEFAULT_PREFERENCES };
export default preferencesService;


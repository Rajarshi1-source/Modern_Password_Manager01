/**
 * Application constants for the Password Manager desktop application.
 * This module contains all the constant values used throughout the application.
 */

// Application Information
const APP_INFO = {
  NAME: 'Password Manager Desktop',
  DESCRIPTION: 'Secure desktop password manager',
  VERSION: '1.0.0',
  AUTHOR: 'Password Manager Team',
  HOMEPAGE: 'https://github.com/your-username/password-manager'
};

// Window Configuration
const WINDOW_CONFIG = {
  DEFAULT_WIDTH: 1200,
  DEFAULT_HEIGHT: 800,
  MIN_WIDTH: 800,
  MIN_HEIGHT: 600,
  MAX_WIDTH: 2000,
  MAX_HEIGHT: 1400
};

// Security Constants
const SECURITY = {
  // Timeouts (in milliseconds)
  AUTO_LOCK_TIMEOUT: 300000,      // 5 minutes
  SESSION_TIMEOUT: 900000,        // 15 minutes
  IDLE_TIMEOUT: 600000,          // 10 minutes
  
  // Encryption
  PBKDF2_ITERATIONS: 100000,
  KEY_LENGTH: 32,                 // 256 bits
  IV_LENGTH: 12,                  // 96 bits for AES-GCM
  SALT_LENGTH: 16,               // 128 bits
  
  // Rate Limiting
  MAX_LOGIN_ATTEMPTS: 5,
  LOCKOUT_DURATION: 1800000,     // 30 minutes
  MAX_API_RETRIES: 3,
  
  // Password Requirements
  MIN_MASTER_PASSWORD_LENGTH: 12,
  MAX_MASTER_PASSWORD_LENGTH: 128,
  MIN_PASSWORD_STRENGTH: 3,       // Out of 5
};

// API Configuration
const API = {
  BASE_URL_DEV: 'http://127.0.0.1:8000/api',
  BASE_URL_PROD: 'https://your-password-manager.com/api',
  
  // Request timeouts (in milliseconds)
  TIMEOUT: 30000,                 // 30 seconds
  RETRY_DELAY: 1000,             // 1 second
  
  // Headers
  CONTENT_TYPE: 'application/json',
  USER_AGENT: 'Password-Manager-Desktop/1.0.0',
  
  // Status codes
  STATUS_CODES: {
    OK: 200,
    CREATED: 201,
    NO_CONTENT: 204,
    BAD_REQUEST: 400,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    INTERNAL_SERVER_ERROR: 500,
    SERVICE_UNAVAILABLE: 503
  }
};

// Storage Keys
const STORAGE_KEYS = {
  USER_PREFERENCES: 'userPreferences',
  WINDOW_STATE: 'windowState',
  LAST_SYNC: 'lastSync',
  AUTO_LOCK_ENABLED: 'autoLockEnabled',
  NOTIFICATIONS_ENABLED: 'notificationsEnabled',
  THEME: 'theme',
  LANGUAGE: 'language',
  SYNC_ENABLED: 'syncEnabled'
};

// File Paths
const FILE_PATHS = {
  SECURE_KEYS_DIR: 'secure_keys',
  LOGS_DIR: 'logs',
  CACHE_DIR: 'cache',
  BACKUPS_DIR: 'backups',
  TEMP_DIR: 'temp',
  
  // File extensions
  BACKUP_EXTENSION: '.backup',
  LOG_EXTENSION: '.log',
  KEY_EXTENSION: '.key'
};

// IPC Channel Names
const IPC_CHANNELS = {
  // Window management
  WINDOW_MINIMIZE: 'window:minimize',
  WINDOW_MAXIMIZE: 'window:maximize',
  WINDOW_CLOSE: 'window:close',
  WINDOW_TOGGLE_FULLSCREEN: 'window:toggle-fullscreen',
  
  // Application
  APP_VERSION: 'app:version',
  APP_QUIT: 'app:quit',
  APP_RESTART: 'app:restart',
  
  // Security
  SECURE_STORAGE_SET: 'secure-storage:set',
  SECURE_STORAGE_GET: 'secure-storage:get',
  SECURE_STORAGE_DELETE: 'secure-storage:delete',
  SECURE_STORAGE_AVAILABLE: 'secure-storage:available',
  
  // Vault
  VAULT_LOCK: 'vault:lock',
  VAULT_UNLOCK: 'vault:unlock',
  VAULT_SYNC: 'vault:sync',
  
  // Settings
  SETTINGS_GET: 'settings:get',
  SETTINGS_SET: 'settings:set',
  SETTINGS_RESET: 'settings:reset',
  
  // Notifications
  NOTIFICATION_SHOW: 'notification:show',
  NOTIFICATION_CLEAR: 'notification:clear'
};

// Event Names
const EVENTS = {
  // Application events
  APP_READY: 'app:ready',
  APP_BEFORE_QUIT: 'app:before-quit',
  APP_WINDOW_ALL_CLOSED: 'app:window-all-closed',
  
  // Window events
  WINDOW_READY_TO_SHOW: 'window:ready-to-show',
  WINDOW_CLOSED: 'window:closed',
  WINDOW_FOCUS: 'window:focus',
  WINDOW_BLUR: 'window:blur',
  
  // Security events
  SESSION_EXPIRED: 'security:session-expired',
  AUTO_LOCK_TRIGGERED: 'security:auto-lock-triggered',
  LOGIN_ATTEMPT: 'security:login-attempt',
  
  // Sync events
  SYNC_STARTED: 'sync:started',
  SYNC_COMPLETED: 'sync:completed',
  SYNC_FAILED: 'sync:failed'
};

// Notification Types
const NOTIFICATION_TYPES = {
  INFO: 'info',
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'error',
  SECURITY: 'security'
};

// Themes
const THEMES = {
  LIGHT: 'light',
  DARK: 'dark',
  SYSTEM: 'system'
};

// Languages
const LANGUAGES = {
  ENGLISH: 'en',
  SPANISH: 'es',
  FRENCH: 'fr',
  GERMAN: 'de',
  ITALIAN: 'it',
  PORTUGUESE: 'pt',
  CHINESE: 'zh',
  JAPANESE: 'ja'
};

// Platform-specific constants
const PLATFORMS = {
  WINDOWS: 'win32',
  MACOS: 'darwin',
  LINUX: 'linux'
};

// Error Codes
const ERROR_CODES = {
  // Authentication errors
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
  SESSION_EXPIRED: 'SESSION_EXPIRED',
  ACCOUNT_LOCKED: 'ACCOUNT_LOCKED',
  
  // Encryption errors
  DECRYPTION_FAILED: 'DECRYPTION_FAILED',
  ENCRYPTION_FAILED: 'ENCRYPTION_FAILED',
  INVALID_KEY: 'INVALID_KEY',
  
  // Storage errors
  STORAGE_NOT_AVAILABLE: 'STORAGE_NOT_AVAILABLE',
  STORAGE_ACCESS_DENIED: 'STORAGE_ACCESS_DENIED',
  STORAGE_CORRUPTED: 'STORAGE_CORRUPTED',
  
  // Network errors
  NETWORK_ERROR: 'NETWORK_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  TIMEOUT_ERROR: 'TIMEOUT_ERROR',
  
  // Application errors
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  INITIALIZATION_FAILED: 'INITIALIZATION_FAILED',
  OPERATION_CANCELLED: 'OPERATION_CANCELLED'
};

// Log Levels
const LOG_LEVELS = {
  ERROR: 'error',
  WARN: 'warn',
  INFO: 'info',
  DEBUG: 'debug',
  TRACE: 'trace'
};

// Sync Status
const SYNC_STATUS = {
  IDLE: 'idle',
  SYNCING: 'syncing',
  SUCCESS: 'success',
  ERROR: 'error',
  CONFLICT: 'conflict'
};

// Application States
const APP_STATES = {
  INITIALIZING: 'initializing',
  LOCKED: 'locked',
  UNLOCKED: 'unlocked',
  SYNCING: 'syncing',
  ERROR: 'error'
};

module.exports = {
  APP_INFO,
  WINDOW_CONFIG,
  SECURITY,
  API,
  STORAGE_KEYS,
  FILE_PATHS,
  IPC_CHANNELS,
  EVENTS,
  NOTIFICATION_TYPES,
  THEMES,
  LANGUAGES,
  PLATFORMS,
  ERROR_CODES,
  LOG_LEVELS,
  SYNC_STATUS,
  APP_STATES
};

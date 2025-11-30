class DarkWebMonitor {
    constructor() {
      this.api = new ApiClient();
    }
    
    async checkPasswordOnSubmit(password, domain) {
      try {
        // Check if this password is known to be breached
        const breachCount = await this.checkPasswordHash(password);
        
        if (breachCount > 0) {
          // Show browser notification
          this.showBreachNotification(domain, breachCount);
          
          // Send alert to main app
          await this.api.reportCompromisedPassword(domain);
        }
      } catch (error) {
        console.error('Error checking password:', error);
      }
    }
    
    async checkPasswordHash(password) {
      // SHA-1 hash computation
      const hash = await this.sha1(password);
      const prefix = hash.substring(0, 5);
      const suffix = hash.substring(5).toUpperCase();
      
      // Call HIBP API directly from extension
      const response = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`);
      const text = await response.text();
      
      // Check if our suffix exists in the results
      for (const line of text.split('\n')) {
        const [hashSuffix, count] = line.split(':');
        if (hashSuffix.trim() === suffix) {
          return parseInt(count.trim());
        }
      }
      
      return 0;
    }
    
    showBreachNotification(domain, count) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/warning.png',
        title: 'Compromised Password Detected',
        message: `The password you used on ${domain} appears in ${count} data breaches. Please change it immediately.`,
        buttons: [
          { title: 'Open Password Manager' }
        ]
      });
    }
    
    async sha1(str) {
      const buffer = new TextEncoder().encode(str);
      const hashBuffer = await crypto.subtle.digest('SHA-1', buffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
  }
  
class ExtensionSecureStorage {
  static async isHardwareSecurityAvailable() {
    // Browser extensions can't directly access hardware
    // but can use platform secure storage
    return true;
  }
  
  static async storeKey(keyId, keyData) {
    return new Promise((resolve, reject) => {
      const keyString = typeof keyData === 'string' 
        ? keyData 
        : btoa(String.fromCharCode.apply(null, new Uint8Array(keyData)));
      
      chrome.storage.local.set({
        [`secure_key_${keyId}`]: keyString
      }, () => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(true);
        }
      });
    });
  }
  
  static async retrieveKey(keyId) {
    return new Promise((resolve, reject) => {
      chrome.storage.local.get([`secure_key_${keyId}`], (result) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
          return;
        }
        
        const keyString = result[`secure_key_${keyId}`];
        if (!keyString) {
          reject(new Error('Key not found'));
          return;
        }
        
        // Convert back from string to array buffer
        const keyData = Uint8Array.from(atob(keyString), c => c.charCodeAt(0));
        resolve(keyData);
      });
    });
  }
}
  
// Background script for the Password Manager Extension
class PasswordManagerExtension {
  constructor() {
    this.api = new ApiClient();
    this.darkWebMonitor = new DarkWebMonitor();
    this.secureStorage = new ExtensionSecureStorage();
    this.setupListeners();
    this.isAuthenticated = false;
    this.vault = null;
    
    // Add these properties for inactivity tracking
    this.lastActivity = Date.now();
    this.autoLockTimer = null;
    this.autoLockTimeout = 300000; // Will be loaded from config (5 minutes default)
    
    // Initialize configuration and auto-lock timer
    this.initializeExtension();
  }
  
  async initializeExtension() {
    // Wait for API client to initialize and get config
    await this.api.initialize();
    if (this.api.config && this.api.config.autoLockTimeout) {
      this.autoLockTimeout = this.api.config.autoLockTimeout;
    }
    
    // Initialize auto-lock timer with correct timeout
    this.setupAutoLock();
  }

  setupListeners() {
    // Listen for messages from content scripts
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
      return true; // Keep channel open for async responses
    });
    
    // Add context menu for filling passwords
    chrome.contextMenus.create({
      id: 'fill-password',
      title: 'Fill Password',
      contexts: ['page', 'editable']
    });
    
    chrome.contextMenus.onClicked.addListener((info, tab) => {
      if (info.menuItemId === 'fill-password') {
        this.promptFillPassword(tab);
      }
    });
    
    // Add activity listeners
    chrome.tabs.onActivated.addListener(() => this.updateActivity());
    chrome.windows.onFocusChanged.addListener(() => this.updateActivity());
    
    // Listen for settings changes
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.settings && changes.settings.newValue) {
        const newSettings = changes.settings.newValue;
        if (newSettings.autoLockTimeout !== undefined) {
          // Convert to milliseconds if the setting is in minutes
          this.autoLockTimeout = typeof newSettings.autoLockTimeout === 'number' 
            ? newSettings.autoLockTimeout * 60000 // Convert minutes to milliseconds
            : newSettings.autoLockTimeout;
          this.setupAutoLock(); // Reset timer with new timeout
        }
      }
    });
  }

  async handleMessage(message, sender, sendResponse) {
    try {
      switch (message.action) {
        case 'login_form_detected':
          this.handleLoginFormDetected(message, sender.tab);
          break;
          
        case 'get_credentials':
          this.getCredentialsForSite(message.domain, sender.tab.id);
          break;
          
        case 'save_credentials':
          await this.saveCredentials(message.credentials);
          sendResponse({ success: true });
          break;
          
        case 'authenticate':
          const authResult = await this.authenticate(message.masterPassword);
          sendResponse(authResult);
          break;
          
        case 'check_auth_status':
          sendResponse({ isAuthenticated: this.isAuthenticated });
          break;
          
        case 'logout':
          this.logout();
          sendResponse({ success: true });
          break;
      }
    } catch (error) {
      console.error('Error handling message:', error);
      sendResponse({ error: error.message });
    }
  }

  async handleLoginFormDetected(message, tab) {
    // If we're authenticated, check if we have credentials for this domain
    if (this.isAuthenticated && this.vault) {
      const domain = message.domain;
      const matchingCredentials = this.findMatchingCredentials(domain);
      
      if (matchingCredentials.length > 0) {
        // Notify the user that credentials are available
        chrome.action.setBadgeText({
          text: matchingCredentials.length.toString(),
          tabId: tab.id
        });
        
        chrome.action.setBadgeBackgroundColor({
          color: '#4A6CF7',
          tabId: tab.id
        });
        
        // If only one credential is available and auto-fill is enabled, fill it
        if (matchingCredentials.length === 1 && await this.isAutoFillEnabled()) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'autofill',
            credentials: matchingCredentials[0]
          });
        }
      }
    }
  }

  async getCredentialsForSite(domain, tabId) {
    if (!this.isAuthenticated) {
      this.showNotification('Please unlock your vault first');
      return;
    }
    
    const matchingCredentials = this.findMatchingCredentials(domain);
    
    if (matchingCredentials.length === 0) {
      this.showNotification('No saved credentials found for this site');
      return;
    }
    
    // Send credentials to content script
    chrome.tabs.sendMessage(tabId, {
      action: 'autofill',
      credentials: matchingCredentials
    });
  }

  findMatchingCredentials(domain) {
    if (!this.vault || !this.vault.items) return [];
    
    // Find credentials matching the domain
    return this.vault.items
      .filter(item => {
        if (item.type !== 'password') return false;
        
        const itemDomain = this.extractDomain(item.data.url);
        return itemDomain === domain;
      })
      .map(item => ({
        id: item.id,
        username: item.data.username,
        password: item.data.password
      }));
  }

  extractDomain(url) {
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname;
      const parts = hostname.split('.');
      
      if (parts.length <= 2) return hostname;
      
      // Handle special cases like co.uk, com.au
      if (parts.length > 2 && (parts[parts.length-2] === 'co' || parts[parts.length-2] === 'com')) {
        return parts.slice(-3).join('.');
      }
      
      return parts.slice(-2).join('.');
    } catch (e) {
      return url; // If not a valid URL, return as is
    }
  }

  async saveCredentials(credentials) {
    if (!this.isAuthenticated) {
      await this.storeForLater(credentials);
      this.showNotification('Please login to save credentials');
      return;
    }
    
    try {
      // Check if we already have these credentials
      const domain = credentials.domain;
      const existing = this.findMatchingCredentials(domain);
      const existingMatch = existing.find(cred => cred.username === credentials.username);
      
      if (existingMatch) {
        // Update if password changed
        if (existingMatch.password !== credentials.password) {
          await this.api.updateVaultItem({
            id: existingMatch.id,
            type: 'password',
            data: credentials
          });
          this.showNotification('Password updated');
        }
      } else {
        // Save new credentials
        await this.api.addVaultItem({
          type: 'password',
          data: credentials
        });
        this.showNotification('Password saved');
      }
      
      // Refresh vault
      await this.refreshVault();
    } catch (error) {
      console.error('Error saving credentials:', error);
      this.showNotification('Failed to save credentials');
    }
  }

  async storeForLater(credentials) {
    // Store credentials temporarily until the user authenticates
    await chrome.storage.local.set({
      'pendingCredentials': credentials
    });
  }

  async authenticate(masterPassword) {
    try {
      const authResult = await this.api.login(masterPassword);
      
      if (authResult.success) {
        this.isAuthenticated = true;
        
        // Initialize auto-lock after successful authentication
        this.updateActivity(); // Reset activity timer
        this.setupAutoLock();
        
        // Fetch vault items
        await this.refreshVault();
        
        // Check for any pending credentials
        await this.checkPendingCredentials();
        
        return { success: true };
      }
      
      return { success: false, error: 'Invalid master password' };
    } catch (error) {
      console.error('Authentication error:', error);
      return { success: false, error: error.message };
    }
  }

  async refreshVault() {
    try {
      this.vault = await this.api.getVault();
    } catch (error) {
      console.error('Error refreshing vault:', error);
      this.showNotification('Failed to load vault');
    }
  }

  async checkPendingCredentials() {
    const result = await chrome.storage.local.get('pendingCredentials');
    
    if (result.pendingCredentials) {
      await this.saveCredentials(result.pendingCredentials);
      await chrome.storage.local.remove('pendingCredentials');
    }
  }

  async isAutoFillEnabled() {
    const result = await chrome.storage.local.get('settings');
    return result.settings?.autoFill !== false; // Default to true
  }

  logout() {
    this.isAuthenticated = false;
    this.vault = null;
    
    // Clear auto-lock timer
    if (this.autoLockTimer) {
      clearInterval(this.autoLockTimer);
      this.autoLockTimer = null;
    }
  }

  showNotification(message) {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-48.png',
      title: 'Password Manager',
      message: message
    });
  }

  promptFillPassword(tab) {
    chrome.tabs.sendMessage(tab.id, {
      action: 'show_credential_picker'
    });
  }

  updateActivity() {
    this.lastActivity = Date.now();
  }

  setupAutoLock() {
    // Clear existing timer if any
    if (this.autoLockTimer) {
      clearInterval(this.autoLockTimer);
    }
    
    // Skip if not authenticated
    if (!this.isAuthenticated) {
      return;
    }
    
    // Get setting from storage
    chrome.storage.local.get(['settings'], (result) => {
      if (result.settings && result.settings.autoLockTimeout !== undefined) {
        // Convert to milliseconds if the stored setting is in minutes
        this.autoLockTimeout = typeof result.settings.autoLockTimeout === 'number' 
          ? result.settings.autoLockTimeout * 60000 // Convert minutes to milliseconds
          : result.settings.autoLockTimeout;
      }
      
      // Create a heartbeat check every minute
      this.autoLockTimer = setInterval(() => {
        const now = Date.now();
        const inactiveTime = now - this.lastActivity; // Keep in milliseconds
        
        if (inactiveTime >= this.autoLockTimeout) {
          this.logout();
          
          // Notify user
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon-48.png',
            title: 'Password Manager',
            message: 'Vault locked due to inactivity'
          });
          
          // Clear the timer
          clearInterval(this.autoLockTimer);
          this.autoLockTimer = null;
        }
      }, 60000); // Check every minute
    });
  }
}

// Configuration system (following shared config pattern)
const getExtensionConfig = async () => {
  // Try to get user-configured API URL from storage first
  try {
    const result = await chrome.storage.sync.get(['apiBaseUrl']);
    if (result.apiBaseUrl) {
      return {
        apiBaseUrl: result.apiBaseUrl,
        appName: 'Password Manager Extension',
        version: '1.0.0'
      };
    }
  } catch (error) {
    console.warn('Could not load user configuration:', error);
  }
  
  // Fall back to environment-based defaults
  const isDevelopment = true; // For extension, assume development unless built differently
  return {
    appName: 'Password Manager Extension',
    version: '1.0.0',
    apiBaseUrl: isDevelopment 
      ? 'http://127.0.0.1:8000/api'  // Django backend
      : 'https://your-password-manager.com/api',
    syncInterval: 300000, // 5 minutes
    maxRetries: 3,
    autoLockTimeout: 300000 // 5 minutes default
  };
};

// ApiClient class for communicating with the Password Manager API
class ApiClient {
  constructor() {
    this.apiUrl = null; // Will be set by config
    this.token = null;
    this.cryptoService = null;
    this.config = null;
    
    // Initialize configuration and token
    this.initialize();
  }
  
  async initialize() {
    this.config = await getExtensionConfig();
    this.apiUrl = this.config.apiBaseUrl;
    
    // Load existing token from storage
    await this.loadTokenFromStorage();
  }
  
  async loadTokenFromStorage() {
    const result = await chrome.storage.local.get('authToken');
    if (result.authToken) {
      this.token = result.authToken;
    }
  }
  
  async login(masterPassword) {
    try {
      // Initialize crypto service
      this.cryptoService = new CryptoService(masterPassword);
      
      // Get salt from server
      const response = await fetch(`${this.apiUrl}/vault/get_salt/`, {
        method: 'GET',
        headers: this.getHeaders()
      });
      
      if (!response.ok) {
        throw new Error('Failed to get salt');
      }
      
      const saltData = await response.json();
      const salt = saltData.salt;
      
      // Derive encryption key
      const key = await this.cryptoService.deriveKey(salt);
      
      // Verify master password
      const verifyResponse = await fetch(`${this.apiUrl}/vault/verify_master_password/`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ master_password: masterPassword })
      });
      
      if (!verifyResponse.ok) {
        throw new Error('Invalid credentials');
      }
      
      const verifyResult = await verifyResponse.json();
      
      if (verifyResult.is_valid) {
        // Store encryption key securely
        await chrome.storage.local.set({
          'encryptionKey': key,
          'masterPasswordHash': await this.cryptoService.hash(masterPassword)
        });
        
        return { success: true };
      }
      
      return { success: false, error: 'Invalid master password' };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: error.message };
    }
  }
  
  getHeaders() {
    const headers = {
      'Content-Type': 'application/json'
    };
    
    if (this.token) {
      headers['Authorization'] = `Token ${this.token}`;
    }
    
    return headers;
  }
  
  async getVault() {
    // Get vault items
    const response = await fetch(`${this.apiUrl}/vault/`, {
      method: 'GET',
      headers: this.getHeaders()
    });
    
    if (!response.ok) {
      throw new Error('Failed to get vault items');
    }
    
    const items = await response.json();
    
    // Get encryption key from storage
    const result = await chrome.storage.local.get('encryptionKey');
    if (!result.encryptionKey) {
      throw new Error('Encryption key not available');
    }
    
    // Decrypt items
    const decryptedItems = await Promise.all(items.map(async (item) => {
      const decrypted = await this.cryptoService.decrypt(
        item.encrypted_data,
        result.encryptionKey
      );
      
      return {
        id: item.id,
        item_id: item.item_id,
        type: item.item_type,
        data: decrypted,
        created_at: item.created_at,
        updated_at: item.updated_at,
        folder_id: item.folder_id,
        tags: item.tags || []
      };
    }));
    
    return { items: decryptedItems };
  }
  
  async addVaultItem(item) {
    // Get encryption key from storage
    const result = await chrome.storage.local.get('encryptionKey');
    if (!result.encryptionKey) {
      throw new Error('Encryption key not available');
    }
    
    // Generate random ID
    const itemId = this.generateRandomId();
    
    // Encrypt item data
    const encryptedData = await this.cryptoService.encrypt(
      item.data,
      result.encryptionKey
    );
    
    // Create payload
    const payload = {
      item_id: itemId,
      item_type: item.type,
      encrypted_data: encryptedData,
      folder_id: item.folder_id,
      tags: item.tags || []
    };
    
    // Send to server
    const response = await fetch(`${this.apiUrl}/vault/`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error('Failed to add vault item');
    }
    
    return await response.json();
  }
  
  async updateVaultItem(item) {
    // Get encryption key from storage
    const result = await chrome.storage.local.get('encryptionKey');
    if (!result.encryptionKey) {
      throw new Error('Encryption key not available');
    }
    
    // Encrypt item data
    const encryptedData = await this.cryptoService.encrypt(
      item.data,
      result.encryptionKey
    );
    
    // Create payload
    const payload = {
      encrypted_data: encryptedData,
      folder_id: item.folder_id,
      tags: item.tags || []
    };
    
    // Send to server
    const response = await fetch(`${this.apiUrl}/vault/${item.id}/`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error('Failed to update vault item');
    }
    
    return await response.json();
  }
  
  generateRandomId() {
    return (([1e7]) + (-1e3) + (-4e3) + (-8e3) + (-1e11)).replace(/[018]/g, c =>
      (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
  }
}

// CryptoService class for browser extension
class CryptoService {
  constructor(masterPassword) {
    this.masterPassword = masterPassword;
    this.keyCache = new Map();
  }

  /**
   * Derive encryption key from master password and salt using PBKDF2
   * @param {string} salt - Base64 encoded salt
   * @param {number} iterations - Number of PBKDF2 iterations (default: 100000)
   * @returns {Promise<CryptoKey>} Derived encryption key
   */
  async deriveKey(salt, iterations = 100000) {
    const cacheKey = `${this.masterPassword}:${salt}`;
    
    if (this.keyCache.has(cacheKey)) {
      return this.keyCache.get(cacheKey);
    }

    try {
      const encoder = new TextEncoder();
      const passwordBuffer = encoder.encode(this.masterPassword);
      
      // Decode salt from base64
      const saltBuffer = Uint8Array.from(atob(salt), c => c.charCodeAt(0));
      
      // Import password as key material
      const keyMaterial = await crypto.subtle.importKey(
        'raw',
        passwordBuffer,
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );
      
      // Derive the actual encryption key
      const derivedKey = await crypto.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: saltBuffer,
          iterations: iterations,
          hash: 'SHA-256'
        },
        keyMaterial,
        {
          name: 'AES-GCM',
          length: 256
        },
        false,
        ['encrypt', 'decrypt']
      );
      
      this.keyCache.set(cacheKey, derivedKey);
      return derivedKey;
    } catch (error) {
      console.error('Key derivation failed:', error);
      throw new Error('Failed to derive encryption key');
    }
  }

  /**
   * Encrypt data using AES-GCM
   * @param {string} plaintext - Data to encrypt
   * @param {CryptoKey} key - Encryption key
   * @returns {Promise<string>} Base64 encoded encrypted data
   */
  async encrypt(plaintext, key) {
    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(plaintext);
      
      // Generate random IV
      const iv = crypto.getRandomValues(new Uint8Array(12));
      
      // Encrypt the data
      const encryptedBuffer = await crypto.subtle.encrypt(
        {
          name: 'AES-GCM',
          iv: iv
        },
        key,
        data
      );
      
      // Combine IV and encrypted data
      const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encryptedBuffer), iv.length);
      
      // Return as base64
      return btoa(String.fromCharCode(...combined));
    } catch (error) {
      console.error('Encryption failed:', error);
      throw new Error('Failed to encrypt data');
    }
  }

  /**
   * Decrypt data using AES-GCM
   * @param {string} encryptedData - Base64 encoded encrypted data
   * @param {CryptoKey} key - Decryption key
   * @returns {Promise<string>} Decrypted plaintext
   */
  async decrypt(encryptedData, key) {
    try {
      // Decode from base64
      const combined = Uint8Array.from(atob(encryptedData), c => c.charCodeAt(0));
      
      // Extract IV and encrypted data
      const iv = combined.slice(0, 12);
      const encrypted = combined.slice(12);
      
      // Decrypt the data
      const decryptedBuffer = await crypto.subtle.decrypt(
        {
          name: 'AES-GCM',
          iv: iv
        },
        key,
        encrypted
      );
      
      // Decode to string
      const decoder = new TextDecoder();
      return decoder.decode(decryptedBuffer);
    } catch (error) {
      console.error('Decryption failed:', error);
      throw new Error('Failed to decrypt data');
    }
  }

  /**
   * Generate secure hash of data
   * @param {string} data - Data to hash
   * @param {string} algorithm - Hash algorithm (default: SHA-256)
   * @returns {Promise<string>} Hex encoded hash
   */
  async hash(data, algorithm = 'SHA-256') {
    try {
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(data);
      const hashBuffer = await crypto.subtle.digest(algorithm, dataBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
      console.error('Hashing failed:', error);
      throw new Error('Failed to hash data');
    }
  }

  /**
   * Generate cryptographically secure random bytes
   * @param {number} length - Number of bytes to generate
   * @returns {Uint8Array} Random bytes
   */
  generateRandomBytes(length) {
    return crypto.getRandomValues(new Uint8Array(length));
  }

  /**
   * Generate secure random string
   * @param {number} length - Length of string
   * @param {string} charset - Character set to use
   * @returns {string} Random string
   */
  generateRandomString(length = 32, charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') {
    const randomBytes = this.generateRandomBytes(length);
    let result = '';
    
    for (let i = 0; i < length; i++) {
      result += charset[randomBytes[i] % charset.length];
    }
    
    return result;
  }

  /**
   * Clear cached keys for security
   */
  clearCache() {
    this.keyCache.clear();
  }

  /**
   * Derive key for specific purpose
   * @param {string} purpose - Purpose identifier
   * @param {string} salt - Salt for derivation
   * @returns {Promise<CryptoKey>} Purpose-specific key
   */
  async deriveKeyForPurpose(purpose, salt) {
    const purposePassword = `${this.masterPassword}:${purpose}`;
    const tempCrypto = new CryptoService(purposePassword);
    return await tempCrypto.deriveKey(salt);
  }
}

// Initialize the extension
const extension = new PasswordManagerExtension();
  
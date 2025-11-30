/**
 * Options page for Password Manager browser extension
 * Handles extension settings and configuration
 */

import config from '@shared/config';

class ExtensionOptions {
  constructor() {
    this.settingsKey = 'passwordmanager_extension_settings';
    this.defaultSettings = {
      autoFill: true,
      autoSave: true,
      showNotifications: true,
      apiEndpoint: config.get('api.baseUrl'),
      sessionTimeout: config.get('security.sessionTimeout') / 60000, // Convert to minutes
      darkMode: false,
      keyboardShortcuts: true,
      contextMenu: true,
      iconBadge: true,
      syncEnabled: true,
      debugMode: config.isDevelopment(),
    };
    
    this.init();
  }

  async init() {
    await this.loadSettings();
    this.setupEventListeners();
    this.updateUI();
  }

  async loadSettings() {
    try {
      const result = await chrome.storage.sync.get([this.settingsKey]);
      this.settings = { 
        ...this.defaultSettings, 
        ...(result[this.settingsKey] || {}) 
      };
    } catch (error) {
      console.error('Failed to load settings:', error);
      this.settings = { ...this.defaultSettings };
    }
  }

  async saveSettings() {
    try {
      await chrome.storage.sync.set({
        [this.settingsKey]: this.settings
      });
      
      // Notify background script of settings change
      chrome.runtime.sendMessage({
        type: 'SETTINGS_UPDATED',
        settings: this.settings
      });
      
      this.showNotification('Settings saved successfully', 'success');
    } catch (error) {
      console.error('Failed to save settings:', error);
      this.showNotification('Failed to save settings', 'error');
    }
  }

  setupEventListeners() {
    // Auto-fill toggle
    const autoFillToggle = document.getElementById('autoFill');
    if (autoFillToggle) {
      autoFillToggle.addEventListener('change', (e) => {
        this.settings.autoFill = e.target.checked;
        this.saveSettings();
      });
    }

    // Auto-save toggle
    const autoSaveToggle = document.getElementById('autoSave');
    if (autoSaveToggle) {
      autoSaveToggle.addEventListener('change', (e) => {
        this.settings.autoSave = e.target.checked;
        this.saveSettings();
      });
    }

    // Notifications toggle
    const notificationsToggle = document.getElementById('showNotifications');
    if (notificationsToggle) {
      notificationsToggle.addEventListener('change', (e) => {
        this.settings.showNotifications = e.target.checked;
        this.saveSettings();
      });
    }

    // API endpoint input
    const apiEndpointInput = document.getElementById('apiEndpoint');
    if (apiEndpointInput) {
      apiEndpointInput.addEventListener('blur', (e) => {
        const url = e.target.value.trim();
        if (this.isValidUrl(url)) {
          this.settings.apiEndpoint = url;
          this.saveSettings();
          apiEndpointInput.classList.remove('error');
        } else {
          apiEndpointInput.classList.add('error');
          this.showNotification('Invalid API endpoint URL', 'error');
        }
      });
    }

    // Session timeout input
    const sessionTimeoutInput = document.getElementById('sessionTimeout');
    if (sessionTimeoutInput) {
      sessionTimeoutInput.addEventListener('change', (e) => {
        const minutes = parseInt(e.target.value);
        if (minutes >= 1 && minutes <= 60) {
          this.settings.sessionTimeout = minutes;
          this.saveSettings();
          sessionTimeoutInput.classList.remove('error');
        } else {
          sessionTimeoutInput.classList.add('error');
          this.showNotification('Session timeout must be between 1 and 60 minutes', 'error');
        }
      });
    }

    // Dark mode toggle
    const darkModeToggle = document.getElementById('darkMode');
    if (darkModeToggle) {
      darkModeToggle.addEventListener('change', (e) => {
        this.settings.darkMode = e.target.checked;
        this.toggleDarkMode(e.target.checked);
        this.saveSettings();
      });
    }

    // Keyboard shortcuts toggle
    const keyboardShortcutsToggle = document.getElementById('keyboardShortcuts');
    if (keyboardShortcutsToggle) {
      keyboardShortcutsToggle.addEventListener('change', (e) => {
        this.settings.keyboardShortcuts = e.target.checked;
        this.saveSettings();
      });
    }

    // Context menu toggle
    const contextMenuToggle = document.getElementById('contextMenu');
    if (contextMenuToggle) {
      contextMenuToggle.addEventListener('change', (e) => {
        this.settings.contextMenu = e.target.checked;
        this.saveSettings();
      });
    }

    // Icon badge toggle
    const iconBadgeToggle = document.getElementById('iconBadge');
    if (iconBadgeToggle) {
      iconBadgeToggle.addEventListener('change', (e) => {
        this.settings.iconBadge = e.target.checked;
        this.saveSettings();
      });
    }

    // Sync toggle
    const syncToggle = document.getElementById('syncEnabled');
    if (syncToggle) {
      syncToggle.addEventListener('change', (e) => {
        this.settings.syncEnabled = e.target.checked;
        this.saveSettings();
      });
    }

    // Debug mode toggle (only in development)
    const debugModeToggle = document.getElementById('debugMode');
    if (debugModeToggle && config.isDevelopment()) {
      debugModeToggle.addEventListener('change', (e) => {
        this.settings.debugMode = e.target.checked;
        this.saveSettings();
      });
    }

    // Reset to defaults button
    const resetButton = document.getElementById('resetDefaults');
    if (resetButton) {
      resetButton.addEventListener('click', () => {
        this.resetToDefaults();
      });
    }

    // Export settings button
    const exportButton = document.getElementById('exportSettings');
    if (exportButton) {
      exportButton.addEventListener('click', () => {
        this.exportSettings();
      });
    }

    // Import settings button
    const importButton = document.getElementById('importSettings');
    const importInput = document.getElementById('importFile');
    if (importButton && importInput) {
      importButton.addEventListener('click', () => {
        importInput.click();
      });
      
      importInput.addEventListener('change', (e) => {
        this.importSettings(e.target.files[0]);
      });
    }
  }

  updateUI() {
    // Update all form elements with current settings
    Object.keys(this.settings).forEach(key => {
      const element = document.getElementById(key);
      if (element) {
        if (element.type === 'checkbox') {
          element.checked = this.settings[key];
        } else {
          element.value = this.settings[key];
        }
      }
    });

    // Apply dark mode if enabled
    if (this.settings.darkMode) {
      this.toggleDarkMode(true);
    }

    // Hide debug options in production
    const debugSection = document.getElementById('debugSection');
    if (debugSection && !config.isDevelopment()) {
      debugSection.style.display = 'none';
    }
  }

  toggleDarkMode(enabled) {
    document.body.classList.toggle('dark-mode', enabled);
  }

  isValidUrl(string) {
    try {
      const url = new URL(string);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
      return false;
    }
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    const container = document.getElementById('notifications');
    if (container) {
      container.appendChild(notification);
      
      // Auto-remove after 3 seconds
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 3000);
    }
  }

  async resetToDefaults() {
    if (confirm('Are you sure you want to reset all settings to defaults? This action cannot be undone.')) {
      this.settings = { ...this.defaultSettings };
      await this.saveSettings();
      this.updateUI();
      this.showNotification('Settings reset to defaults', 'success');
    }
  }

  exportSettings() {
    const settingsJson = JSON.stringify(this.settings, null, 2);
    const blob = new Blob([settingsJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'password-manager-extension-settings.json';
    a.click();
    
    URL.revokeObjectURL(url);
    this.showNotification('Settings exported successfully', 'success');
  }

  async importSettings(file) {
    if (!file) return;
    
    try {
      const text = await file.text();
      const importedSettings = JSON.parse(text);
      
      // Validate imported settings
      const validSettings = {};
      Object.keys(this.defaultSettings).forEach(key => {
        if (key in importedSettings && typeof importedSettings[key] === typeof this.defaultSettings[key]) {
          validSettings[key] = importedSettings[key];
        }
      });
      
      this.settings = { ...this.defaultSettings, ...validSettings };
      await this.saveSettings();
      this.updateUI();
      this.showNotification('Settings imported successfully', 'success');
    } catch (error) {
      console.error('Import error:', error);
      this.showNotification('Failed to import settings. Please check the file format.', 'error');
    }
  }

  // Get current settings (for use by other scripts)
  getSettings() {
    return { ...this.settings };
  }

  // Update specific setting
  async updateSetting(key, value) {
    if (key in this.settings) {
      this.settings[key] = value;
      await this.saveSettings();
      this.updateUI();
    }
  }
}

// Initialize options page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.extensionOptions = new ExtensionOptions();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ExtensionOptions;
}

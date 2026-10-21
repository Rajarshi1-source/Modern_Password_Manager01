const { contextBridge, ipcRenderer } = require('electron');

// Channel names must match IPC_CHANNELS / EVENTS in src/shared/constants.js,
// which main.js registers. They are repeated here because a sandboxed
// preload cannot require local modules.

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Secure storage
  secureStorage: {
    isAvailable: () => ipcRenderer.invoke('secure-storage:available'),
    set: (key, value) => ipcRenderer.invoke('secure-storage:set', { key, value }),
    get: (key) => ipcRenderer.invoke('secure-storage:get', key),
    delete: (key) => ipcRenderer.invoke('secure-storage:delete', key)
  },

  // App information
  app: {
    getVersion: () => ipcRenderer.invoke('app:version')
  },

  // Window controls
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close')
  },

  // Event listeners
  onVaultLock: (callback) => {
    ipcRenderer.on('security:auto-lock-triggered', callback);
    return () => ipcRenderer.removeListener('security:auto-lock-triggered', callback);
  },

  onOpenSettings: (callback) => {
    ipcRenderer.on('open-settings', callback);
    return () => ipcRenderer.removeListener('open-settings', callback);
  },

  // Platform detection
  platform: process.platform,
  isElectron: true
});

// Remove the loading text
window.addEventListener('DOMContentLoaded', () => {
  const replaceText = (selector, text) => {
    const element = document.getElementById(selector);
    if (element) element.innerText = text;
  };

  for (const type of ['chrome', 'node', 'electron']) {
    replaceText(`${type}-version`, process.versions[type]);
  }
});

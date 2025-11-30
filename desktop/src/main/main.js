const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';

// Import secure storage for IPC handling
const WindowsSecureStorage = require('./windowsSecureStorage');

// Keep a global reference of the window object
let mainWindow;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false, // Security: disable node integration
      contextIsolation: true, // Security: enable context isolation
      preload: path.join(__dirname, 'preload.js'), // Use preload script
      webSecurity: true
    },
    icon: path.join(__dirname, '../../assets/icon.png'), // App icon
    show: false // Don't show until ready
  });

  // Load the app
  if (isDev) {
    // Development: load from React dev server
    mainWindow.loadURL('http://localhost:3000');
    // Open DevTools in development
    mainWindow.webContents.openDevTools();
  } else {
    // Production: load from built React app
    mainWindow.loadFile(path.join(__dirname, '../../build/index.html'));
  }

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    // Focus window
    if (isDev) {
      mainWindow.focus();
    }
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url);
    return { action: 'deny' };
  });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  createWindow();
  
  // Create application menu
  createMenu();
  
  // Setup IPC handlers
  setupIpcHandlers();

  app.on('activate', () => {
    // On macOS, re-create window when dock icon is clicked
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Security: prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, url) => {
    event.preventDefault();
    require('electron').shell.openExternal(url);
  });
});

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Lock Vault',
          accelerator: 'CmdOrCtrl+L',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send('vault-lock');
            }
          }
        },
        {
          label: 'Settings',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send('open-settings');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Quit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectall' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Password Manager',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Password Manager',
              message: 'Password Manager Desktop',
              detail: 'Version 1.0.0\nSecure password management for desktop'
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function setupIpcHandlers() {
  // Secure storage IPC handlers
  ipcMain.handle('secure-storage-available', async () => {
    try {
      const available = await WindowsSecureStorage.isHardwareSecurityAvailable();
      return { available, success: true };
    } catch (error) {
      console.error('Error checking secure storage availability:', error);
      return { available: false, success: false, error: error.message };
    }
  });

  ipcMain.handle('secure-storage-set', async (event, { key, value }) => {
    try {
      const success = await WindowsSecureStorage.storeKey(key, value);
      return { success };
    } catch (error) {
      console.error('Error storing key:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('secure-storage-get', async (event, key) => {
    try {
      const value = await WindowsSecureStorage.retrieveKey(key);
      return { success: true, value };
    } catch (error) {
      console.error('Error retrieving key:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('secure-storage-delete', async (event, key) => {
    try {
      const success = await WindowsSecureStorage.deleteKey(key);
      return { success };
    } catch (error) {
      console.error('Error deleting key:', error);
      return { success: false, error: error.message };
    }
  });

  // App information
  ipcMain.handle('app-version', () => {
    return app.getVersion();
  });

  ipcMain.handle('app-path', (event, name) => {
    return app.getPath(name);
  });

  // Window controls
  ipcMain.handle('window-minimize', () => {
    if (mainWindow) {
      mainWindow.minimize();
    }
  });

  ipcMain.handle('window-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.handle('window-close', () => {
    if (mainWindow) {
      mainWindow.close();
    }
  });
}

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    // Someone tried to run a second instance, focus our window instead
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// Security: Prevent navigation to external websites
app.on('web-contents-created', (event, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);
    
    if (parsedUrl.origin !== 'http://localhost:3000' && !navigationUrl.startsWith('file://')) {
      event.preventDefault();
    }
  });
});

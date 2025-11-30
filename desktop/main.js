/**
 * Main entry point for the Password Manager desktop application.
 * This file initializes and manages the Electron application lifecycle.
 */

const { app, BrowserWindow, Menu, dialog, shell, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';

// Import application modules
const { getFullConfig } = require('./src/shared/config');
const { Platform, PathUtils, LogUtils } = require('./src/shared/utils');
const { APP_INFO, WINDOW_CONFIG, IPC_CHANNELS, EVENTS } = require('./src/shared/constants');
const WindowsSecureStorage = require('./src/main/windowsSecureStorage');

// Create application logger
const logger = LogUtils.createLogger('Main');

// Global references
let mainWindow = null;
let appConfig = null;
let isAppReady = false;

/**
 * Initialize application configuration
 */
function initializeConfig() {
  try {
    appConfig = getFullConfig();
    logger.info('Application configuration loaded successfully');
    
    // Ensure required directories exist
    PathUtils.ensureDirectoryExists(PathUtils.getUserDataPath());
    PathUtils.ensureDirectoryExists(PathUtils.getSecureKeysPath());
    PathUtils.ensureDirectoryExists(PathUtils.getLogsPath());
    
    return true;
  } catch (error) {
    logger.error('Failed to initialize configuration:', error);
    return false;
  }
}

/**
 * Create the main application window
 */
function createMainWindow() {
  const windowConfig = {
    ...WINDOW_CONFIG,
    width: appConfig.userPreferences.windowWidth || WINDOW_CONFIG.DEFAULT_WIDTH,
    height: appConfig.userPreferences.windowHeight || WINDOW_CONFIG.DEFAULT_HEIGHT,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,
      sandbox: true,                    // Add sandboxing
      preload: path.join(__dirname, 'src/main/preload.js'),
      allowRunningInsecureContent: false,
      experimentalFeatures: false
    },
    icon: getAppIcon(),
    show: false, // Don't show until ready to prevent visual flash
    titleBarStyle: Platform.isMacOS() ? 'hiddenInset' : 'default'
  };

  mainWindow = new BrowserWindow(windowConfig);

  // Load the application content
  if (isDev && appConfig.enableReactDevServer) {
    // Development: load from React dev server
    mainWindow.loadURL(appConfig.reactDevServerUrl);
    
    if (appConfig.enableDevTools) {
      mainWindow.webContents.openDevTools();
    }
  } else {
    // Production: load from built files
    const indexPath = path.join(__dirname, 'src/renderer/index.html');
    mainWindow.loadFile(indexPath);
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    if (isDev) {
      mainWindow.focus();
    }
    
    logger.info('Main window is ready and visible');
  });

  // Handle window events
  mainWindow.on('closed', () => {
    mainWindow = null;
    logger.info('Main window closed');
  });

  mainWindow.on('focus', () => {
    logger.debug('Main window focused');
  });

  mainWindow.on('blur', () => {
    logger.debug('Main window blurred');
  });

  // Enhanced navigation protection
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url !== mainWindow.webContents.getURL()) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  // Handle new window creation
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Prevent external protocol handling
  mainWindow.webContents.on('will-redirect', (event, url) => {
    if (!url.startsWith('file://') && !url.startsWith('http://localhost')) {
      event.preventDefault();
    }
  });

  // Handle certificate errors
  mainWindow.webContents.on('certificate-error', (event, url, error, certificate, callback) => {
    if (isDev && url.startsWith('http://localhost')) {
      // Allow localhost in development
      event.preventDefault();
      callback(true);
    } else {
      // Deny certificate errors in production
      callback(false);
    }
  });

  return mainWindow;
}

/**
 * Get application icon path for the current platform
 */
function getAppIcon() {
  const iconDir = path.join(__dirname, 'assets');
  
  if (Platform.isWindows()) {
    return path.join(iconDir, 'icon.ico');
  } else if (Platform.isMacOS()) {
    return path.join(iconDir, 'icon.icns');
  } else {
    return path.join(iconDir, 'icon.png');
  }
}

/**
 * Create application menu
 */
function createApplicationMenu() {
  const isMac = Platform.isMacOS();
  
  const template = [
    // macOS app menu
    ...(isMac ? [{
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideothers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),
    
    // File menu
    {
      label: 'File',
      submenu: [
        {
          label: 'Lock Vault',
          accelerator: 'CmdOrCtrl+L',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send(EVENTS.AUTO_LOCK_TRIGGERED);
            }
          }
        },
        {
          label: 'Sync Now',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send(EVENTS.SYNC_STARTED);
            }
          }
        },
        { type: 'separator' },
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
        isMac ? { role: 'close' } : { role: 'quit' }
      ]
    },
    
    // Edit menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        ...(isMac ? [
          { role: 'pasteAndMatchStyle' },
          { role: 'delete' },
          { role: 'selectAll' },
          { type: 'separator' },
          {
            label: 'Speech',
            submenu: [
              { role: 'startSpeaking' },
              { role: 'stopSpeaking' }
            ]
          }
        ] : [
          { role: 'delete' },
          { type: 'separator' },
          { role: 'selectAll' }
        ])
      ]
    },
    
    // View menu
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
    
    // Window menu
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        ...(isMac ? [
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'window' }
        ] : [
          { role: 'close' }
        ])
      ]
    },
    
    // Help menu
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Password Manager',
          click: async () => {
            await dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Password Manager',
              message: APP_INFO.NAME,
              detail: `Version: ${app.getVersion()}\n${APP_INFO.DESCRIPTION}\n\nBuilt with Electron ${process.versions.electron}`
            });
          }
        },
        {
          label: 'Learn More',
          click: async () => {
            await shell.openExternal(APP_INFO.HOMEPAGE);
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

/**
 * Setup IPC handlers for communication with renderer process
 */
function setupIpcHandlers() {
  // Secure storage handlers
  ipcMain.handle(IPC_CHANNELS.SECURE_STORAGE_AVAILABLE, async () => {
    try {
      const available = await WindowsSecureStorage.isHardwareSecurityAvailable();
      return { available, success: true };
    } catch (error) {
      logger.error('Error checking secure storage availability:', error);
      return { available: false, success: false, error: error.message };
    }
  });

  ipcMain.handle(IPC_CHANNELS.SECURE_STORAGE_SET, async (event, { key, value }) => {
    try {
      const success = await WindowsSecureStorage.storeKey(key, value);
      return { success };
    } catch (error) {
      logger.error('Error storing key:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle(IPC_CHANNELS.SECURE_STORAGE_GET, async (event, key) => {
    try {
      const value = await WindowsSecureStorage.retrieveKey(key);
      return { success: true, value };
    } catch (error) {
      logger.error('Error retrieving key:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle(IPC_CHANNELS.SECURE_STORAGE_DELETE, async (event, key) => {
    try {
      const success = await WindowsSecureStorage.deleteKey(key);
      return { success };
    } catch (error) {
      logger.error('Error deleting key:', error);
      return { success: false, error: error.message };
    }
  });

  // Application handlers
  ipcMain.handle(IPC_CHANNELS.APP_VERSION, () => {
    return app.getVersion();
  });

  // Window control handlers
  ipcMain.handle(IPC_CHANNELS.WINDOW_MINIMIZE, () => {
    if (mainWindow) {
      mainWindow.minimize();
    }
  });

  ipcMain.handle(IPC_CHANNELS.WINDOW_MAXIMIZE, () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.handle(IPC_CHANNELS.WINDOW_CLOSE, () => {
    if (mainWindow) {
      mainWindow.close();
    }
  });

  logger.info('IPC handlers setup completed');
}

/**
 * Application event handlers
 */
function setupApplicationEvents() {
  // App ready event
  app.whenReady().then(() => {
    logger.info('Application is ready');
    
    if (!initializeConfig()) {
      logger.error('Failed to initialize configuration, exiting');
      app.quit();
      return;
    }
    
    createMainWindow();
    createApplicationMenu();
    setupIpcHandlers();
    setupAutoUpdater();
    
    isAppReady = true;
    
    // macOS: Re-create window when dock icon is clicked
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
      }
    });
  });

  // Window all closed event
  app.on('window-all-closed', () => {
    // On macOS, keep app running even when all windows are closed
    if (!Platform.isMacOS()) {
      app.quit();
    }
  });

  // Before quit event
  app.on('before-quit', (event) => {
    logger.info('Application is about to quit');
    
    // Save window state
    if (mainWindow && !mainWindow.isDestroyed()) {
      const bounds = mainWindow.getBounds();
      const Store = require('electron-store');
      const store = new Store({ name: 'preferences' });
      store.set('windowWidth', bounds.width);
      store.set('windowHeight', bounds.height);
    }
  });

  // Security: Prevent new window creation
  app.on('web-contents-created', (event, contents) => {
    contents.on('new-window', (event, url) => {
      event.preventDefault();
      shell.openExternal(url);
    });
  });
}

/**
 * Handle single instance lock
 */
function handleSingleInstance() {
  const gotTheLock = app.requestSingleInstanceLock();

  if (!gotTheLock) {
    logger.warn('Another instance is already running, quitting');
    app.quit();
  } else {
    app.on('second-instance', (event, commandLine, workingDirectory) => {
      logger.info('Second instance detected, focusing main window');
      
      // Someone tried to run a second instance, focus our window instead
      if (mainWindow) {
        if (mainWindow.isMinimized()) {
          mainWindow.restore();
        }
        mainWindow.focus();
      }
    });
  }
}

/**
 * Setup auto-updater
 */
function setupAutoUpdater() {
  if (isDev) {
    logger.info('Auto-updater disabled in development mode');
    return;
  }

  // Configure auto-updater
  autoUpdater.checkForUpdatesAndNotify();
  
  autoUpdater.on('checking-for-update', () => {
    logger.info('Checking for updates...');
  });
  
  autoUpdater.on('update-available', (info) => {
    logger.info('Update available:', info.version);
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'Update Available',
      message: `A new version (${info.version}) is available. It will be downloaded in the background.`,
      buttons: ['OK']
    });
  });
  
  autoUpdater.on('update-not-available', (info) => {
    logger.info('Update not available:', info.version);
  });
  
  autoUpdater.on('error', (err) => {
    logger.error('Auto-updater error:', err);
  });
  
  autoUpdater.on('download-progress', (progressObj) => {
    let log_message = "Download speed: " + progressObj.bytesPerSecond;
    log_message = log_message + ' - Downloaded ' + progressObj.percent + '%';
    log_message = log_message + ' (' + progressObj.transferred + "/" + progressObj.total + ')';
    logger.info(log_message);
  });
  
  autoUpdater.on('update-downloaded', (info) => {
    logger.info('Update downloaded:', info.version);
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'Update Ready',
      message: 'Update downloaded. The application will restart to apply the update.',
      buttons: ['Restart Now', 'Later']
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });
}

/**
 * Main application initialization
 */
function main() {
  logger.info(`Starting ${APP_INFO.NAME} v${APP_INFO.VERSION}`);
  logger.info(`Platform: ${Platform.getCurrentPlatform()} ${Platform.getArchitecture()}`);
  logger.info(`Electron: v${process.versions.electron}, Node: v${process.versions.node}`);
  
  // Handle single instance
  handleSingleInstance();
  
  // Setup application events
  setupApplicationEvents();
  
  // Security: Disable web security in development only
  if (isDev) {
    app.commandLine.appendSwitch('disable-web-security');
    app.commandLine.appendSwitch('disable-features', 'OutOfBlinkCors');
  }
  
  logger.info('Application initialization completed');
}

// Start the application
if (require.main === module) {
  main();
}

module.exports = { main, createMainWindow, setupIpcHandlers };

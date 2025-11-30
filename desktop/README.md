# Password Manager Desktop Application

A secure desktop application built with Electron for managing passwords and sensitive data.

## Features

- Cross-platform desktop application (Windows, macOS, Linux)
- Secure storage using OS-level encryption (Windows DPAPI, macOS Keychain, Linux Secret Service)
- Integration with the main Password Manager backend
- Offline vault access with sync capabilities
- Hardware security module support where available

## Requirements

- Node.js 16 or higher
- npm or yarn
- Platform-specific requirements:
  - **Windows**: Windows 10 or later (for Windows Hello/DPAPI support)
  - **macOS**: macOS 10.14 or later (for Keychain integration)
  - **Linux**: Secret Service daemon (usually provided by GNOME Keyring or KDE Wallet)

## Installation

1. **Install dependencies:**
   ```bash
   cd desktop
   npm install
   ```

2. **Install platform-specific dependencies:**
   ```bash
   # For Windows DPAPI support
   npm install node-dpapi

   # For additional Electron utilities
   npm install electron-store
   ```

## Development

1. **Start the development server:**
   ```bash
   npm run dev
   ```

2. **Build the application:**
   ```bash
   # Build for current platform
   npm run build

   # Build for specific platforms
   npm run build:win    # Windows
   npm run build:mac    # macOS
   npm run build:linux  # Linux
   ```

## Project Structure

```
desktop/
├── package.json              # Dependencies and build configuration
├── src/
│   ├── main/                 # Main process files
│   │   ├── main.js          # Application entry point
│   │   ├── preload.js       # Preload script for renderer security
│   │   └── windowsSecureStorage.js  # Platform-specific secure storage
│   ├── renderer/            # Renderer process files
│   │   └── index.html       # Main application HTML
│   └── shared/              # Shared utilities and configurations
├── assets/                  # Application assets (icons, etc.)
└── dist/                   # Built application files
```

## Configuration

The application can be configured through:

1. **Environment variables:**
   ```bash
   # API endpoint for backend communication
   REACT_APP_API_URL=http://127.0.0.1:8000/api

   # Enable debug mode
   DEBUG=true
   ```

2. **Application settings** (stored in user data directory):
   - Auto-lock timeout
   - Sync preferences
   - UI preferences

## Security Features

### Secure Storage
- **Windows**: Uses Windows Data Protection API (DPAPI) with Windows Hello integration
- **macOS**: Integrates with macOS Keychain for secure key storage
- **Linux**: Uses Secret Service API (compatible with GNOME Keyring, KDE Wallet)

### Application Security
- Context isolation enabled for renderer processes
- Node.js integration disabled in renderer for security
- Content Security Policy (CSP) headers
- Secure communication with backend API

### Data Protection
- Master password never stored locally
- Encryption keys derived using PBKDF2 with high iteration counts
- Secure memory management for sensitive data
- Auto-lock functionality with configurable timeout

## API Integration

The desktop application communicates with the Django backend through:

- RESTful API endpoints for vault operations
- JWT token authentication
- Real-time sync capabilities
- Offline mode with local caching

## Platform-Specific Features

### Windows
- Windows Hello integration for biometric authentication
- DPAPI encryption for local key storage
- Windows notifications for security alerts

### macOS
- Touch ID/Face ID integration
- Keychain integration for secure storage
- Native macOS notifications

### Linux
- Secret Service integration
- Desktop environment notifications
- AppImage/Snap/Flatpak packaging support

## Building for Production

1. **Configure signing certificates** (for code signing):
   ```bash
   # Set environment variables for code signing
   export CSC_LINK=path/to/certificate.p12
   export CSC_KEY_PASSWORD=certificate_password
   ```

2. **Build and package:**
   ```bash
   npm run build
   npm run dist
   ```

## Troubleshooting

### Common Issues

1. **Secure storage not working:**
   - Ensure platform-specific dependencies are installed
   - Check OS-level security settings
   - Verify user permissions

2. **Backend connection issues:**
   - Check API endpoint configuration
   - Verify network connectivity
   - Ensure backend server is running

3. **Build failures:**
   - Clear node_modules and reinstall: `rm -rf node_modules && npm install`
   - Check Node.js version compatibility
   - Verify platform-specific build tools are installed

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Windows
set DEBUG=* && npm start

# macOS/Linux
DEBUG=* npm start
```

## Contributing

1. Follow the existing code structure and patterns
2. Test on all target platforms before submitting
3. Update documentation for any new features
4. Ensure security best practices are followed

## License

This project is part of the Password Manager application suite.

# Firebase Setup Guide

## Current Issue
The Firebase error occurs because the environment variables for Firebase configuration are not set.

## Quick Fix (For Development)
The app will now run with demo Firebase configuration and show warnings in the console instead of crashing. Real-time sync will not work, but the rest of the app will function normally.

## To Enable Real Firebase Functionality

### 1. Create Firebase Project
1. Go to https://firebase.google.com/
2. Click "Get started" and create a new project
3. Choose a project name (e.g., "password-manager-app")
4. Enable/disable Google Analytics as preferred

### 2. Enable Realtime Database
1. In your Firebase console, go to "Realtime Database"
2. Click "Create Database"
3. Start in test mode (you can change rules later)
4. Choose your preferred location

### 3. Get Configuration
1. Go to Project Settings (gear icon)
2. In the "General" tab, scroll to "Your apps"
3. Click "Add app" and choose "Web"
4. Register your app with a nickname
5. Copy the config object

### 4. Create Environment File
Create a file named `.env.local` in the `frontend` directory with:

```env
VITE_FIREBASE_API_KEY=your-api-key-here
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com/
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abcdef123456
```

Replace the values with your actual Firebase configuration.

### 5. Restart Development Server
After creating the `.env.local` file, restart your Vite development server:
```bash
npm run dev
```

## Security Notes
- Never commit `.env` files to version control
- The `.env` file is already in `.gitignore`
- Use Firebase security rules to protect your data in production
- Consider using different Firebase projects for development and production

## Troubleshooting
If you still see Firebase errors after setup:
1. Verify all environment variables are correctly set
2. Check that the Firebase project is active
3. Ensure Realtime Database is enabled
4. Check browser console for specific error messages

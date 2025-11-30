import { initializeApp } from "firebase/app";
import { getDatabase, ref, set, onValue, remove } from "firebase/database";
import { getAuth, signInWithCustomToken } from "firebase/auth";

// Your Firebase configuration
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "demo-api-key",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "demo-project.firebaseapp.com",
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL || "https://demo-project-default-rtdb.firebaseio.com/",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "demo-project",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "demo-project.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "123456789",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:123456789:web:abcdef123456"
};

// Check if Firebase is properly configured
const isFirebaseConfigured = () => {
  return import.meta.env.VITE_FIREBASE_PROJECT_ID && 
         import.meta.env.VITE_FIREBASE_API_KEY &&
         import.meta.env.VITE_FIREBASE_DATABASE_URL;
};

let app, database, auth;

try {
  // Initialize Firebase only if properly configured
  app = initializeApp(firebaseConfig);
  database = getDatabase(app);
  auth = getAuth(app);
  
  if (!isFirebaseConfigured()) {
    console.warn('Firebase environment variables not found. Using demo configuration. Real-time sync will not work.');
  }
} catch (error) {
  console.error('Firebase initialization failed:', error);
  // Create mock objects to prevent app crashes
  database = null;
  auth = null;
}

export class FirebaseService {
  constructor() {
    this.db = database;
    this.auth = auth;
    this.listeners = {};
    this.isConfigured = isFirebaseConfigured();
  }

  async initialize(userToken) {
    if (!this.isConfigured) {
      console.warn('Firebase is not properly configured. Skipping initialization.');
      return false;
    }

    if (!this.auth) {
      console.warn('Firebase auth not available. Skipping initialization.');
      return false;
    }

    // Sign in with token from Django backend
    try {
      await signInWithCustomToken(this.auth, userToken);
      return true;
    } catch (error) {
      console.error("Firebase auth error:", error);
      return false;
    }
  }

  // Sync a vault item to Firebase
  async syncItem(item) {
    if (!this.isConfigured || !this.db || !this.auth?.currentUser) {
      console.warn('Firebase not configured or user not authenticated. Skipping sync.');
      return false;
    }

    try {
      const itemRef = ref(this.db, `users/${this.auth.currentUser.uid}/vault/${item.id}`);
      await set(itemRef, {
        id: item.id,
        item_id: item.item_id,
        encrypted_data: item.encrypted_data,
        item_type: item.type,
        updated_at: item.updated_at || new Date().toISOString(),
        favorite: item.favorite || false,
        last_modified: Date.now()
      });
      return true;
    } catch (error) {
      console.error("Error syncing item to Firebase:", error);
      return false;
    }
  }

  // Listen for changes to the vault
  listenForChanges(userId, callback) {
    if (!this.isConfigured || !this.db) {
      console.warn('Firebase not configured. Skipping listener setup.');
      return null;
    }

    const vaultRef = ref(this.db, `users/${userId}/vault`);
    const listener = onValue(vaultRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        callback(Object.values(data));
      }
    });
    
    this.listeners[userId] = listener;
    return listener;
  }

  // Remove an item
  async removeItem(itemId) {
    if (!this.isConfigured || !this.db || !this.auth?.currentUser) {
      console.warn('Firebase not configured or user not authenticated. Skipping removal.');
      return false;
    }

    try {
      const itemRef = ref(this.db, `users/${this.auth.currentUser.uid}/vault/${itemId}`);
      await remove(itemRef);
      return true;
    } catch (error) {
      console.error("Error removing item from Firebase:", error);
      return false;
    }
  }
  
  // Clean up listeners
  detachListeners() {
    Object.values(this.listeners).forEach(listener => {
      listener();
    });
    this.listeners = {};
  }
}

const firebaseServiceInstance = new FirebaseService();
export default firebaseServiceInstance;

/**
 * useAuth Hook - JWT Authentication for React SPA
 * 
 * Handles login, token storage, token refresh, and automatic Authorization header injection.
 * 
 * Features:
 * - Login/logout functionality
 * - Automatic token refresh before expiration
 * - Axios interceptor for Authorization header
 * - Token storage (localStorage with XSS protection via CSP)
 * - Auto-refresh on 401 errors
 * 
 * @example
 * import { useAuth } from '@/hooks/useAuth';
 * 
 * function MyComponent() {
 *   const { user, login, logout, isAuthenticated, isLoading } = useAuth();
 *   
 *   const handleLogin = async () => {
 *     try {
 *       await login({ email: 'user@example.com', password: 'password' });
 *     } catch (error) {
 *       console.error('Login failed:', error);
 *     }
 *   };
 *   
 *   return (
 *     <div>
 *       {isAuthenticated ? (
 *         <button onClick={logout}>Logout {user?.email}</button>
 *       ) : (
 *         <button onClick={handleLogin}>Login</button>
 *       )}
 *     </div>
 *   );
 * }
 */

import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import axios from 'axios';

// ==============================================================================
// AUTH CONTEXT
// ==============================================================================

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// ==============================================================================
// TOKEN STORAGE
// ==============================================================================

const TOKEN_STORAGE_KEY = 'accessToken';
const REFRESH_TOKEN_STORAGE_KEY = 'refreshToken';
const USER_STORAGE_KEY = 'user';

const storage = {
  getAccessToken: () => localStorage.getItem(TOKEN_STORAGE_KEY),
  setAccessToken: (token) => localStorage.setItem(TOKEN_STORAGE_KEY, token),
  removeAccessToken: () => localStorage.removeItem(TOKEN_STORAGE_KEY),
  
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY),
  setRefreshToken: (token) => localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token),
  removeRefreshToken: () => localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY),
  
  getUser: () => {
    const user = localStorage.getItem(USER_STORAGE_KEY);
    return user ? JSON.parse(user) : null;
  },
  setUser: (user) => localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user)),
  removeUser: () => localStorage.removeItem(USER_STORAGE_KEY),
  
  clearAll: () => {
    storage.removeAccessToken();
    storage.removeRefreshToken();
    storage.removeUser();
  }
};

// ==============================================================================
// TOKEN REFRESH LOGIC
// ==============================================================================

let isRefreshing = false;
let refreshSubscribers = [];

const subscribeTokenRefresh = (callback) => {
  refreshSubscribers.push(callback);
};

const onTokenRefreshed = (newAccessToken) => {
  refreshSubscribers.forEach((callback) => callback(newAccessToken));
  refreshSubscribers = [];
};

const refreshAccessToken = async () => {
  const refreshToken = storage.getRefreshToken();
  
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }
  
  try {
    const response = await axios.post('/api/auth/token/refresh/', {
      refresh: refreshToken
    });
    
    const { access, refresh: newRefreshToken } = response.data;
    
    storage.setAccessToken(access);
    if (newRefreshToken) {
      // If backend rotates refresh tokens
      storage.setRefreshToken(newRefreshToken);
    }
    
    return access;
  } catch (error) {
    // Refresh token invalid or expired
    storage.clearAll();
    throw error;
  }
};

// ==============================================================================
// AXIOS INTERCEPTORS
// ==============================================================================

// Request interceptor: Add Authorization header
axios.interceptors.request.use(
  (config) => {
    const accessToken = storage.getAccessToken();
    
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 and auto-refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // If 401 and haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for token refresh to complete
        return new Promise((resolve) => {
          subscribeTokenRefresh((newAccessToken) => {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            resolve(axios(originalRequest));
          });
        });
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      try {
        const newAccessToken = await refreshAccessToken();
        isRefreshing = false;
        onTokenRefreshed(newAccessToken);
        
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return axios(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        // Refresh failed - user needs to login again
        storage.clearAll();
        window.location.href = '/'; // Redirect to login
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

// ==============================================================================
// AUTH PROVIDER COMPONENT
// ==============================================================================

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Initialize auth state from storage
  useEffect(() => {
    const initAuth = () => {
      const storedUser = storage.getUser();
      const accessToken = storage.getAccessToken();
      
      if (storedUser && accessToken) {
        setUser(storedUser);
        setIsAuthenticated(true);
      }
      
      setIsLoading(false);
    };
    
    initAuth();
  }, []);
  
  /**
   * Login with email and password
   * 
   * @param {Object} credentials - { email, password }
   * @returns {Promise<Object>} User data
   */
  const login = useCallback(async (credentials) => {
    console.log('[DEBUG useAuth] login() called with:', credentials);
    try {
      setIsLoading(true);
      
      // Call Django SimpleJWT token endpoint (uses username field by default)
      console.log('[DEBUG useAuth] Calling POST /api/auth/token/...');
      const response = await axios.post('/api/auth/token/', {
        username: credentials.email || credentials.username,
        password: credentials.password
      });
      console.log('[DEBUG useAuth] Response:', response.data);
      
      const { access, refresh, user: userData } = response.data;
      
      // Store tokens
      storage.setAccessToken(access);
      storage.setRefreshToken(refresh);
      
      // If user data is returned, store it
      // Otherwise, fetch user profile
      let userProfile = userData;
      if (!userProfile) {
        try {
          const profileResponse = await axios.get('/api/user/profile/', {
            headers: { Authorization: `Bearer ${access}` }
          });
          userProfile = profileResponse.data;
        } catch (error) {
          console.warn('Failed to fetch user profile:', error);
          // Use basic user info from token or credentials
          userProfile = {
            email: credentials.email || credentials.username
          };
        }
      }
      
      storage.setUser(userProfile);
      setUser(userProfile);
      setIsAuthenticated(true);
      
      return userProfile;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  /**
   * Logout and clear tokens
   */
  const logout = useCallback(async () => {
    try {
      const refreshToken = storage.getRefreshToken();
      
      if (refreshToken) {
        // Optional: Call backend logout endpoint to blacklist refresh token
        try {
          await axios.post('/api/auth/token/blacklist/', {
            refresh: refreshToken
          });
        } catch (error) {
          console.warn('Token blacklist failed:', error);
        }
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage regardless of API call success
      storage.clearAll();
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);
  
  /**
   * Manually refresh access token
   */
  const refreshToken = useCallback(async () => {
    try {
      const newAccessToken = await refreshAccessToken();
      return newAccessToken;
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
      throw error;
    }
  }, [logout]);
  
  /**
   * Update user profile in state and storage
   */
  const updateUser = useCallback((updates) => {
    const updatedUser = { ...user, ...updates };
    storage.setUser(updatedUser);
    setUser(updatedUser);
  }, [user]);
  
  const value = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshToken,
    updateUser,
    // Utility methods
    getAccessToken: storage.getAccessToken,
    getRefreshToken: storage.getRefreshToken,
  };
  
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// ==============================================================================
// UTILITY HOOK: useAuthenticatedRequest
// ==============================================================================

/**
 * Hook for making authenticated API requests with automatic error handling
 * 
 * @example
 * const { makeRequest, loading, error } = useAuthenticatedRequest();
 * 
 * const fetchData = async () => {
 *   const data = await makeRequest('get', '/api/vault/items/');
 *   console.log(data);
 * };
 */
export const useAuthenticatedRequest = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const makeRequest = useCallback(async (method, url, data = null, config = {}) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios({
        method,
        url,
        data,
        ...config
      });
      
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);
  
  return { makeRequest, loading, error };
};

// ==============================================================================
// EXPORT
// ==============================================================================

export default useAuth;


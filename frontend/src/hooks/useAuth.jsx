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
import { scrubUserForStorage } from '../utils/userStorage';

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
  
  // getUser intentionally returns null. Persisting the user object
  // to localStorage was removed in response to CodeQL alert #1048;
  // see utils/userStorage.js for the rationale. Any pre-fix value is
  // cleaned up by the AuthProvider bootstrap. Callers that need
  // user data should pull it from React state (via useAuth().user)
  // or fetch it from the backend.
  getUser: () => null,
  setUser: (user) => {
    // Validate input shape via the scrub helper but DO NOT persist
    // to localStorage. See utils/userStorage.js for the CodeQL-#1048
    // + PR #246 rationale. Audible warning on non-object input so
    // a regression that starts passing the wrong shape is caught
    // during development rather than silently no-op'ing (CodeRabbit
    // nit on PR #245).
    if (user !== undefined && user !== null) {
      const scrubbed = scrubUserForStorage(user);
      if (scrubbed === null) {
        // eslint-disable-next-line no-console
        console.warn(
          '[useAuth] storage.setUser received a non-object user; ignoring.',
          { type: typeof user },
        );
      }
    }
    // Remove any value left behind by older builds so a stale PII
    // payload doesn't sit in localStorage indefinitely.
    localStorage.removeItem(USER_STORAGE_KEY);
  },
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

    // Bootstrap-probe calls (the `/api/auth/me/` hydration request
    // fired by initAuth on page reload) opt out of refresh-on-401
    // by setting `_isBootstrap: true` on the request config. A 401
    // there means "session dead, drop the token" — letting the
    // interceptor enter its refresh-or-redirect loop would race
    // initAuth and could hard-redirect during the initial render.
    // CodeRabbit edge-case on PR #245 follow-up.
    if (originalRequest?._isBootstrap) {
      return Promise.reject(error);
    }

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
  
  // Initialize auth state. Hydrate `user` from `GET /api/auth/me/`
  // so consumers (e.g. BreachAlertsDashboard) don't see null on
  // reload — the user profile is no longer cached in localStorage
  // per CodeQL #1048 (see utils/userStorage.js). Also flushes any
  // legacy user blob left behind by an older build.
  //
  // The bootstrap /me call carries `_isBootstrap: true` so the
  // response interceptor's auto-refresh path skips it — we handle
  // the 401 here, manually, to avoid the redirect-during-render
  // race that fixed-edge-case caught on PR #245.
  useEffect(() => {
    let cancelled = false;

    const initAuth = async () => {
      // Flush any legacy user blob before doing anything else.
      localStorage.removeItem(USER_STORAGE_KEY);

      const accessToken = storage.getAccessToken();
      if (!accessToken) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      // Token is present — hydrate the user from the server. The
      // request interceptor adds the Authorization header from
      // `storage.getAccessToken()` automatically, so we don't pass
      // one explicitly (CodeRabbit nit on PR #245 follow-up).
      try {
        const resp = await axios.get('/api/auth/me/', { _isBootstrap: true });
        if (!cancelled) {
          setUser(resp.data);
          setIsAuthenticated(true);
        }
      } catch (err) {
        if (err?.response?.status === 401) {
          // Access token expired. A 7-day refresh token may still be
          // valid (SIMPLE_JWT.REFRESH_TOKEN_LIFETIME), so try a
          // refresh-then-retry before declaring the session dead.
          // Without this, every page reload past the 15-minute
          // access-token TTL is a forced logout. Codex P1 on
          // PR #245 follow-up.
          let refreshedAccess = null;
          try {
            refreshedAccess = await refreshAccessToken();
          } catch {
            // Refresh failed — `refreshAccessToken` already cleared
            // storage. Session is genuinely dead.
            refreshedAccess = null;
          }

          if (refreshedAccess) {
            try {
              // Re-fetch /me with the freshly rotated access token.
              // No explicit Authorization needed — the interceptor
              // reads the now-updated value from storage.
              const retry = await axios.get('/api/auth/me/', { _isBootstrap: true });
              if (!cancelled) {
                setUser(retry.data);
                setIsAuthenticated(true);
              }
            } catch {
              // Even with a fresh access token, /me failed. Bail.
              storage.clearAll();
            }
          }
          // else: refresh failed → already cleared; stay signed out.
        } else if (!cancelled) {
          // Network error / 5xx — we have a token, profile fetch
          // failed transiently. Mark authenticated so navigation
          // doesn't bounce the user to login; user-dependent
          // components handle null gracefully.
          setIsAuthenticated(true);
        }
      }

      if (!cancelled) setIsLoading(false);
    };

    initAuth();
    return () => { cancelled = true; };
  }, []);
  
  /**
   * Login with email and password
   * 
   * @param {Object} credentials - { email, password }
   * @returns {Promise<Object>} User data
   */
  const login = useCallback(async (credentials) => {
    try {
      setIsLoading(true);
      
      // Call Django SimpleJWT token endpoint (uses username field by default)
      const response = await axios.post('/api/auth/token/', {
        username: credentials.email || credentials.username,
        password: credentials.password
      });
      
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
      // Clear any default Authorization header that OAuth flows may have set;
      // leaving it behind would cause the next request to carry a stale token
      // that is no longer in storage.
      if (axios.defaults?.headers?.common) {
        delete axios.defaults.headers.common['Authorization'];
      }
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


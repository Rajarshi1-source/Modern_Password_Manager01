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
import {
  loginWithCookie,
  refreshAccessTokenViaCookie,
  logoutWithCookie,
} from '../services/cookieAuthService';
import {
  getAccessToken as getInMemoryAccessToken,
  clearAccessToken,
} from '../services/tokenStore';

// Opt-in feature flag for the HttpOnly-cookie refresh-token flow.
// When true, the SPA:
//   * never writes the refresh token to localStorage (it lives in an
//     HttpOnly cookie issued by /api/auth/cookie/token/),
//   * keeps the short-lived access token in a module-scope closure
//     in `services/tokenStore.js` (never persisted),
//   * refreshes via /api/auth/cookie/token/refresh/ (cookie-only).
// When false (default), the legacy localStorage flow runs untouched
// so existing logged-in users keep their session. Roll this out by
// setting VITE_USE_COOKIE_AUTH=true in the environment.
const USE_COOKIE_AUTH =
  (import.meta?.env?.VITE_USE_COOKIE_AUTH || '').toString().toLowerCase() === 'true';

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
  // Cookie-flow path: the refresh token is in an HttpOnly cookie the
  // browser sends automatically; the SPA never sees the refresh token.
  // The cookieAuthService writes the new access token into tokenStore
  // (module-scope memory), so we just return it for the interceptor's
  // retry logic. Returns null if the cookie is missing/expired — the
  // caller's catch path handles that as "user must log in again".
  if (USE_COOKIE_AUTH) {
    const access = await refreshAccessTokenViaCookie();
    if (!access) {
      throw new Error('Refresh cookie missing or expired');
    }
    return access;
  }

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

// Request interceptor: Add Authorization header.
// In cookie-flow mode the access token lives in the tokenStore
// closure (services/tokenStore.js) and is never persisted to
// localStorage. The legacy path keeps reading from localStorage so
// existing logged-in users transition without a forced re-login.
axios.interceptors.request.use(
  (config) => {
    const accessToken = USE_COOKIE_AUTH
      ? getInMemoryAccessToken()
      : storage.getAccessToken();

    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// URLs of the refresh endpoints themselves. The interceptor must NEVER
// try to refresh-on-401 against these — doing so creates a recursive
// loop: the refresh call 401s (cookie missing/expired) → interceptor
// fires refresh-on-401 → calls refresh again → 401 again → meanwhile
// `isRefreshing` is already true so the second attempt subscribes
// to `onTokenRefreshed` and waits forever for a notification that
// will never come, hanging every queued request. Codex P1 on PR #246
// caught this.
const _REFRESH_URLS = new Set([
  '/api/auth/cookie/token/refresh/',
  '/api/auth/token/refresh/',
]);

function _isRefreshUrl(config) {
  if (!config || !config.url) return false;
  // Compare on the path portion only — axios may give us a relative
  // path or a full URL depending on baseURL configuration.
  try {
    const path = config.url.startsWith('http')
      ? new URL(config.url).pathname
      : config.url;
    return _REFRESH_URLS.has(path);
  } catch {
    return _REFRESH_URLS.has(config.url);
  }
}

// Response interceptor: Handle 401 and auto-refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Never refresh-on-401 the refresh endpoint itself. A 401 from a
    // refresh call means "your refresh credential is invalid" — the
    // user must log in again. Bouncing it back through the same
    // interceptor would deadlock.
    if (_isRefreshUrl(originalRequest)) {
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
        // Refresh failed → drop local auth state and redirect to
        // login. In cookie mode we deliberately DO NOT call
        // logoutWithCookie() here: the refresh failure may be the
        // losing-tab side of a benign two-tab rotation race (this
        // tab's cookie value was blacklisted because the other tab
        // already rotated). The backend's refresh endpoint preserves
        // the cookie in that case (see `is_rotation_race` branch in
        // cookie_auth_view.py), and if we then fire a logout we'd
        // delete the WINNING tab's freshly rotated cookie — exactly
        // the regression the backend fix was meant to prevent.
        //
        // Instead: drop only the in-memory access token. The cookie
        // either (a) was just rotated by another tab and stays valid,
        // or (b) is genuinely dead and will be cleaned up on its
        // own max-age or by an explicit user-initiated logout. The
        // /login redirect is unchanged — the user sees the login
        // page either way; if (a) they can refresh and continue,
        // if (b) they re-authenticate. Codex P2 on PR #246 follow-up.
        if (USE_COOKIE_AUTH) {
          clearAccessToken();
        } else {
          storage.clearAll();
        }
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
  
  // Initialize auth state from storage.
  //
  // Cookie flow:
  //   1. Ask backend to mint an access token from the HttpOnly
  //      refresh cookie. If that succeeds, fetch the real user
  //      profile from /api/auth/me/ so consumers
  //      (VaultUnlockModal, ReputationDashboard, etc.) that read
  //      user.id/user.email don't break. Setting a placeholder
  //      {authenticated: true} was a Codex P2 finding — those
  //      consumers explicitly need real identity fields.
  //   2. If the cookie refresh fails (no cookie / cookie expired),
  //      FALL THROUGH to the legacy localStorage path. Users who
  //      were signed in via the legacy flow BEFORE
  //      VITE_USE_COOKIE_AUTH was flipped on still have valid
  //      access/refresh tokens in localStorage; treating them as
  //      logged out the moment the flag deploys would force-
  //      logout an entire user base. Codex P2 finding #2.
  //
  // Legacy flow: read user + access token from localStorage as
  // before, so existing sessions survive.
  useEffect(() => {
    let cancelled = false;

    const initAuth = async () => {
      let triedCookieFlow = false;

      if (USE_COOKIE_AUTH) {
        triedCookieFlow = true;
        try {
          const access = await refreshAccessTokenViaCookie();
          if (cancelled) return;
          if (access) {
            // Have a fresh access token — fetch the real user
            // profile so user.id / user.email are populated.
            // _isBootstrap so the response interceptor doesn't
            // try its own refresh-then-retry on a 401 from /me/.
            try {
              const resp = await axios.get('/api/auth/me/', {
                _isBootstrap: true,
              });
              if (!cancelled) {
                setUser(resp.data);
                setIsAuthenticated(true);
              }
            } catch {
              // /me failed but the access token is valid. Mark
              // authenticated; consumers handle null user
              // gracefully. (Network blip / 5xx case.)
              if (!cancelled) setIsAuthenticated(true);
            }
            if (!cancelled) setIsLoading(false);
            return;
          }
          // access === null: cookie missing/expired. Fall through
          // to the legacy localStorage path below.
        } catch {
          // Network error during cookie refresh. Fall through to
          // the legacy path so a transient outage doesn't
          // unconditionally bounce active migration users.
        }
      }

      // Legacy localStorage path. Reached when:
      //   * USE_COOKIE_AUTH is false (default), OR
      //   * USE_COOKIE_AUTH is true but the cookie refresh
      //     returned null / threw, AND the user might still have
      //     a valid legacy session from before the flag deploy.
      const storedUser = storage.getUser();
      const accessToken = storage.getAccessToken();

      if (storedUser && accessToken) {
        setUser(storedUser);
        setIsAuthenticated(true);
      } else if (triedCookieFlow) {
        // Neither cookie nor legacy storage has anything for us.
        // User is unauthenticated; let the login screen render.
      }

      setIsLoading(false);
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

      // Cookie flow: backend issues an HttpOnly refresh cookie and
      // returns the short-lived access token in the JSON body. The
      // access token is written to tokenStore (in-memory) by
      // loginWithCookie itself; we never persist it.
      if (USE_COOKIE_AUTH) {
        // Wipe any legacy localStorage tokens BEFORE the cookie
        // login. If the user previously authenticated via the
        // localStorage flow (pre-flag, or in another build), the
        // access/refresh tokens are still sitting in localStorage —
        // readable by any XSS payload until they expire (up to 7
        // days for the refresh token). Codex P2 on PR #246 follow-up
        // caught this: a successful hardened cookie login was
        // leaving the old long-lived refresh token in storage,
        // undermining the entire migration.
        try {
          storage.clearAll();
        } catch { /* never let cleanup throw */ }

        const { user: userData } = await loginWithCookie({
          username: credentials.email || credentials.username,
          password: credentials.password,
        });
        let userProfile = userData;
        if (!userProfile) {
          try {
            const profileResponse = await axios.get('/api/user/profile/');
            userProfile = profileResponse.data;
          } catch {
            userProfile = { email: credentials.email || credentials.username };
          }
        }
        // Profile is held in React state only — not persisted to
        // localStorage so the value can't be exfiltrated by XSS.
        setUser(userProfile);
        setIsAuthenticated(true);
        return userProfile;
      }

      // Legacy localStorage flow — unchanged so existing sessions
      // and clients that haven't flipped the feature flag keep
      // working exactly as before.
      const response = await axios.post('/api/auth/token/', {
        username: credentials.email || credentials.username,
        password: credentials.password
      });

      const { access, refresh, user: userData } = response.data;

      storage.setAccessToken(access);
      storage.setRefreshToken(refresh);

      let userProfile = userData;
      if (!userProfile) {
        try {
          const profileResponse = await axios.get('/api/user/profile/', {
            headers: { Authorization: `Bearer ${access}` }
          });
          userProfile = profileResponse.data;
        } catch (error) {
          console.warn('Failed to fetch user profile:', error);
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
      if (USE_COOKIE_AUTH) {
        // logoutWithCookie hits /api/auth/cookie/token/logout/ which
        // blacklists the refresh token (when the SimpleJWT blacklist
        // app is installed) and clears the HttpOnly cookie. It also
        // clears the in-memory access token via tokenStore.
        await logoutWithCookie();
      } else {
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
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Local cleanup runs regardless of API call success.
      if (!USE_COOKIE_AUTH) {
        storage.clearAll();
      }
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
   * Update user profile in state and (legacy mode) storage.
   *
   * In cookie mode the profile is held in React state only — see PR
   * #246 + the CodeQL #1048 rationale. Persisting it would re-introduce
   * the XSS-exfil hole the cookie flow is meant to close. CodeRabbit
   * outside-diff finding on PR #246.
   */
  const updateUser = useCallback((updates) => {
    const updatedUser = { ...user, ...updates };
    if (!USE_COOKIE_AUTH) {
      storage.setUser(updatedUser);
    }
    setUser(updatedUser);
  }, [user]);

  // Token-accessor that components like DuressCodeManager,
  // DuressEventLog, ReputationDashboard et al. call as
  // `useAuth().getAccessToken()` and pass into fetch services. Under
  // cookie auth the token lives in `tokenStore` (module-scope memory),
  // NOT in localStorage — if we kept exposing `storage.getAccessToken`
  // here, those components would build `Authorization: Bearer null`
  // immediately after a cookie login. Codex P2 on PR #246.
  const getAccessToken = USE_COOKIE_AUTH
    ? getInMemoryAccessToken
    : storage.getAccessToken;

  const value = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshToken,
    updateUser,
    // Utility methods
    getAccessToken,
    // In cookie mode the refresh token lives in an HttpOnly cookie
    // that JS cannot read. Expose a no-op getter so callers that
    // still ask for it don't read a stale localStorage value.
    getRefreshToken: USE_COOKIE_AUTH ? () => null : storage.getRefreshToken,
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


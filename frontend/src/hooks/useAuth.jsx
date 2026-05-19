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

// User profile lives in React state only — never persisted to
// localStorage. Resolves CodeQL alerts #1048/#1049/#1050 by
// eliminating the storage flow CodeQL was tracking. Rehydration on
// page load happens via GET /api/auth/me/ in initAuth(). The only
// 'user' key references that remain are removeItem() cleanups for
// users upgrading from pre-fix builds.
const LEGACY_USER_KEY = 'user';

const storage = {
  getAccessToken: () => localStorage.getItem(TOKEN_STORAGE_KEY),
  setAccessToken: (token) => localStorage.setItem(TOKEN_STORAGE_KEY, token),
  removeAccessToken: () => localStorage.removeItem(TOKEN_STORAGE_KEY),

  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY),
  setRefreshToken: (token) => localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token),
  removeRefreshToken: () => localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY),

  clearAll: () => {
    storage.removeAccessToken();
    storage.removeRefreshToken();
    // Defensive cleanup of any legacy user blob left by older builds.
    localStorage.removeItem(LEGACY_USER_KEY);
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
  // browser sends automatically; the SPA never sees the refresh
  // token. cookieAuthService writes the new access token into
  // tokenStore (module-scope memory) and returns it for the
  // interceptor's retry logic.
  //
  // FALLBACK to legacy refresh when the cookie path can't proceed.
  // This is the migration bridge for users whose session predates
  // the flag flip — they have a valid localStorage refresh token
  // but no HttpOnly cookie yet. Codex P2 #1 on PR #246 follow-up
  // caught that the original "cookie-only in cookie mode" wiring
  // would force-logout these users on the next 401. The fallback
  // window closes naturally once the refresh token rotates into
  // the cookie flow (which it can't here directly; the user has
  // to log in once via the cookie path) — but for the lifetime
  // of an existing legacy session it keeps refresh working.
  if (USE_COOKIE_AUTH) {
    try {
      const access = await refreshAccessTokenViaCookie();
      if (access) return access;
      // access === null: cookie missing / refresh returned no token.
      // Fall through to the legacy refresh below if available.
    } catch {
      /* fall through to legacy */
    }
    // No cookie path succeeded. The legacy refresh-token may still
    // be in localStorage from a pre-flag session — try it.
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
// In cookie-flow mode the access token lives in tokenStore (memory)
// and is never persisted to localStorage. The legacy path reads
// from localStorage.
//
// Migration window: when the cookie flag is on but the user is on
// the legacy-fallback path (no cookie, but valid pre-flag localStorage
// tokens), the in-memory tokenStore is empty so we fall through to
// localStorage. Codex P2 #1 on PR #246 follow-up caught that without
// this fallback, every API call from a fallback session went out
// without an Authorization header and 401'd.
axios.interceptors.request.use(
  (config) => {
    const accessToken = USE_COOKIE_AUTH
      ? (getInMemoryAccessToken() || storage.getAccessToken())
      : storage.getAccessToken();

    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// URLs that mint refresh credentials. The response interceptor must
// NEVER try to refresh-on-401 against these — doing so creates the
// recursive deadlock Codex P1 caught on PR #245 follow-up:
//
//   1. initAuth calls refreshAccessToken() because /me/ 401'd.
//   2. refreshAccessToken() POSTs to /api/auth/token/refresh/.
//   3. The refresh token is ALSO expired → 401.
//   4. Interceptor catches that 401. Sets isRefreshing = true.
//      Calls refreshAccessToken() recursively.
//   5. The recursive call POSTs to /api/auth/token/refresh/ → 401.
//   6. Interceptor catches THAT 401. isRefreshing is true so it
//      subscribes via subscribeTokenRefresh and waits forever for
//      a notification that will never come.
//
// Result: initAuth's await on refreshAccessToken() never resolves;
// setIsLoading(false) is never called; app stuck on loading screen.
// Both legacy and cookie refresh URLs are listed so the guard is
// symmetric across the dual-flow migration.
const _REFRESH_URLS = new Set([
  '/api/auth/token/refresh/',
  '/api/auth/cookie/token/refresh/',
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

    // Never refresh-on-401 the refresh endpoint itself — that's the
    // recursive deadlock Codex P1 caught on PR #245 follow-up. A 401
    // here means "your refresh credential is invalid"; the caller
    // must handle the rejection (initAuth / login flow), not bounce
    // back into another refresh attempt.
    if (_isRefreshUrl(originalRequest)) {
      return Promise.reject(error);
    }

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
  
  // Initialize auth state on mount. Two-tier flow:
  //
  // 1. Cookie mode (VITE_USE_COOKIE_AUTH=true):
  //    a. Ask backend to mint an access token from the HttpOnly
  //       refresh cookie. If that succeeds, fetch the real user
  //       profile from /api/auth/me/ so consumers (VaultUnlockModal,
  //       ReputationDashboard, …) that read user.id/user.email don't
  //       break. Setting a placeholder {authenticated: true} was a
  //       Codex P2 finding on PR #246.
  //    b. If the cookie refresh fails (no cookie / cookie expired),
  //       FALL THROUGH to the legacy localStorage path below. Users
  //       who were signed in via the legacy flow BEFORE
  //       VITE_USE_COOKIE_AUTH was flipped on still have valid
  //       access/refresh tokens in localStorage; treating them as
  //       logged out on the flag-deploy is the wrong default.
  //       Codex P2 finding #2 on PR #246.
  //
  // 2. Legacy / fallback path: hydrate from GET /api/auth/me/ using
  //    the localStorage access token. On 401, try refresh-then-retry
  //    (PR #245 Codex P1) so a still-valid 7-day refresh token isn't
  //    thrown away every 15 minutes. Also flushes any legacy USER
  //    blob (PII payload from older builds — CodeQL #1048).
  //
  // The bootstrap /me calls carry `_isBootstrap: true` so the
  // response interceptor's auto-refresh path skips them — we handle
  // their 401s manually here to avoid the redirect-during-render
  // race that landed on PR #245.
  useEffect(() => {
    let cancelled = false;

    // Inner helper so both the cookie-mode and legacy-path branches
    // can share the same /me-fetch logic without duplicating it.
    // Returns true on success, false on failure (caller decides what
    // to do with state).
    const hydrateUserFromMe = async () => {
      try {
        const resp = await axios.get('/api/auth/me/', { _isBootstrap: true });
        if (!cancelled) {
          setUser(resp.data);
          setIsAuthenticated(true);
        }
        return { ok: true, status: 200 };
      } catch (err) {
        return { ok: false, status: err?.response?.status ?? 0 };
      }
    };

    const initAuth = async () => {
      // Flush any legacy user blob a pre-fix build may have left
      // behind. The current code never writes it; this is purely a
      // cleanup for upgrading users.
      localStorage.removeItem(LEGACY_USER_KEY);

      // ─── Cookie path ──────────────────────────────────────────
      if (USE_COOKIE_AUTH) {
        try {
          const access = await refreshAccessTokenViaCookie();
          if (cancelled) return;
          if (access) {
            const meRes = await hydrateUserFromMe();
            if (cancelled) return;
            if (!meRes.ok) {
              // /me failed even though we just minted a fresh access
              // token. Likely a transient 5xx; the access token is
              // valid so mark authenticated and let consumers handle
              // null user gracefully. A 401 here is unexpected but
              // mirror the legacy-path behavior: stay signed out.
              if (meRes.status !== 401) setIsAuthenticated(true);
            }
            setIsLoading(false);
            return;
          }
          // access === null: cookie missing / cookie expired. Fall
          // through to the legacy path so a pre-flag session with
          // localStorage tokens isn't force-logged-out on flag flip.
        } catch {
          // Network error during cookie refresh. Same fall-through.
        }
      }

      // ─── Legacy / fallback path ──────────────────────────────
      const accessToken = storage.getAccessToken();
      if (!accessToken) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      // Try /me with the legacy access token (interceptor attaches
      // the Authorization header from storage.getAccessToken()
      // automatically).
      const first = await hydrateUserFromMe();
      if (cancelled) return;
      if (first.ok) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      if (first.status === 401) {
        // Access token expired. A 7-day refresh token may still be
        // valid (SIMPLE_JWT.REFRESH_TOKEN_LIFETIME), so try a
        // refresh-then-retry before declaring the session dead.
        // Codex P1 on PR #245 follow-up.
        let refreshedAccess = null;
        try {
          refreshedAccess = await refreshAccessToken();
        } catch {
          // Refresh failed — `refreshAccessToken` already cleared
          // storage. Session is genuinely dead.
          refreshedAccess = null;
        }

        if (refreshedAccess) {
          const retry = await hydrateUserFromMe();
          if (cancelled) return;
          if (!retry.ok && !cancelled) {
            // Even with a fresh access token, /me failed. Bail.
            // Guarded on !cancelled for stylistic consistency.
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

      // Profile is held in React state only — never persisted.
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
      //
      // ALWAYS clear localStorage — including in cookie mode. A user
      // who authenticated via the legacy-fallback path during the
      // migration window has accessToken/refreshToken/user sitting
      // in localStorage; if we skip clearAll() in cookie mode the
      // next reload's bootstrap fall-through path picks them up and
      // silently logs them back in. Codex P2 #2 on PR #246
      // follow-up caught this — logout must be the same idempotent
      // "wipe ALL credential surfaces" in both modes.
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
   * Update user profile in state and (legacy mode) storage.
   *
   * In cookie mode the profile is held in React state only — see PR
   * #246 + the CodeQL #1048 rationale. Persisting it would re-introduce
   * the XSS-exfil hole the cookie flow is meant to close. CodeRabbit
   * outside-diff finding on PR #246.
   */
  const updateUser = useCallback((updates) => {
    const updatedUser = { ...user, ...updates };
    // Profile lives in React state only on both cookie and legacy
    // flows. Never persist to localStorage.
    setUser(updatedUser);
  }, [user]);

  // Token-accessor that components like DuressCodeManager,
  // DuressEventLog, ReputationDashboard et al. call as
  // `useAuth().getAccessToken()` and pass into fetch services that
  // build `Authorization: Bearer ${authToken}`.
  //
  // Cookie mode is layered: the in-memory tokenStore is the
  // canonical source after a pure-cookie login, but legacy-fallback
  // sessions (cookie flag on, no cookie, valid pre-flag localStorage
  // tokens) keep the token in localStorage. The exposed getter
  // mirrors the request-interceptor's `getInMemoryAccessToken() ||
  // storage.getAccessToken()` pattern so the two reads never disagree
  // — without this fallback, fetch-service callers in legacy-fallback
  // sessions would build `Bearer null` even though the axios
  // interceptor sends the right header. Codex P2 on PR #246 follow-up.
  const getAccessToken = USE_COOKIE_AUTH
    ? () => getInMemoryAccessToken() || storage.getAccessToken()
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


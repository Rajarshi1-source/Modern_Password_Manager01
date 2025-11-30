import React, { useState, useEffect, memo, useMemo, Suspense, lazy, useCallback } from 'react';
import axios from 'axios';
import './App.css';
import { AccessibilityProvider } from './contexts/AccessibilityContext';
import { BehavioralProvider } from './contexts/BehavioralContext';
import { createGlobalStyle } from 'styled-components';
import { Routes, Route, Navigate, Link, useNavigate, useLocation } from 'react-router-dom';
import { FaExclamationCircle, FaLock, FaRegEye, FaRegEyeSlash, FaUnlock } from 'react-icons/fa';
import Modal from './Modal.jsx';
import ParticleBackground from './Components/animations/ParticleBackground';
import SocialLoginButtons from './Components/auth/SocialLoginButtons';
import LoadingIndicator from './Components/common/LoadingIndicator';
import ErrorBoundary from './Components/common/ErrorBoundary';
import ApiService from './services/api';
import toast from 'react-hot-toast';
import oauthService from './services/oauthService';
import PasswordStrengthMeterML from './Components/security/PasswordStrengthMeterML';
import SessionMonitor from './Components/security/SessionMonitor';
import { errorTracker } from './services/errorTracker';
import analyticsService from './services/analyticsService';
import abTestingService from './services/abTestingService';
import preferencesService from './services/preferencesService';
import { useAuth } from './hooks/useAuth.jsx'; // JWT Authentication Hook

// Lazy load heavy components
const RecoveryKeySetupPage = lazy(() => import('./Components/auth/RecoveryKeySetup'));
const PasskeyManagement = lazy(() => import('./Components/auth/PasskeyManagement'));
const AccountProtection = lazy(() => import('./Components/security/AccountProtection'));
const SecurityDashboard = lazy(() => import('./Components/security/components/SecurityDashboard'));
const SocialMediaLogin = lazy(() => import('./Components/auth/SocialMediaLogin'));
const VerifyIdentity = lazy(() => import('./Components/security/components/VerifyIdentity'));
const OAuthCallback = lazy(() => import('./Components/auth/OAuthCallback'));
const PerformanceMonitoring = lazy(() => import('./Components/admin/PerformanceMonitoring'));
const PasswordRecoveryPage = lazy(() => import('./Components/auth/PasswordRecovery'));
const BreachAlertsDashboard = lazy(() => import('./Components/security/components/BreachAlertsDashboard'));
const SettingsPage = lazy(() => import('./Components/settings/SettingsPage'));
const EmailMaskingDashboard = lazy(() => import('./Components/emailmasking/EmailMaskingDashboard'));
const SharedFoldersDashboard = lazy(() => import('./Components/sharedfolders/SharedFoldersDashboard'));
const RecoveryDashboard = lazy(() => import('./Components/admin/RecoveryDashboard'));
// Primary Passkey Recovery components
const PasskeyPrimaryRecoverySetup = lazy(() => import('./Components/auth/PasskeyPrimaryRecoverySetup'));
const PasskeyPrimaryRecoveryInitiate = lazy(() => import('./Components/auth/PasskeyPrimaryRecoveryInitiate'));
// Quantum (Social Mesh) Recovery component
const QuantumRecoverySetup = lazy(() => import('./Components/auth/QuantumRecoverySetup'));

// Add global styles for accessibility
const GlobalStyle = createGlobalStyle`
  /* Focus styles */
  *:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
  
  /* Screen reader only class */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
  }
  
  /* Improved contrast for text */
  body {
    color: ${props => props.theme.textPrimary};
    line-height: 1.5;
  }
  
  /* Skip to content link */
  .skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: ${props => props.theme.primary};
    color: white;
    padding: 8px;
    z-index: 100;
    transition: top 0.2s;
  }
  
  .skip-link:focus {
    top: 0;
  }
`;

// Login form component (memoized to prevent unnecessary re-renders)
const LoginForm = memo(({ onLogin, onForgotPassword, toggleAuthMode, error }) => {
  // Use controlled inputs to preserve values when password visibility toggles
  const [loginData, setLoginData] = useState({
    email: '',
    password: '',
    rememberMe: false
  });
  
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [emailError, setEmailError] = useState('');

  // Check if email is valid (must be a Gmail address)
  const isValidEmail = useMemo(() => {
    return loginData.email && loginData.email.toLowerCase().endsWith('@gmail.com');
  }, [loginData.email]);

  // Check if password meets minimum requirements
  const isValidPassword = useMemo(() => {
    return loginData.password && loginData.password.length >= 8;
  }, [loginData.password]);

  // Check if form is valid for submission
  const isFormValid = useMemo(() => {
    return isValidEmail && isValidPassword;
  }, [isValidEmail, isValidPassword]);

  // Prevent copy, paste, and cut operations for security
  const preventCopyPaste = (e) => {
    e.preventDefault();
    toast.error('Copy, paste, and cut are disabled for security reasons', { 
      id: 'copy-paste-disabled',
      duration: 2000 
    });
    return false;
  };

  const handleLoginChange = (e) => {
    const { name, value, type, checked } = e.target;
    setLoginData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Clear email error when user types
    if (name === 'email') {
      if (value && !value.toLowerCase().endsWith('@gmail.com')) {
        setEmailError('Please enter a valid Gmail address');
      } else {
        setEmailError('');
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const { email, password, rememberMe } = loginData;
    
    console.log('[DEBUG] Form submitted with:', { email, password: '***', rememberMe });
    
    // Validate
    if (!email.toLowerCase().endsWith('@gmail.com')) {
      setEmailError('Please enter a valid Gmail address');
      return;
    }
    if (!password) {
      console.log('[DEBUG] Password is empty');
      return;
    }
    
    // Submit
    console.log('[DEBUG] Calling onLogin...');
    onLogin({ email, password, rememberMe });
  };

  const handleSocialLogin = async (provider) => {
    try {
      toast.loading(`Connecting to ${provider}...`, { id: 'oauth-loading' });
      
      const result = await oauthService.initiateLogin(provider);
      
      if (result && result.tokens) {
        toast.success('Login successful!', { id: 'oauth-loading' });
        
        // Store tokens
        localStorage.setItem('token', result.tokens.access);
        localStorage.setItem('refreshToken', result.tokens.refresh);
        axios.defaults.headers.common['Authorization'] = `Bearer ${result.tokens.access}`;
        
        // Trigger the login success callback
        onLogin({ tokens: result.tokens, user: result.user });
      }
    } catch (error) {
      console.error(`${provider} login error:`, error);
      toast.error(error.message || `Failed to login with ${provider}`, { id: 'oauth-loading' });
    }
  };

  return (
    <div className="login-form">
      {error && (
        <div className="error-message">
          <FaExclamationCircle /> {error}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="login-email">Email Address</label>
          <input
            type="email"
            id="login-email"
            name="email"
            value={loginData.email}
            onChange={handleLoginChange}
            onCopy={preventCopyPaste}
            onPaste={preventCopyPaste}
            onCut={preventCopyPaste}
            required
            placeholder="name@gmail.com"
          />
          {emailError && (
            <small style={{ color: 'var(--danger)', marginTop: '4px', display: 'block' }}>
              {emailError}
            </small>
          )}
        </div>
        <div className="form-group">
          <label htmlFor="login-password">Master Password</label>
          <div style={{ position: 'relative' }}>
            <input
              type={passwordVisible ? "text" : "password"}
              id="login-password"
              name="password"
              value={loginData.password}
              onChange={handleLoginChange}
              onCopy={preventCopyPaste}
              onPaste={preventCopyPaste}
              onCut={preventCopyPaste}
              required
              placeholder="enter your password"
              autoComplete="current-password"
            />
            <button
              type="button"
              style={{
                position: 'absolute',
                right: '15px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#888'
              }}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setPasswordVisible(prev => !prev);
              }}
            >
              {passwordVisible ? <FaRegEyeSlash /> : <FaRegEye />}
            </button>
          </div>
        </div>
        <div className="form-group checkbox-group">
          <input
            type="checkbox"
            id="login-remember"
            name="rememberMe"
            checked={loginData.rememberMe}
            onChange={handleLoginChange}
          />
          <label htmlFor="login-remember">Keep me logged in for 14 days</label>
        </div>
        <button
          type="submit"
          className="submit-btn"
          disabled={!isFormValid}
          style={{
            opacity: isFormValid ? 1 : 0.5,
            cursor: isFormValid ? 'pointer' : 'not-allowed',
            filter: isFormValid ? 'none' : 'blur(1px)',
            transition: 'all 0.3s ease'
          }}
        >
          Login to Vault
        </button>

        <div className="passkey-section" style={{ marginTop: '16px', padding: '12px', backgroundColor: 'var(--primary-light)', borderRadius: '8px', fontSize: '0.9rem' }}>
          <h4 style={{ margin: '0 0 8px 0', fontSize: '1rem' }}>Passwordless sign-in with passkeys</h4>
          <p style={{ margin: '0 0 8px 0', lineHeight: '1.4' }}>
            Passkeys are webauthn credentials that validate your identity using touch, facial recognition, a device password, or a PIN. They can be used as a password replacement or as a 2FA method.
          </p>
          <p style={{ margin: '0 0 8px 0', lineHeight: '1.4' }}>
            This browser or device is reporting partial passkey support, but you may be able to use a passkey from a nearby device.
          </p>
          <button
            type="button"
            className="text-btn"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', padding: '10px', marginTop: '8px', borderRadius: 'var(--button-border-radius)', border: '1px solid var(--primary)', color: 'var(--primary)', background: 'transparent', fontWeight: '600', cursor: 'pointer' }}
            onClick={() => console.log('Passkey login clicked')}
          >
            Login with a Passkey
          </button>
        </div>

        <button type="button" className="forgot-password-btn" onClick={onForgotPassword}>
          Forgot Your Password?
        </button>
      </form>

      <SocialLoginButtons
        onGoogleLogin={() => handleSocialLogin('google')}
        onAppleLogin={() => handleSocialLogin('apple')}
        onGithubLogin={() => handleSocialLogin('github')}
      />

      <p className="auth-switch">
        Don't have an account? <button onClick={toggleAuthMode} className="text-btn">Sign up now</button>
      </p>
    </div>
  );
});

// Signup form component (memoized to prevent unnecessary re-renders)
const SignupForm = memo(({ onSignup, toggleAuthMode, error }) => {
  const [signupData, setSignupData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    rememberMe: false
  });
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [passwordRequirements, setPasswordRequirements] = useState({
    minLength: false,
    hasUpper: false,
    hasLower: false,
    hasNumber: false,
    hasSpecial: false
  });

  // Prevent copy, paste, and cut operations for security
  const preventCopyPaste = (e) => {
    e.preventDefault();
    toast.error('Copy, paste, and cut are disabled for security reasons', { 
      id: 'copy-paste-disabled',
      duration: 2000 
    });
    return false;
  };

  // Check if email is valid (must be a Gmail address)
  const isValidEmail = useMemo(() => {
    return signupData.email.toLowerCase().endsWith('@gmail.com');
  }, [signupData.email]);

  // Check if all password requirements are met
  const isPasswordStrong = useMemo(() => {
    return Object.values(passwordRequirements).every(req => req === true);
  }, [passwordRequirements]);

  // Check if passwords match and form is valid
  const isFormValid = useMemo(() => {
    return (
      isValidEmail &&
      isPasswordStrong &&
      signupData.confirmPassword &&
      signupData.password === signupData.confirmPassword
    );
  }, [signupData, isPasswordStrong, isValidEmail]);

  const handleSignupChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSignupData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));

    // Show email error message if not a Gmail address
    if (name === 'email' && value && !value.toLowerCase().endsWith('@gmail.com')) {
      setEmailError('Please enter a valid Gmail address');
    } else if (name === 'email') {
      setEmailError('');
    }

    // Update password requirements when password changes
    if (name === 'password') {
      setPasswordRequirements({
        minLength: value.length >= 12,
        hasUpper: /[A-Z]/.test(value),
        hasLower: /[a-z]/.test(value),
        hasNumber: /[0-9]/.test(value),
        hasSpecial: /[^A-Za-z0-9]/.test(value)
      });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isFormValid) {
      onSignup(signupData);
    }
  };

  const handleSocialLogin = async (provider) => {
    try {
      toast.loading(`Connecting to ${provider}...`, { id: 'oauth-loading' });
      
      const result = await oauthService.initiateLogin(provider);
      
      if (result && result.tokens) {
        toast.success('Signup successful!', { id: 'oauth-loading' });
        
        // Store tokens
        localStorage.setItem('token', result.tokens.access);
        localStorage.setItem('refreshToken', result.tokens.refresh);
        axios.defaults.headers.common['Authorization'] = `Bearer ${result.tokens.access}`;
        
        // Trigger the signup success callback
        onSignup({ tokens: result.tokens, user: result.user });
      }
    } catch (error) {
      console.error(`${provider} signup error:`, error);
      toast.error(error.message || `Failed to sign up with ${provider}`, { id: 'oauth-loading' });
    }
  };

  return (
    <div className="signup-form">
      {error && (
        <div className="error-message">
          <FaExclamationCircle /> {error}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="signup-email">Email Address</label>
          <input
            type="email"
            id="signup-email"
            name="email"
            value={signupData.email}
            onChange={handleSignupChange}
            onCopy={preventCopyPaste}
            onPaste={preventCopyPaste}
            onCut={preventCopyPaste}
            required
            placeholder="name@gmail.com"
          />
          {emailError && (
            <small style={{ color: 'var(--danger)', marginTop: '4px', display: 'block' }}>
              {emailError}
            </small>
          )}
        </div>
        <div className="form-group">
          <label htmlFor="signup-password">Master Password</label>

          {/* ML-Powered Password Strength Indicator */}
          <PasswordStrengthMeterML password={signupData.password} />

          <div style={{ position: 'relative' }}>
            <input
              type={passwordVisible ? "text" : "password"}
              id="signup-password"
              name="password"
              value={signupData.password}
              onChange={handleSignupChange}
              onCopy={preventCopyPaste}
              onPaste={preventCopyPaste}
              onCut={preventCopyPaste}
              required
              placeholder="enter your password"
              autoComplete="new-password"
            />
            <button
              type="button"
              style={{
                position: 'absolute',
                right: '15px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#888'
              }}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setPasswordVisible(prev => !prev);
              }}
            >
              {passwordVisible ? <FaRegEyeSlash /> : <FaRegEye />}
            </button>
          </div>

          {/* Password requirements list */}
          <div style={{ marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <div style={{ color: passwordRequirements.minLength ? 'var(--success)' : 'var(--text-secondary)' }}>
              ✓ At least 12 characters
            </div>
            <div style={{ color: passwordRequirements.hasUpper ? 'var(--success)' : 'var(--text-secondary)' }}>
              ✓ At least one uppercase letter
            </div>
            <div style={{ color: passwordRequirements.hasLower ? 'var(--success)' : 'var(--text-secondary)' }}>
              ✓ At least one lowercase letter
            </div>
            <div style={{ color: passwordRequirements.hasNumber ? 'var(--success)' : 'var(--text-secondary)' }}>
              ✓ At least one number
            </div>
            <div style={{ color: passwordRequirements.hasSpecial ? 'var(--success)' : 'var(--text-secondary)' }}>
              ✓ At least one special character
            </div>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="signup-confirm-password">Confirm Master Password</label>
          <input
            type="password"
            id="signup-confirm-password"
            name="confirmPassword"
            value={signupData.confirmPassword}
            onChange={handleSignupChange}
            onCopy={preventCopyPaste}
            onPaste={preventCopyPaste}
            onCut={preventCopyPaste}
            required
            placeholder="••••••••••••••••"
          />
          {signupData.confirmPassword && signupData.password !== signupData.confirmPassword && (
            <small style={{ color: 'var(--danger)', marginTop: '4px', display: 'block' }}>
              Passwords don't match
            </small>
          )}
        </div>
        <div className="form-group checkbox-group">
          <input
            type="checkbox"
            id="signup-remember"
            name="rememberMe"
            checked={signupData.rememberMe}
            onChange={handleSignupChange}
          />
          <label htmlFor="signup-remember">Keep me logged in for 14 days</label>
        </div>
        <button
          type="submit"
          className="submit-btn"
          disabled={!isFormValid}
          style={{
            opacity: isFormValid ? 1 : 0.5,
            cursor: isFormValid ? 'pointer' : 'not-allowed',
            filter: isFormValid ? 'none' : 'blur(1px)',
            transition: 'all 0.3s ease'
          }}
        >
          Create Free Account
        </button>
      </form>

      <SocialLoginButtons
        onGoogleLogin={() => handleSocialLogin('google')}
        onAppleLogin={() => handleSocialLogin('apple')}
        onGithubLogin={() => handleSocialLogin('github')}
      />

      <p className="auth-switch">
        Already have an account? <button onClick={toggleAuthMode} className="text-btn">Login</button>
      </p>
    </div>
  );
});

function App() {
  // JWT Authentication Hook
  const { user, isAuthenticated, isLoading: authLoading, login, logout: authLogout } = useAuth();
  
  // State for storing vault items and form data
  const [vaultItems, setVaultItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [appInitialized, setAppInitialized] = useState(false);

  // Login/Signup toggle state
  const [isLoginMode, setIsLoginMode] = useState(true);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    username: '',
    password: '',
    website: '',
    notes: ''
  });

  // Help center modal state
  const [showHelpCenter, setShowHelpCenter] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Handle user login state and initialize services
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Initialize Kyber Service (Post-Quantum Cryptography) - Non-blocking
        // Load in background, don't block app rendering
        import('./services/quantum/kyberService')
          .then(async ({ kyberService }) => {
            await kyberService.initialize();
            const info = kyberService.getAlgorithmInfo();
            console.log(`[Kyber] ${info.status}`);
            
            if (!info.quantumResistant) {
              console.warn('[Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant!');
            }
          })
          .catch(error => {
            console.warn('[Kyber] Failed to initialize Kyber service:', error);
          });

        // Initialize services for authenticated users (in parallel)
        if (isAuthenticated && user) {
          // Run all initializations in parallel for faster load
          const userEmail = user.email || 'anonymous';
          
          await Promise.allSettled([
            // Device fingerprint
            ApiService.initializeDeviceFingerprint().catch(err => {
              console.warn('Failed to initialize device fingerprint:', err);
            }),
            
            // Analytics service
            analyticsService.initialize({
              userId: userEmail,
              email: userEmail
            }).then(() => analyticsService.startSession()).catch(err => {
              console.warn('Failed to initialize analytics:', err);
            }),
            
            // A/B testing service
            abTestingService.initialize({
              userId: user.email || 'anonymous'
            }).catch(err => {
              console.warn('Failed to initialize A/B testing:', err);
            }),
            
            // Preferences service
            preferencesService.initialize().then(() => {
              const theme = preferencesService.get('theme');
              if (theme) {
                applyThemePreferences(theme);
              }
            }).catch(err => {
              console.warn('Failed to initialize preferences:', err);
            })
          ]);
        }
      } catch (error) {
        console.error('Error during app initialization:', error);
      } finally {
        // Mark app as initialized so UI can render
        setAppInitialized(true);
        setLoading(false);
      }
    };

    initializeApp();

    // Cleanup function - end analytics session
    return () => {
      if (isAuthenticated) {
        analyticsService.endSession().catch(console.warn);
      }
    };
  }, [isAuthenticated, user]);

  // Apply theme preferences
  const applyThemePreferences = (theme) => {
    // Apply theme mode
    document.body.classList.remove('light-mode', 'dark-mode');
    if (theme.mode === 'light') {
      document.body.classList.add('light-mode');
    } else if (theme.mode === 'dark') {
      document.body.classList.add('dark-mode');
    } else {
      // Auto mode - use system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.body.classList.add(prefersDark ? 'dark-mode' : 'light-mode');
    }

    // Apply font size
    if (theme.fontSize) {
      document.documentElement.style.fontSize = `${theme.fontSize}px`;
    }

    // Apply animations
    if (theme.animations === false) {
      document.body.classList.add('reduce-motion');
    }
  };

  // Track page views on route changes
  useEffect(() => {
    if (isAuthenticated) {
      analyticsService.trackPageView(location.pathname);
    }
  }, [location, isAuthenticated]);

  // Fetch vault items from API
  useEffect(() => {
    if (isAuthenticated) {
      fetchVaultItems();
    }
  }, [isAuthenticated]);

  // Handle body and html class for particle background visibility
  useEffect(() => {
    const body = document.body;
    const html = document.documentElement;
    if (!isAuthenticated) {
      body.classList.add('auth-page-body');
      html.classList.add('auth-page-body');
    } else {
      body.classList.remove('auth-page-body');
      html.classList.remove('auth-page-body');
    }

    // Cleanup function to remove class when component unmounts
    return () => {
      body.classList.remove('auth-page-body');
      html.classList.remove('auth-page-body');
    };
  }, [isAuthenticated]);

  const fetchVaultItems = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/vault/');
      // Ensure vaultItems is always an array
      const items = response.data?.results || response.data || [];
      setVaultItems(Array.isArray(items) ? items : []);
      setError(null);
    } catch (err) {
      console.error('Error fetching vault items:', err);
      setError('Failed to load your password vault. Please try again.');
      setVaultItems([]); // Reset to empty array on error
    } finally {
      setLoading(false);
    }
  };

  // Handle form input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      // Create encrypted data structure - in a real app, you'd encrypt this client-side
      // This is just a placeholder structure
      const itemData = {
        item_type: 'password',
        item_id: `item_${Date.now()}`, // Generate a unique ID
        encrypted_data: JSON.stringify({
          name: formData.name,
          username: formData.username,
          password: formData.password,
          website: formData.website,
          notes: formData.notes
        }),
        favorite: false
      };

      // Send data to API
      const response = await axios.post('/api/vault/', itemData);

      // Update vault items with new item
      setVaultItems(prev => [...prev, response.data]);

      // Reset form
      setFormData({
        name: '',
        username: '',
        password: '',
        website: '',
        notes: ''
      });

    } catch (err) {
      console.error('Error adding vault item:', err);
      setError('Failed to add new password. Please try again.');
    }
  };

  const handleLogin = useCallback(async (loginData) => {
    console.log('[DEBUG] handleLogin called with:', loginData);
    try {
      // Use JWT authentication from useAuth hook
      console.log('[DEBUG] Calling login() from useAuth hook...');
      await login({
        email: loginData.email,
        password: loginData.password
      });
      console.log('[DEBUG] login() completed successfully');

      // Initialize error tracker user context
      errorTracker.setUserContext({
        email: loginData.email,
        loginTime: new Date().toISOString()
      });

      // Track successful login
      try {
        analyticsService.trackEvent('login_success', 'authentication', {
          rememberMe: loginData.rememberMe || false
        });
      } catch (error) {
        console.warn('Failed to track login:', error);
      }

      // Clear any previous errors
      setError(null);

    } catch (err) {
      console.error('Login failed:', err);
      setError('Invalid email or password. Please try again.');
      
      // Track failed login
      analyticsService.trackEvent('login_failed', 'authentication', {
        error: err.message
      }).catch(console.warn);
    }
  }, [login, setError]);

  const handleSignup = useCallback(async (signupData) => {
    // Check if passwords match
    if (signupData.password !== signupData.confirmPassword) {
      setError('Passwords do not match. Please try again.');
      return;
    }

    try {
      // Note: Signup still uses the old endpoint (/auth/register/)
      // You may need to create a JWT signup endpoint or modify this
      const response = await axios.post('/auth/register/', {
        username: signupData.email,
        email: signupData.email,
        password: signupData.password,
        rememberMe: signupData.rememberMe
      });

      // If backend returns JWT tokens, use them
      if (response.data.access && response.data.refresh) {
        const { access, refresh } = response.data;
        localStorage.setItem('accessToken', access);
        localStorage.setItem('refreshToken', refresh);
        localStorage.setItem('user', JSON.stringify({ email: signupData.email }));
        axios.defaults.headers.common['Authorization'] = `Bearer ${access}`;
      } else {
        // Fallback: old token format, then login with JWT
        await login({
          email: signupData.email,
          password: signupData.password
        });
      }

      // Initialize error tracker user context
      errorTracker.setUserContext({
        email: signupData.email,
        signupTime: new Date().toISOString()
      });

      // Track successful signup
      try {
        analyticsService.trackEvent('signup_success', 'authentication', {
          rememberMe: signupData.rememberMe
        });
        
        // Track conversion
        analyticsService.trackConversion('signup', {
          source: 'organic'
        });
      } catch (error) {
        console.warn('Failed to track signup:', error);
      }

      // Clear any previous errors
      setError(null);

    } catch (err) {
      console.error('Signup failed:', err);
      setError('Failed to create account. Please try again.');
      
      // Track failed signup
      analyticsService.trackEvent('signup_failed', 'authentication', {
        error: err.message
      }).catch(console.warn);
    }
  }, [login, setError]);

  const handleLogout = async () => {
    // Track logout event
    try {
      analyticsService.trackEvent('logout', 'authentication');
      await analyticsService.endSession();
    } catch (error) {
      console.warn('Failed to track logout:', error);
    }

    // Clear device fingerprint on logout
    ApiService.clearDeviceFingerprint();

    // Clear error tracker user context
    errorTracker.clearUserContext();

    // Use JWT logout from useAuth hook
    await authLogout();

    // Clear vault items
    setVaultItems([]);
  };

  const toggleAuthMode = useCallback(() => {
    setIsLoginMode(prev => !prev);
    setError(null); // Clear any existing errors when switching modes
  }, []);

  // Handle forgot password - navigate to recovery page
  const handleForgotPassword = useCallback(() => {
    navigate('/password-recovery');
  }, [navigate]);

  // Memoized auth content - prevents remounting of login/signup forms
  const authContent = useMemo(() => {
    return (
      <div className="auth-container">
        <div className="auth-header">
          <FaLock size={40} color="#7B68EE" />
          <h1>SecureVault</h1>
          <p>Your personal password fortress</p>
        </div>

        <div className="auth-toggle">
          <button
            className={`toggle-btn ${isLoginMode ? 'active' : ''}`}
            onClick={() => setIsLoginMode(true)}
          >
            Login
          </button>
          <button
            className={`toggle-btn ${!isLoginMode ? 'active' : ''}`}
            onClick={() => setIsLoginMode(false)}
          >
            Sign Up
          </button>
          <div className="toggle-slider"></div>
        </div>

        {isLoginMode ? (
          <LoginForm
            onLogin={handleLogin}
            onForgotPassword={handleForgotPassword}
            toggleAuthMode={toggleAuthMode}
            error={error}
          />
        ) : (
          <SignupForm
            onSignup={handleSignup}
            toggleAuthMode={toggleAuthMode}
            error={error}
          />
        )}
      </div>
    );
  }, [isLoginMode, error, handleLogin, handleSignup, handleForgotPassword, toggleAuthMode]);

  // Main App content
  const MainContent = () => {
    // Conditionally set the className for the main App div
    const appClassName = `App ${!isAuthenticated ? 'auth-page' : ''}`;
    if (!isAuthenticated) {
      return (
        <div className={appClassName}> {/* Apply conditional class here */}
          <ParticleBackground />
          <div id="main-content" tabIndex="-1">
            <header className="App-header">
              {/* Background shapes for modern look */}
              <div className="bg-shape bg-shape-1"></div>
              <div className="bg-shape bg-shape-2"></div>

              {authContent}
            </header>
          </div>
          <Modal 
            isOpen={showHelpCenter} 
            onClose={() => setShowHelpCenter(false)}
            title="Help Center"
            size="medium"
          >
            <p>
              If you were redirected to the Help Center after selecting Forgot password,
              you haven't generated an account recovery key. You won't be able to use this
              option to regain access to your account.
            </p>
            <p style={{ marginTop: '16px' }}>
              <Link to="/recovery-key-setup" className="recovery-link" onClick={() => setShowHelpCenter(false)}>
                <FaUnlock /> Set up your recovery key
              </Link>
            </p>
          </Modal>
        </div>
      );
    }

    return (
      <div className={appClassName}> {/* Apply conditional class here as well for consistency */}
        <div id="main-content" tabIndex="-1">
          <nav className="app-nav">
            <h1>SecureVault</h1>
            <div className="nav-links">
              <Link to="/security/dashboard" className="nav-link">Security Dashboard</Link>
              <Link to="/settings" className="nav-link">Settings</Link>
              <button onClick={handleLogout} className="logout-btn">Logout</button>
            </div>
          </nav>

          {/* ML Security Session Monitor */}
          <SessionMonitor userId="authenticated_user" />

          <main className="app-content">
            <section className="add-password-section">
              <h2>Add New Password</h2>
              {error && <div className="error-message">{error}</div>}
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label htmlFor="name">Name</label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="website">Website</label>
                  <input
                    type="url"
                    id="website"
                    name="website"
                    value={formData.website}
                    onChange={handleInputChange}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="username">Username</label>
                  <input
                    type="text"
                    id="username"
                    name="username"
                    value={formData.username}
                    onChange={handleInputChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    type="password"
                    id="password"
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="notes">Notes</label>
                  <textarea
                    id="notes"
                    name="notes"
                    value={formData.notes}
                    onChange={handleInputChange}
                  />
                </div>

                <button type="submit" className="submit-btn">Save Password</button>
              </form>
            </section>

            <section className="password-list">
              <h2>Your Passwords</h2>
              {loading ? (
                <p>Loading your passwords...</p>
              ) : (
                <div className="password-grid">
                  {vaultItems.length === 0 ? (
                    <p>No passwords saved yet. Add one above!</p>
                  ) : (
                    vaultItems.map(item => {
                      // Parse encrypted data - in a real app, you'd decrypt this client-side
                      let itemData = {};
                      try {
                        itemData = JSON.parse(item.encrypted_data);
                      } catch (e) {
                        console.error('Error parsing item data:', e);
                      }

                      return (
                        <div key={item.item_id} className="password-card">
                          <h3>{itemData.name || 'Untitled'}</h3>
                          {itemData.website && (
                            <p className="website">{itemData.website}</p>
                          )}
                          <p className="username">
                            <strong>Username:</strong> {itemData.username}
                          </p>
                          <p className="password">
                            <strong>Password:</strong> •••••••••••
                          </p>
                          <div className="card-actions">
                            <button className="action-btn">View</button>
                            <button className="action-btn">Edit</button>
                            <button className="action-btn delete">Delete</button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </section>
          </main>
        </div>
      </div>
    );
  };

  // Show loading screen while auth is initializing (after all hooks are called)
  if (authLoading && !appInitialized) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        backgroundColor: '#ffffff'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '50px',
            height: '50px',
            border: '4px solid #f3f3f3',
            borderTop: '4px solid #7B68EE',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 20px'
          }} />
          <p style={{ color: '#666', fontSize: '16px' }}>Loading SecureVault...</p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <AccessibilityProvider>
        <BehavioralProvider>
          <GlobalStyle />
          <a href="#main-content" className="skip-link">Skip to main content</a>
          <Suspense fallback={<LoadingIndicator />}>
          <Routes>
          <Route path="/" element={MainContent()} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : MainContent()} />
          <Route path="/signup" element={isAuthenticated ? <Navigate to="/" /> : MainContent()} />
          <Route path="/vault" element={!isAuthenticated ? <Navigate to="/" /> : MainContent()} />
          <Route path="/auth/callback" element={<OAuthCallback />} />
          <Route path="/password-recovery" element={
            isAuthenticated ? <Navigate to="/" /> : <PasswordRecoveryPage />
          } />
          <Route path="/recovery-key-setup" element={
            isAuthenticated ? <Navigate to="/" /> : <RecoveryKeySetupPage />
          } />
          <Route path="/settings/passkeys" element={
            !isAuthenticated ? <Navigate to="/" /> : <PasskeyManagement />
          } />
          <Route path="/security/account-protection" element={
            !isAuthenticated ? <Navigate to="/" /> : <AccountProtection />
          } />
          <Route path="/security/dashboard" element={
            !isAuthenticated ? <Navigate to="/" /> : <SecurityDashboard />
          } />
          <Route path="/auth/social-login/:socialAccountId" element={
            !isAuthenticated ? <Navigate to="/" /> : <SocialMediaLogin />
          } />
          <Route path="/security/verify-identity/:socialAccountId" element={
            !isAuthenticated ? <Navigate to="/" /> : <VerifyIdentity />
          } />
          <Route path="/admin/performance" element={
            !isAuthenticated ? <Navigate to="/" /> : <PerformanceMonitoring />
          } />
          <Route path="/security/breach-alerts" element={
            !isAuthenticated ? <Navigate to="/" /> : <BreachAlertsDashboard />
          } />
          <Route path="/settings" element={
            !isAuthenticated ? <Navigate to="/" /> : <SettingsPage />
          } />
          <Route path="/email-masking" element={
            !isAuthenticated ? <Navigate to="/" /> : <EmailMaskingDashboard />
          } />
          <Route path="/shared-folders" element={
            !isAuthenticated ? <Navigate to="/" /> : <SharedFoldersDashboard />
          } />
          {/* Admin Recovery Dashboard */}
          <Route path="/admin/recovery-dashboard" element={
            !isAuthenticated ? <Navigate to="/" /> : <RecoveryDashboard />
          } />
          {/* Primary Passkey Recovery routes */}
          <Route path="/passkey-recovery/setup" element={
            !isAuthenticated ? <Navigate to="/" /> : <PasskeyPrimaryRecoverySetup />
          } />
          <Route path="/passkey-recovery/recover" element={<PasskeyPrimaryRecoveryInitiate />} />
          {/* Quantum (Social Mesh) Recovery route */}
          <Route path="/recovery/social-mesh" element={<QuantumRecoverySetup />} />
        </Routes>
      </Suspense>
        </BehavioralProvider>
      </AccessibilityProvider>
    </ErrorBoundary>
  );
}

export default App;

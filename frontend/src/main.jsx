import React from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.jsx'
import reportWebVitals from './reportWebVitals'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from 'styled-components'
import { AuthProvider } from './hooks/useAuth.jsx' // JWT Authentication Provider

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }),
    ],
    tracesSampleRate: parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || '0.1'),
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
  })
}

// Default theme for the application
const theme = {
  primary: '#4A6CF7',
  primaryDark: '#3A5CD7',
  primaryLight: '#E0E7FF',
  accent: '#FF9500',
  accentDark: '#E98600',
  accentLight: '#FFE9CC',
  success: '#00C853',
  error: '#FF3B30',
  warning: '#FFCC00',
  danger: '#FF3B30',
  dangerLight: '#FFEBEB',
  textPrimary: '#333333',
  textSecondary: '#666666',
  borderColor: '#E0E0E0',
  cardBg: '#FFFFFF',
  backgroundPrimary: '#F9F9FB',
  backgroundSecondary: '#F0F0F5',
  backgroundHover: '#F5F5F5',
  inputBg: '#FFFFFF',
  bgHover: '#F5F5F5'
}

// Vite handles environment variables differently
if (typeof window !== 'undefined') {
  window.process = window.process || {}
  window.process.env = window.process.env || {}
  window.process.browser = true
}

const root = ReactDOM.createRoot(document.getElementById('root'))
root.render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
)

// Performance monitoring with Web Vitals
const sendToAnalytics = (metric) => {
  // In production, send to your analytics service
  if (import.meta.env.PROD) {
    console.log('Web Vitals metric:', metric)
  } else {
    console.log('Web Vitals metric:', metric)
  }
}

reportWebVitals(sendToAnalytics)

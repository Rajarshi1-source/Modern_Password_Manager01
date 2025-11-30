import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import wasm from 'vite-plugin-wasm'

export default defineConfig({
  plugins: [
    react(),
    wasm()
  ],
  
  // Development server configuration
  server: {
    port: 5173,  // Vite default (change to 3000 if you prefer)
    host: true,
    proxy: {
      // Proxy API calls to Django dev server
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      // Proxy auth endpoints (JWT token endpoints)
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      // Proxy dj-rest-auth endpoints
      '/dj-rest-auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      // Proxy WebSocket connections to Django/Daphne
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        secure: false,
      }
    }
  },
  
  // Build configuration
  build: {
    outDir: 'dist',
    sourcemap: true,
    chunkSizeWarningLimit: 1000, // Increase limit to 1MB
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Separate vendor libraries
          if (id.includes('node_modules')) {
            // Core React libraries
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            
            // Routing
            if (id.includes('react-router')) {
              return 'router';
            }
            
            // UI Libraries
            if (id.includes('styled-components') || id.includes('framer-motion')) {
              return 'ui-vendor';
            }
            
            // Firebase (large dependency)
            if (id.includes('firebase')) {
              return 'firebase';
            }
            
            // Crypto libraries (large)
            if (id.includes('crypto-js') || id.includes('argon2')) {
              return 'crypto';
            }
            
            // Post-Quantum Crypto / Kyber libraries
            if (id.includes('pqc-kyber') || id.includes('crystals-kyber') || 
                id.includes('mlkem') || id.includes('@stablelib')) {
              return 'kyber-crypto';
            }
            
            // Form libraries
            if (id.includes('formik') || id.includes('yup')) {
              return 'forms';
            }
            
            // Icons and particles (can be large)
            if (id.includes('react-icons') || id.includes('@tsparticles')) {
              return 'ui-effects';
            }
            
            // Other vendor libraries
            return 'vendor';
          }
          
          // Separate by feature/route
          if (id.includes('/Components/security/')) {
            return 'security';
          }
          
          if (id.includes('/Components/auth/')) {
            return 'auth';
          }
          
          if (id.includes('/Components/vault/')) {
            return 'vault';
          }
          
          if (id.includes('/services/')) {
            return 'services';
          }
          
          // Kyber-specific modules
          if (id.includes('/utils/kyber-wasm-loader') || 
              id.includes('/utils/kyber-cache')) {
            return 'kyber-core';
          }
          
          if (id.includes('/workers/kyber-worker')) {
            return 'kyber-worker';
          }
          
          if (id.includes('/hooks/useKyber')) {
            return 'kyber-hooks';
          }
          
          // Quantum services
          if (id.includes('/services/quantum/')) {
            return 'quantum-services';
          }
        }
      },
      external: ['argon2-browser', 'tfhe']
    }
  },
  
  // Path resolution
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/Components'),
      '@services': resolve(__dirname, 'src/services'),
      '@contexts': resolve(__dirname, 'src/contexts'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@hooks': resolve(__dirname, 'src/hooks'),
      '@workers': resolve(__dirname, 'src/workers'),
    }
  },
  
  // Environment variables
  define: {
    global: 'globalThis',
  },
  
  // Handle Node.js polyfills and optimize Kyber dependencies
  optimizeDeps: {
    include: ['path-browserify', '@stablelib/random', '@stablelib/x25519', '@stablelib/sha256'],
    exclude: ['argon2-browser', 'mlkem', 'pqc-kyber', 'crystals-kyber-js', 'tfhe']
  },
  
  // Assets configuration for WASM
  assetsInclude: ['**/*.wasm'],
  
  // Worker configuration for WASM
  worker: {
    format: 'es'
  }
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import wasm from 'vite-plugin-wasm'
import topLevelAwait from 'vite-plugin-top-level-await'

export default defineConfig({
  plugins: [
    react({
      jsxRuntime: 'automatic',  // Automatic JSX runtime
      fastRefresh: true,        // Disable Fast Refresh for faster builds in development
    }),
    wasm({
      filter: (id) => !id.includes('argon2.wasm')
    }),
    topLevelAwait()
  ],
  
  // Development server configuration (CRITICAL - keeps your API working)
  server: {
    port: 5173,  // Vite default (change to 3000 if you prefer)
    host: true,
    strictPort: false,
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
  
    // OPTIMIZED: Pre-bundle commonly used dependencies
    optimizeDeps: {
      //Only include packages imported at entry point
      include: [
        'react',
        'react-dom/client',
        'react-router-dom',
        'axios',
        'styled-components',
        'react-hot-toast',
        'react-icons/fa',
        'lucide-react',
        'lodash',
        'framer-motion',
        // ADD: explicitly pre-bundle the problematic packages
        'long',
        '@tensorflow/tfjs-core',
        '@tensorflow/tfjs'         // if you import tfjs-core or tfjs directlyi n your code
      ],
      // Exclude large optional/lazy-loaded packages
      exclude: [
        '@tensorflow/tfjs',
        '@tensorflow/tfjs-backend-webgl',
        '@tensorflow-models/universal-sentence-encoder',
        '@grpc/grpc-js',
        'firebase',
        'argon2-browser',
        'tfhe',
        // Keep Kyber libs excluded (loaded dynamically)
        'mlkem',
        'pqc-kyber', 
        'crystals-kyber-js'
      ],
      // Target ES2020 for compatibility with Kyber WASM
      esbuildOptions: {
        target: 'es2020',
        // make sure esbuild bundles for the browser platform (helps cjs -> esm transform)
        platform: 'browser',
      },
    },

  // Build configuration
  // SIMPLIFIED: let Vite handle chunking automatically
  build: {
    target: 'es2020',
    outDir: 'dist',
    sourcemap: false, //Disable sourcemaps for faster builds
    chunkSizeWarningLimit: 1500, // Increase limit to 1MB
    rollupOptions: {
      external: ['fs', 'path', 'crypto'],
      output: {
        // Simpler chunking strategy
        manualChunks(id) {
          // Core vendors
          if (id.includes('node_modules')) {
            // Core React libraries
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            // Firebase (large dependency)
            if (id.includes('firebase')) {
              return 'firebase';
            }
            // Everything else goes to vendor
            return 'vendor';
        }
      }
    }
  },

  // ADD: make sure mixed ESM/CJS packages are properly transformed
  commonjsOptions: {
    transformMixedEsModules: true,
    include: [/node_modules/, /node_modules\/@tensorflow\/.*/],
  },
  // Reduce minification time (optional - use it builds are slow)
  minify: 'esbuild', // Faster than terser
  //Disable CSS code splitting for faster builds
  cssCodeSplit: false,
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
      'argon2-browser': resolve(__dirname, 'node_modules/argon2-browser/dist/argon2-bundled.min.js'),
    },
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
  },
  
  // Environment variables
  define: {
    global: 'globalThis',
  },
  
  // Assets configuration for WASM
  // WASM support (CRITICAL for Kyber crypto)
  assetsInclude: ['**/*.wasm'],
  
  // Worker configuration for WASM (CRITICAL for Kyber worker)
  worker: {
    format: 'es'
  },

  // Cache configuration for faster rebuilds
  cacheDir: process.env.VITE_CACHE_DIR || 'node_modules/.vite',

  // Clear screen for cleaner output
  clearScreen: true,
})

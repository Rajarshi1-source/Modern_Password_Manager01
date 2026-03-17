import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import wasm from 'vite-plugin-wasm'
import topLevelAwait from 'vite-plugin-top-level-await'

export default defineConfig({
  plugins: [
    react({
      jsxRuntime: 'automatic',
      fastRefresh: true,
    }),
    wasm(),
    topLevelAwait()
  ],

  // Development server configuration
  server: {
    port: 5173,
    host: true,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/dj-rest-auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        secure: false,
      }
    }
  },

  // Pre-bundle commonly used dependencies
  optimizeDeps: {
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
      'long',
      '@tensorflow/tfjs-core',
      '@tensorflow/tfjs',
      'pqc-kyber',
      'crystals-kyber-js',
      'mlkem',
      'argon2-browser',
    ],
    exclude: [
      '@tensorflow/tfjs',
      '@tensorflow/tfjs-backend-webgl',
      '@tensorflow-models/universal-sentence-encoder',
      '@grpc/grpc-js',
      'firebase',
      'tfhe'
    ],
    esbuildOptions: {
      target: 'es2020',
      platform: 'browser',
    },
  },

  // Build configuration — minify and cssCodeSplit MUST live inside build
  build: {
    target: 'es2020',
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    minify: 'esbuild',
    cssCodeSplit: false,
    rollupOptions: {
      external: ['fs', 'path', 'crypto'],
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;

          // Firebase — large, lazy-loaded
          if (id.includes('/firebase/') || id.includes('/@firebase/')) {
            return 'firebase';
          }

          // TensorFlow.js — very large, lazy-loaded in app
          if (id.includes('/@tensorflow/') || /\/tfjs[/-]/.test(id)) {
            return 'tensorflow';
          }

          // Post-quantum crypto — WASM-heavy
          if (
            id.includes('/pqc-kyber/') ||
            id.includes('/crystals-kyber-js/') ||
            id.includes('/mlkem/')
          ) {
            return 'pqc-crypto';
          }

          // Crypto primitives
          if (
            id.includes('/argon2-browser/') ||
            id.includes('/@noble/') ||
            id.includes('/@stablelib/')
          ) {
            return 'crypto-primitives';
          }

          // Three.js and WebGL
          if (
            id.includes('/three/') ||
            id.includes('/@react-three/') ||
            id.includes('/three-mesh-bvh/')
          ) {
            return 'three-vendor';
          }

          // Charts
          if (id.includes('/chart.js/') || id.includes('/react-chartjs-2/')) {
            return 'charts-vendor';
          }

          // Animation
          if (id.includes('/framer-motion/')) {
            return 'animation-vendor';
          }

          // FIX for circular dep: react-router-dom depends on react, so it MUST
          // be in react-vendor, not vendor. Previously react-router-dom fell into
          // vendor, which then imported react-vendor → circular warning.
          if (
            id.includes('/node_modules/react/') ||
            id.includes('/node_modules/react-dom/') ||
            id.includes('/node_modules/scheduler/') ||
            id.includes('/node_modules/react-router') ||   // react-router + react-router-dom
            id.includes('/node_modules/@remix-run/')        // react-router-dom's internals
          ) {
            return 'react-vendor';
          }

          // Remaining node_modules
          return 'vendor';
        },
      },
    },
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
      'argon2-browser': 'argon2-browser/dist/argon2-bundled.min.js',
    },
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
  },

  // Environment variables
  define: {
    global: 'globalThis',
  },

  // WASM asset support
  assetsInclude: ['**/*.wasm'],

  // Worker format for WASM workers
  worker: {
    format: 'es'
  },

  // Cache dir for faster rebuilds
  cacheDir: process.env.VITE_CACHE_DIR || 'node_modules/.vite',

  clearScreen: true,
})

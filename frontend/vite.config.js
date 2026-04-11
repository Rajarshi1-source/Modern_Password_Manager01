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

  // Development server + proxy to Django
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
      },
    },
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
      'crystals-kyber-js',
      'mlkem',
    ],
    exclude: [
      // WASM-heavy packages: let Vite serve them as native ESM so .wasm
      // files are fetched separately rather than inlined by esbuild (which
      // cannot handle WASM imports during dep pre-bundling).
      'pqc-kyber',
      'argon2-browser',
      '@tensorflow/tfjs',
      '@tensorflow/tfjs-backend-webgl',
      '@tensorflow-models/universal-sentence-encoder',
      '@grpc/grpc-js',
      'firebase',
      'tfhe',
    ],
    esbuildOptions: {
      target: 'es2020',
      platform: 'browser',
    },
  },

  // ─── Build ───────────────────────────────────────────────────────────────
  build: {
    target: 'es2020',
    outDir: 'dist',
    // 'hidden' generates source maps without adding the //# sourceMappingURL
    // comment to the bundles — users never see (or download) the maps, but
    // they can be uploaded to Sentry / error-tracking for readable stack traces.
    sourcemap: 'hidden',
    chunkSizeWarningLimit: 1500,

    // these two options MUST live inside `build`, not at the root level
    minify: 'esbuild',
    cssCodeSplit: false,

    // commonjsOptions is a `build`-level option in Vite (passed to
    // @rollup/plugin-commonjs). Placing it at the root level was silently ignored.
    commonjsOptions: {
      transformMixedEsModules: true,
      include: [/node_modules/, /node_modules\/@tensorflow\/.*/],
    },

    rollupOptions: {
      // FIX: suppress the 15 "@__PURE__ annotation" warnings that come from
      // commented-out code inside crystals-kyber-js and mlkem node_modules.
      // Rollup cannot interpret @__PURE__ inside a comment; it removes them and
      // warns. Since these are third-party files we cannot change, we silence the
      // warning for node_modules only.
      onwarn(warning, warn) {
        if (
          warning.code === 'INVALID_ANNOTATION' &&
          warning.id?.includes('node_modules')
        ) {
          return; // suppress – the comment is removed automatically, no runtime impact
        }
        warn(warning); // keep all other warnings
      },

      external: ['fs', 'path', 'crypto'],

      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;

          // Firebase ─ 229 KB gzip, isolated for cache efficiency
          if (id.includes('/firebase/') || id.includes('/@firebase/')) {
            return 'firebase';
          }

          // TensorFlow.js ─ very large, lazy-loaded in the app
          if (id.includes('/@tensorflow/') || /\/tfjs[/-]/.test(id)) {
            return 'tensorflow';
          }

          // Post-quantum crypto ─ WASM-heavy
          if (
            id.includes('/pqc-kyber/') ||
            id.includes('/crystals-kyber-js/') ||
            id.includes('/mlkem/')
          ) {
            return 'pqc-crypto';
          }

          // Crypto primitives ─ argon2, noble curves, stablelib
          if (
            id.includes('/argon2-browser/') ||
            id.includes('/@noble/') ||
            id.includes('/@stablelib/')
          ) {
            return 'crypto-primitives';
          }

          // Chart libraries
          if (id.includes('/chart.js/') || id.includes('/react-chartjs-2/')) {
            return 'charts-vendor';
          }

          // Animation library
          if (id.includes('/framer-motion/')) {
            return 'animation-vendor';
          }

          // FIX for react-vendor circular dep: react-router-dom and @remix-run
          // depend on React, so they MUST be grouped with React here.
          // Previously react-router-dom fell into `vendor`, which imported
          // react-vendor, creating: vendor → react-vendor → vendor.
          if (
            id.includes('/node_modules/react/') ||
            id.includes('/node_modules/react-dom/') ||
            id.includes('/node_modules/scheduler/') ||
            id.includes('/node_modules/react-router') ||  // react-router + react-router-dom
            id.includes('/node_modules/@remix-run/')       // react-router-dom internals
          ) {
            return 'react-vendor';
          }

          // NOTE: three-vendor has been intentionally removed.
          //
          // The previous config had:
          //   three-vendor -> vendor -> three-vendor   (circular chunk warning)
          //
          // This happened because @react-three/drei and @react-three/fiber depend
          // on packages (draco3d, meshopt_decoder, maath, camera-controls, etc.)
          // that landed in `vendor`, and those packages in turn imported Three.js
          // internals, completing the cycle.
          //
          // The fix is to merge Three.js into `vendor`. Yes, `vendor` grows from
          // ~795 KB to ~1.55 MB (ungzip), but it gzips to ~467 KB, the circular
          // warning is eliminated, and chunking is simpler.
          //
          // If you later want to re-separate Three.js, you must also add ALL of
          // its transitive dependencies to the same chunk (draco3d, meshopt_decoder,
          // maath, camera-controls, @monogrid/gainmap-js, suspend-react, troika-*,
          // potpack, etc.) to avoid reintroducing the cycle.

          // Everything else from node_modules
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
      // Fix for argon2-browser WASM issue in some bundler modes
      'argon2-browser': 'argon2-browser/dist/argon2-bundled.min.js',
    },
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
  },

  // Expose `globalThis` as `global` for CJS shims
  define: {
    global: 'globalThis',
  },

  // Include WASM files as static assets
  assetsInclude: ['**/*.wasm'],

  // Workers must emit ES modules for WASM workers (kyberService web worker)
  worker: {
    format: 'es',
  },

  // Persistent cache for faster rebuilds
  cacheDir: process.env.VITE_CACHE_DIR || 'node_modules/.vite',

  clearScreen: true,
})

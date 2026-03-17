/**
 * Quantum Cryptography Service Index
 * ====================================
 *
 * FIX: kyberService is intentionally NOT re-exported from this index file.
 *
 * Why: App.jsx lazy-loads kyberService with a dynamic import so it does not
 * block the initial render:
 *
 *   import('./services/quantum/kyberService').then(({ kyberService }) => {
 *     kyberService.initialize();
 *   });
 *
 * When this index file statically re-exported kyberService, Rollup bundled it
 * into the main chunk regardless of the dynamic import, and emitted this
 * build warning:
 *
 *   kyberService.js is dynamically imported by App.jsx but also statically
 *   imported by src/services/quantum/index.js, dynamic import will not move
 *   module into another chunk.
 *
 * Removing the static re-export restores true lazy loading.
 * Any file that needs kyberService at runtime should import it directly:
 *
 *   // Lazy (preferred — does not block initial bundle)
 *   const { kyberService } = await import('./quantum/kyberService');
 *
 *   // Eager (only use in files that already run after the initial render)
 *   import { kyberService } from './quantum/kyberService';
 */

// Export the error class and constants — these are small and type-safe to
// include statically (no WASM, no heavy crypto initialisation on import).
export { KyberError, KYBER_CONSTANTS } from './kyberService';

// KyberService class is exported for consumers who want to instantiate their
// own instance (e.g. tests). The singleton `kyberService` is NOT exported
// here — use a dynamic import or direct file import instead.
export { KyberService } from './kyberService';

// @ts-check
/**
 * FHE Share — sealed autofill canary (Playwright).
 *
 * Loads the browser-extension build in a persistent Chromium context
 * and verifies:
 *   1. The content-script installs the sealed-fill listener.
 *   2. A `fhe_share:autofill_request_v2` postMessage on the dashboard
 *      page receives an ack from the extension (even if the background
 *      worker answers "no_identity").
 *
 * The full end-to-end "password lands in form input" path requires
 * real Umbral keys and a logged-in dashboard, which is out of scope
 * for a CI canary. The extra steps are documented in
 * `password_manager/fhe_sharing/SPEC.md`.
 *
 * Opt-in: set ``PLAYWRIGHT_EXTENSION_PATH`` to the ``dist/`` folder
 * produced by ``npm run build`` in ``browser-extension``.
 */

import { test, expect, chromium } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const extensionPath = process.env.PLAYWRIGHT_EXTENSION_PATH
  || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../browser-extension/dist');

test.describe('FHE Share sealed autofill canary', () => {
  test.skip(!process.env.PLAYWRIGHT_EXTENSION_PATH && !process.env.CI_RUN_EXTENSION_CANARY,
    'Set PLAYWRIGHT_EXTENSION_PATH or CI_RUN_EXTENSION_CANARY=1 to enable.');

  test('content script acknowledges sealed-fill requests', async () => {
    const userDataDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '.playwright-user-data-fhe-share');
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        `--disable-extensions-except=${extensionPath}`,
        `--load-extension=${extensionPath}`,
      ],
    });
    try {
      const page = await context.newPage();
      await page.goto('http://localhost:5173/homomorphic-sharing', { waitUntil: 'domcontentloaded' });

      const ack = await page.evaluate(async () => {
        return await new Promise((resolve) => {
          const token = 'canary-' + Math.random().toString(36).slice(2);
          const handler = (ev) => {
            const d = ev.data;
            if (!d || d.type !== 'fhe_share:autofill_ack' || d.token !== token) return;
            window.removeEventListener('message', handler);
            resolve({ ok: !!d.ok, reason: d.reason || null });
          };
          window.addEventListener('message', handler);
          window.postMessage({
            type: 'fhe_share:autofill_request_v2',
            token,
            payload: { cipherSuite: 'umbral-v1', domain: 'example.com' },
          }, window.location.origin);
          setTimeout(() => {
            window.removeEventListener('message', handler);
            resolve({ ok: false, reason: 'timeout' });
          }, 2000);
        });
      });

      expect(['no_identity', 'umbral_unavailable', null]).toContain(ack.reason);
      // Either the extension answered or we timed out — but NOT both.
      // "timeout" means the bridge wasn't wired.
      expect(ack.reason).not.toBe('timeout');
    } finally {
      await context.close();
    }
  });
});

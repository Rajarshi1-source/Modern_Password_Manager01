// @ts-check
/**
 * Vault hygiene: copied secrets are cleared, and an idle vault locks.
 *
 * F12 and section 9.1 of docs/pqc-hybrid-architecture-review.md. Both checks
 * use Playwright's fake clock (page.clock) instead of real waits, and assert
 * on behaviour (what is on the clipboard, what the vault UI shows), not on
 * any in-memory key: there is deliberately no window-global debug hook.
 *
 * Clipboard permissions are granted per test and only exist in Chromium, so
 * the clipboard test is Chromium-only.
 */

import { test, expect } from '@playwright/test';
import { signupAndLogin } from './helpers/auth';

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';

// Defaults: preferencesService security.clipboardTimeout = 30 s,
// VaultContext DEFAULT_AUTO_LOCK_TIMEOUT = 5 min.
const CLIPBOARD_TIMEOUT_MS = 30_000;
const AUTO_LOCK_MS = 5 * 60_000;

// A full page load drops the in-memory vault session key, and the app then
// offers to set up a vault password. The generator needs no vault, so close it.
async function dismissVaultPrompt(page) {
  try {
    await page.getByRole('button', { name: 'Later' }).click({ timeout: 3000 });
  } catch {
    // No prompt.
  }
}

test.describe('Vault hygiene', () => {
  test('a copied password is cleared from the clipboard after the timeout', async ({
    page,
    context,
    browserName,
  }) => {
    test.skip(browserName !== 'chromium', 'Clipboard permissions are Chromium-only');
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE_URL });
    await page.clock.install();

    await signupAndLogin(page, { baseUrl: BASE_URL, emailPrefix: 'hygiene-clip' });
    await page.goto(`${BASE_URL}/security/synesthetic`);
    await dismissVaultPrompt(page);

    const generated = page.getByTestId('generated-password');
    await expect(generated).not.toBeEmpty();
    const password = (await generated.textContent()) ?? '';

    await page.getByTestId('copy-password').click();
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe(password);

    // Just before the timeout the password is still there.
    await page.clock.runFor(CLIPBOARD_TIMEOUT_MS - 1_000);
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(password);

    await page.clock.runFor(2_000);
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe('');
  });

  test('an idle vault locks after the auto-lock timeout', async ({ page }) => {
    await page.clock.install();

    // Stay in the single-page app after login: a reload drops the in-memory
    // session key, so the vault would already be locked.
    await signupAndLogin(page, { baseUrl: BASE_URL, emailPrefix: 'hygiene-lock' });

    // Reflects whether a vault session key is held (VaultContext canEdit).
    const lockStatus = page.getByTestId('vault-lock-status');
    await expect(lockStatus).toHaveText('Vault unlocked');

    // Idle just short of the timeout: still unlocked.
    await page.clock.runFor(AUTO_LOCK_MS - 30_000);
    await expect(lockStatus).toHaveText('Vault unlocked');

    // No input events from here on either; the inactivity check re-arms at
    // most every 10 s, so allow one interval past the timeout.
    await page.clock.runFor(30_000 + 15_000);
    await expect(lockStatus).toHaveText('Vault locked');
  });
});

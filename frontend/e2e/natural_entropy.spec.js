/**
 * Natural Entropy Enhancement - E2E Tests
 * =========================================
 *
 * End-to-end tests for the "Ultimate Natural Entropy" dashboard
 * (UltimateEntropyDashboard.tsx, mounted at /security/natural-entropy):
 * multi-source status, source selection, password generation, and the
 * generated-password display.
 *
 * Rewritten 2026-09 after an explore subagent found this file predated the
 * shipped dashboard entirely: it assumed a tabbed UI (lightning/seismic/
 * solar/history/statistics tabs, a preferences modal, per-source
 * data-testids) that was never built. The real dashboard is a single-page
 * layout -- source cards are plain onClick divs with no data-testid, the
 * length control is a range input (not a fillable text field), and there
 * are no tabs at all. See UltimateEntropyDashboard.tsx for the real markup.
 *
 * @created 2026-01-31
 * @updated 2026-09-17
 */

// @ts-check
import { test, expect } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';

// =============================================================================
// Helpers
// =============================================================================

/**
 * Sign up a fresh user and log in. There is no seeded test account and no
 * separate "username" field anywhere in the UI -- registration sets
 * Django's User.username to the email address (App.jsx handleSignup), and
 * handleSignup does NOT log the new user in; a second, explicit login is
 * required. Same flow as adaptive_password.spec.ts's signupAndLogin.
 */
async function signupAndLogin(page) {
  const email = `e2e-entropy-${Date.now()}-${Math.floor(Math.random() * 1e6)}@test.com`;
  const password = 'TestPassword123!';

  await page.goto(`${BASE_URL}/signup`);
  await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
  await page.fill('#signup-email', email);
  await page.fill('#signup-password', password);
  await page.fill('#signup-confirm-password', password);
  await page.getByRole('button', { name: 'Create Free Account' }).click();

  await page.waitForSelector('#login-email');
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.getByRole('button', { name: 'Login to Vault' }).click();

  await page.waitForFunction(
    () => !!window.localStorage.getItem('accessToken'),
    { timeout: 15000 },
  );
}

const STATUS_RESPONSE = {
  sources: {
    ocean: { available: true },
    lightning: { available: true, activity: { strikes_last_hour: 4200 } },
    seismic: { available: true, activity: { events_24h: 37 } },
    solar: { available: false, weather: { storm_level: 'G1' } },
  },
  available_sources: 3,
  total_sources: 4,
  timestamp: new Date().toISOString(),
};

async function routeStatus(page, overrides = {}) {
  await page.route('**/api/security/natural/status/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...STATUS_RESPONSE, ...overrides }),
    });
  });
}

test.describe('Natural Entropy Enhancement E2E', () => {
  test.beforeEach(async ({ page }) => {
    await signupAndLogin(page);
  });

  // ===========================================================================
  // Dashboard Tests
  // ===========================================================================

  test('should load the dashboard and list entropy sources', async ({ page }) => {
    await routeStatus(page);
    await page.goto(`${BASE_URL}/security/natural-entropy`);

    await expect(page.getByRole('heading', { name: /Ultimate Natural Entropy/i })).toBeVisible();
    await expect(page.getByText('Ocean Waves')).toBeVisible();
    await expect(page.getByText('Lightning')).toBeVisible();
    await expect(page.getByText('Seismic')).toBeVisible();
    await expect(page.getByText('Solar Wind')).toBeVisible();

    // 3 of 4 mocked sources are available.
    await expect(page.getByText('3/4 sources online')).toBeVisible();
  });

  test('reflects a source as offline', async ({ page }) => {
    await routeStatus(page);
    await page.goto(`${BASE_URL}/security/natural-entropy`);

    // EntropySourceCard renders "* Available" / "o Offline" per source;
    // solar is the only one mocked unavailable above, so exactly one
    // offline badge should be on the page (avoids a fragile "find the div
    // containing this source's name" relative lookup).
    await expect(page.getByText('○ Offline')).toHaveCount(1);
    await expect(page.getByText('● Available')).toHaveCount(3);
  });

  test('can toggle a source selection', async ({ page }) => {
    await routeStatus(page);
    await page.goto(`${BASE_URL}/security/natural-entropy`);

    // All 4 sources start selected (component default), so the generate
    // button reads "...4 Sources". Deselecting one should update the count.
    await expect(page.getByRole('button', { name: /Generate from 4 Sources/i })).toBeVisible();
    await page.getByText('Lightning').click();
    await expect(page.getByRole('button', { name: /Generate from 3 Sources/i })).toBeVisible();
  });

  // ===========================================================================
  // Password Generation Tests
  // ===========================================================================

  test('generates a password from selected sources', async ({ page }) => {
    await routeStatus(page);
    await page.route('**/api/security/natural/generate-password/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          password: 'Xk9!mQ2wPz7#vL4t',
          sources_used: ['ocean', 'lightning', 'seismic', 'solar'],
          quality_score: 0.93,
          certificate: null,
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.getByRole('button', { name: /Generate from 4 Sources/i }).click();

    await expect(page.locator('.password-display code')).toHaveText('Xk9!mQ2wPz7#vL4t', {
      timeout: 10000,
    });
    await expect(page.getByText('93%')).toBeVisible();
  });

  test('adjusts password length via the range control', async ({ page }) => {
    await routeStatus(page);
    await page.goto(`${BASE_URL}/security/natural-entropy`);

    const lengthSlider = page.locator('#password-length');
    await expect(page.getByText('Password Length: 24')).toBeVisible();
    await lengthSlider.fill('40');
    await expect(page.getByText('Password Length: 40')).toBeVisible();
  });

  // ===========================================================================
  // Error Handling
  // ===========================================================================

  test('shows an error banner when status cannot be loaded', async ({ page }) => {
    await page.route('**/api/security/natural/status/', async (route) => {
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' });
    });

    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await expect(page.locator('.error-banner')).toBeVisible();
  });

  test('shows an error when password generation fails', async ({ page }) => {
    await routeStatus(page);
    await page.route('**/api/security/natural/generate-password/', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    });

    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.getByRole('button', { name: /Generate from 4 Sources/i }).click();

    await expect(page.locator('.error-banner')).toBeVisible();
  });
});

/**
 * Storm Chase Mode - E2E Tests
 * =============================
 *
 * End-to-end tests for Storm Chase Mode (StormChaseCard.jsx), which lives
 * inside the Ocean Wave dashboard at /security/ocean-entropy -- NOT
 * /security/natural-entropy, which is a separate feature
 * (UltimateEntropyDashboard, see natural_entropy.spec.js).
 *
 * Rewritten 2026-09 after an explore subagent found this file navigated to
 * the wrong route entirely (storm chase moved to its own /ocean-entropy
 * route in June 2026, splitting away from natural-entropy) and assumed UI
 * that was never built: a storm-alerts toggle, a manual entropy-generation
 * button, a region-detail modal, a storm-history tab, and a mobile nav.
 * The real card is a single always-visible panel with a scan button, an
 * always-visible status indicator, and (when a storm is active) an alerts
 * list and affected-regions row. See StormChaseCard.jsx for the real
 * markup and password_manager/security/urls.py for the real API paths
 * (ocean/storms/status/, ocean/storms/scan/ -- not
 * ocean/storms/generate-storm-entropy/, which exists server-side but has
 * no UI button to trigger it).
 *
 * @created 2026-01-30
 * @updated 2026-09-17
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';

// =============================================================================
// Helpers
// =============================================================================

async function signupAndLogin(page) {
  const email = `e2e-storm-${Date.now()}-${Math.floor(Math.random() * 1e6)}@test.com`;
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

const NO_STORM = {
  is_active: false,
  most_severe: 'none',
  storm_alerts: [],
  regions_affected: [],
  max_entropy_bonus: 0,
  message: null,
  last_scan: '2026-09-17T10:00:00Z',
};

const ACTIVE_STORM = {
  is_active: true,
  most_severe: 'severe',
  max_entropy_bonus: 0.35,
  regions_affected: ['North Pacific'],
  message: 'Elevated entropy available from storm-affected buoys.',
  last_scan: '2026-09-17T10:05:00Z',
  storm_alerts: [
    {
      buoy_id: 'buoy-51',
      buoy_name: 'NDBC 51101',
      region: 'North Pacific',
      severity: 'severe',
      severity_label: 'Severe',
      wave_height_m: 6.2,
      wind_speed_mps: 24.5,
      pressure_hpa: 972,
      entropy_bonus: 0.35,
    },
  ],
};

async function routeStormStatus(page, body) {
  await page.route('**/api/security/ocean/storms/status/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

test.describe('Storm Chase Mode E2E', () => {
  test.beforeEach(async ({ page }) => {
    await signupAndLogin(page);
  });

  // ===========================================================================
  // Inactive State
  // ===========================================================================

  test('shows "No Active Storms" when nothing is happening', async ({ page }) => {
    await routeStormStatus(page, NO_STORM);
    await page.goto(`${BASE_URL}/security/ocean-entropy`);

    await expect(page.getByText('No Active Storms')).toBeVisible();
    await expect(page.getByText('Monitoring for storm conditions')).toBeVisible();
    // No entropy bonus badge and no alerts list while inactive.
    await expect(page.locator('.entropy-bonus-badge')).toHaveCount(0);
    await expect(page.locator('.storm-alerts-list')).toHaveCount(0);
  });

  test('shows the last scan time', async ({ page }) => {
    await routeStormStatus(page, NO_STORM);
    await page.goto(`${BASE_URL}/security/ocean-entropy`);

    await expect(page.locator('.last-scan-time')).toBeVisible();
  });

  // ===========================================================================
  // Active Storm State
  // ===========================================================================

  test('shows active storm count and entropy bonus', async ({ page }) => {
    await routeStormStatus(page, ACTIVE_STORM);
    await page.goto(`${BASE_URL}/security/ocean-entropy`);

    await expect(page.getByText('1 Active Storm Detected')).toBeVisible();
    await expect(page.getByText('+35% Entropy')).toBeVisible();
    await expect(page.getByText('MAXIMUM ENTROPY AVAILABLE', { exact: false })).toBeVisible();
  });

  test('lists storm alert details', async ({ page }) => {
    await routeStormStatus(page, ACTIVE_STORM);
    await page.goto(`${BASE_URL}/security/ocean-entropy`);

    const alertsList = page.locator('.storm-alerts-list');
    await expect(alertsList).toBeVisible();

    const alertItem = page.locator('.storm-alert-item').first();
    await expect(alertItem).toContainText('NDBC 51101');
    await expect(alertItem).toContainText('North Pacific');
    await expect(alertItem).toContainText('6.2m');
    await expect(alertItem).toContainText('24.5m/s');
    await expect(alertItem).toContainText('972hPa');
  });

  test('shows affected regions', async ({ page }) => {
    await routeStormStatus(page, ACTIVE_STORM);
    await page.goto(`${BASE_URL}/security/ocean-entropy`);

    await expect(page.locator('.regions-affected')).toContainText('North Pacific');
  });

  // ===========================================================================
  // Manual Scan
  // ===========================================================================

  test('can trigger a manual storm scan', async ({ page }) => {
    await routeStormStatus(page, NO_STORM);
    let scanned = false;
    await page.route('**/api/security/ocean/storms/scan/', async (route) => {
      scanned = true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });

    await page.goto(`${BASE_URL}/security/ocean-entropy`);
    await page.click('.storm-scan-btn');

    await expect.poll(() => scanned).toBe(true);
  });

  // ===========================================================================
  // Error Handling
  // ===========================================================================

  test('shows an error message when the status fetch fails', async ({ page }) => {
    await page.route('**/api/security/ocean/storms/status/', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    });

    await page.goto(`${BASE_URL}/security/ocean-entropy`);
    await expect(page.locator('.storm-error')).toBeVisible();
  });
});

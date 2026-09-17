/**
 * Honeypot Credentials — E2E smoke test
 * =====================================
 *
 * Verifies the "attacker touches honeypot → alert shows up for owner"
 * flow at the UI layer. We stub the backend so the test is fast and
 * hermetic — the point is to prove the wiring between the interceptor
 * response shape, the React state, and the toast/banner rendering.
 */

import { test, expect } from '@playwright/test';

test.describe('Honeypot alert toast', () => {
  test.beforeEach(async ({ page }) => {
    // Both routes are behind the `!isAuthenticated ? <Navigate to="/" />`
    // guard in App.jsx, and useAuth only flips isAuthenticated once
    // GET /api/auth/me/ resolves 200 for the token in localStorage. Without
    // this, the page never mounts and the honeypot stubs below are never
    // hit -- see liveness_ble_spo2.spec.js's header for the same guard.
    // Stubbing /me (rather than requiring a live backend) keeps this test
    // hermetic, matching its own stated design intent.
    await page.addInitScript(() => {
      localStorage.setItem('accessToken', 'e2e-honeypot-test-token');
    });
    await page.route('**/api/auth/me/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          username: 'e2e-honeypot',
          email: 'e2e-honeypot@test.com',
        }),
      });
    });

    // Stub the honeypot credential list so the settings screen loads
    // deterministically without any auth flow noise.
    await page.route('**/api/honeypot/credentials/', async (route) => {
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'hp-test-001',
            label: 'admin-backup',
            fake_site: 'internal-portal.example.com',
            fake_username: 'admin_backup@example.com',
            decoy_strategy: 'static',
            template: null,
            is_active: true,
            alert_channels: ['email'],
            last_rotated_at: now,
            created_at: now,
            updated_at: now,
            access_count: 1,
          },
        ]),
      });
    });

    // The event table stub drives the "alert happened" visual.
    await page.route('**/api/honeypot/events/', async (route) => {
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'evt-1',
            honeypot: 'hp-test-001',
            honeypot_label: 'admin-backup',
            access_type: 'retrieve',
            ip: '203.0.113.9',
            user_agent: 'Mozilla/5.0 (e2e stub)',
            geo_country: 'US',
            geo_city: 'Denver',
            session_key: '',
            alert_sent: true,
            alert_errors: {},
            accessed_at: now,
          },
        ]),
      });
    });
  });

  test('settings screen renders the planted honeypot', async ({ page }) => {
    await page.goto('/security/honeypot-credentials');

    // Heading rendered by HoneypotSettings.jsx.
    await expect(page.getByRole('heading', { name: /Honeypot credentials/i })).toBeVisible();
    // The stubbed honeypot row.
    await expect(page.getByText('admin-backup')).toBeVisible();
    await expect(page.getByText('internal-portal.example.com')).toBeVisible();
  });

  test('events screen shows a triggered alert row', async ({ page }) => {
    await page.goto('/security/honeypot-credentials/events');

    await expect(page.getByRole('heading', { name: /Honeypot access log/i })).toBeVisible();
    await expect(page.getByText('203.0.113.9')).toBeVisible();
    await expect(page.getByText('sent')).toBeVisible();
  });
});

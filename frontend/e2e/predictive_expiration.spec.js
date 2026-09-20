/**
 * Predictive Password Expiration - E2E Tests
 * ===========================================
 *
 * End-to-end tests for PredictiveExpirationDashboard.jsx, mounted at
 * /security/predictive-expiration: risk overview, at-risk credentials,
 * active threats, recent activity, and settings.
 *
 * Rewritten 2026-09 after an explore subagent found this file predated the
 * shipped dashboard: it used login data-testids and a /dashboard route
 * that don't exist, several CSS class names that were renamed
 * (.overview-stats -> .risk-stats, .risk-score-ring/.risk-indicator ->
 * .risk-circle, .threat-section/.active-threats -> .threats-section), an
 * unauthenticated redirect target that doesn't match (App.jsx redirects to
 * "/", not /login), an invalid Playwright API (toHaveCount() takes a
 * number, not {minimum: N}), a settings panel that's actually hidden
 * behind a slide-out toggle, a rotation "timeline" component that exists
 * in the repo but is never imported/rendered (the real section is a
 * simple "Recent Activity" summary), and a risk filter control that was
 * never built at all.
 *
 * The subagent also found a real production bug (fixed separately, in
 * predictiveExpirationService.js): the service called
 * /security/predictive-expiration/... instead of
 * /api/security/predictive-expiration/..., which Vite's dev proxy never
 * forwards to Django -- the dashboard was in its error state in every
 * environment, not just under test.
 *
 * @created 2026-02-08
 * @updated 2026-09-17
 */

import { test, expect } from '@playwright/test';
import { signupAndLogin as authSignupAndLogin } from './helpers/auth.js';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

const signupAndLogin = (page) =>
  authSignupAndLogin(page, { baseUrl: BASE_URL, emailPrefix: 'e2e-predictive' });

const DEFAULT_DASHBOARD = {
  overall_risk_score: 0.42,
  critical_count: 1,
  high_count: 2,
  medium_count: 3,
  pending_rotations: 1,
  at_risk_count: 1,
  credentials_at_risk: [
    {
      credential_id: 'cred-1',
      credential_domain: 'example.com',
      risk_level: 'critical',
      risk_score: 0.91,
      predicted_compromise_date: new Date(Date.now() + 3 * 86400000).toISOString(),
      recommended_action: 'rotate_immediately',
      user_acknowledged: false,
    },
  ],
  active_threats: [
    {
      actor_id: 'actor-1',
      name: 'ShadowSyndicate',
      threat_level: 'high',
      actor_type: 'ransomware',
      is_currently_active: true,
    },
  ],
  industry_threat: null,
  recent_rotations: 4,
  total_credentials: 12,
  last_scan_at: new Date().toISOString(),
};

const DEFAULT_THREAT_SUMMARY = {
  total_active_actors: 1,
  critical_threats: 0,
  high_threats: 1,
  ransomware_active: 1,
  apt_active: 0,
};

const DEFAULT_SETTINGS = {
  is_enabled: true,
  auto_rotation_enabled: false,
  force_rotation_threshold: 0.8,
  industry: '',
  notify_on_high_risk: false,
};

/**
 * Mock the three endpoints PredictiveExpirationDashboard fetches in
 * parallel on mount (Promise.all -- if any one is unmocked and unreachable,
 * the whole dashboard renders its .error state instead).
 */
async function routeDashboardData(page, overrides = {}) {
  const dashboard = { ...DEFAULT_DASHBOARD, ...overrides.dashboard };
  const threatSummary = { ...DEFAULT_THREAT_SUMMARY, ...overrides.threatSummary };
  const settings = { ...DEFAULT_SETTINGS, ...overrides.settings };

  await page.route('**/api/security/predictive-expiration/dashboard/', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) });
  });
  await page.route('**/api/security/predictive-expiration/threat-summary/', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(threatSummary) });
  });
  await page.route('**/api/security/predictive-expiration/settings/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(settings) });
    } else {
      // PATCH from the settings panel -- echo back what was sent, merged
      // over the current settings, matching what a real update would do.
      const body = route.request().postDataJSON() || {};
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...settings, ...body }),
      });
    }
  });
}

// =============================================================================
// Dashboard Tests
// =============================================================================

test.describe('Predictive Password Expiration E2E', () => {
  test.beforeEach(async ({ page }) => {
    await signupAndLogin(page);
  });

  test('should display predictive expiration dashboard', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.predictive-dashboard')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.dashboard-header')).toBeVisible();
  });

  test('should display risk overview section', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.risk-overview')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.risk-stats')).toBeVisible();
  });

  test('should display stat cards with metrics', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    // Exactly 4 unconditional cards: Critical, High Risk, Medium Risk, Pending.
    await expect(page.locator('.stat-card')).toHaveCount(4, { timeout: 10000 });
  });

  test('should show overall risk indicator', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.risk-circle')).toBeVisible({ timeout: 10000 });
  });

  // ===========================================================================
  // At-Risk Credentials Tests
  // ===========================================================================

  test('should display at-risk credentials section', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.credentials-section')).toBeVisible({ timeout: 10000 });
  });

  test('should show credential risk cards', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.credential-risk-card')).toHaveCount(1);
    await expect(page.getByText('example.com')).toBeVisible();
  });

  test('should show the empty state when nothing is at risk', async ({ page }) => {
    await routeDashboardData(page, {
      dashboard: { at_risk_count: 0, credentials_at_risk: [] },
    });
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.credentials-section .empty-state')).toBeVisible();
    await expect(page.getByText('No credentials at risk!')).toBeVisible();
  });

  test('should acknowledge credential risk', async ({ page }) => {
    await routeDashboardData(page);
    let acknowledged = false;
    await page.route('**/api/security/predictive-expiration/credential/cred-1/acknowledge/', async (route) => {
      acknowledged = true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });

    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await page.click('.btn-acknowledge');

    await expect.poll(() => acknowledged).toBe(true);
  });

  test('should show a rotate button for credentials recommended for rotation', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    // recommended_action: 'rotate_immediately' on the mocked credential.
    // Full rotation goes through the real client-side vault crypto
    // (rotateCredential()), which needs a genuinely decryptable vault item
    // to complete -- out of scope here; this only verifies the button
    // renders and is enabled for the right recommendation.
    await expect(page.locator('.btn-rotate')).toBeVisible();
    await expect(page.locator('.btn-rotate')).toBeEnabled();
  });

  // ===========================================================================
  // Threat Intelligence Tests
  // ===========================================================================

  test('should display threat actors section', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.threats-section')).toBeVisible({ timeout: 10000 });
  });

  test('should show threat actor cards', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.threat-actor-card')).toHaveCount(1);
    await expect(page.getByText('ShadowSyndicate')).toBeVisible();
  });

  test('should display threat levels with appropriate styling', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.risk-badge').first()).toBeVisible();
  });

  // ===========================================================================
  // Recent Activity Tests
  // ===========================================================================
  // Note: RotationHistoryTimeline.jsx exists in the repo (with .rotation-
  // timeline/.timeline-item classes and per-outcome icons) but is not
  // imported or rendered by PredictiveExpirationDashboard.jsx. The actual
  // dashboard shows a plain "Recent Activity" summary instead -- there is
  // no timeline, and GET .../history/ is never called from this page.

  test('should display the recent activity section', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.rotations-section')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'Recent Activity' })).toBeVisible();
  });

  test('should show rotation and credential counts in recent activity', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    const activity = page.locator('.activity-summary');
    await expect(activity).toContainText('4'); // recent_rotations
    await expect(activity).toContainText('12'); // total_credentials
  });

  // ===========================================================================
  // Settings Tests
  // ===========================================================================
  // The settings panel is a slide-out overlay, closed by default
  // (showSettings starts false) -- it must be opened via .btn-settings
  // before any of its controls are reachable.

  test('should open the settings panel', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.settings-panel')).not.toBeVisible();
    await page.click('.btn-settings');
    await expect(page.locator('.settings-panel')).toBeVisible();
  });

  test('should toggle the feature on/off from the header button', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    // Feature enable/disable is a header button (.btn-toggle), not a
    // checkbox -- its label swaps between Enabled/Disabled.
    await page.getByRole('button', { name: /Enabled/i }).click();
    await expect(page.getByRole('button', { name: /Disabled/i })).toBeVisible();

    await page.getByRole('button', { name: /Disabled/i }).click();
    await expect(page.getByRole('button', { name: /Enabled/i })).toBeVisible();
  });

  test('should update notification preferences', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await page.click('.btn-settings');
    const notifCheckbox = page
      .locator('.setting-item', { hasText: 'High Risk Notifications' })
      .locator('input[type="checkbox"]');
    await expect(notifCheckbox).not.toBeChecked();
    await notifCheckbox.click();
    await expect(notifCheckbox).toBeChecked();
  });

  test('should select industry for threat matching', async ({ page }) => {
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await page.click('.btn-settings');
    const industrySelect = page
      .locator('.setting-item', { hasText: 'Industry' })
      .locator('select');
    await industrySelect.selectOption('technology');
    await expect(industrySelect).toHaveValue('technology');
  });

  // ===========================================================================
  // Loading & Error States Tests
  // ===========================================================================

  test('should show loading state while fetching data', async ({ page }) => {
    await routeDashboardData(page);

    // Hold the dashboard response open so the loading state is observable.
    // Registered AFTER routeDashboardData(), so it takes precedence for this
    // URL (Playwright runs the most recently registered matching route first).
    let releaseDashboard;
    const dashboardGate = new Promise((resolve) => { releaseDashboard = resolve; });
    await page.route('**/api/security/predictive-expiration/dashboard/', async (route) => {
      await dashboardGate;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DEFAULT_DASHBOARD),
      });
    });

    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    try {
      await expect(page.locator('.predictive-dashboard.loading')).toBeVisible();
    } finally {
      releaseDashboard(); // never leave the request hanging if the assertion fails
    }
    await expect(page.locator('.dashboard-header')).toBeVisible({ timeout: 10000 });
  });

  test('should show an error state when the dashboard fetch fails', async ({ page }) => {
    await page.route('**/api/security/predictive-expiration/dashboard/', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    });
    await page.route('**/api/security/predictive-expiration/threat-summary/', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEFAULT_THREAT_SUMMARY) });
    });
    await page.route('**/api/security/predictive-expiration/settings/', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEFAULT_SETTINGS) });
    });

    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await expect(page.locator('.predictive-dashboard.error')).toBeVisible({ timeout: 10000 });
  });

  // ===========================================================================
  // Responsive Design Tests
  // ===========================================================================

  test('should be responsive on mobile viewports', async ({ page }) => {
    await routeDashboardData(page);
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.predictive-dashboard')).toBeVisible({ timeout: 10000 });
  });

  test('should be responsive on tablet viewports', async ({ page }) => {
    await routeDashboardData(page);
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await expect(page.locator('.predictive-dashboard')).toBeVisible({ timeout: 10000 });
  });

  // ===========================================================================
  // Performance Tests
  // ===========================================================================

  test('should load dashboard within performance budget', async ({ page }) => {
    await routeDashboardData(page);
    const startTime = Date.now();

    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await expect(page.locator('.predictive-dashboard')).toBeVisible({ timeout: 10000 });

    const loadTime = Date.now() - startTime;
    expect(loadTime).toBeLessThan(5000);
  });
});

// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('Predictive Expiration Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await signupAndLogin(page);
    await routeDashboardData(page);
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    const focusedElement = await page.evaluate(() => document.activeElement.tagName);
    expect(['INPUT', 'BUTTON', 'SELECT', 'A', 'DIV']).toContain(focusedElement);
  });

  test('should have proper ARIA labels on interactive elements', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/predictive-expiration`);

    const buttons = await page.locator('button').count();
    expect(buttons).toBeGreaterThan(0);
  });
});

// =============================================================================
// Security Tests
// =============================================================================

test.describe('Predictive Expiration Security', () => {
  test('should require authentication', async ({ page }) => {
    // App.jsx redirects unauthenticated visitors of this route to "/"
    // (<Navigate to="/" />), not to a dedicated /login or /auth page.
    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await expect(page).toHaveURL(`${BASE_URL}/`);
  });

  test('should not expose sensitive data in console', async ({ page }) => {
    const consoleLogs = [];
    page.on('console', (msg) => consoleLogs.push(msg.text()));

    await signupAndLogin(page);
    await routeDashboardData(page);
    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await page.waitForTimeout(2000);

    const hasLeakedPassword = consoleLogs.some(
      (log) => log.toLowerCase().includes('testpassword123'),
    );
    expect(hasLeakedPassword).toBe(false);
  });
});

// =============================================================================
// Integration Tests
// =============================================================================

test.describe('Predictive Expiration Integration', () => {
  test.beforeEach(async ({ page }) => {
    await signupAndLogin(page);
    await routeDashboardData(page);
  });

  test('full workflow: view dashboard, check credentials, view activity', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await expect(page.locator('.predictive-dashboard')).toBeVisible({ timeout: 10000 });

    await expect(page.locator('.risk-overview')).toBeVisible();

    await page.locator('.credentials-section').scrollIntoViewIfNeeded();
    await expect(page.locator('.credential-risk-card')).toHaveCount(1);

    await page.locator('.rotations-section').scrollIntoViewIfNeeded();
    await expect(page.locator('.rotations-section')).toBeVisible();
  });

  test('acknowledging a risk refreshes the dashboard', async ({ page }) => {
    let acknowledgeCalls = 0;
    let dashboardCalls = 0;
    await page.route('**/api/security/predictive-expiration/credential/cred-1/acknowledge/', async (route) => {
      acknowledgeCalls += 1;
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });
    await page.route('**/api/security/predictive-expiration/dashboard/', async (route) => {
      dashboardCalls += 1;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEFAULT_DASHBOARD) });
    });

    await page.goto(`${BASE_URL}/security/predictive-expiration`);
    await expect(page.locator('.dashboard-header')).toBeVisible({ timeout: 10000 });
    const dashboardCallsBefore = dashboardCalls;
    await page.click('.btn-acknowledge');

    // handleAcknowledge() calls fetchDashboard() again after a successful
    // acknowledge -- confirms the UI actually refreshes, not just that the
    // network call fired.
    await expect.poll(() => acknowledgeCalls).toBe(1);
    await expect.poll(() => dashboardCalls).toBeGreaterThan(dashboardCallsBefore);
  });
});

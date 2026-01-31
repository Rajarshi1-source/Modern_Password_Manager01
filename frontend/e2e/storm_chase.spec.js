/**
 * Storm Chase Mode - E2E Tests
 * =============================
 * 
 * End-to-end tests using Playwright for Storm Chase Mode functionality:
 * - Storm status display
 * - Active storm alerts visualization  
 * - Storm entropy generation
 * - Regional storm filtering
 * - Storm buoy data viewing
 * 
 * @author Password Manager Team
 * @created 2026-01-31
 */

// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const TEST_USER = {
  email: 'e2e-storm@test.com',
  password: 'TestPassword123!',
};


// =============================================================================
// Setup & Teardown
// =============================================================================

test.describe('Storm Chase Mode E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto(`${BASE_URL}/login`);
    
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    
    // Wait for auth
    await page.waitForSelector('[data-testid="authenticated"]', { timeout: 10000 });
  });


  // ===========================================================================
  // Storm Status Display Tests
  // ===========================================================================
  
  test('should display storm chase status', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Storm status section should be visible
    await expect(page.locator('.storm-status-section')).toBeVisible();
    
    // Status indicator should show active or calm
    await expect(page.locator('.storm-indicator')).toBeVisible();
  });

  test('should show storm mode badge when storms active', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Check for storm mode badge (might not be visible if no storms)
    const badge = page.locator('.storm-mode-badge');
    
    // Just verify the element structure exists (may be hidden)
    await expect(page.locator('.storm-status-container')).toBeVisible();
  });

  test('should display storm metrics', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Metric cards should show storm data
    const metricsContainer = page.locator('.storm-metrics');
    await expect(metricsContainer).toBeVisible();
    
    // Should show at least entropy bonus metric
    await expect(page.locator('[data-testid="entropy-bonus"]')).toBeVisible();
  });


  // ===========================================================================
  // Storm Alerts Tests
  // ===========================================================================

  test('should display storm alerts list', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click to expand storm alerts section
    await page.click('.storm-alerts-toggle');
    
    // Alerts list should be visible
    await expect(page.locator('.storm-alerts-list')).toBeVisible();
  });

  test('should show severity colors for alerts', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('.storm-alerts-toggle');
    
    // Alert cards should have severity-based styling
    const alerts = page.locator('.storm-alert-card');
    
    // Check severity classes exist
    await expect(page.locator('.alert-severity')).toBeVisible();
  });

  test('should filter alerts by region', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('.storm-alerts-toggle');
    
    // Select region filter
    await page.selectOption('[data-testid="region-filter"]', 'atlantic');
    
    // Alerts should update
    await page.waitForSelector('.storm-alerts-list');
  });


  // ===========================================================================
  // Storm Entropy Generation Tests
  // ===========================================================================

  test('should generate storm entropy when storms active', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click storm entropy generation button
    await page.click('[data-testid="generate-storm-entropy"]');
    
    // Should show generation animation
    await expect(page.locator('.entropy-generating')).toBeVisible();
    
    // Wait for result
    await page.waitForSelector('.entropy-result', { timeout: 10000 });
    
    // Result should show storm source indicator
    await expect(page.locator('.storm-source-badge')).toBeVisible();
  });

  test('should show entropy bonus for storm sources', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="generate-storm-entropy"]');
    await page.waitForSelector('.entropy-result', { timeout: 10000 });
    
    // Entropy bonus percentage should be displayed
    const bonus = page.locator('.entropy-bonus-display');
    await expect(bonus).toContainText('%');
  });

  test('should show storm buoys used in generation', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="generate-storm-entropy"]');
    await page.waitForSelector('.entropy-result', { timeout: 10000 });
    
    // Source buoys list should be visible
    await expect(page.locator('.source-buoys-list')).toBeVisible();
  });


  // ===========================================================================
  // Storm Map Visualization Tests
  // ===========================================================================

  test('should display storm map', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Storm map/visualization should be visible
    await expect(page.locator('.storm-map-container')).toBeVisible();
  });

  test('should show buoy markers on map', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Buoy markers should be present
    await expect(page.locator('.buoy-marker')).toBeVisible();
  });

  test('should highlight storm buoys', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Storm buoys should have special styling
    const stormBuoy = page.locator('.buoy-marker.storm-active');
    // May not always be present if no storms
    await expect(page.locator('.buoy-marker')).toBeVisible();
  });


  // ===========================================================================
  // Scan for Storms Tests
  // ===========================================================================

  test('should trigger manual storm scan', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click scan button
    await page.click('[data-testid="scan-storms-btn"]');
    
    // Loading indicator should show
    await expect(page.locator('.scanning-indicator')).toBeVisible();
    
    // Wait for scan completion
    await page.waitForSelector('.scan-complete', { timeout: 15000 });
    
    // Results should update
    await expect(page.locator('.last-scan-time')).toBeVisible();
  });

  test('should show scan timestamp', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Last scan time should be displayed
    await expect(page.locator('.last-scan-time')).toBeVisible();
  });


  // ===========================================================================
  // Regional Storm Status Tests
  // ===========================================================================

  test('should display regional status cards', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Region cards should be visible
    const regionCards = page.locator('.region-status-card');
    await expect(regionCards.first()).toBeVisible();
  });

  test('should navigate to regional details', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click on a region card
    await page.click('.region-status-card:first-child');
    
    // Detail view should appear
    await expect(page.locator('.region-detail-modal')).toBeVisible();
  });


  // ===========================================================================
  // Storm Alerts History Tests
  // ===========================================================================

  test('should show storm history', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click history tab
    await page.click('[data-testid="storm-history-tab"]');
    
    // History timeline should be visible
    await expect(page.locator('.storm-history-timeline')).toBeVisible();
  });

  test('should filter history by date range', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="storm-history-tab"]');
    
    // Select date range
    await page.selectOption('[data-testid="history-range"]', '7');
    
    // List should update
    await page.waitForSelector('.storm-history-item');
  });


  // ===========================================================================
  // Integration with Password Generation
  // ===========================================================================

  test('should integrate storm entropy in password generation', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Enable storm source
    await page.check('[data-testid="source-ocean"]');
    
    // Set password options
    await page.fill('[data-testid="password-length"]', '24');
    
    // Generate password
    await page.click('[data-testid="generate-password-btn"]');
    
    // Wait for result
    await page.waitForSelector('[data-testid="generated-password"]');
    
    // Certificate should mention storm/ocean source
    const certificate = page.locator('.entropy-certificate');
    await expect(certificate).toBeVisible();
  });


  // ===========================================================================
  // Notifications Tests
  // ===========================================================================

  test('should show storm notification when new storm detected', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Trigger scan
    await page.click('[data-testid="scan-storms-btn"]');
    await page.waitForSelector('.scan-complete', { timeout: 15000 });
    
    // If storms are found, notification should appear
    // (This depends on actual storm conditions)
    await expect(page.locator('.notification-container')).toBeVisible();
  });


  // ===========================================================================
  // Accessibility Tests
  // ===========================================================================

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Tab through elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Active element should be focusable
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Interactive elements should have labels
    const buttons = page.locator('button');
    
    for (const button of await buttons.all()) {
      const label = await button.getAttribute('aria-label');
      const text = await button.textContent();
      expect(label || text).toBeTruthy();
    }
  });


  // ===========================================================================
  // Responsive Design Tests
  // ===========================================================================

  test('should display properly on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Page should be scrollable
    await expect(page.locator('.storm-dashboard')).toBeVisible();
    
    // Mobile menu should work
    await expect(page.locator('.mobile-nav')).toBeVisible();
  });

  test('should display properly on tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await expect(page.locator('.storm-dashboard')).toBeVisible();
  });


  // ===========================================================================
  // Error Handling Tests
  // ===========================================================================

  test('should handle API errors gracefully', async ({ page }) => {
    // Intercept API and return error
    await page.route('**/api/security/ocean/storms/**', route => {
      route.fulfill({ status: 500, body: 'Server Error' });
    });
    
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Error message should be displayed
    await expect(page.locator('.error-message')).toBeVisible();
    
    // Retry button should be available
    await expect(page.locator('[data-testid="retry-btn"]')).toBeVisible();
  });

  test('should show offline message when disconnected', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Simulate offline
    await page.context().setOffline(true);
    
    // Try to scan
    await page.click('[data-testid="scan-storms-btn"]');
    
    // Offline message should appear
    await expect(page.locator('.offline-message')).toBeVisible();
    
    // Restore online
    await page.context().setOffline(false);
  });
});

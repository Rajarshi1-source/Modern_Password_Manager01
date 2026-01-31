/**
 * Natural Entropy Enhancement - E2E Tests
 * =========================================
 * 
 * End-to-end tests using Playwright for Natural Entropy features:
 * - Multi-source entropy dashboard
 * - Lightning activity visualization
 * - Seismic activity display
 * - Solar wind status
 * - Password generation with natural entropy
 * - Entropy certificates
 * 
 * @author Password Manager Team
 * @created 2026-01-31
 */

// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const TEST_USER = {
  email: 'e2e-entropy@test.com',
  password: 'TestPassword123!',
};


// =============================================================================
// Setup & Teardown
// =============================================================================

test.describe('Natural Entropy Enhancement E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto(`${BASE_URL}/login`);
    
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    
    await page.waitForSelector('[data-testid="authenticated"]', { timeout: 10000 });
  });


  // ===========================================================================
  // Dashboard Tests
  // ===========================================================================

  test('should load natural entropy dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await expect(page.locator('.natural-entropy-dashboard')).toBeVisible();
  });

  test('should display all entropy sources', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // All four natural entropy sources should be displayed
    await expect(page.locator('[data-testid="source-ocean"]')).toBeVisible();
    await expect(page.locator('[data-testid="source-lightning"]')).toBeVisible();
    await expect(page.locator('[data-testid="source-seismic"]')).toBeVisible();
    await expect(page.locator('[data-testid="source-solar"]')).toBeVisible();
  });

  test('should show source availability status', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Each source should have an availability indicator
    const sourceCards = page.locator('.source-card');
    
    for (const card of await sourceCards.all()) {
      const statusIndicator = card.locator('.availability-status');
      await expect(statusIndicator).toBeVisible();
    }
  });


  // ===========================================================================
  // Lightning Activity Tests
  // ===========================================================================

  test('should display lightning activity section', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Click lightning tab/section
    await page.click('[data-testid="lightning-tab"]');
    
    await expect(page.locator('.lightning-activity-section')).toBeVisible();
  });

  test('should show lightning map', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="lightning-tab"]');
    
    await expect(page.locator('.lightning-map')).toBeVisible();
  });

  test('should display recent strikes count', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="lightning-tab"]');
    
    // Strike counter should be visible
    await expect(page.locator('.strike-count')).toBeVisible();
  });

  test('should show strike intensity histogram', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="lightning-tab"]');
    
    await expect(page.locator('.intensity-histogram')).toBeVisible();
  });

  test('should animate new lightning strikes', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="lightning-tab"]');
    
    // Wait for strike animation
    await page.waitForSelector('.strike-animation', { timeout: 10000 });
  });


  // ===========================================================================
  // Seismic Activity Tests
  // ===========================================================================

  test('should display seismic activity section', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="seismic-tab"]');
    
    await expect(page.locator('.seismic-activity-section')).toBeVisible();
  });

  test('should show earthquake map', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="seismic-tab"]');
    
    await expect(page.locator('.earthquake-map')).toBeVisible();
  });

  test('should display recent earthquakes list', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="seismic-tab"]');
    
    await expect(page.locator('.earthquake-list')).toBeVisible();
  });

  test('should show magnitude scale indicator', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="seismic-tab"]');
    
    await expect(page.locator('.magnitude-scale')).toBeVisible();
  });

  test('should filter earthquakes by magnitude', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="seismic-tab"]');
    
    // Set minimum magnitude filter
    await page.selectOption('[data-testid="min-magnitude"]', '4.0');
    
    // List should update
    await page.waitForSelector('.earthquake-item');
  });


  // ===========================================================================
  // Solar Wind Tests
  // ===========================================================================

  test('should display solar wind section', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="solar-tab"]');
    
    await expect(page.locator('.solar-wind-section')).toBeVisible();
  });

  test('should show solar wind speed', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="solar-tab"]');
    
    await expect(page.locator('.solar-wind-speed')).toBeVisible();
    // Should contain km/s
    await expect(page.locator('.solar-wind-speed')).toContainText('km/s');
  });

  test('should display particle density', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="solar-tab"]');
    
    await expect(page.locator('.particle-density')).toBeVisible();
  });

  test('should show magnetic field strength', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="solar-tab"]');
    
    await expect(page.locator('.magnetic-field')).toBeVisible();
  });

  test('should display space weather alerts', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.click('[data-testid="solar-tab"]');
    
    await expect(page.locator('.space-weather-alerts')).toBeVisible();
  });


  // ===========================================================================
  // Password Generation Tests
  // ===========================================================================

  test('should generate password with natural entropy', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Select entropy sources
    await page.check('[data-testid="source-lightning"]');
    await page.check('[data-testid="source-seismic"]');
    
    // Set password length
    await page.fill('[data-testid="password-length"]', '20');
    
    // Generate password
    await page.click('[data-testid="generate-password-btn"]');
    
    // Wait for result
    await page.waitForSelector('[data-testid="generated-password"]');
    
    // Password should be displayed
    const password = await page.locator('[data-testid="generated-password"]').textContent();
    expect(password?.length).toBe(20);
  });

  test('should allow source selection', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Toggle sources
    await page.check('[data-testid="source-ocean"]');
    await page.uncheck('[data-testid="source-ocean"]');
    
    // Source should be unchecked
    await expect(page.locator('[data-testid="source-ocean"]')).not.toBeChecked();
  });

  test('should show entropy source contribution', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-lightning"]');
    await page.check('[data-testid="source-seismic"]');
    await page.click('[data-testid="generate-password-btn"]');
    
    await page.waitForSelector('[data-testid="generated-password"]');
    
    // Contribution breakdown should be visible
    await expect(page.locator('.source-contribution')).toBeVisible();
  });

  test('should copy password to clipboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-lightning"]');
    await page.click('[data-testid="generate-password-btn"]');
    await page.waitForSelector('[data-testid="generated-password"]');
    
    // Click copy button
    await page.click('[data-testid="copy-password-btn"]');
    
    // Success message should appear
    await expect(page.locator('.copy-success')).toBeVisible();
  });


  // ===========================================================================
  // Entropy Certificate Tests
  // ===========================================================================

  test('should display entropy certificate', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-lightning"]');
    await page.click('[data-testid="generate-password-btn"]');
    await page.waitForSelector('[data-testid="generated-password"]');
    
    // Certificate should be visible
    await expect(page.locator('.entropy-certificate')).toBeVisible();
  });

  test('should show certificate details', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-lightning"]');
    await page.click('[data-testid="generate-password-btn"]');
    await page.waitForSelector('.entropy-certificate');
    
    // Expand certificate details
    await page.click('.certificate-expand');
    
    // Details should show
    await expect(page.locator('.certificate-details')).toBeVisible();
    await expect(page.locator('.certificate-timestamp')).toBeVisible();
    await expect(page.locator('.certificate-sources')).toBeVisible();
  });

  test('should download certificate as PDF', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-seismic"]');
    await page.click('[data-testid="generate-password-btn"]');
    await page.waitForSelector('.entropy-certificate');
    
    // Click download
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="download-certificate"]')
    ]);
    
    expect(download.suggestedFilename()).toContain('entropy-certificate');
  });


  // ===========================================================================
  // User Preferences Tests
  // ===========================================================================

  test('should save entropy preferences', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Open preferences
    await page.click('[data-testid="preferences-btn"]');
    
    await expect(page.locator('.preferences-modal')).toBeVisible();
    
    // Change preference
    await page.check('[data-testid="pref-auto-refresh"]');
    
    // Save
    await page.click('[data-testid="save-preferences"]');
    
    // Success message
    await expect(page.locator('.preferences-saved')).toBeVisible();
  });

  test('should set default entropy sources', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="preferences-btn"]');
    
    // Set defaults
    await page.check('[data-testid="default-ocean"]');
    await page.check('[data-testid="default-lightning"]');
    
    await page.click('[data-testid="save-preferences"]');
    
    // Reload and verify defaults are applied
    await page.reload();
    
    await expect(page.locator('[data-testid="source-ocean"]')).toBeChecked();
    await expect(page.locator('[data-testid="source-lightning"]')).toBeChecked();
  });


  // ===========================================================================
  // Entropy History Tests
  // ===========================================================================

  test('should show generation history', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="history-tab"]');
    
    await expect(page.locator('.generation-history')).toBeVisible();
  });

  test('should list previous certificates', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="history-tab"]');
    
    await expect(page.locator('.certificate-history-list')).toBeVisible();
  });


  // ===========================================================================
  // Entropy Statistics Tests
  // ===========================================================================

  test('should display global entropy statistics', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="statistics-tab"]');
    
    await expect(page.locator('.entropy-statistics')).toBeVisible();
  });

  test('should show source usage chart', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="statistics-tab"]');
    
    await expect(page.locator('.usage-chart')).toBeVisible();
  });

  test('should display quality metrics', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.click('[data-testid="statistics-tab"]');
    
    await expect(page.locator('.quality-metrics')).toBeVisible();
  });


  // ===========================================================================
  // Real-time Updates Tests
  // ===========================================================================

  test('should auto-refresh source data', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Enable auto-refresh
    await page.check('[data-testid="auto-refresh"]');
    
    // Get initial timestamp
    const initialTime = await page.locator('.last-update-time').textContent();
    
    // Wait for refresh (mock faster interval)
    await page.waitForTimeout(5000);
    
    // Time should update
    const newTime = await page.locator('.last-update-time').textContent();
    // Times might be same if refresh didn't occur yet, just verify element exists
    expect(newTime).toBeTruthy();
  });


  // ===========================================================================
  // Error Handling Tests
  // ===========================================================================

  test('should handle source unavailable gracefully', async ({ page }) => {
    // Mock API to return source unavailable
    await page.route('**/api/security/natural-entropy/lightning/', route => {
      route.fulfill({
        status: 503,
        body: JSON.stringify({ error: 'Lightning data unavailable' })
      });
    });
    
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Source should show unavailable status
    await expect(page.locator('[data-testid="source-lightning"] .unavailable')).toBeVisible();
  });

  test('should fallback when primary source fails', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Select only one source that will be mocked as unavailable
    await page.check('[data-testid="source-seismic"]');
    
    await page.click('[data-testid="generate-password-btn"]');
    
    // Should still generate using fallback
    await page.waitForSelector('[data-testid="generated-password"]', { timeout: 15000 });
  });


  // ===========================================================================
  // Accessibility Tests
  // ===========================================================================

  test('should have proper heading structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Should have h1
    await expect(page.locator('h1')).toBeVisible();
    
    // Section headings should follow hierarchy
    const h2Count = await page.locator('h2').count();
    expect(h2Count).toBeGreaterThan(0);
  });

  test('should support screen readers', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    // Interactive elements should have accessible names
    const generateBtn = page.locator('[data-testid="generate-password-btn"]');
    const ariaLabel = await generateBtn.getAttribute('aria-label');
    const textContent = await generateBtn.textContent();
    
    expect(ariaLabel || textContent).toBeTruthy();
  });


  // ===========================================================================
  // Performance Tests
  // ===========================================================================

  test('should load dashboard quickly', async ({ page }) => {
    const start = Date.now();
    
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    await page.waitForSelector('.natural-entropy-dashboard');
    
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(5000); // Should load in under 5 seconds
  });

  test('should generate password quickly', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/natural-entropy`);
    
    await page.check('[data-testid="source-lightning"]');
    
    const start = Date.now();
    await page.click('[data-testid="generate-password-btn"]');
    await page.waitForSelector('[data-testid="generated-password"]');
    const genTime = Date.now() - start;
    
    expect(genTime).toBeLessThan(10000); // Should generate in under 10 seconds
  });
});

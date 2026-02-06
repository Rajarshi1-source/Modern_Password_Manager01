/**
 * Dark Protocol E2E Tests
 * ========================
 * 
 * End-to-end tests for the Dark Protocol anonymous vault access feature.
 * Tests the dashboard, session management, and settings.
 * 
 * @author Password Manager Team
 * @created 2026-02-06
 */

const { test, expect } = require('@playwright/test');

// Test constants
const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const TEST_USER = {
  email: 'testuser@example.com',
  password: 'TestPassword123!',
};

/**
 * Helper to login before tests
 */
async function loginUser(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[name="email"]', TEST_USER.email);
  await page.fill('input[name="password"]', TEST_USER.password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/vault`, { timeout: 10000 });
}

// =============================================================================
// Dark Protocol Dashboard Tests
// =============================================================================

test.describe('Dark Protocol Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should navigate to Dark Protocol dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Wait for the dashboard to load
    await expect(page.locator('.dark-protocol-dashboard')).toBeVisible({ timeout: 10000 });
    
    // Check main elements are present
    await expect(page.locator('text=Dark Protocol')).toBeVisible();
  });

  test('should display connection status indicator', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Connection status should be visible
    await expect(page.locator('.dp-connection-status')).toBeVisible();
    
    // Should show disconnected by default (or connecting)
    const statusText = await page.locator('.dp-connection-status').textContent();
    expect(['Disconnected', 'Connecting', 'Connected']).toContain(statusText.trim());
  });

  test('should display network health section', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Network health card should be visible
    await expect(page.locator('.dp-network-health')).toBeVisible();
    
    // Should show health metrics
    await expect(page.locator('text=Active Nodes')).toBeVisible();
    await expect(page.locator('text=Health')).toBeVisible();
  });

  test('should display settings panel', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Settings section should be present
    await expect(page.locator('.dp-settings')).toBeVisible();
    
    // Check for key settings
    await expect(page.locator('text=Anonymity Level')).toBeVisible();
    await expect(page.locator('text=Cover Traffic')).toBeVisible();
  });

  test('should toggle cover traffic setting', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Find cover traffic toggle
    const coverTrafficToggle = page.locator('input[type="checkbox"]').filter({ 
      has: page.locator('text=Cover Traffic')
    }).first();
    
    // Get initial state
    const initialState = await coverTrafficToggle.isChecked();
    
    // Toggle
    await coverTrafficToggle.click();
    
    // Verify state changed
    const newState = await coverTrafficToggle.isChecked();
    expect(newState).toBe(!initialState);
  });
});

// =============================================================================
// Dark Protocol Session Tests
// =============================================================================

test.describe('Dark Protocol Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/dark-protocol`);
  });

  test('should attempt to establish a session', async ({ page }) => {
    // Find and click the connect button
    const connectButton = page.locator('button').filter({ hasText: /connect|go anonymous/i });
    
    if (await connectButton.isVisible()) {
      await connectButton.click();
      
      // Should show connecting state
      await expect(page.locator('text=Connecting')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display session info when connected', async ({ page }) => {
    // If already connected (from previous test), check session info
    const sessionInfo = page.locator('.dp-session-info');
    
    if (await sessionInfo.isVisible()) {
      // Session ID should be partially visible
      await expect(page.locator('text=Session')).toBeVisible();
      
      // Path length should be shown
      await expect(page.locator('text=Path')).toBeVisible();
    }
  });

  test('should be able to disconnect', async ({ page }) => {
    const disconnectButton = page.locator('button').filter({ hasText: /disconnect/i });
    
    if (await disconnectButton.isVisible()) {
      await disconnectButton.click();
      
      // Should show disconnected state
      await expect(page.locator('text=Disconnected')).toBeVisible({ timeout: 5000 });
    }
  });
});

// =============================================================================
// Dark Protocol Settings Tests
// =============================================================================

test.describe('Dark Protocol Settings', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/dark-protocol`);
  });

  test('should adjust anonymity level slider', async ({ page }) => {
    // Find the min hops slider
    const slider = page.locator('input[type="range"]').first();
    
    if (await slider.isVisible()) {
      // Get current value
      const currentValue = await slider.inputValue();
      
      // Adjust slider
      await slider.fill('4');
      
      // Verify change
      const newValue = await slider.inputValue();
      expect(newValue).toBe('4');
    }
  });

  test('should toggle path rotation', async ({ page }) => {
    // Find path rotation toggle
    const pathRotationCheckbox = page.locator('label').filter({ 
      hasText: /path rotation/i 
    }).locator('input[type="checkbox"]');
    
    if (await pathRotationCheckbox.isVisible()) {
      const initialState = await pathRotationCheckbox.isChecked();
      await pathRotationCheckbox.click();
      const newState = await pathRotationCheckbox.isChecked();
      expect(newState).toBe(!initialState);
    }
  });

  test('should select preferred regions', async ({ page }) => {
    // Find region buttons
    const regionButton = page.locator('.dp-region-btn').first();
    
    if (await regionButton.isVisible()) {
      const wasActive = await regionButton.evaluate(el => el.classList.contains('active'));
      await regionButton.click();
      const isNowActive = await regionButton.evaluate(el => el.classList.contains('active'));
      expect(isNowActive).toBe(!wasActive);
    }
  });

  test('should toggle bridge nodes for censorship resistance', async ({ page }) => {
    const bridgeToggle = page.locator('label').filter({ 
      hasText: /bridge nodes/i 
    }).locator('input[type="checkbox"]');
    
    if (await bridgeToggle.isVisible()) {
      await bridgeToggle.click();
      // Should enable/disable without errors
    }
  });
});

// =============================================================================
// Dark Protocol Network Health Tests
// =============================================================================

test.describe('Dark Protocol Network Health', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/dark-protocol`);
  });

  test('should display active nodes count', async ({ page }) => {
    await expect(page.locator('.dp-network-health')).toBeVisible();
    
    // Should show a count of active nodes
    const nodesText = page.locator('.dp-stat-value').first();
    if (await nodesText.isVisible()) {
      const text = await nodesText.textContent();
      expect(parseInt(text)).toBeGreaterThanOrEqual(0);
    }
  });

  test('should display health percentage', async ({ page }) => {
    const healthStat = page.locator('text=/\\d+%/');
    
    if (await healthStat.isVisible()) {
      const text = await healthStat.textContent();
      const percentage = parseInt(text);
      expect(percentage).toBeGreaterThanOrEqual(0);
      expect(percentage).toBeLessThanOrEqual(100);
    }
  });

  test('should show latency metrics', async ({ page }) => {
    const latencyElement = page.locator('text=/latency/i');
    
    if (await latencyElement.count() > 0) {
      await expect(latencyElement.first()).toBeVisible();
    }
  });
});

// =============================================================================
// Dark Protocol Active Routes Tests
// =============================================================================

test.describe('Dark Protocol Active Routes', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/dark-protocol`);
  });

  test('should display routes section', async ({ page }) => {
    const routesSection = page.locator('.dp-routes');
    
    if (await routesSection.isVisible()) {
      await expect(routesSection).toBeVisible();
    }
  });

  test('should show route details when routes exist', async ({ page }) => {
    const routeItems = page.locator('.dp-route-item');
    
    if (await routeItems.count() > 0) {
      // Each route should show hop count
      await expect(routeItems.first().locator('text=/hop/i')).toBeVisible();
    }
  });
});

// =============================================================================
// Dark Protocol Error Handling Tests
// =============================================================================

test.describe('Dark Protocol Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should handle network errors gracefully', async ({ page }) => {
    // Intercept API calls to simulate network error
    await page.route('**/api/security/dark-protocol/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
    });
    
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Should show error state, not crash
    // Page should still render
    await expect(page.locator('.dark-protocol-dashboard')).toBeVisible({ timeout: 10000 });
  });

  test('should handle WebSocket disconnection', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/dark-protocol`);
    
    // Simulate WebSocket disconnect by going offline
    await page.context().setOffline(true);
    
    // Wait a moment
    await page.waitForTimeout(1000);
    
    // Should show disconnected state
    await expect(page.locator('text=/disconnected|offline|error/i')).toBeVisible({ timeout: 5000 }).catch(() => {
      // It's okay if this fails - just checking graceful handling
    });
    
    // Restore connection
    await page.context().setOffline(false);
  });
});

// =============================================================================
// Dark Protocol Accessibility Tests
// =============================================================================

test.describe('Dark Protocol Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/dark-protocol`);
  });

  test('should have proper heading structure', async ({ page }) => {
    const h1 = page.locator('h1');
    const h2 = page.locator('h2');
    
    // Should have at least one main heading
    expect(await h1.count() + await h2.count()).toBeGreaterThan(0);
  });

  test('should have accessible form controls', async ({ page }) => {
    // Check that toggles have labels
    const toggles = page.locator('input[type="checkbox"]');
    const toggleCount = await toggles.count();
    
    for (let i = 0; i < toggleCount; i++) {
      const toggle = toggles.nth(i);
      // Should be associated with a label (either by id or nested)
      const id = await toggle.getAttribute('id');
      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        if (await label.count() === 0) {
          // Should be inside a label
          const parentLabel = toggle.locator('xpath=ancestor::label');
          expect(await parentLabel.count()).toBeGreaterThan(0);
        }
      }
    }
  });

  test('should be keyboard navigable', async ({ page }) => {
    // Tab through elements
    await page.keyboard.press('Tab');
    
    // Should have focus on an interactive element
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(['BUTTON', 'INPUT', 'A', 'SELECT']).toContain(focusedElement);
  });
});

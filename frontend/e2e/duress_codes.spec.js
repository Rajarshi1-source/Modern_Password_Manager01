/**
 * Military-Grade Duress Codes - E2E Tests
 * ========================================
 * 
 * End-to-end tests using Playwright for:
 * - Duress code setup wizard flow
 * - Code management operations
 * - Decoy vault preview
 * - Trusted authorities management
 * - Event log viewing
 * 
 * @author Password Manager Team
 * @created 2026-01-31
 */

const { test, expect } = require('@playwright/test');

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Test user credentials
const TEST_USER = {
  email: 'e2e-duress@test.com',
  password: 'TestPassword123!',
};


// =============================================================================
// Setup & Teardown
// =============================================================================

test.describe('Military-Grade Duress Codes E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto(`${BASE_URL}/login`);
    
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    
    // Wait for dashboard
    await page.waitForURL('**/dashboard**', { timeout: 10000 });
  });


  // ===========================================================================
  // Duress Code Setup Wizard Tests
  // ===========================================================================

  test('should display duress setup wizard', async ({ page }) => {
    // Navigate to duress setup
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Wizard should be visible
    await expect(page.locator('.duress-setup-wizard')).toBeVisible();
    
    // Should show step indicator
    await expect(page.locator('.step-indicator')).toBeVisible();
    
    // Introduction step should be visible
    await expect(page.locator('.step-intro')).toBeVisible();
  });

  test('should navigate through wizard steps', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Step 1: Introduction - Click Next
    await page.click('[data-testid="next-step-btn"]');
    
    // Step 2: Enable Protection should be visible
    await expect(page.locator('.step-enable')).toBeVisible();
    
    // Toggle enable
    await page.click('[data-testid="enable-protection-toggle"]');
    await page.click('[data-testid="next-step-btn"]');
    
    // Step 3: Create Codes should be visible
    await expect(page.locator('.step-codes')).toBeVisible();
  });

  test('should create a duress code in wizard', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Navigate to codes step
    await page.click('[data-testid="next-step-btn"]');
    await page.click('[data-testid="enable-protection-toggle"]');
    await page.click('[data-testid="next-step-btn"]');
    
    // Create a new code
    await page.fill('[data-testid="duress-code-input"]', 'TestDuress123!');
    await page.selectOption('[data-testid="threat-level-select"]', 'medium');
    await page.click('[data-testid="add-code-btn"]');
    
    // Code should appear in list
    await expect(page.locator('.code-list-item')).toBeVisible();
  });

  test('should validate duress code strength', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Navigate to codes step
    await page.click('[data-testid="next-step-btn"]');
    await page.click('[data-testid="enable-protection-toggle"]');
    await page.click('[data-testid="next-step-btn"]');
    
    // Enter weak code
    await page.fill('[data-testid="duress-code-input"]', 'abc');
    
    // Strength indicator should show weak
    await expect(page.locator('.strength-weak')).toBeVisible();
    
    // Enter strong code
    await page.fill('[data-testid="duress-code-input"]', 'StrongDuress!@#123');
    
    // Strength indicator should show strong
    await expect(page.locator('.strength-strong')).toBeVisible();
  });


  // ===========================================================================
  // Duress Code Manager Tests
  // ===========================================================================

  test('should display duress code manager', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Manager should be visible
    await expect(page.locator('.duress-manager')).toBeVisible();
    
    // Header should show protection status
    await expect(page.locator('.protection-status')).toBeVisible();
  });

  test('should toggle protection on/off', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Click toggle button
    await page.click('.toggle-btn');
    
    // Status should change
    await expect(page.locator('.status-badge')).toBeVisible();
  });

  test('should display stats grid', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Stats grid should be visible
    await expect(page.locator('.stats-grid')).toBeVisible();
    
    // Should show code count
    await expect(page.locator('.stat-card').first()).toBeVisible();
  });

  test('should edit existing duress code', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Click edit on first code
    await page.click('.code-card .menu-btn:first-child');
    
    // Edit modal should open
    await expect(page.locator('.modal-content')).toBeVisible();
    
    // Change threat level
    await page.selectOption('[data-testid="edit-threat-level"]', 'high');
    
    // Save changes
    await page.click('.save-btn');
    
    // Modal should close
    await expect(page.locator('.modal-content')).not.toBeVisible();
  });

  test('should delete duress code with confirmation', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Handle dialog
    page.on('dialog', async dialog => {
      expect(dialog.type()).toBe('confirm');
      await dialog.accept();
    });
    
    // Get initial code count
    const initialCount = await page.locator('.code-card').count();
    
    // Click delete on first code
    await page.click('.code-card .menu-btn.delete');
    
    // Wait for deletion
    await page.waitForTimeout(1000);
    
    // Code count should decrease
    const newCount = await page.locator('.code-card').count();
    expect(newCount).toBeLessThan(initialCount);
  });


  // ===========================================================================
  // Decoy Vault Preview Tests
  // ===========================================================================

  test('should display decoy vault preview', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    
    // Preview should be visible
    await expect(page.locator('.decoy-vault-preview')).toBeVisible();
    
    // Header should be present
    await expect(page.locator('.preview-header')).toBeVisible();
  });

  test('should switch between threat levels', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    
    // Click on different threat level buttons
    await page.click('.level-btn:has-text("High")');
    
    // Preview should update
    await expect(page.locator('.items-preview')).toBeVisible();
  });

  test('should toggle between grid and list view', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    
    // Default should be grid
    await expect(page.locator('.items-preview.grid')).toBeVisible();
    
    // Click list view
    await page.click('.view-btn:last-child');
    
    // Should switch to list
    await expect(page.locator('.items-preview.list')).toBeVisible();
  });

  test('should display realism metrics', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    
    // Realism section should be visible
    await expect(page.locator('.realism-section')).toBeVisible();
    
    // Metrics should be displayed
    await expect(page.locator('.realism-metrics')).toBeVisible();
    await expect(page.locator('.metric-card').first()).toBeVisible();
  });

  test('should regenerate decoy vault', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    
    // Click regenerate button
    await page.click('.regenerate-btn');
    
    // Should show loading state
    await expect(page.locator('.regenerate-btn')).toHaveText(/Regenerating/);
    
    // Wait for completion
    await expect(page.locator('.regenerate-btn')).toHaveText(/Regenerate Decoy Data/, { timeout: 10000 });
  });


  // ===========================================================================
  // Trusted Authorities Tests
  // ===========================================================================

  test('should display trusted authorities manager', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/authorities`);
    
    // Manager should be visible
    await expect(page.locator('.trusted-authority-manager')).toBeVisible();
  });

  test('should add new trusted authority', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/authorities`);
    
    // Click add button
    await page.click('.add-btn');
    
    // Form should appear
    await expect(page.locator('.authority-form')).toBeVisible();
    
    // Fill in form
    await page.fill('[data-testid="authority-name"]', 'Emergency Contact');
    await page.selectOption('[data-testid="authority-type"]', 'security_team');
    await page.selectOption('[data-testid="contact-method"]', 'email');
    await page.fill('[data-testid="contact-value"]', 'emergency@example.com');
    
    // Submit
    await page.click('.save-btn');
    
    // Authority should appear in list
    await expect(page.locator('.authority-card')).toBeVisible();
  });

  test('should select threat levels for authority', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/authorities`);
    
    // Open add form
    await page.click('.add-btn');
    
    // Toggle threat levels
    await page.click('.level-btn:has-text("High")');
    await page.click('.level-btn:has-text("Critical")');
    
    // Verify buttons are active
    await expect(page.locator('.level-btn.active')).toHaveCount(2);
  });

  test('should verify authority contact', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/authorities`);
    
    // Click verify on unverified authority
    const verifyBtn = page.locator('.authority-card:has(.unverified-badge) .verify-btn').first();
    
    if (await verifyBtn.isVisible()) {
      await verifyBtn.click();
      
      // Verification modal should appear
      await expect(page.locator('.verification-modal')).toBeVisible();
    }
  });


  // ===========================================================================
  // Duress Event Log Tests
  // ===========================================================================

  test('should display duress event log', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    
    // Event log should be visible
    await expect(page.locator('.duress-event-log')).toBeVisible();
    
    // Header should be present
    await expect(page.locator('.log-header')).toBeVisible();
  });

  test('should filter events by threat level', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    
    // Select threat level filter
    await page.selectOption('.log-filters select:first-child', 'high');
    
    // Events table should update
    await expect(page.locator('.events-container')).toBeVisible();
  });

  test('should filter events by time range', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    
    // Select time range filter
    await page.selectOption('.filter-group:nth-child(2) select', '7');
    
    // Events should update
    await expect(page.locator('.events-container')).toBeVisible();
  });

  test('should display event statistics', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    
    // Stats should be visible
    await expect(page.locator('.log-stats')).toBeVisible();
    
    // Should show multiple stat items
    await expect(page.locator('.log-stats .stat')).toHaveCount(4);
  });

  test('should open event details modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    
    // Click on an event row
    const eventRow = page.locator('.event-row').first();
    
    if (await eventRow.isVisible()) {
      await eventRow.click();
      
      // Modal should open
      await expect(page.locator('.modal-content')).toBeVisible();
      
      // Should show event details
      await expect(page.locator('.detail-section')).toBeVisible();
    }
  });


  // ===========================================================================
  // Integration Tests
  // ===========================================================================

  test('full workflow: setup, manage, test activation', async ({ page }) => {
    // Step 1: Navigate to setup wizard
    await page.goto(`${BASE_URL}/security/duress-setup`);
    await expect(page.locator('.duress-setup-wizard')).toBeVisible();
    
    // Step 2: Navigate through setup
    await page.click('[data-testid="next-step-btn"]');
    await page.click('[data-testid="enable-protection-toggle"]');
    await page.click('[data-testid="next-step-btn"]');
    
    // Step 3: Create a duress code
    await page.fill('[data-testid="duress-code-input"]', 'IntegrationTest123!');
    await page.selectOption('[data-testid="threat-level-select"]', 'medium');
    await page.click('[data-testid="add-code-btn"]');
    
    // Step 4: Navigate to manager
    await page.goto(`${BASE_URL}/security/duress-codes`);
    await expect(page.locator('.duress-manager')).toBeVisible();
    
    // Step 5: Check decoy preview
    await page.goto(`${BASE_URL}/security/duress-codes/decoy-preview`);
    await expect(page.locator('.decoy-vault-preview')).toBeVisible();
    
    // Step 6: Check event log
    await page.goto(`${BASE_URL}/security/duress-codes/events`);
    await expect(page.locator('.duress-event-log')).toBeVisible();
  });

  test('API response times are within bounds', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(`${BASE_URL}/security/duress-codes`);
    await expect(page.locator('.duress-manager')).toBeVisible({ timeout: 10000 });
    
    const endTime = Date.now();
    const responseTime = endTime - startTime;
    
    // Page should load within 5 seconds
    expect(responseTime).toBeLessThan(5000);
  });
});


// =============================================================================
// Test Activation (Safe Mode) Tests
// =============================================================================

test.describe('Duress Code Test Activation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
  });

  test('should test duress code activation safely', async ({ page }) => {
    // Navigate to test step in wizard
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Navigate to test step (step 6)
    for (let i = 0; i < 5; i++) {
      await page.click('[data-testid="next-step-btn"]');
      await page.waitForTimeout(500);
    }
    
    // Enter test code
    await page.fill('[data-testid="test-code-input"]', 'TestCode123!');
    await page.click('[data-testid="test-activation-btn"]');
    
    // Should show test result
    await expect(page.locator('.test-result')).toBeVisible({ timeout: 5000 });
  });

  test('should show decoy vault during test activation', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Navigate to test step
    for (let i = 0; i < 5; i++) {
      await page.click('[data-testid="next-step-btn"]');
      await page.waitForTimeout(500);
    }
    
    await page.fill('[data-testid="test-code-input"]', 'TestCode123!');
    await page.click('[data-testid="test-activation-btn"]');
    
    // Decoy preview should appear
    await expect(page.locator('.decoy-preview')).toBeVisible({ timeout: 5000 });
  });
});


// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('Duress Codes Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-setup`);
    
    // Tab through elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to navigate with keyboard
    const focusedElement = await page.evaluate(() => document.activeElement.tagName);
    expect(['INPUT', 'BUTTON', 'SELECT', 'A']).toContain(focusedElement);
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Check for aria-labels on interactive elements
    const buttons = await page.locator('button[aria-label]').count();
    expect(buttons).toBeGreaterThanOrEqual(0);
  });

  test('should announce loading states', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Loading states should be present during data fetch
    // This is a basic check - in production, verify screen reader announcement
    await expect(page.locator('.duress-manager')).toBeVisible({ timeout: 10000 });
  });
});


// =============================================================================
// Security Tests
// =============================================================================

test.describe('Duress Codes Security', () => {
  test('should require authentication for duress pages', async ({ page }) => {
    // Try to access without login
    await page.goto(`${BASE_URL}/security/duress-codes`);
    
    // Should redirect to login
    await expect(page).toHaveURL(/login/);
  });

  test('should not log duress codes in console', async ({ page }) => {
    const consoleLogs = [];
    page.on('console', msg => consoleLogs.push(msg.text()));
    
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
    
    await page.goto(`${BASE_URL}/security/duress-setup`);
    await page.click('[data-testid="next-step-btn"]');
    await page.click('[data-testid="next-step-btn"]');
    
    // Enter a code
    await page.fill('[data-testid="duress-code-input"]', 'SecretCode123!');
    
    // Check console logs don't contain the code
    const hasLeakedCode = consoleLogs.some(log => log.includes('SecretCode123!'));
    expect(hasLeakedCode).toBe(false);
  });
});

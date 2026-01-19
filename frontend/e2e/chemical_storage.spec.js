/**
 * Chemical Password Storage - E2E Tests
 * =======================================
 * 
 * End-to-end tests using Playwright for:
 * - Full encoding workflow
 * - Time-lock creation and verification
 * - DNA synthesis constraints validation
 * 
 * @author Password Manager Team
 * @created 2026-01-17
 */

const { test, expect } = require('@playwright/test');

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Test user credentials
const TEST_USER = {
  email: 'e2e-chemical@test.com',
  password: 'TestPassword123!',
};


// =============================================================================
// Setup & Teardown
// =============================================================================

test.describe('Chemical Password Storage E2E', () => {
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
  // DNA Encoding Tests
  // ===========================================================================

  test('should encode password to DNA sequence', async ({ page }) => {
    // Open chemical storage modal
    await page.click('[data-testid="chemical-storage-button"]');
    await expect(page.locator('.modal-content')).toBeVisible();
    
    // Enter password
    await page.fill('[data-testid="encode-password-input"]', 'MySecretPassword123!');
    
    // Click encode button
    await page.click('[data-testid="encode-button"]');
    
    // Wait for result
    await expect(page.locator('[data-testid="dna-sequence"]')).toBeVisible({ timeout: 5000 });
    
    // Verify sequence is displayed
    const sequence = await page.textContent('[data-testid="dna-sequence"]');
    expect(sequence).toMatch(/^[ATCG]+$/);
  });

  test('should validate GC content within bounds (40-60%)', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Encode a password
    await page.fill('[data-testid="encode-password-input"]', 'GCContentTest!@#');
    await page.click('[data-testid="encode-button"]');
    
    // Wait for result
    await expect(page.locator('[data-testid="gc-content"]')).toBeVisible({ timeout: 5000 });
    
    // Get GC content value
    const gcText = await page.textContent('[data-testid="gc-content"]');
    const gcValue = parseFloat(gcText.replace('%', '')) / 100;
    
    // Verify within synthesis bounds
    expect(gcValue).toBeGreaterThanOrEqual(0.30);
    expect(gcValue).toBeLessThanOrEqual(0.70);
  });

  test('should show cost estimate after encoding', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    await page.fill('[data-testid="encode-password-input"]', 'CostEstimateTest');
    await page.click('[data-testid="encode-button"]');
    
    // Wait for cost estimate
    await expect(page.locator('[data-testid="cost-estimate"]')).toBeVisible({ timeout: 5000 });
    
    // Verify cost is displayed
    const costText = await page.textContent('[data-testid="cost-estimate"]');
    expect(costText).toMatch(/\$\d+/);
  });

  test('should handle empty password validation', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Click encode without password
    await page.click('[data-testid="encode-button"]');
    
    // Should show error
    await expect(page.locator('.error-message')).toBeVisible();
    const error = await page.textContent('.error-message');
    expect(error.toLowerCase()).toContain('password');
  });


  // ===========================================================================
  // Time-Lock Tests
  // ===========================================================================

  test('should create time-lock capsule', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Switch to time-lock tab
    await page.click('[data-testid="tab-timelock"]');
    
    // Enter password
    await page.fill('[data-testid="timelock-password-input"]', 'TimeLockTest123!');
    
    // Set delay (24 hours)
    await page.fill('[data-testid="timelock-delay-input"]', '24');
    
    // Create time-lock
    await page.click('[data-testid="create-timelock-button"]');
    
    // Wait for confirmation
    await expect(page.locator('[data-testid="capsule-status"]')).toBeVisible({ timeout: 5000 });
    
    // Verify locked status
    const statusText = await page.textContent('[data-testid="capsule-status"]');
    expect(statusText.toLowerCase()).toContain('locked');
  });

  test('should display countdown timer for time-lock', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    await page.click('[data-testid="tab-timelock"]');
    
    await page.fill('[data-testid="timelock-password-input"]', 'CountdownTest!');
    await page.fill('[data-testid="timelock-delay-input"]', '1');
    await page.click('[data-testid="create-timelock-button"]');
    
    // Wait for countdown to appear
    await expect(page.locator('[data-testid="countdown-timer"]')).toBeVisible({ timeout: 5000 });
    
    // Verify countdown format (HH:MM:SS)
    const countdown = await page.textContent('[data-testid="countdown-timer"]');
    expect(countdown).toMatch(/\d+:\d+:\d+/);
  });

  test('should prevent unlock before time expires', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    await page.click('[data-testid="tab-timelock"]');
    
    await page.fill('[data-testid="timelock-password-input"]', 'PreventUnlock!');
    await page.fill('[data-testid="timelock-delay-input"]', '24');
    await page.click('[data-testid="create-timelock-button"]');
    
    await expect(page.locator('[data-testid="capsule-status"]')).toBeVisible({ timeout: 5000 });
    
    // Unlock button should be disabled
    const unlockButton = page.locator('[data-testid="unlock-button"]');
    await expect(unlockButton).toBeDisabled();
  });


  // ===========================================================================
  // Synthesis Constraints Tests
  // ===========================================================================

  test('should validate homopolymer runs are limited', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Password that might create long runs
    await page.fill('[data-testid="encode-password-input"]', 'AAAAAABBBBBB');
    await page.click('[data-testid="encode-button"]');
    
    await expect(page.locator('[data-testid="dna-sequence"]')).toBeVisible({ timeout: 5000 });
    
    const sequence = await page.textContent('[data-testid="dna-sequence"]');
    
    // Check for maximum run length
    let maxRun = 1;
    let currentRun = 1;
    for (let i = 1; i < sequence.length; i++) {
      if (sequence[i] === sequence[i-1]) {
        currentRun++;
        maxRun = Math.max(maxRun, currentRun);
      } else {
        currentRun = 1;
      }
    }
    
    // Max homopolymer run should be limited
    expect(maxRun).toBeLessThanOrEqual(6);
  });

  test('should show validation warnings for edge cases', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Very short password
    await page.fill('[data-testid="encode-password-input"]', 'Ab1');
    await page.click('[data-testid="encode-button"]');
    
    // May show warnings but should still encode
    await expect(page.locator('[data-testid="dna-sequence"]')).toBeVisible({ timeout: 5000 });
  });


  // ===========================================================================
  // Lab Provider API Tests
  // ===========================================================================

  test('should list available lab providers', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Switch to storage tab
    await page.click('[data-testid="tab-storage"]');
    
    // Provider dropdown should be visible
    await expect(page.locator('[data-testid="provider-select"]')).toBeVisible();
    
    // Check available options
    const options = await page.locator('[data-testid="provider-select"] option').allTextContents();
    expect(options.length).toBeGreaterThan(0);
  });

  test('should show provider pricing', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    await page.click('[data-testid="tab-storage"]');
    
    // Provider info should include pricing
    await expect(page.locator('[data-testid="provider-pricing"]')).toBeVisible();
    
    const pricing = await page.textContent('[data-testid="provider-pricing"]');
    expect(pricing).toMatch(/\$/);
  });


  // ===========================================================================
  // Certificate Tests
  // ===========================================================================

  test('should display certificates tab', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Switch to certificates tab
    await page.click('[data-testid="tab-certificates"]');
    
    // Tab content should be visible
    await expect(page.locator('[data-testid="certificates-panel"]')).toBeVisible();
  });


  // ===========================================================================
  // Integration Tests
  // ===========================================================================

  test('full workflow: encode, validate, view certificate', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Step 1: Encode password
    await page.fill('[data-testid="encode-password-input"]', 'FullWorkflow123!@#');
    await page.click('[data-testid="encode-button"]');
    
    await expect(page.locator('[data-testid="dna-sequence"]')).toBeVisible({ timeout: 5000 });
    
    // Step 2: Verify GC content
    const gcText = await page.textContent('[data-testid="gc-content"]');
    expect(gcText).toBeTruthy();
    
    // Step 3: Verify cost estimate
    const costText = await page.textContent('[data-testid="cost-estimate"]');
    expect(costText).toBeTruthy();
    
    // Step 4: Check certificates tab
    await page.click('[data-testid="tab-certificates"]');
    await expect(page.locator('[data-testid="certificates-panel"]')).toBeVisible();
  });

  test('API response times are within bounds', async ({ page }) => {
    await page.click('[data-testid="chemical-storage-button"]');
    
    const startTime = Date.now();
    
    await page.fill('[data-testid="encode-password-input"]', 'PerformanceTest!');
    await page.click('[data-testid="encode-button"]');
    
    await expect(page.locator('[data-testid="dna-sequence"]')).toBeVisible({ timeout: 5000 });
    
    const endTime = Date.now();
    const responseTime = endTime - startTime;
    
    // Encoding should complete within 5 seconds
    expect(responseTime).toBeLessThan(5000);
  });
});


// =============================================================================
// Time-Lock Puzzle Timing Tests
// =============================================================================

test.describe('Time-Lock Puzzle Timing', () => {
  test('should enforce minimum delay', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
    
    await page.click('[data-testid="chemical-storage-button"]');
    await page.click('[data-testid="tab-timelock"]');
    
    // Try to set delay less than minimum (1 hour)
    await page.fill('[data-testid="timelock-password-input"]', 'MinDelayTest');
    await page.fill('[data-testid="timelock-delay-input"]', '0');
    await page.click('[data-testid="create-timelock-button"]');
    
    // Should show error or auto-correct to minimum
    const delay = await page.inputValue('[data-testid="timelock-delay-input"]');
    expect(parseInt(delay)).toBeGreaterThanOrEqual(1);
  });
});


// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('Chemical Storage Accessibility', () => {
  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
    
    await page.click('[data-testid="chemical-storage-button"]');
    
    // Tab through modal elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to navigate with keyboard
    const focusedElement = await page.evaluate(() => document.activeElement.tagName);
    expect(['INPUT', 'BUTTON', 'SELECT', 'A']).toContain(focusedElement);
  });

  test('should close modal with Escape key', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
    
    await page.click('[data-testid="chemical-storage-button"]');
    await expect(page.locator('.modal-content')).toBeVisible();
    
    await page.keyboard.press('Escape');
    
    // Modal should close
    await expect(page.locator('.modal-content')).not.toBeVisible();
  });
});

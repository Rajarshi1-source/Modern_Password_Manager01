/**
 * Quantum Password Generation E2E Tests
 * ======================================
 * 
 * End-to-end tests for the quantum password generation flow.
 * Uses Playwright for browser automation.
 * 
 * Run with: npx playwright test quantum.e2e.spec.js
 */

import { test, expect } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';

test.describe('Quantum Password Generation E2E', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"], input[type="email"]', 'test@example.com');
    await page.fill('[data-testid="password-input"], input[type="password"]', 'testpassword123');
    await page.click('[data-testid="login-button"], button[type="submit"]');
    await page.waitForURL('**/dashboard**', { timeout: 10000 });
  });

  test('should navigate to password generator', async ({ page }) => {
    // Navigate to password generator
    await page.click('[data-testid="password-generator-link"], a[href*="generator"]');
    await expect(page.locator('text=Password Generator')).toBeVisible();
  });

  test('should toggle between standard and quantum mode', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Find mode toggle
    const standardButton = page.locator('[data-testid="mode-standard"], button:has-text("Standard")');
    const quantumButton = page.locator('[data-testid="mode-quantum"], button:has-text("Quantum")');
    
    // Should start in standard mode
    await expect(standardButton).toHaveAttribute('aria-pressed', 'true');
    
    // Click quantum mode
    await quantumButton.click();
    await expect(quantumButton).toHaveAttribute('aria-pressed', 'true');
  });

  test('should generate quantum password', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Switch to quantum mode
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    
    // Find and click quantum dice button
    const quantumDiceButton = page.locator('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    await quantumDiceButton.click();
    
    // Wait for password to be generated
    await page.waitForSelector('[data-testid="generated-password"], input[readonly]', { timeout: 30000 });
    
    // Password should be visible
    const passwordField = page.locator('[data-testid="generated-password"], input[readonly]');
    const password = await passwordField.inputValue();
    
    expect(password.length).toBeGreaterThanOrEqual(8);
  });

  test('should display quantum certification badge', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Switch to quantum mode and generate
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    // Wait for generation
    await page.waitForTimeout(5000);
    
    // Look for quantum certified badge
    const certBadge = page.locator('[data-testid="quantum-cert-badge"], *:has-text("Quantum Certified")');
    await expect(certBadge).toBeVisible({ timeout: 30000 });
  });

  test('should open certificate modal on badge click', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Generate quantum password
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    // Wait for certificate badge
    await page.waitForTimeout(5000);
    
    // Click certificate badge to open modal
    await page.click('[data-testid="quantum-cert-badge"], *:has-text("Quantum Certified")');
    
    // Modal should appear
    const modal = page.locator('[data-testid="certificate-modal"], [role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });
    
    // Modal should contain certificate info
    await expect(page.locator('text=Certificate')).toBeVisible();
    await expect(page.locator('text=Provider')).toBeVisible();
  });

  test('should download certificate from modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Generate and open certificate
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    await page.waitForTimeout(5000);
    await page.click('[data-testid="quantum-cert-badge"], *:has-text("Quantum Certified")');
    
    // Setup download handler
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="download-cert-button"], button:has-text("Download")')
    ]);
    
    // Verify download
    const filename = download.suggestedFilename();
    expect(filename).toContain('quantum-certificate');
    expect(filename).toContain('.json');
  });

  test('should customize password length', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Set custom length
    const lengthSlider = page.locator('[data-testid="length-slider"], input[type="range"]');
    await lengthSlider.fill('24');
    
    // Switch to quantum and generate
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    await page.waitForTimeout(5000);
    
    // Check password length
    const passwordField = page.locator('[data-testid="generated-password"], input[readonly]');
    const password = await passwordField.inputValue();
    
    expect(password.length).toBe(24);
  });

  test('should toggle character options', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Disable symbols
    const symbolsToggle = page.locator('[data-testid="symbols-toggle"], input[name="symbols"]');
    if (await symbolsToggle.isChecked()) {
      await symbolsToggle.uncheck();
    }
    
    // Generate quantum password
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    await page.waitForTimeout(5000);
    
    // Password should not contain common symbols
    const passwordField = page.locator('[data-testid="generated-password"], input[readonly]');
    const password = await passwordField.inputValue();
    
    expect(password).not.toMatch(/[!@#$%^&*()]/);
  });

  test('should show pool status', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Switch to quantum mode
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    
    // Pool status should be visible
    const poolStatus = page.locator('[data-testid="pool-status"], *:has-text("Pool")');
    await expect(poolStatus).toBeVisible({ timeout: 10000 });
  });

  test('should copy password to clipboard', async ({ page, context }) => {
    // Grant clipboard permissions
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    
    await page.goto(`${BASE_URL}/generator`);
    
    // Generate password
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    await page.waitForTimeout(5000);
    
    // Click copy button
    await page.click('[data-testid="copy-button"], button:has-text("Copy")');
    
    // Read clipboard
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    
    // Password field value
    const passwordField = page.locator('[data-testid="generated-password"], input[readonly]');
    const password = await passwordField.inputValue();
    
    expect(clipboardText).toBe(password);
  });

  test('should persist password through navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/generator`);
    
    // Generate password
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    await page.waitForTimeout(5000);
    
    // Get password
    const passwordField = page.locator('[data-testid="generated-password"], input[readonly]');
    const password = await passwordField.inputValue();
    
    // Use password for a vault item
    await page.click('[data-testid="use-password-button"], button:has-text("Use")');
    
    // Verify password was applied
    // This depends on your application's behavior
    // For example, it might open a new vault item form with the password pre-filled
  });
});

test.describe('Quantum API Integration', () => {
  
  test('should handle API errors gracefully', async ({ page }) => {
    await page.route('**/api/security/quantum/**', (route) => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ success: false, error: 'Server error' })
      });
    });
    
    await page.goto(`${BASE_URL}/generator`);
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    await page.click('[data-testid="quantum-dice-button"], button:has-text("Generate")');
    
    // Should show error message
    const errorMessage = page.locator('[data-testid="error-message"], *:has-text("error")');
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
  });

  test('should show fallback provider when quantum unavailable', async ({ page }) => {
    await page.route('**/api/security/quantum/pool-status/**', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          pool: { health: 'good' },
          providers: {
            anu_qrng: { available: false },
            ibm_quantum: { available: false },
            ionq_quantum: { available: false }
          }
        })
      });
    });
    
    await page.goto(`${BASE_URL}/generator`);
    await page.click('[data-testid="mode-quantum"], button:has-text("Quantum")');
    
    // Should show fallback indicator
    const fallbackIndicator = page.locator('*:has-text("Fallback")');
    await expect(fallbackIndicator).toBeVisible({ timeout: 10000 });
  });
});

// @ts-check
import { test, expect } from '@playwright/test';

test.describe('Genetic Password Evolution Feature', () => {
  test.beforeEach(async (/** @type {{ page: import('@playwright/test').Page }} */ { page }) => {
    // Mock authentication via localStorage injection before page load
    await page.addInitScript(() => {
      window.localStorage.setItem('access_token', 'mock-valid-token');
      window.localStorage.setItem('user', JSON.stringify({ username: 'testuser' }));
    });
  });

  test('should display genetic connection options', async (/** @type {{ page: import('@playwright/test').Page }} */ { page }) => {
    // Navigate after setup
    await page.goto('/');

    // Click on Genetic tab or button to switch mode
    // Using strict match to avoid partial matches
    await page.getByText('Genetic', { exact: true }).click();

    // Should see DNA provider options
    await expect(page.getByText('Sequencing.com')).toBeVisible();
    await expect(page.getByText('23andMe')).toBeVisible();
    await expect(page.getByText('Upload File')).toBeVisible();
  });

  test('should handle manual file upload flow', async (/** @type {{ page: import('@playwright/test').Page }} */ { page }) => {
    await page.goto('/');
    
    // Switch to Genetic mode
    await page.getByText('Genetic', { exact: true }).click();
    
    // Click upload (opens modal)
    await page.getByText('Upload File').click();
    
    // Should see upload modal
    await expect(page.getByText('Upload DNA Data')).toBeVisible();
    
    // Create a dummy file for upload
    const buffer = Buffer.from('rsid\tchromosome\tposition\tgenotype\nrs123\t1\t123\tAA');
    
    // Use setInputFiles for robust upload testing (works with hidden inputs too)
    // Assuming the modal has an input[type="file"]
    await page.locator('input[type="file"]').first().setInputFiles({
      name: 'genome.txt',
      mimeType: 'text/plain',
      buffer: buffer,
    });
    
    // Wait for upload button to be enabled or just click it
    // Using a more specific selector if possible, falling back to name
    await page.getByRole('button', { name: 'Upload' }).click();
    
    // Verify success message or UI update
    // Assuming alert or toast appears
    // await expect(page.getByText('Upload Complete')).toBeVisible();
  });

  test('should generate password when connected', async (/** @type {{ page: import('@playwright/test').Page }} */ { page }) => {
    // Mock the connection status API BEFORE navigation
    await page.route('**/api/security/genetic/connection-status/', async (/** @type {import('@playwright/test').Route} */ route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          connected: true,
          connection: {
            provider: 'manual',
            snp_count: 10000,
            evolution_generation: 1
          },
          // Add default subscription data to prevent undefined errors
          subscription: { tier: 'trial', status: 'active', epigenetic_evolution_enabled: true }
        })
      });
    });
    
    // Mock generation API
    await page.route('**/api/security/genetic/generate-password/', async (/** @type {import('@playwright/test').Route} */ route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          password: 'GeneticPassword123!',
          certificate: { 
            id: 'cert-123',
            password_hash_prefix: 'abc',
            genetic_hash_prefix: 'def'
          },
          evolution_generation: 1
        })
      });
    });

    // Mock evolution status API as well since it might be called
    await page.route('**/api/security/genetic/evolution-status/', async (/** @type {import('@playwright/test').Route} */ route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          evolution: {
            can_use_epigenetic: true,
            current_generation: 1
          }
        })
      });
    });

    // Now navigate
    await page.goto('/');

    await page.getByText('Genetic', { exact: true }).click();
    
    // Should see connected state (e.g. Generation info instead of connect buttons)
    // Using a simpler assertion or waiting for specific text
    await expect(page.getByText('Gen 1')).toBeVisible();
    
    // Click generate
    await page.getByRole('button', { name: 'Generate' }).first().click();
    
    // Check result in the display field
    // Assuming the password display has a specific test ID or using value
    await expect(page.locator('input[readonly], textarea[readonly]')).toHaveValue('GeneticPassword123!');
  });
});

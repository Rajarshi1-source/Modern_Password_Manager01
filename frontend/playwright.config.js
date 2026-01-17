// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Quantum Password E2E Tests
 * ========================================================
 * 
 * Run all tests: npx playwright test
 * Run quantum tests: npx playwright test quantum.e2e.spec.js
 * Run with UI: npx playwright test --ui
 */

export default defineConfig({
  testDir: './e2e',
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if test.only is committed
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter config
  reporter: [
    ['html', { outputFolder: 'e2e-report' }],
    ['list']
  ],
  
  // Global timeout
  timeout: 60000,
  
  // Expect timeout
  expect: {
    timeout: 10000
  },
  
  // Shared settings for all projects
  use: {
    // Base URL for page.goto()
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    
    // Collect trace when retrying a failed test
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video on failure
    video: 'on-first-retry',
    
    // Viewport
    viewport: { width: 1280, height: 720 },
    
    // Ignore HTTPS errors
    ignoreHTTPSErrors: true,
  },
  
  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    
    // Mobile viewports
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
  
  // Web server config
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});

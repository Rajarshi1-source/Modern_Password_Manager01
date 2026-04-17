/**
 * Heartbeat authentication — E2E smoke test
 * =========================================
 *
 * A full camera-PPG capture is impossible in a headless runner,
 * so this smoke just validates that both routes mount, the
 * enrollment wizard advances through its "I'm ready" step, and
 * the verify screen exposes the capture button.
 */

import { test, expect } from '@playwright/test';

test.describe('Heartbeat enrollment screen', () => {
  test('renders wizard and advances past permissions', async ({ page }) => {
    await page.goto('/auth/heartbeat/enroll');
    await expect(
      page.getByRole('heading', { name: /Heartbeat Enrollment/i }),
    ).toBeVisible();
    await page.getByRole('button', { name: /I'm ready/i }).click();
    await expect(
      page.getByText(/Readings captured:/i),
    ).toBeVisible();
  });
});

test.describe('Heartbeat verify screen', () => {
  test('renders capture button', async ({ page }) => {
    await page.goto('/auth/heartbeat/verify');
    await expect(
      page.getByRole('heading', { name: /Heartbeat Authentication/i }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Capture pulse/i }),
    ).toBeVisible();
  });
});

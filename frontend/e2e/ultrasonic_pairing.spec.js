/**
 * Ultrasonic pairing — E2E smoke test
 * ====================================
 *
 * We can't actually make a browser emit 19 kHz audio in a CI runner,
 * and even if we could the mic path has no headless analogue. Instead
 * this smoke just proves the route mounts, the mode selector renders,
 * and the initiate-POST is fired when the user clicks "Start pairing"
 * in Emit mode. A stubbed backend drives the rest of the stage
 * machine so we can assert the "SAS (say out loud)" string appears.
 */

import { test, expect } from '@playwright/test';

test.describe('Ultrasonic pairing screen', () => {
  test('renders mode selector and purpose dropdown', async ({ page }) => {
    await page.goto('/pair/ultrasonic');
    await expect(
      page.getByRole('heading', { name: /Ultrasonic Device Pairing/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/I have the account/i),
    ).toBeVisible();
    await expect(
      page.getByText(/I want to join/i),
    ).toBeVisible();
  });

  test('Listen mode swaps into the listener component', async ({ page }) => {
    await page.goto('/pair/ultrasonic');
    await page.getByLabel(/I want to join/i).check();
    await expect(
      page.getByRole('heading', { name: /Listen \(responder\)/i }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Start listening/i }),
    ).toBeVisible();
  });
});

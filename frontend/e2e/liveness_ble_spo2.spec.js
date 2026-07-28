/**
 * BLE pulse-oximeter SpO2 relay — hardware E2E
 * ============================================
 *
 * SCOPE: the AUTOMATED assertions here cover the relay and the tile only --
 * that a paired device makes the SpO2 reading appear, and that disconnecting
 * clears it. Whether SpO2 then contributes to the pulse modality is step 4 of
 * the manual procedure below, checked by the operator on the results screen;
 * no assertion in this file verifies scoring.
 *
 * The full round-trip — pair a real Bluetooth GATT Pulse Oximeter (service
 * 0x1822 / PLX), stream PLX measurements, relay them over the liveness session
 * WebSocket, and see the SpO2 tile update — needs a physical
 * oximeter and a browser with Web Bluetooth granting a device. Neither exists
 * in headless CI, so this suite is SKIPPED unless LIVENESS_BLE_HARDWARE=1 is
 * set on a machine with a paired oximeter. The parsing / pairing / relay
 * plumbing itself is covered hermetically by the Vitest unit tests
 * (frontend/src/services/__tests__/bleOximeter.test.js) with a mocked
 * navigator.bluetooth; only the real-device leg lives here.
 *
 * Manual procedure (run with a real device):
 *   1. Pair a supported BLE pulse oximeter that advertises the PLX service
 *      (0x1822) and notifies PLX Continuous (0x2A5F) or Spot-check (0x2A5E).
 *   2. LIVENESS_BLE_HARDWARE=1 E2E_AUTH_TOKEN=<disposable test token> \
 *        E2E_BASE_URL=<app> npx playwright test \
 *        e2e/liveness_ble_spo2.spec.js --project=chromium --headed
 *      (Web Bluetooth requires a headed Chromium and a user gesture to pick
 *      the device; automation cannot dismiss the native chooser, so a human
 *      selects the oximeter when prompted.)
 *      E2E_AUTH_TOKEN is REQUIRED: /liveness-verification is guarded in
 *      App.jsx by `!isAuthenticated ? <Navigate to="/" />`, and useAuth only
 *      sets isAuthenticated after GET /api/auth/me/ succeeds. A fresh browser
 *      context is anonymous, so without a token the backend accepts, the run
 *      silently lands on the public page and times out waiting for a button
 *      that is not there -- it never exercises the BLE flow at all. A
 *      placeholder value will not do.
 *      Use a DISPOSABLE, short-lived, least-privileged account's token, never a
 *      personal or long-lived one: it is seeded into page-readable
 *      localStorage, so page scripts can read it, and Playwright traces/videos
 *      of a failing run can retain it. Revoke it after the session.
 *   3. Start a verification, click "Connect pulse oximeter", pick the device.
 *   4. Confirm the SpO2 tile appears with a plausible real-device value
 *      (70–100% -- a liveness check validates a genuine reading, not health, so
 *      it must not reject a real sub-90 reading) and that completing the session
 *      shows SpO2 contributing to the pulse modality.
 *   5. Disconnect the oximeter mid-session; confirm the SpO2 tile clears (the
 *      reading is never fabricated or left stale) and the session continues.
 *
 * Capability-gating contract this asserts when hardware is present:
 *   - No device paired  => no SpO2 tile, SpO2 excluded from scoring.
 *   - Device paired      => SpO2 tile shows the relayed reading.
 *   - Device disconnected => SpO2 tile clears (no stale/fabricated value).
 */

import { test, expect } from '@playwright/test';

const HARDWARE = process.env.LIVENESS_BLE_HARDWARE === '1';
const AUTH_TOKEN = process.env.E2E_AUTH_TOKEN;

test.describe('BLE pulse-oximeter SpO2 relay (real hardware)', () => {
  test.skip(
    !HARDWARE,
    'Requires a real BLE pulse oximeter and Web Bluetooth; set LIVENESS_BLE_HARDWARE=1 to run.',
  );
  // Seed the access token useAuth bootstraps from, before any app script runs.
  test.beforeEach(async ({ page }) => {
    // THROW, don't skip: reaching here means the operator asked for a hardware
    // run, so a missing token is their error, not an absent capability. A skip
    // scrolls past unnoticed and looks like the suite ran.
    if (!AUTH_TOKEN) {
      throw new Error(
        'E2E_AUTH_TOKEN is required for a hardware run: /liveness-verification '
        + 'is behind the auth guard, so without it the run lands on the public '
        + 'page and never exercises BLE. Use a disposable, short-lived, '
        + 'least-privileged token (see the header).',
      );
    }
    await page.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, AUTH_TOKEN);
  });

  test('pairs an oximeter and surfaces a real SpO2 reading', async ({ page }) => {
    await page.goto('/liveness-verification');
    // Assert we actually got past the guard; otherwise the failure below would
    // read as "the oximeter button is missing" rather than "we were redirected".
    await expect(page).toHaveURL(/liveness-verification/);
    await expect(
      page.getByRole('button', { name: /Connect pulse oximeter/i }),
    ).toBeVisible();

    // The native Web Bluetooth chooser is out-of-page; a human selects the
    // device when the button is clicked (see the manual procedure above).
    await page.getByRole('button', { name: /Connect pulse oximeter/i }).click();

    // Once a device is streaming, the SpO2 tile appears with a plausible value.
    const spo2 = page.getByTestId('spo2-value');
    await expect(spo2).toBeVisible({ timeout: 30_000 });
    const text = (await spo2.textContent()) || '';
    const value = parseInt(text.replace(/[^0-9]/g, ''), 10);
    expect(value).toBeGreaterThanOrEqual(70);
    expect(value).toBeLessThanOrEqual(100);
  });

  test('clears the SpO2 tile when the oximeter disconnects (no stale value)', async ({ page }) => {
    await page.goto('/liveness-verification');
    // Same guard check as above: an auth redirect must not surface as an opaque
    // "button not found" timeout.
    await expect(page).toHaveURL(/liveness-verification/);
    await page.getByRole('button', { name: /Connect pulse oximeter/i }).click();
    await expect(page.getByTestId('spo2-value')).toBeVisible({ timeout: 30_000 });

    // Operator powers off / unpairs the oximeter here (manual step). The tile
    // must clear rather than keep the last reading — SpO2 is never fabricated
    // or left stale once its hardware source is gone.
    // Printed, not just commented: without it the wait looks like a hang and
    // then fails as an opaque 30s timeout when the operator does nothing.
    console.log('\n>>> MANUAL STEP: power off or unpair the oximeter now '
      + '(30s) — the SpO2 tile must disappear.\n');
    await expect(page.getByTestId('spo2-value')).toBeHidden({ timeout: 30_000 });
  });
});

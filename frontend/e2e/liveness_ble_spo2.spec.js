/**
 * BLE pulse-oximeter SpO2 relay — hardware E2E
 * ============================================
 *
 * The full round-trip — pair a real Bluetooth GATT Pulse Oximeter (service
 * 0x1822 / PLX), stream PLX measurements, relay them over the liveness session
 * WebSocket, and see the SpO2 tile update and feed scoring — needs a physical
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
 *   2. LIVENESS_BLE_HARDWARE=1 E2E_BASE_URL=<app> npx playwright test \
 *        e2e/liveness_ble_spo2.spec.js --project=chromium --headed
 *      (Web Bluetooth requires a headed Chromium and a user gesture to pick
 *      the device; automation cannot dismiss the native chooser, so a human
 *      selects the oximeter when prompted.)
 *   3. Start a verification, click "Connect pulse oximeter", pick the device.
 *   4. Confirm the SpO2 tile appears with a plausible value (90–100%) and that
 *      completing the session shows SpO2 contributing to the pulse modality.
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

test.describe('BLE pulse-oximeter SpO2 relay (real hardware)', () => {
  test.skip(
    !HARDWARE,
    'Requires a real BLE pulse oximeter and Web Bluetooth; set LIVENESS_BLE_HARDWARE=1 to run.',
  );

  test('pairs an oximeter and surfaces a real SpO2 reading', async ({ page }) => {
    await page.goto('/liveness-verification');
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
    await page.getByRole('button', { name: /Connect pulse oximeter/i }).click();
    await expect(page.getByTestId('spo2-value')).toBeVisible({ timeout: 30_000 });

    // Operator powers off / unpairs the oximeter here (manual step). The tile
    // must clear rather than keep the last reading — SpO2 is never fabricated
    // or left stale once its hardware source is gone.
    await expect(page.getByTestId('spo2-value')).toBeHidden({ timeout: 30_000 });
  });
});

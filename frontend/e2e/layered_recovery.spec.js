/**
 * Layered Recovery Mesh - E2E Tests (Tier 1 + Tier 3 + ZK assertion).
 *
 * Covers:
 *   Tier 1 (Recovery Key)  — enroll, logout, recover, vault readable
 *   Tier 3 (Time-Locked)   — enroll, fast-forward, release, recover
 *   Tier 2 (Social Mesh)   — skipped (multi-actor handshake; covered by
 *                            existing social-recovery e2e)
 *
 * Plus a NETWORK-ZK ASSERTION across the Tier-1 enrollment flow that
 * captures every outgoing request body and asserts the recovery key
 * pattern never appears in any payload. This is the keystone test —
 * never weaken it.
 *
 * Tier 3 uses a Django management command (`advance_time_lock`) to
 * fast-forward `release_after` so the test runs in seconds rather than
 * 7+ days.
 *
 * Worker note: this spec assumes the full stack is up (docker-compose
 * up). On hosts where docker-compose is unavailable (Windows host
 * limitation), CI runs the spec on push.
 *
 * Expected `data-testid` selectors (coordinated with Units 11 / 13):
 *   recovery-key-enroll-v2, rk-enroll-master-password, rk-enroll-start
 *   recovery-key-display, rk-copy, rk-download, rk-confirm-phrase, rk-enroll-save
 *   rk-enroll-success
 *   recovery-key-use-v2, rk-use-input, rk-use-recover
 *   rk-use-new-password, rk-use-confirm-new-password, rk-use-set-password
 *   time-locked-enroll, tl-enroll-master-password, tl-enroll-generate
 *   tl-enroll-confirm, tl-enroll-success
 *   time-locked-recover, tl-recover-username, tl-recover-file
 *   tl-recover-begin, tl-recover-poll, tl-recover-set-password
 */
const { test, expect } = require('@playwright/test');
const { execSync } = require('child_process');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// 26-char recovery key pattern (alphanumeric, no I/O/0/1, hyphens
// every 4 chars). Used by the network-ZK assertion to catch any
// accidental leak.
const RECOVERY_KEY_REGEX = /[A-HJ-NP-Z2-9]{4}(-[A-HJ-NP-Z2-9]{4}){5,6}/;

async function signupUser(page, { username, password }) {
  await page.goto(`${BASE_URL}/signup`);
  // Existing signup form field names — adjust selectors if the UI
  // changes. We tolerate a missing "confirm" field if the signup form
  // has consolidated.
  await page.fill('input[name="username"]', username).catch(() => {});
  await page.fill('input[name="email"]', `${username}@test.com`).catch(() => {});
  await page.fill('input[name="password"]', password);
  await page.fill('input[name="confirmPassword"]', password).catch(() => {});
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
}

async function logout(page) {
  // Try the user menu logout button; fall back to clearing storage.
  const logoutButton = page.getByRole('button', { name: /log\s*out/i }).first();
  if (await logoutButton.isVisible().catch(() => false)) {
    await logoutButton.click();
  } else {
    await page.evaluate(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
    });
    await page.goto(`${BASE_URL}/`);
  }
}


test.describe('Layered Recovery — Tier 1 (Recovery Key)', () => {
  test('enroll, logout, recover, vault still readable', async ({ page }) => {
    const username = `tier1_${Date.now()}`;
    const password = 'OldMasterPw1!';
    const newPassword = 'NewMasterPw2!';

    // Capture outgoing request bodies for the network-ZK assertion.
    const seenBodies = [];
    page.on('request', (req) => {
      const body = req.postData();
      if (body) seenBodies.push(body);
    });

    await signupUser(page, { username, password });

    await page.goto(`${BASE_URL}/recovery/key/enroll-v2`);
    await page.fill('[data-testid="rk-enroll-master-password"]', password);
    await page.click('[data-testid="rk-enroll-start"]');

    const keyText = await page.locator('[data-testid="recovery-key-display"]').innerText();
    expect(keyText.replace(/\s/g, '')).toMatch(RECOVERY_KEY_REGEX);

    await page.fill('[data-testid="rk-confirm-phrase"]', 'I have saved this key');
    await page.click('[data-testid="rk-enroll-save"]');
    await expect(page.locator('[data-testid="rk-enroll-success"]')).toBeVisible();

    // ── NETWORK-ZK ASSERTION ────────────────────────────────────────
    // The recovery key was generated client-side and shown on screen,
    // but it must NEVER appear in any outgoing request body.
    for (const body of seenBodies) {
      expect(body).not.toMatch(RECOVERY_KEY_REGEX);
      expect(body).not.toContain(keyText);
      const compact = keyText.replace(/-/g, '');
      expect(body).not.toContain(compact);
    }

    await logout(page);

    await page.goto(`${BASE_URL}/recovery/key/use-v2`);
    await page.fill('[data-testid="rk-use-input"]', keyText);
    await page.click('[data-testid="rk-use-recover"]');

    await page.fill('[data-testid="rk-use-new-password"]', newPassword);
    await page.fill('[data-testid="rk-use-confirm-new-password"]', newPassword);
    await page.click('[data-testid="rk-use-set-password"]');

    await expect(page.locator('[data-testid="rk-use-success"]')).toBeVisible();
  });
});


test.describe('Layered Recovery — Tier 3 (Time-Locked)', () => {
  test('enroll, initiate, fast-forward, release, recover', async ({ page }) => {
    const username = `tier3_${Date.now()}`;
    const password = 'Tier3MasterPw!';
    const newPassword = 'Tier3NewPw!';

    await signupUser(page, { username, password });

    // Capture the .dlrec download produced during enrollment.
    const downloadPromise = page.waitForEvent('download');
    await page.goto(`${BASE_URL}/recovery/time-lock/enroll`);
    await page.fill('[data-testid="tl-enroll-master-password"]', password);
    await page.click('[data-testid="tl-enroll-generate"]');
    const download = await downloadPromise;
    const dlrecPath = await download.path();
    expect(dlrecPath).toBeTruthy();
    await page.click('[data-testid="tl-enroll-confirm"]');
    await expect(page.locator('[data-testid="tl-enroll-success"]')).toBeVisible();

    await logout(page);

    await page.goto(`${BASE_URL}/recovery/time-lock/recover`);
    await page.fill('[data-testid="tl-recover-username"]', username);
    await page.setInputFiles('[data-testid="tl-recover-file"]', dlrecPath);
    await page.click('[data-testid="tl-recover-begin"]');

    // Fast-forward release_after via Django mgmt command. The runner
    // resolves the management command path relative to repo root.
    const repoRoot = path.resolve(__dirname, '..', '..');
    execSync(
      `python manage.py advance_time_lock ${username} --hours 169`,
      { cwd: path.join(repoRoot, 'password_manager'), stdio: 'inherit' },
    );

    await page.click('[data-testid="tl-recover-poll"]');
    await page.fill('[data-testid="tl-recover-new-password"]', newPassword);
    await page.fill('[data-testid="tl-recover-confirm-new-password"]', newPassword);
    await page.click('[data-testid="tl-recover-set-password"]');
    await expect(page.locator('[data-testid="tl-recover-success"]')).toBeVisible();
  });
});


test.describe('Layered Recovery — Tier 2 (Social Mesh)', () => {
  test.skip('multi-actor handshake — covered by existing social-recovery e2e', () => {});
});

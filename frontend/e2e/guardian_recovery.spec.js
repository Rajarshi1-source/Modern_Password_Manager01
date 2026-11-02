/**
 * Guardian recovery end to end: real endpoints and real client crypto, with
 * each person in their own browser context, as each key lives in one browser.
 *
 * Owner setup -> guardians accept -> a new device requests -> owner confirms
 * from the emailed link -> guardians check the code and re-seal -> the wait ->
 * the seed recombines in the requester's browser -> new master password.
 *
 * Needs a live Django backend on :8000 and something to run its tasks: a Celery
 * worker (CI's e2e.yml), or with no broker, recovery_notice.dispatch's fallback.
 * `python manage.py guardian_recovery_e2e` stands in for reading the emails and
 * for the hours the flow takes; the emails have tests of their own in
 * auth_module/tests/test_guardian_recovery_flow.py.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { signupAndLogin } from './helpers/auth.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const PYTHON = process.env.E2E_PYTHON || 'python';

function backend(username, ...flags) {
  const out = execFileSync(PYTHON, ['manage.py', 'guardian_recovery_e2e', username, ...flags], {
    cwd: path.resolve(__dirname, '../../password_manager'),
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'ignore'],
  });
  return JSON.parse(out.trim().split('\n').pop());
}

// goto would drop the in-memory vault session the owner just unlocked.
const navigateInApp = (page, to) => page.evaluate((target) => {
  window.history.pushState({}, '', target);
  window.dispatchEvent(new PopStateEvent('popstate'));
}, to);

test('a user who lost their master password recovers with guardians', async ({ browser }) => {
  test.setTimeout(300000);
  const password = 'TestPassword123!';
  const newPassword = 'AnotherPassword456!';

  // Three guardians make keys in their own browsers.
  const guardians = [];
  for (let i = 0; i < 3; i++) {
    const page = await (await browser.newContext()).newPage();
    await page.goto(`${BASE_URL}/recovery/guardian-key`);
    const publicKey = await page.getByTestId('guardian-public-key').inputValue();
    expect(publicKey.length).toBeGreaterThan(1000);
    guardians.push({ page, publicKey, email: `guardian${i}-${Date.now()}@test.com` });
  }

  // The owner chooses them; only sealed values may leave the browser.
  const ownerContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const { email } = await signupAndLogin(owner, { baseUrl: BASE_URL, emailPrefix: 'guardian-owner', password });
  const setupBodies = [];
  owner.on('request', (request) => {
    if (request.url().includes('/quantum-recovery/setup_recovery/')) setupBodies.push(request.postDataJSON());
  });
  await navigateInApp(owner, '/recovery/guardian/setup');
  await guardians.reduce((chain, g, i) => chain.then(async () => {
    await owner.getByTestId(`guardian-setup-email-${i}`).fill(g.email);
    await owner.getByTestId(`guardian-setup-key-${i}`).fill(g.publicKey);
    await owner.getByTestId(`guardian-setup-fingerprint-checked-${i}`).check();
  }), Promise.resolve());
  await owner.getByTestId('guardian-setup-threshold').fill('2');
  await owner.getByTestId('guardian-setup-master-password').fill(password);
  await owner.getByTestId('guardian-setup-submit').click();
  await expect(owner.getByTestId('guardian-setup-done')).toBeVisible({ timeout: 60000 });

  expect(Object.keys(setupBodies[0]).sort()).toEqual(
    ['guardians', 'recovery_factor', 'secret_check', 'secret_type', 'threshold_shards']);
  expect(Object.keys(setupBodies[0].recovery_factor).sort()).toEqual(['auth_hash', 'blob', 'dek_id']);
  expect(Object.keys(setupBodies[0].guardians[0]).sort()).toEqual(
    ['email', 'public_key', 'requires_video', 'sealed_share', 'share_index', 'share_proof_hash']);

  // Each guardian accepts its invitation, proving it can open its share.
  const links = await owner.locator('code').allTextContents();
  const invitePaths = links.filter((l) => l.includes('/recovery/guardian-invite/'));
  expect(invitePaths).toHaveLength(3);
  for (let i = 0; i < 3; i++) {
    await guardians[i].page.goto(invitePaths[i]);
    await guardians[i].page.getByTestId('guardian-invite-accept').click();
    await expect(guardians[i].page.getByTestId('guardian-invite-accepted')).toBeVisible({ timeout: 30000 });
  }
  await ownerContext.close();

  // Later, from a new device, with the master password gone.
  const requesterContext = await browser.newContext();
  const requester = await requesterContext.newPage();
  await requester.goto(`${BASE_URL}/recovery/guardian/start`);
  await requester.getByTestId('guardian-recovery-start-email').fill(email);
  await requester.getByTestId('guardian-recovery-start-submit').click();
  await expect(requester.getByTestId('guardian-recovery-start-message')).toBeVisible({ timeout: 30000 });

  // The request itself asks no guardian.
  await expect.poll(() => backend(email).attempt_path, { timeout: 60000 }).toBeTruthy();
  const { attempt_path: attemptPath, approval_tokens: before } = backend(email);
  expect(before).toEqual({});

  // Another browser that has the link cannot act on it.
  const elsewhere = await (await browser.newContext()).newPage();
  await elsewhere.goto(`${BASE_URL}${attemptPath}`);
  await expect(elsewhere.getByTestId('guardian-recovery-other-device')).toBeVisible();

  await requester.goto(`${BASE_URL}${attemptPath}`);
  await requester.getByTestId('guardian-recovery-confirm').click();
  const code = await requester.getByTestId('guardian-recovery-code').textContent();
  await expect.poll(() => Object.keys(backend(email).approval_tokens).length, { timeout: 60000 }).toBe(3);
  const { approval_tokens: tokens } = backend(email, '--open-windows');

  // A wrong code keeps the share sealed; the right one releases it.
  const first = guardians[0].page;
  await first.goto(`${BASE_URL}/recovery/guardian-approve/${tokens[guardians[0].email]}`);
  await first.getByTestId('guardian-approve-code').fill('0000-0000-0000-0000-0000');
  await first.getByTestId('guardian-approve-submit').click();
  await expect(first.getByRole('alert')).toContainText('does not match');
  for (let i = 0; i < 2; i++) {
    const page = guardians[i].page;
    await page.goto(`${BASE_URL}/recovery/guardian-approve/${tokens[guardians[i].email]}`);
    await page.getByTestId('guardian-approve-code').fill(code);
    await page.getByTestId('guardian-approve-submit').click();
    await expect(page.getByTestId('guardian-approve-result')).toContainText('approved', { timeout: 30000 });
  }

  // Enough approvals, but the owner's time to cancel has not passed.
  await requester.getByTestId('guardian-recovery-check').click();
  await expect(requester.getByTestId('guardian-recovery-progress')).toContainText('2 of 2');
  await expect(requester.getByTestId('guardian-recovery-wait')).toBeVisible();
  await expect(requester.getByTestId('guardian-recovery-recover')).toHaveCount(0);

  expect(backend(email).alert_sent).toBe(true);
  backend(email, '--end-wait');
  await requester.getByTestId('guardian-recovery-check').click();
  await requester.getByTestId('guardian-recovery-username').fill(email);
  await requester.getByTestId('guardian-recovery-recover').click();
  await requester.getByTestId('guardian-recovery-new-password').fill(newPassword);
  await requester.getByTestId('guardian-recovery-confirm-password').fill(newPassword);
  await requester.getByTestId('guardian-recovery-set-password').click();
  await expect(requester.getByTestId('guardian-recovery-done')).toBeVisible({ timeout: 60000 });

  // The new master password opens the account.
  const fresh = await (await browser.newContext()).newPage();
  await fresh.goto(`${BASE_URL}/`);
  await fresh.fill('#login-email', email);
  await fresh.fill('#login-password', newPassword);
  await fresh.getByRole('button', { name: 'Login to Vault' }).click();
  await fresh.getByTestId('login-success-status').waitFor({ timeout: 30000 });

  // Sign-in alone does not open the vault key. Enrolling another factor unwraps
  // the real key with the new password and sends its dek_id for the server to
  // check. Retried because the login's own unlock finishes after the marker.
  await navigateInApp(fresh, '/recovery/key/enroll-v2');
  await fresh.getByTestId('rk-enroll-master-password').fill(newPassword);
  await fresh.getByTestId('rk-enroll-start').click();
  await fresh.getByTestId('rk-confirm-phrase').fill('I have saved this key');
  const save = fresh.getByTestId('rk-enroll-save');
  await expect(async () => {
    if (await save.isVisible()) await save.click({ timeout: 5000 });
    await expect(fresh.getByTestId('rk-enroll-success')).toBeVisible({ timeout: 15000 });
  }).toPass({ timeout: 60000 });
});

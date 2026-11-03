/**
 * Replacing the vault key after a recovery compromise, end to end: real
 * endpoints and real client crypto (Argon2id and AES-GCM in the browser).
 *
 * The owner has an item and a recovery key -> support's unlock opens the warning
 * -> the key is replaced -> the next sign-in reads the item through the old key
 * and moves it to the new one -> a row restored from an old backup comes back
 * readable too -> the owner enrolls a new recovery key.
 *
 * Needs a live Django backend on :8000. `manage.py shell` stands in for support's
 * unlock (its effects have tests in auth_module/tests) and reads what the server
 * stored, which is how this checks that only ciphertext reached it.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { signupAndLogin } from './helpers/auth.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const PYTHON = process.env.E2E_PYTHON || 'python';

function django(code) {
  const out = execFileSync(PYTHON, ['manage.py', 'shell', '-c', code], {
    cwd: path.resolve(__dirname, '../../password_manager'),
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'ignore'],
  });
  return JSON.parse(out.trim().split('\n').pop());
}

const serverState = (email) => django(`
import json
from django.contrib.auth.models import User
from auth_module.recovery_models_v2 import RecoveryWrappedDEK, VaultWrappedDEK
from vault.models.vault_models import EncryptedVaultItem
u = User.objects.get(username=${JSON.stringify(email)})
w = VaultWrappedDEK.objects.get(user=u)
print(json.dumps({
    'dek_id': str(w.dek_id),
    'wrapped': w.blob['wrapped'],
    'retired': [r['dek_id'] for r in w.retired_keys],
    'active_factors': list(RecoveryWrappedDEK.objects.filter(user=u, status='active').values_list('factor_type', flat=True)),
    'rows': {str(i.id): {'data': i.encrypted_data, 'updated_at': i.updated_at.isoformat()}
             for i in EncryptedVaultItem.objects.filter(user=u)},
}))
`);

const openExposureWarning = (email) => django(`
import json
from django.contrib.auth.models import User
from auth_module.recovery_notice import create_notice
create_notice(User.objects.get(username=${JSON.stringify(email)}), 'account_unlocked', send_email=False)
print(json.dumps(True))
`);

const restoreRow = (id, encryptedData) => django(`
import json
from vault.models.vault_models import EncryptedVaultItem
n = EncryptedVaultItem.objects.filter(id=${JSON.stringify(id)}).update(encrypted_data=${JSON.stringify(encryptedData)})
print(json.dumps(n))
`);

// goto would drop the in-memory vault session the owner just unlocked.
const navigateInApp = (page, to) => page.evaluate((target) => {
  window.history.pushState({}, '', target);
  window.dispatchEvent(new PopStateEvent('popstate'));
}, to);

async function signIn(browser, email, password) {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`${BASE_URL}/`);
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.getByRole('button', { name: 'Login to Vault' }).click();
  await page.getByTestId('login-success-status').waitFor({ timeout: 30000 });
  return page;
}

// Retried because the login's own unlock finishes after the sign-in marker.
async function enrollRecoveryKey(page, password) {
  await navigateInApp(page, '/recovery/key/enroll-v2');
  await page.getByTestId('rk-enroll-master-password').fill(password);
  await page.getByTestId('rk-enroll-start').click();
  await page.getByTestId('rk-confirm-phrase').fill('I have saved this key');
  const save = page.getByTestId('rk-enroll-save');
  await expect(async () => {
    if (await save.isVisible()) await save.click({ timeout: 5000 });
    await expect(page.getByTestId('rk-enroll-success')).toBeVisible({ timeout: 15000 });
  }).toPass({ timeout: 60000 });
}

async function addItem(page, name, website, itemPassword) {
  await page.fill('#name', name);
  await page.fill('#website', website);
  await page.fill('#username', 'owner@example.com');
  await page.fill('#password', itemPassword);
  await page.getByRole('button', { name: 'Save Password' }).click();
}

const envelopeKey = (row) => JSON.parse(row.data).dek_id;

test('the owner replaces the vault key without losing an item', async ({ browser }) => {
  test.setTimeout(300000);
  const password = 'TestPassword123!';
  const itemPassword = 'item-secret-do-not-leak';
  const owner = await (await browser.newContext()).newPage();
  const { email } = await signupAndLogin(owner, { baseUrl: BASE_URL, emailPrefix: 'key-replace', password });

  // A real item under the first key, and a recovery factor that wraps that key.
  await enrollRecoveryKey(owner, password);
  await navigateInApp(owner, '/');
  await addItem(owner, 'Bank login', 'https://bank.example.com', itemPassword);
  await expect.poll(() => Object.keys(serverState(email).rows).length, { timeout: 30000 }).toBe(1);
  const before = serverState(email);
  const [rowId] = Object.keys(before.rows);
  await expect(owner.getByTestId('vault-item').filter({ hasText: 'Bank login' })).toBeVisible({ timeout: 30000 });
  expect(envelopeKey(before.rows[rowId])).toBe(before.dek_id);
  expect(before.rows[rowId].data).not.toContain(itemPassword);
  expect(before.active_factors).toEqual(['recovery_key']);

  // Nothing offers the replacement until support's unlock opens the warning.
  await navigateInApp(owner, '/security/recovery-notices');
  await owner.getByTestId('recovery-notices').waitFor({ timeout: 30000 });
  await expect(owner.getByTestId('replace-vault-key')).toHaveCount(0);

  openExposureWarning(email);
  await owner.reload();
  await owner.waitForLoadState();
  // The reload dropped the in-memory key, so sign in afresh and go by the app's own link.
  const session = await signIn(browser, email, password);
  await session.getByTestId('vault-exposure-banner').getByRole('link').click({ timeout: 30000 });
  await session.getByTestId('replace-vault-key').waitFor({ timeout: 30000 });
  await expect(session.getByTestId('vault-exposure-warning')).toContainText('can no longer be replaced');

  // A wrong password changes nothing, and is refused in the browser.
  const replaceBodies = [];
  session.on('request', (request) => {
    if (request.url().includes('/wrapped-dek/replace-key/')) replaceBodies.push(request.postData());
  });
  await session.getByLabel('Master password').fill('not-the-master-password');
  await session.getByRole('button', { name: 'Replace vault key' }).click();
  await expect(session.getByRole('alert')).toContainText('Incorrect password', { timeout: 30000 });
  expect(replaceBodies).toHaveLength(0);
  expect(serverState(email).dek_id).toBe(before.dek_id);

  // Retried like enrolling: the login's own unlock can still be running.
  await expect(async () => {
    await session.getByLabel('Master password').fill(password);
    await session.getByRole('button', { name: 'Replace vault key' }).click();
    await expect(session.getByTestId('replace-vault-key-done')).toBeVisible({ timeout: 20000 });
  }).toPass({ timeout: 90000 });

  // Only ciphertext left the browser.
  expect(replaceBodies).toHaveLength(1);
  const sent = JSON.parse(replaceBodies[0]);
  expect(Object.keys(sent).sort()).toEqual(['blob', 'dek_id', 'login_verifier', 'retired_key']);
  expect(replaceBodies[0]).not.toContain(password);

  const replaced = serverState(email);
  expect(replaced.dek_id).not.toBe(before.dek_id);
  expect(replaced.wrapped).not.toBe(before.wrapped);
  expect(replaced.retired).toEqual([before.dek_id]);
  expect(replaced.active_factors).toEqual([]);
  expect(envelopeKey(replaced.rows[rowId])).toBe(before.dek_id);

  // Every session ended, this one included.
  const status = await session.evaluate(async () => (await fetch('/api/auth/recovery-notices/', {
    headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
  })).status);
  expect(status).toBe(401);

  // The same master password opens the vault: the item reads through the old
  // key, and this sign-in moves it to the new one.
  const fresh = await signIn(browser, email, password);
  await navigateInApp(fresh, '/');
  await expect(fresh.getByTestId('vault-item').filter({ hasText: 'Bank login' })).toBeVisible({ timeout: 30000 });
  await expect(fresh.getByTestId('vault-item').filter({ hasText: 'bank.example.com' })).toBeVisible();
  await expect.poll(() => envelopeKey(serverState(email).rows[rowId]), { timeout: 60000 }).toBe(replaced.dek_id);
  const moved = serverState(email).rows[rowId];
  expect(moved.data).not.toBe(before.rows[rowId].data);
  expect(moved.data).not.toContain(itemPassword);
  expect(moved.updated_at).toBe(before.rows[rowId].updated_at);

  // The warning stays, but the key for this exposure is done.
  await fresh.getByTestId('vault-exposure-banner').getByRole('link').click({ timeout: 30000 });
  await fresh.getByTestId('vault-key-replaced').waitFor({ timeout: 30000 });
  await expect(fresh.getByTestId('replace-vault-key')).toHaveCount(0);

  // A new factor wraps the new key.
  await enrollRecoveryKey(fresh, password);
  expect(serverState(email).active_factors).toEqual(['recovery_key']);

  // A row sealed under the old key, as a restored backup would bring back, is
  // still readable, and the next sign-in moves it as well.
  restoreRow(rowId, before.rows[rowId].data);
  const afterRestore = await signIn(browser, email, password);
  await navigateInApp(afterRestore, '/');
  await expect(afterRestore.getByTestId('vault-item').filter({ hasText: 'Bank login' })).toBeVisible({ timeout: 30000 });
  await expect.poll(() => envelopeKey(serverState(email).rows[rowId]), { timeout: 60000 }).toBe(replaced.dek_id);
});

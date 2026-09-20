// @ts-check

/**
 * Sign up a fresh user, then log in as that user.
 *
 * - There is no seeded test account and no separate "username" field in the
 *   UI: registration sets Django's User.username to the email address
 *   (App.jsx handleSignup).
 * - /signup renders the LOGIN form first (isLoginMode starts true); the
 *   signup form only appears after clicking the "Sign Up" tab.
 * - handleSignup does NOT log the new user in -- it registers, then flips
 *   back to the login form -- so a second, explicit login is required.
 * - Login is a pure React-state transition (no client-side navigation), so
 *   we wait for the accessToken that useAuth persists, not for a URL change.
 * - Generated emails end in @test.com: isValidEmail's dev/test carve-out
 *   (App.jsx) accepts any "@...test..." address outside production.
 *
 * @param {import('@playwright/test').Page} page
 * @param {{ baseUrl: string, emailPrefix?: string, email?: string, password?: string }} options
 *   Pass `email`/`password` to reuse known credentials (recovery flows);
 *   otherwise a unique email is generated from `emailPrefix`.
 * @returns {Promise<{ email: string, password: string }>}
 */
export async function signupAndLogin(page, options) {
  const { baseUrl, emailPrefix = 'e2e', password = 'TestPassword123!' } = options;
  const email =
    options.email ?? `${emailPrefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@test.com`;

  await page.goto(`${baseUrl}/signup`);
  await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
  await page.fill('#signup-email', email);
  await page.fill('#signup-password', password);
  await page.fill('#signup-confirm-password', password);
  await page.getByRole('button', { name: 'Create Free Account' }).click();

  await page.waitForSelector('#login-email');
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.getByRole('button', { name: 'Login to Vault' }).click();

  await page.waitForFunction(
    () => !!window.localStorage.getItem('accessToken'),
    { timeout: 15000 },
  );

  return { email, password };
}

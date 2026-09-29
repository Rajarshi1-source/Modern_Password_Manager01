/**
 * Playwright E2E Tests for Adaptive Password Feature
 * ===================================================
 *
 * End-to-end browser tests covering the Epigenetic Password Adaptation
 * feature's actual current UI (AdaptivePasswordDashboard, mounted at
 * /security/adaptive -- see that component's own header comment for the
 * "this used to be unreachable" history).
 *
 * Rewritten 2026-09 after this file was found to predate that dashboard: it
 * referenced a /dashboard route and data-testids on the login form that
 * were never built, assumed a login-page typing-capture UI that does not
 * exist, and pointed API mocks at http://localhost:8000/... directly --
 * but axios calls relative paths through Vite's dev-server proxy
 * (localhost:5173 -> 127.0.0.1:8000 server-side), so page.route() never
 * saw a matching request and every one of those mocks was a silent no-op.
 */

import { test, expect, Page } from '@playwright/test';
import { signupAndLogin as authSignupAndLogin } from './helpers/auth.js';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

const signupAndLogin = async (page: Page): Promise<string> =>
  (await authSignupAndLogin(page, { baseUrl: BASE_URL, emailPrefix: 'e2e-adaptive' })).email;

async function navigateToAdaptiveSettings(page: Page): Promise<void> {
    await page.click('[data-testid="settings-menu"]');
    await page.click('[data-testid="security-settings"]');
    await page.click('[data-testid="adaptive-password-tab"]');
}

/** Opt in via the consent dialog and wait for the panel to report Enabled. */
async function enableAdaptivePasswords(page: Page): Promise<void> {
    await page.click('[data-testid="adaptive-enable-toggle"]');
    await page.click('[data-testid="consent-checkbox"]');
    await page.click('[data-testid="confirm-consent-button"]');
    await expect(page.getByText('Enabled', { exact: true })).toBeVisible();
}

// =============================================================================
// Feature Flag Tests
// =============================================================================

test.describe('Adaptive Password Feature Visibility', () => {
    test('feature is visible when enabled', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        const section = page.locator('[data-testid="adaptive-password-section"]');
        await expect(section).toBeVisible();
    });

    test('opt-in toggle is present', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        const toggle = page.locator('[data-testid="adaptive-enable-toggle"]');
        await expect(toggle).toBeVisible();
    });
});

// =============================================================================
// Opt-In Flow Tests
// =============================================================================

test.describe('Adaptive Password Opt-In', () => {
    test('shows consent dialog when enabling', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        await page.click('[data-testid="adaptive-enable-toggle"]');

        const dialog = page.locator('[data-testid="consent-dialog"]');
        await expect(dialog).toBeVisible();

        await expect(page.locator('text=typing patterns')).toBeVisible();
        await expect(page.locator('text=differential privacy')).toBeVisible();
    });

    test('enables feature after consent', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        await enableAdaptivePasswords(page);
    });

    test('cancel consent does not enable', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        await page.click('[data-testid="adaptive-enable-toggle"]');
        await page.click('[data-testid="cancel-consent-button"]');

        await expect(page.locator('[data-testid="adaptive-status-disabled"]')).toBeVisible();
    });
});

// =============================================================================
// Typing Pattern Capture Tests -- SKIPPED
// =============================================================================
// The unit tests already document this gap explicitly
// (frontend/src/__tests__/adaptive_password.test.tsx): "TypingPatternCapture
// is a headless component (renders null); the visible password-input/privacy
// UI it was originally specced with was never built". It is not imported or
// mounted anywhere in App.jsx's login form, and there is no
// [data-testid="typing-capture-indicator"] anywhere in the frontend source.
// Skipping here rather than asserting against UI that does not exist -- the
// same call the unit tests already made.

test.describe('Typing Pattern Capture', () => {
    test.skip(
        'captures typing patterns on login without sending the password -- '
        + 'login-page capture UI was never built (see adaptive_password.test.tsx)',
        () => {},
    );
    test.skip(
        'shows capture indicator when enabled -- '
        + 'no [data-testid="typing-capture-indicator"] exists in the frontend',
        () => {},
    );
});

// =============================================================================
// Adaptation Suggestion Tests -- SKIPPED
// =============================================================================
// Reaching AdaptivePasswordSuggestion's modal for real requires, in order: a
// decryptable vault item (client-side AES-GCM against the real session key
// -- not mockable over the network), enabling the feature, switching to the
// "Adapt a credential" tab, re-deriving the adaptive fingerprint key via a
// SECOND master-password prompt, selecting the item, and clicking
// "Check for a better version". Even after all of that, suggestAdaptation()'s
// own docstring (TypingPatternCapture.jsx) states the strength gate "rejects
// roughly three quarters of candidate substitutions... measured over a
// 200-password corpus" -- has_suggestion is genuinely non-deterministic for
// any single fixed password, so a test asserting the modal always appears
// would be flaky by the algorithm's own design, not by test construction.
// Exercising this reliably needs a test-only hook to force a specific
// substitution outcome, which does not currently exist.

test.describe('Adaptation Suggestions', () => {
    test.skip(
        'shows suggestion modal when available -- needs a real vault item + '
        + 'fingerprint unlock + a non-deterministic strength gate (see block comment)',
        () => {},
    );
    test.skip('displays a memorability improvement -- same gap as above', () => {});
    test.skip('can accept suggestion without sending the password -- same gap as above', () => {});
    test.skip('can reject suggestion -- same gap as above', () => {});
});

// =============================================================================
// Typing Profile Dashboard Tests
// =============================================================================

test.describe('Typing Profile Dashboard', () => {
    test('displays typing profile statistics', async ({ page }) => {
        await signupAndLogin(page);

        // page.route matches against the request as the PAGE sees it
        // (http://localhost:5173/api/... via Vite's dev-server proxy), not
        // the :8000 origin the backend actually runs on -- a bare
        // 'http://localhost:8000/...' pattern here would never match.
        await page.route('**/api/security/adaptive/profile/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                // Flat, not nested under a "profile" key --
                // TypingProfileCard.jsx reads profile?.total_sessions etc.
                // directly off this response.
                body: JSON.stringify({
                    has_profile: true,
                    total_sessions: 25,
                    success_rate: 0.85,
                    average_wpm: 45,
                    profile_confidence: 0.75,
                }),
            });
        });

        await navigateToAdaptiveSettings(page);
        await enableAdaptivePasswords(page);

        // Default tab is 'profile'. TypingProfileCard renders each stat's
        // value and label as separate elements ("25" then "Sessions"), not
        // one combined "25 sessions" text node.
        await expect(page.locator('text=25').first()).toBeVisible();
        await expect(page.getByText('Sessions', { exact: true })).toBeVisible();
        await expect(page.locator('text=85%')).toBeVisible();
        await expect(page.getByText('WPM', { exact: true })).toBeVisible();
    });

    test('shows adaptation history', async ({ page }) => {
        await signupAndLogin(page);

        await page.route('**/api/security/adaptive/history/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                // AdaptivePasswordDashboard's history rows key off
                // generation/status/suggested_at/can_rollback, not
                // id/status/created_at.
                body: JSON.stringify({
                    adaptations: [
                        {
                            id: '1', generation: 2, status: 'active',
                            suggested_at: '2024-01-15T10:00:00Z', can_rollback: true,
                        },
                        {
                            id: '2', generation: 1, status: 'rolled_back',
                            suggested_at: '2024-01-10T10:00:00Z', can_rollback: false,
                        },
                    ],
                }),
            });
        });

        await navigateToAdaptiveSettings(page);
        await enableAdaptivePasswords(page);
        await page.click('[data-testid="history-tab"]');

        const historyList = page.locator('[data-testid="adaptation-history-list"]');
        await expect(historyList).toBeVisible();
        await expect(historyList.locator('li')).toHaveCount(2);
    });
});

// =============================================================================
// Rollback Tests
// =============================================================================

test.describe('Password Rollback', () => {
    test('can rollback to previous password', async ({ page }) => {
        await signupAndLogin(page);

        await page.route('**/api/security/adaptive/history/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    adaptations: [
                        {
                            id: '1', generation: 1, status: 'active',
                            suggested_at: '2024-01-15T10:00:00Z', can_rollback: true,
                        },
                    ],
                }),
            });
        });
        await page.route('**/api/security/adaptive/rollback/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true }),
            });
        });

        await navigateToAdaptiveSettings(page);
        await enableAdaptivePasswords(page);
        await page.click('[data-testid="history-tab"]');

        // rollback-button only renders when can_rollback is true; clicking
        // it swaps it in place for confirm-rollback-button (the same
        // click-then-confirm pattern the delete flow below also uses).
        await page.click('[data-testid="rollback-button"]');
        await page.click('[data-testid="confirm-rollback-button"]');

        await expect(page.locator('text=Rolled back')).toBeVisible();
    });
});

// =============================================================================
// GDPR Data Management Tests
// =============================================================================
// data-management-tab (and the export/erasure it exposes) is deliberately
// NOT gated on `enabled` -- AdaptivePasswordDashboard.jsx: "Both work even
// if the feature is switched off... they are GDPR rights, not features" --
// so these two tests skip the opt-in flow entirely.

test.describe('GDPR Data Management', () => {
    test('can export all data', async ({ page }) => {
        await signupAndLogin(page);

        await page.route('**/api/security/adaptive/export/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    export_date: '2024-01-15T10:00:00Z',
                    configuration: { is_enabled: true },
                    typing_profile: { total_sessions: 25 },
                    adaptations: [],
                }),
            });
        });

        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="data-management-tab"]');
        await page.click('[data-testid="export-data-button"]');

        await expect(page.locator('text=Export complete')).toBeVisible();
    });

    test('can delete all typing data', async ({ page }) => {
        await signupAndLogin(page);

        await page.route('**/api/security/adaptive/data/', async (route) => {
            if (route.request().method() === 'DELETE') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ success: true }),
                });
            } else {
                await route.continue();
            }
        });

        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="data-management-tab"]');
        await page.click('[data-testid="delete-data-button"]');
        await page.click('[data-testid="confirm-delete-button"]');

        await expect(page.locator('text=Data deleted')).toBeVisible();
    });
});

// =============================================================================
// Feedback Submission Tests
// =============================================================================

test.describe('Adaptation Feedback', () => {
    test('can submit feedback after using adaptation', async ({ page }) => {
        await signupAndLogin(page);

        await page.route('**/api/security/adaptive/history/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    adaptations: [
                        {
                            id: '1', generation: 1, status: 'active',
                            suggested_at: '2024-01-15T10:00:00Z', can_rollback: false,
                        },
                    ],
                }),
            });
        });
        await page.route('**/api/security/adaptive/feedback/', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true }),
            });
        });

        await navigateToAdaptiveSettings(page);
        await enableAdaptivePasswords(page);
        await page.click('[data-testid="history-tab"]');

        await page.click('[data-testid="feedback-button"]');
        await page.click('[data-testid="rating-star-4"]');
        await page.click('[data-testid="accuracy-improved-checkbox"]');
        await page.fill('[data-testid="feedback-text"]', 'Works great!');
        await page.click('[data-testid="submit-feedback-button"]');

        await expect(page.locator('text=Feedback submitted')).toBeVisible();
    });
});

// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('Accessibility', () => {
    test.skip(
        'suggestion modal is accessible -- depends on the suggestion modal '
        + '(see the "Adaptation Suggestions" block comment above)',
        () => {},
    );

    test('keyboard navigation works', async ({ page }) => {
        await signupAndLogin(page);
        await navigateToAdaptiveSettings(page);

        const toggle = page.locator('[data-testid="adaptive-enable-toggle"]');
        // The persistent authenticated nav (Settings/Logout/feature links)
        // renders ABOVE this routed page content, so it -- not the toggle --
        // owns the first several Tab stops. Tab forward until the toggle is
        // reached rather than assuming Tab #1 lands on it.
        let focused = false;
        for (let i = 0; i < 30 && !focused; i++) {
            await page.keyboard.press('Tab');
            // eslint-disable-next-line no-loop-func -- toggle is stable across iterations
            focused = await toggle.evaluate((el) => el === document.activeElement);
        }
        expect(focused).toBe(true);

        await page.keyboard.press('Space');
        await expect(page.locator('[data-testid="consent-dialog"]')).toBeVisible();

        await page.keyboard.press('Escape');
        await expect(page.locator('[data-testid="consent-dialog"]')).not.toBeVisible();
    });
});

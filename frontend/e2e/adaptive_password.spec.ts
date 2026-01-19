/**
 * Playwright E2E Tests for Adaptive Password Feature
 * ===================================================
 * 
 * End-to-end browser tests covering the full user journey
 * of the Epigenetic Password Adaptation feature.
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const API_URL = process.env.API_URL || 'http://localhost:8000/api';

// Test user credentials
const TEST_USER = {
    email: 'e2e-adaptive@test.com',
    password: 'TestPassword123!',
};

// =============================================================================
// Helper Functions
// =============================================================================

async function loginUser(page: Page): Promise<void> {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', TEST_USER.email);
    await page.fill('[data-testid="password-input"]', TEST_USER.password);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('**/dashboard**');
}

async function navigateToAdaptiveSettings(page: Page): Promise<void> {
    await page.click('[data-testid="settings-menu"]');
    await page.click('[data-testid="security-settings"]');
    await page.click('[data-testid="adaptive-password-tab"]');
}

// =============================================================================
// Feature Flag Tests
// =============================================================================

test.describe('Adaptive Password Feature Visibility', () => {
    test('feature is visible when enabled', async ({ page }) => {
        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        // Feature section should be visible
        const section = page.locator('[data-testid="adaptive-password-section"]');
        await expect(section).toBeVisible();
    });

    test('opt-in toggle is present', async ({ page }) => {
        await loginUser(page);
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
        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        // Click enable toggle
        await page.click('[data-testid="adaptive-enable-toggle"]');

        // Consent dialog should appear
        const dialog = page.locator('[data-testid="consent-dialog"]');
        await expect(dialog).toBeVisible();

        // Privacy information should be shown
        await expect(page.locator('text=typing patterns')).toBeVisible();
        await expect(page.locator('text=differential privacy')).toBeVisible();
    });

    test('enables feature after consent', async ({ page }) => {
        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        await page.click('[data-testid="adaptive-enable-toggle"]');
        await page.click('[data-testid="consent-checkbox"]');
        await page.click('[data-testid="confirm-consent-button"]');

        // Status should change to enabled
        await expect(page.locator('text=Enabled')).toBeVisible();
    });

    test('cancel consent does not enable', async ({ page }) => {
        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        await page.click('[data-testid="adaptive-enable-toggle"]');
        await page.click('[data-testid="cancel-consent-button"]');

        // Should still be disabled
        await expect(page.locator('[data-testid="adaptive-status-disabled"]')).toBeVisible();
    });
});

// =============================================================================
// Typing Pattern Capture Tests
// =============================================================================

test.describe('Typing Pattern Capture', () => {
    test('captures typing patterns on login', async ({ page }) => {
        // First enable adaptive passwords
        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="adaptive-enable-toggle"]');
        await page.click('[data-testid="consent-checkbox"]');
        await page.click('[data-testid="confirm-consent-button"]');

        // Logout
        await page.click('[data-testid="logout-button"]');

        // Login again - pattern should be captured
        await page.goto(`${BASE_URL}/login`);
        await page.fill('[data-testid="email-input"]', TEST_USER.email);

        // Type password slowly to simulate real typing
        const passwordInput = page.locator('[data-testid="password-input"]');
        for (const char of TEST_USER.password) {
            await passwordInput.type(char, { delay: 100 });
        }

        await page.click('[data-testid="login-button"]');
        await page.waitForURL('**/dashboard**');

        // Check typing session was recorded (via API response or notification)
        // Note: Actual verification would require checking API or database
    });

    test('shows capture indicator when enabled', async ({ page }) => {
        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="adaptive-enable-toggle"]');
        await page.click('[data-testid="consent-checkbox"]');
        await page.click('[data-testid="confirm-consent-button"]');

        // Logout and go to login
        await page.click('[data-testid="logout-button"]');
        await page.goto(`${BASE_URL}/login`);

        // When focusing password input, capture indicator should show
        await page.focus('[data-testid="password-input"]');

        // Look for capture indicator (privacy indicator)
        await expect(page.locator('[data-testid="typing-capture-indicator"]')).toBeVisible();
    });
});

// =============================================================================
// Adaptation Suggestion Tests
// =============================================================================

test.describe('Adaptation Suggestions', () => {
    test('shows suggestion modal when available', async ({ page }) => {
        // Mock API to return a suggestion
        await page.route(`${API_URL}/security/adaptive/suggest/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_suggestion: true,
                    suggestion: {
                        original_preview: 'te***23',
                        adapted_preview: 't3***23',
                        substitutions: [{ position: 1, from: 'e', to: '3' }],
                        confidence_score: 0.85,
                        memorability_improvement: 0.15,
                    },
                }),
            });
        });

        await loginUser(page);

        // Trigger suggestion check
        await page.goto(`${BASE_URL}/dashboard`);

        // Wait for suggestion modal
        const modal = page.locator('[data-testid="adaptation-suggestion-modal"]');
        await expect(modal).toBeVisible({ timeout: 5000 });
    });

    test('displays memorability improvement', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/suggest/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_suggestion: true,
                    suggestion: {
                        memorability_improvement: 0.15,
                        confidence_score: 0.85,
                    },
                }),
            });
        });

        await loginUser(page);
        await page.goto(`${BASE_URL}/dashboard`);

        const modal = page.locator('[data-testid="adaptation-suggestion-modal"]');
        await modal.waitFor({ state: 'visible', timeout: 5000 });

        // Check memorability improvement is displayed
        await expect(page.locator('text=+15%')).toBeVisible();
    });

    test('can accept suggestion', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/suggest/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_suggestion: true,
                    suggestion: {
                        adaptation_id: 'test-uuid',
                        memorability_improvement: 0.15,
                    },
                }),
            });
        });

        await page.route(`${API_URL}/security/adaptive/apply/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true }),
            });
        });

        await loginUser(page);
        await page.goto(`${BASE_URL}/dashboard`);

        const modal = page.locator('[data-testid="adaptation-suggestion-modal"]');
        await modal.waitFor({ state: 'visible', timeout: 5000 });

        await page.click('[data-testid="accept-suggestion-button"]');

        // Success message should appear
        await expect(page.locator('text=Password updated')).toBeVisible();
    });

    test('can reject suggestion', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/suggest/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_suggestion: true,
                    suggestion: { adaptation_id: 'test-uuid' },
                }),
            });
        });

        await loginUser(page);
        await page.goto(`${BASE_URL}/dashboard`);

        const modal = page.locator('[data-testid="adaptation-suggestion-modal"]');
        await modal.waitFor({ state: 'visible', timeout: 5000 });

        await page.click('[data-testid="reject-suggestion-button"]');

        // Modal should close
        await expect(modal).not.toBeVisible();
    });
});

// =============================================================================
// Typing Profile Dashboard Tests
// =============================================================================

test.describe('Typing Profile Dashboard', () => {
    test('displays typing profile statistics', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/profile/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_profile: true,
                    profile: {
                        total_sessions: 25,
                        success_rate: 0.85,
                        average_wpm: 45,
                        profile_confidence: 0.75,
                    },
                }),
            });
        });

        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        // Statistics should be visible
        await expect(page.locator('text=25 sessions')).toBeVisible();
        await expect(page.locator('text=85%')).toBeVisible();
        await expect(page.locator('text=45 WPM')).toBeVisible();
    });

    test('shows adaptation history', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/history/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    adaptations: [
                        { id: '1', status: 'active', created_at: '2024-01-15T10:00:00Z' },
                        { id: '2', status: 'rolled_back', created_at: '2024-01-10T10:00:00Z' },
                    ],
                }),
            });
        });

        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="history-tab"]');

        // History items should be visible
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
        await page.route(`${API_URL}/security/adaptive/rollback/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true }),
            });
        });

        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="history-tab"]');

        // Click rollback on active adaptation
        await page.click('[data-testid="rollback-button"]');

        // Confirm rollback
        await page.click('[data-testid="confirm-rollback-button"]');

        // Success message
        await expect(page.locator('text=Rolled back')).toBeVisible();
    });
});

// =============================================================================
// GDPR Data Management Tests
// =============================================================================

test.describe('GDPR Data Management', () => {
    test('can export all data', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/export/`, async (route) => {
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

        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="data-management-tab"]');
        await page.click('[data-testid="export-data-button"]');

        // Download should trigger (or data should display)
        await expect(page.locator('text=Export complete')).toBeVisible();
    });

    test('can delete all typing data', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/data/`, async (route) => {
            if (route.request().method() === 'DELETE') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ success: true }),
                });
            }
        });

        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="data-management-tab"]');
        await page.click('[data-testid="delete-data-button"]');

        // Confirm deletion
        await page.click('[data-testid="confirm-delete-button"]');

        // Success message
        await expect(page.locator('text=Data deleted')).toBeVisible();
    });
});

// =============================================================================
// Feedback Submission Tests
// =============================================================================

test.describe('Adaptation Feedback', () => {
    test('can submit feedback after using adaptation', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/feedback/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true }),
            });
        });

        await loginUser(page);
        await navigateToAdaptiveSettings(page);
        await page.click('[data-testid="history-tab"]');

        // Click feedback button on an adaptation
        await page.click('[data-testid="feedback-button"]');

        // Fill feedback form
        await page.click('[data-testid="rating-star-4"]');
        await page.click('[data-testid="accuracy-improved-checkbox"]');
        await page.fill('[data-testid="feedback-text"]', 'Works great!');
        await page.click('[data-testid="submit-feedback-button"]');

        // Success message
        await expect(page.locator('text=Feedback submitted')).toBeVisible();
    });
});

// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('Accessibility', () => {
    test('suggestion modal is accessible', async ({ page }) => {
        await page.route(`${API_URL}/security/adaptive/suggest/`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    has_suggestion: true,
                    suggestion: { adaptation_id: 'test' },
                }),
            });
        });

        await loginUser(page);
        await page.goto(`${BASE_URL}/dashboard`);

        const modal = page.locator('[data-testid="adaptation-suggestion-modal"]');
        await modal.waitFor({ state: 'visible', timeout: 5000 });

        // Check ARIA attributes
        await expect(modal).toHaveAttribute('role', 'dialog');
        await expect(modal).toHaveAttribute('aria-modal', 'true');

        // Focus should be trapped in modal
        await page.keyboard.press('Tab');
        const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
        expect(['BUTTON', 'INPUT', 'A']).toContain(focusedElement);
    });

    test('keyboard navigation works', async ({ page }) => {
        await loginUser(page);
        await navigateToAdaptiveSettings(page);

        // Tab through interactive elements
        await page.keyboard.press('Tab');

        // Enable toggle should be focusable
        const toggle = page.locator('[data-testid="adaptive-enable-toggle"]');
        await expect(toggle).toBeFocused();

        // Space should toggle
        await page.keyboard.press('Space');
        // Consent dialog should open
        await expect(page.locator('[data-testid="consent-dialog"]')).toBeVisible();

        // Escape should close
        await page.keyboard.press('Escape');
        await expect(page.locator('[data-testid="consent-dialog"]')).not.toBeVisible();
    });
});

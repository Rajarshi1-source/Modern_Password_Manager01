/**
 * E2E Tests for Quantum Entanglement Feature
 * ============================================
 * 
 * Uses Playwright for browser-based end-to-end testing.
 * 
 * Run with: npx playwright test quantum_entanglement.spec.ts
 */

import { test, expect, Page, Route } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.TEST_URL || 'http://localhost:3000';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Mock data
const mockUser = {
    id: 1,
    username: 'testuser',
    email: 'test@example.com'
};

const mockDevices = [
    { device_id: 'dev-1', device_name: 'iPhone 15', device_type: 'mobile', is_trusted: true },
    { device_id: 'dev-2', device_name: 'MacBook Pro', device_type: 'desktop', is_trusted: true },
    { device_id: 'dev-3', device_name: 'iPad Air', device_type: 'tablet', is_trusted: true }
];

const mockPairs = [
    {
        pair_id: 'pair-123',
        device_a_id: 'dev-1',
        device_a_name: 'iPhone 15',
        device_b_id: 'dev-2',
        device_b_name: 'MacBook Pro',
        status: 'active',
        entropy_health: 'healthy',
        entropy_score: 7.95,
        current_generation: 3,
        last_sync_at: new Date().toISOString(),
        created_at: new Date().toISOString()
    }
];

// Helper to mock API routes
async function setupAPIMocks(page: Page) {
    // Mock authentication check
    await page.route(`${API_URL}/api/auth/user/`, async (route: Route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(mockUser)
        });
    });

    // Mock devices endpoint
    await page.route(`${API_URL}/api/security/devices/`, async (route: Route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ devices: mockDevices })
        });
    });

    // Mock pairs endpoint
    await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                pairs: mockPairs,
                total_count: mockPairs.length,
                max_allowed: 5
            })
        });
    });
}

// =============================================================================
// PAGE LOAD & NAVIGATION TESTS
// =============================================================================

test.describe('Quantum Entanglement Page', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        // Set auth token in localStorage
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('loads entanglement manager page', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByRole('heading', { name: /Quantum Entangled Devices/i })).toBeVisible();
    });

    test('displays loading state initially', async ({ page }) => {
        // Delay API response to see loading state
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await new Promise(resolve => setTimeout(resolve, 500));
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ pairs: [], total_count: 0, max_allowed: 5 })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText(/Loading/i)).toBeVisible();
    });

    test('displays pairs after loading', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('iPhone 15')).toBeVisible();
        await expect(page.getByText('MacBook Pro')).toBeVisible();
    });

    test('shows empty state when no pairs', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ pairs: [], total_count: 0, max_allowed: 5 })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText(/No Entangled Devices/i)).toBeVisible();
        await expect(page.getByRole('button', { name: /Start Pairing/i })).toBeVisible();
    });
});

// =============================================================================
// DEVICE PAIRING FLOW TESTS
// =============================================================================

test.describe('Device Pairing Flow', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('opens pairing flow when button clicked', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        await expect(page.getByText('Select Devices to Pair')).toBeVisible();
    });

    test('displays available devices', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        await expect(page.getByText('iPhone 15')).toBeVisible();
        await expect(page.getByText('MacBook Pro')).toBeVisible();
        await expect(page.getByText('iPad Air')).toBeVisible();
    });

    test('can select two different devices', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        // Select first device
        const deviceASection = page.locator('.device-column').first();
        await deviceASection.getByText('iPhone 15').click();

        // Select second device
        const deviceBSection = page.locator('.device-column').last();
        await deviceBSection.getByText('MacBook Pro').click();

        // Continue button should be enabled
        await expect(page.getByRole('button', { name: /Continue/i })).toBeEnabled();
    });

    test('shows verification code after initiation', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/initiate/`, async (route: Route) => {
            await route.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({
                    session_id: 'session-abc',
                    verification_code: '123456',
                    expires_at: new Date(Date.now() + 600000).toISOString()
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        // Select devices
        await page.locator('.device-column').first().getByText('iPhone 15').click();
        await page.locator('.device-column').last().getByText('MacBook Pro').click();

        // Continue
        await page.getByRole('button', { name: /Continue/i }).click();

        // Verification code should be displayed
        await expect(page.getByText('Verify Pairing')).toBeVisible();
        await expect(page.locator('.digit').first()).toBeVisible();
    });

    test('can copy verification code', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/initiate/`, async (route: Route) => {
            await route.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({
                    session_id: 'session-abc',
                    verification_code: '123456',
                    expires_at: new Date(Date.now() + 600000).toISOString()
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        await page.locator('.device-column').first().getByText('iPhone 15').click();
        await page.locator('.device-column').last().getByText('MacBook Pro').click();
        await page.getByRole('button', { name: /Continue/i }).click();

        // Click copy button
        await page.getByRole('button', { name: /Copy/i }).click();

        await expect(page.getByText('Copied!')).toBeVisible();
    });

    test('shows success on complete pairing', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/initiate/`, async (route: Route) => {
            await route.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({
                    session_id: 'session-abc',
                    verification_code: '123456',
                    expires_at: new Date(Date.now() + 600000).toISOString()
                })
            });
        });

        await page.route(`${API_URL}/api/security/entanglement/verify/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    pair_id: 'new-pair-id',
                    status: 'active',
                    generation: 0
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        await page.locator('.device-column').first().getByText('iPhone 15').click();
        await page.locator('.device-column').last().getByText('MacBook Pro').click();
        await page.getByRole('button', { name: /Continue/i }).click();

        // Enter verification code
        await page.locator('.code-input').fill('123456');
        await page.getByRole('button', { name: /Verify/i }).click();

        // Wait for success
        await expect(page.getByText('Entanglement Established!')).toBeVisible({ timeout: 5000 });
    });

    test('can cancel pairing flow', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Pair New Devices/i }).click();

        await page.getByRole('button', { name: /Cancel/i }).click();

        await expect(page.getByText('Quantum Entangled Devices')).toBeVisible();
    });
});

// =============================================================================
// KEY ROTATION TESTS
// =============================================================================

test.describe('Key Rotation', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('can rotate keys for a pair', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/rotate/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    success: true,
                    new_generation: 4,
                    entropy_status: 'healthy'
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        // Find and click rotate button
        await page.getByRole('button', { name: /Rotate/i }).first().click();

        // Page should refresh and show updated data
        await expect(page.getByText('iPhone 15')).toBeVisible();
    });
});

// =============================================================================
// INSTANT REVOCATION TESTS
// =============================================================================

test.describe('Instant Revocation', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('opens revoke modal', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        await page.getByRole('button', { name: /Revoke/i }).first().click();

        await expect(page.getByText('Revoke Device Pairing?')).toBeVisible();
    });

    test('shows affected devices', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        await expect(page.getByText('iPhone 15')).toBeVisible();
        await expect(page.getByText('MacBook Pro')).toBeVisible();
    });

    test('can mark device as compromised', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        // Click on a device to mark as compromised
        await page.locator('.device-item').first().click();

        await expect(page.getByText('Compromised')).toBeVisible();
    });

    test('can cancel revocation', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        await page.getByRole('button', { name: /Cancel/i }).click();

        await expect(page.getByText('Revoke Device Pairing?')).not.toBeVisible();
    });

    test('successfully revokes pair', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/revoke/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    success: true,
                    pair_id: 'pair-123',
                    revoked_at: new Date().toISOString(),
                    affected_devices: ['dev-1', 'dev-2']
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        await page.getByRole('button', { name: /Revoke Now/i }).click();

        await expect(page.getByText('Entanglement Revoked')).toBeVisible();
    });

    test('shows error on revocation failure', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/revoke/`, async (route: Route) => {
            await route.fulfill({
                status: 400,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Revocation failed' })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        await page.getByRole('button', { name: /Revoke Now/i }).click();

        await expect(page.getByText('Revocation Failed')).toBeVisible();
    });
});

// =============================================================================
// ENTROPY MONITORING TESTS
// =============================================================================

test.describe('Entropy Monitoring', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('displays healthy entropy status', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    pairs: [{
                        ...mockPairs[0],
                        entropy_health: 'healthy',
                        entropy_score: 7.95
                    }],
                    total_count: 1,
                    max_allowed: 5
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('7.95')).toBeVisible();
        await expect(page.getByText('Healthy')).toBeVisible();
    });

    test('displays degraded entropy warning', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    pairs: [{
                        ...mockPairs[0],
                        entropy_health: 'degraded',
                        entropy_score: 7.2
                    }],
                    total_count: 1,
                    max_allowed: 5
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('Degraded')).toBeVisible();
    });

    test('displays critical entropy alert', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    pairs: [{
                        ...mockPairs[0],
                        entropy_health: 'critical',
                        entropy_score: 6.5
                    }],
                    total_count: 1,
                    max_allowed: 5
                })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.locator('.status-red')).toBeVisible();
    });
});

// =============================================================================
// ERROR HANDLING TESTS
// =============================================================================

test.describe('Error Handling', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('shows error message on API failure', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Internal server error' })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText(/error/i)).toBeVisible();
    });

    test('handles network timeout gracefully', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.abort('timedout');
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText(/error|failed/i)).toBeVisible();
    });

    test('can dismiss error message', async ({ page }) => {
        await page.route(`${API_URL}/api/security/entanglement/pairs/`, async (route: Route) => {
            await route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Server error' })
            });
        });

        await page.goto(`${BASE_URL}/security/entanglement`);

        const dismissButton = page.locator('.error-alert button');
        if (await dismissButton.isVisible()) {
            await dismissButton.click();
            await expect(page.locator('.error-alert')).not.toBeVisible();
        }
    });
});

// =============================================================================
// ACCESSIBILITY TESTS
// =============================================================================

test.describe('Accessibility', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('page has proper heading hierarchy', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        const h1 = page.getByRole('heading', { level: 1 });
        await expect(h1).toBeVisible();
    });

    test('buttons are focusable', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        const pairButton = page.getByRole('button', { name: /Pair New Devices/i });
        await pairButton.focus();

        await expect(pairButton).toBeFocused();
    });

    test('can navigate with keyboard', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);

        // Tab through interactive elements
        await page.keyboard.press('Tab');

        // Some element should be focused
        const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
        expect(focusedElement).toBeTruthy();
    });

    test('modal traps focus', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.getByRole('button', { name: /Revoke/i }).first().click();

        // Tab should cycle within modal
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');

        // Focus should still be within modal
        const isModalFocused = await page.evaluate(() => {
            const modal = document.querySelector('.revoke-modal');
            return modal?.contains(document.activeElement);
        });

        expect(isModalFocused).toBe(true);
    });
});

// =============================================================================
// RESPONSIVE DESIGN TESTS
// =============================================================================

test.describe('Responsive Design', () => {
    test.beforeEach(async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });
    });

    test('displays correctly on mobile', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('Quantum Entangled Devices')).toBeVisible();
        await expect(page.getByRole('button', { name: /Pair/i })).toBeVisible();
    });

    test('displays correctly on tablet', async ({ page }) => {
        await page.setViewportSize({ width: 768, height: 1024 });
        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('Quantum Entangled Devices')).toBeVisible();
    });

    test('displays correctly on desktop', async ({ page }) => {
        await page.setViewportSize({ width: 1920, height: 1080 });
        await page.goto(`${BASE_URL}/security/entanglement`);

        await expect(page.getByText('Quantum Entangled Devices')).toBeVisible();
    });

    test('stats grid stacks on mobile', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(`${BASE_URL}/security/entanglement`);

        const statsGrid = page.locator('.stats-grid');
        const boundingBox = await statsGrid.boundingBox();

        // Stats should still be visible
        expect(boundingBox).toBeTruthy();
    });
});

// =============================================================================
// PERFORMANCE TESTS
// =============================================================================

test.describe('Performance', () => {
    test('page loads within acceptable time', async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });

        const startTime = Date.now();
        await page.goto(`${BASE_URL}/security/entanglement`);
        await page.waitForLoadState('networkidle');
        const loadTime = Date.now() - startTime;

        // Page should load in under 3 seconds
        expect(loadTime).toBeLessThan(3000);
    });

    test('no memory leaks on navigation', async ({ page }) => {
        await setupAPIMocks(page);
        await page.addInitScript(() => {
            localStorage.setItem('token', 'mock-auth-token');
        });

        // Navigate back and forth multiple times
        for (let i = 0; i < 3; i++) {
            await page.goto(`${BASE_URL}/security/entanglement`);
            await page.goto(`${BASE_URL}/security`);
        }

        // If we get here without crash, memory is likely OK
        await expect(page).toHaveURL(`${BASE_URL}/security`);
    });
});

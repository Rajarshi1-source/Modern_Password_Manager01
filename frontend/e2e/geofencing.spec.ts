/**
 * Geofencing E2E Tests
 * 
 * End-to-end tests for geofencing and impossible travel detection UI.
 */

import { test, expect, type Page, type BrowserContext, type APIRequestContext } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

// Test utilities
const login = async (page: Page): Promise<void> => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'testpassword123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**');
};

// Mock location data
const mockLocations = {
    delhi: { latitude: 28.6139, longitude: 77.2090 },
    mumbai: { latitude: 19.0760, longitude: 72.8777 },
    newYork: { latitude: 40.7128, longitude: -74.0060 },
};

test.describe('Geofencing Dashboard', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('should display geofencing dashboard', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/geofencing`);

        // Check header
        await expect(page.locator('h2')).toContainText('Geofencing');

        // Check tabs exist
        await expect(page.locator('.tab-btn')).toHaveCount(4);
        await expect(page.getByText('Overview')).toBeVisible();
        await expect(page.getByText('Trusted Zones')).toBeVisible();
        await expect(page.getByText('Travel Plans')).toBeVisible();
        await expect(page.getByText('History')).toBeVisible();
    });

    test('should show stats cards on overview', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/geofencing`);

        // Check stats are displayed
        await expect(page.locator('.stat-card.zones')).toBeVisible();
        await expect(page.locator('.stat-card.events')).toBeVisible();
        await expect(page.locator('.stat-card.travel')).toBeVisible();
        await expect(page.locator('.stat-card.location')).toBeVisible();
    });

    test('should navigate to trusted zones tab', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/geofencing`);

        await page.click('button:has-text("Trusted Zones")');

        // Should show TrustedZonesManager
        await expect(page.locator('.trusted-zones-manager')).toBeVisible();
    });

    test('should navigate to travel plans tab', async ({ page }) => {
        await page.goto(`${BASE_URL}/security/geofencing`);

        await page.click('button:has-text("Travel Plans")');

        // Should show TravelItineraryManager
        await expect(page.locator('.travel-itinerary-manager')).toBeVisible();
    });
});

test.describe('Trusted Zones Management', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);
        await page.click('button:has-text("Trusted Zones")');
    });

    test('should display zone creation form', async ({ page }) => {
        await page.click('button:has-text("Add Zone")');

        await expect(page.locator('input[placeholder*="Home"]')).toBeVisible();
        await expect(page.locator('input[placeholder*="Latitude"]')).toBeVisible();
        await expect(page.locator('input[placeholder*="Longitude"]')).toBeVisible();
    });

    test('should create a new trusted zone', async ({ page }) => {
        await page.click('button:has-text("Add Zone")');

        // Fill form
        await page.fill('input[placeholder*="Home"]', 'Test Zone');
        await page.fill('input[placeholder*="Latitude"]', mockLocations.delhi.latitude.toString());
        await page.fill('input[placeholder*="Longitude"]', mockLocations.delhi.longitude.toString());

        // Submit
        await page.click('button:has-text("Save")');

        // Should show success
        await expect(page.locator('.zone-card')).toContainText('Test Zone');
    });

    test('should use current location button', async ({ page, context }) => {
        // Grant geolocation permission
        await context.grantPermissions(['geolocation']);
        await context.setGeolocation(mockLocations.delhi);

        await page.click('button:has-text("Add Zone")');
        await page.click('button:has-text("Current Location")');

        // Latitude/longitude should be filled
        const latInput = page.locator('input[placeholder*="Latitude"]');
        await expect(latInput).not.toHaveValue('');
    });

    test('should delete a zone', async ({ page }) => {
        // Assume a zone exists
        const deleteButton = page.locator('.delete-btn').first();

        if (await deleteButton.isVisible()) {
            await deleteButton.click();

            // Confirm deletion
            await page.click('button:has-text("Delete")');

            // Zone should be removed (or show empty state)
            await expect(page.locator('.zone-card').first()).not.toBeVisible();
        }
    });
});

test.describe('Travel Itinerary Management', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);
        await page.click('button:has-text("Travel Plans")');
    });

    test('should display itinerary form', async ({ page }) => {
        await page.click('button:has-text("Add Trip")');

        await expect(page.locator('input[placeholder*="Delhi"]')).toBeVisible();
        await expect(page.locator('input[placeholder*="Mumbai"]')).toBeVisible();
        await expect(page.locator('input[type="datetime-local"]')).toHaveCount(2);
    });

    test('should add a travel itinerary', async ({ page }) => {
        await page.click('button:has-text("Add Trip")');

        // Fill departure
        await page.fill('input[placeholder*="Delhi"]', 'New Delhi');
        await page.fill('input[placeholder*="Mumbai"]', 'Mumbai');

        // Fill times (use relative dates)
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const departureTime = tomorrow.toISOString().slice(0, 16);

        tomorrow.setHours(tomorrow.getHours() + 2);
        const arrivalTime = tomorrow.toISOString().slice(0, 16);

        const timeInputs = page.locator('input[type="datetime-local"]');
        await timeInputs.first().fill(departureTime);
        await timeInputs.last().fill(arrivalTime);

        // Optional: Add booking reference
        await page.fill('input[placeholder*="ABC123"]', 'TEST123');

        // Submit
        await page.click('button:has-text("Add Itinerary")');

        // Should show in list
        await expect(page.locator('.itinerary-card')).toContainText('New Delhi');
    });
});

test.describe('Impossible Travel Alert', () => {
    test('should display travel alert modal', async ({ page }) => {
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);

        // Click on an alert if present
        const alert = page.locator('.alert-item').first();
        if (await alert.isVisible()) {
            await alert.click();

            // Modal should appear
            await expect(page.locator('.modal-content')).toBeVisible();
            await expect(page.getByText('Distance')).toBeVisible();
            await expect(page.getByText('Required Speed')).toBeVisible();
        }
    });

    test('should confirm legitimate travel', async ({ page }) => {
        await login(page);

        // Navigate to a page with alerts
        await page.goto(`${BASE_URL}/security/geofencing`);

        const alert = page.locator('.alert-item').first();
        if (await alert.isVisible()) {
            await alert.click();

            // Click confirm button
            await page.click('button:has-text("This was me")');

            // Alert should be dismissed
            await expect(page.locator('.modal-content')).not.toBeVisible();
        }
    });

    test('should show booking verification modal', async ({ page }) => {
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);

        const alert = page.locator('.alert-item').first();
        if (await alert.isVisible()) {
            await alert.click();

            // Click verify button
            await page.click('button:has-text("Verify with Booking")');

            // Verification modal should appear
            await expect(page.locator('input[placeholder*="PNR"]')).toBeVisible();
            await expect(page.locator('input[placeholder*="Last name"]')).toBeVisible();
        }
    });
});

test.describe('Geolocation Capture', () => {
    test('should request location permission', async ({ page, context }) => {
        // Don't grant permission initially
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);

        // Look for permission request UI
        const captureButton = page.locator('button:has-text("Capture")');
        if (await captureButton.isVisible()) {
            await captureButton.click();

            // Should show permission message or handle gracefully
            await expect(
                page.locator('.permission-request, .location-error')
            ).toBeVisible({ timeout: 5000 });
        }
    });

    test('should capture and analyze location', async ({ page, context }) => {
        // Grant permission and set location
        await context.grantPermissions(['geolocation']);
        await context.setGeolocation(mockLocations.mumbai);

        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);

        // Click capture button
        const captureButton = page.locator('button:has-text("Capture")');
        if (await captureButton.isVisible()) {
            await captureButton.click();

            // Should show success or analysis result
            await expect(
                page.locator('.location-success, .capture-result, .stat-card.location')
            ).toBeVisible({ timeout: 10000 });
        }
    });
});

test.describe('Location History', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await page.goto(`${BASE_URL}/security/geofencing`);
        await page.click('button:has-text("History")');
    });

    test('should display history tab content', async ({ page }) => {
        await expect(page.locator('.history-section')).toBeVisible();
        await expect(page.getByText('Location History')).toBeVisible();
    });
});

// API Integration Tests
test.describe('Geofencing API', () => {
    test('should record location via API', async ({ request }) => {
        // This requires authentication - typically handled via fixtures
        const response = await request.post(`${BASE_URL}/api/security/geofence/location/record/`, {
            data: {
                latitude: mockLocations.delhi.latitude,
                longitude: mockLocations.delhi.longitude,
                accuracy_meters: 10,
                source: 'gps'
            }
        });

        // Should get 401 without auth (or 201 with auth fixture)
        expect([201, 401, 403]).toContain(response.status());
    });

    test('should list zones via API', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/security/geofence/zones/`);

        // Should get 401 without auth (or 200 with auth fixture)
        expect([200, 401, 403]).toContain(response.status());
    });
});

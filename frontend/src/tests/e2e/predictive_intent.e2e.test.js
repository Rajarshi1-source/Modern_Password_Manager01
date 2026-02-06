/**
 * Predictive Intent E2E Tests
 * ============================
 *
 * End-to-end tests for the predictive intent feature:
 * - API endpoints
 * - Prediction flow
 * - Feedback recording
 * - Settings management
 * - GDPR compliance
 *
 * @author Password Manager Team
 * @created 2026-02-07
 */

const { test, expect } = require('@playwright/test');

const API_BASE = 'http://localhost:8000/api/ml-security';

// Test user credentials
const TEST_USER = {
  username: 'test_user',
  password: 'TestPassword123!',
};

let authToken = null;

// ===========================================================================
// Setup and Authentication
// ===========================================================================

test.beforeAll(async ({ request }) => {
  // Login and get auth token
  const loginResponse = await request.post('http://localhost:8000/api/auth/login/', {
    data: {
      username: TEST_USER.username,
      password: TEST_USER.password,
    },
  });

  const loginData = await loginResponse.json();
  authToken = loginData.access;
  expect(authToken).toBeTruthy();
});

// Helper function for authenticated requests
async function authenticatedRequest(request, method, endpoint, data = null) {
  const options = {
    headers: {
      Authorization: `Bearer ${authToken}`,
      'Content-Type': 'application/json',
    },
  };

  if (data) {
    options.data = data;
  }

  const url = `${API_BASE}${endpoint}`;

  switch (method) {
    case 'GET':
      return request.get(url, options);
    case 'POST':
      return request.post(url, options);
    case 'PUT':
      return request.put(url, options);
    case 'DELETE':
      return request.delete(url, options);
    default:
      throw new Error(`Unknown method: ${method}`);
  }
}

// ===========================================================================
// Settings Tests
// ===========================================================================

test.describe('Predictive Intent Settings', () => {
  test('should get default settings', async ({ request }) => {
    const response = await authenticatedRequest(request, 'GET', '/intent/settings/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.settings).toBeDefined();
    expect(data.settings.is_enabled).toBeDefined();
    expect(data.settings.min_confidence_threshold).toBeGreaterThanOrEqual(0);
    expect(data.settings.max_predictions_shown).toBeGreaterThan(0);
  });

  test('should update settings', async ({ request }) => {
    const newSettings = {
      min_confidence_threshold: 0.8,
      max_predictions_shown: 3,
      excluded_domains: ['example.com', 'test.com'],
    };

    const response = await authenticatedRequest(
      request,
      'PUT',
      '/intent/settings/update/',
      newSettings
    );
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.settings.min_confidence_threshold).toBe(0.8);
    expect(data.settings.max_predictions_shown).toBe(3);
    expect(data.settings.excluded_domains).toContain('example.com');
  });

  test('should toggle feature on/off', async ({ request }) => {
    // Disable
    let response = await authenticatedRequest(
      request,
      'PUT',
      '/intent/settings/update/',
      { is_enabled: false }
    );
    let data = await response.json();
    expect(data.settings.is_enabled).toBe(false);

    // Enable
    response = await authenticatedRequest(
      request,
      'PUT',
      '/intent/settings/update/',
      { is_enabled: true }
    );
    data = await response.json();
    expect(data.settings.is_enabled).toBe(true);
  });
});

// ===========================================================================
// Prediction Tests
// ===========================================================================

test.describe('Predictions', () => {
  test('should get predictions for domain', async ({ request }) => {
    const response = await authenticatedRequest(
      request,
      'GET',
      '/intent/predictions/?domain=github.com'
    );
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.predictions).toBeDefined();
    expect(Array.isArray(data.predictions)).toBe(true);
  });

  test('should return empty predictions for excluded domain', async ({ request }) => {
    // First add to excluded domains
    await authenticatedRequest(request, 'PUT', '/intent/settings/update/', {
      excluded_domains: ['excluded-domain.com'],
    });

    const response = await authenticatedRequest(
      request,
      'GET',
      '/intent/predictions/?domain=excluded-domain.com'
    );

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.predictions.length).toBe(0);
  });
});

// ===========================================================================
// Context Signal Tests
// ===========================================================================

test.describe('Context Signals', () => {
  test('should send context signal', async ({ request }) => {
    const contextData = {
      domain: 'github.com',
      url_hash: 'abc123',
      page_title: 'Sign in to GitHub',
      form_fields: ['username', 'password'],
      time_on_page: 5,
      is_new_tab: false,
      device_type: 'desktop',
    };

    const response = await authenticatedRequest(
      request,
      'POST',
      '/intent/context/',
      contextData
    );
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.signal_id).toBeDefined();
    expect(data.login_probability).toBeDefined();
  });

  test('should require domain in context signal', async ({ request }) => {
    const response = await authenticatedRequest(request, 'POST', '/intent/context/', {
      page_title: 'Test Page',
    });

    expect(response.ok()).toBeFalsy();
  });

  test('should detect login form probability', async ({ request }) => {
    const contextData = {
      domain: 'login.example.com',
      page_title: 'Login - Example',
      form_fields: ['email', 'password'],
      device_type: 'desktop',
    };

    const response = await authenticatedRequest(
      request,
      'POST',
      '/intent/context/',
      contextData
    );
    const data = await response.json();

    expect(data.success).toBe(true);
    expect(data.login_probability).toBeGreaterThan(0.5);
  });
});

// ===========================================================================
// Usage Recording Tests
// ===========================================================================

test.describe('Usage Recording', () => {
  let testVaultItemId = null;

  test.beforeAll(async ({ request }) => {
    // Create a test vault item
    const response = await request.post('http://localhost:8000/api/vault/items/', {
      headers: {
        Authorization: `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: 'Test Password',
        encrypted_data: 'encrypted_test_data',
        item_type: 'password',
      },
    });

    if (response.ok()) {
      const data = await response.json();
      testVaultItemId = data.id;
    }
  });

  test('should record usage pattern', async ({ request }) => {
    if (!testVaultItemId) {
      test.skip();
      return;
    }

    const usageData = {
      vault_item_id: testVaultItemId,
      domain: 'github.com',
      access_method: 'browse',
    };

    const response = await authenticatedRequest(
      request,
      'POST',
      '/intent/usage/',
      usageData
    );

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.pattern_id || data.message).toBeDefined();
  });

  test('should require vault_item_id', async ({ request }) => {
    const response = await authenticatedRequest(request, 'POST', '/intent/usage/', {
      domain: 'github.com',
    });

    expect(response.ok()).toBeFalsy();
  });
});

// ===========================================================================
// Feedback Tests
// ===========================================================================

test.describe('Feedback Recording', () => {
  test('should require prediction_id and feedback_type', async ({ request }) => {
    const response = await authenticatedRequest(request, 'POST', '/intent/feedback/', {
      feedback_type: 'used',
    });

    expect(response.ok()).toBeFalsy();
  });

  test('should validate feedback_type', async ({ request }) => {
    const response = await authenticatedRequest(request, 'POST', '/intent/feedback/', {
      prediction_id: '00000000-0000-0000-0000-000000000000',
      feedback_type: 'invalid_type',
    });

    expect(response.ok()).toBeFalsy();
  });
});

// ===========================================================================
// Statistics Tests
// ===========================================================================

test.describe('Statistics', () => {
  test('should get prediction statistics', async ({ request }) => {
    const response = await authenticatedRequest(request, 'GET', '/intent/stats/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.statistics).toBeDefined();
    expect(data.statistics.total_predictions).toBeDefined();
    expect(data.statistics.accuracy).toBeDefined();
  });
});

// ===========================================================================
// GDPR Compliance Tests
// ===========================================================================

test.describe('GDPR Data Privacy', () => {
  test('should export all prediction data', async ({ request }) => {
    const response = await authenticatedRequest(request, 'GET', '/intent/export/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.export).toBeDefined();
    expect(data.export.user_id).toBeDefined();
    expect(data.export.exported_at).toBeDefined();
    expect(data.export.usage_patterns).toBeDefined();
    expect(data.export.predictions).toBeDefined();
    expect(data.export.feedback).toBeDefined();
    expect(data.export.summary).toBeDefined();
  });

  test('should require confirmation for data deletion', async ({ request }) => {
    const response = await authenticatedRequest(request, 'DELETE', '/intent/data/');
    expect(response.ok()).toBeFalsy();

    const data = await response.json();
    expect(data.error).toContain('confirm');
  });

  test('should delete all prediction data with confirmation', async ({ request }) => {
    const response = await authenticatedRequest(
      request,
      'DELETE',
      '/intent/data/?confirm=true'
    );
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.deleted).toBeDefined();
    expect(data.deleted.patterns).toBeDefined();
    expect(data.deleted.predictions).toBeDefined();
    expect(data.message).toContain('deleted');
  });

  test('should optionally delete settings with data', async ({ request }) => {
    const response = await authenticatedRequest(
      request,
      'DELETE',
      '/intent/data/?confirm=true&include_settings=true'
    );

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.deleted.settings_reset).toBe(true);
  });
});

// ===========================================================================
// Preloaded Credentials Tests
// ===========================================================================

test.describe('Preloaded Credentials', () => {
  test('should get preloaded credentials list', async ({ request }) => {
    const response = await authenticatedRequest(request, 'GET', '/intent/preloaded/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.preloaded).toBeDefined();
    expect(Array.isArray(data.preloaded)).toBe(true);
  });
});

// ===========================================================================
// Integration Flow Test
// ===========================================================================

test.describe('Full Prediction Flow', () => {
  test('should complete full prediction cycle', async ({ request }) => {
    // 1. Enable feature
    await authenticatedRequest(request, 'PUT', '/intent/settings/update/', {
      is_enabled: true,
      min_confidence_threshold: 0.5,
    });

    // 2. Send context signal
    const contextResponse = await authenticatedRequest(
      request,
      'POST',
      '/intent/context/',
      {
        domain: 'flow-test.com',
        page_title: 'Login Page',
        form_fields: ['username', 'password'],
        device_type: 'desktop',
      }
    );
    const contextData = await contextResponse.json();
    expect(contextData.success).toBe(true);

    // 3. Get predictions
    const predictionsResponse = await authenticatedRequest(
      request,
      'GET',
      '/intent/predictions/?domain=flow-test.com'
    );
    const predictionsData = await predictionsResponse.json();
    expect(predictionsData.success).toBe(true);

    // 4. Get statistics
    const statsResponse = await authenticatedRequest(request, 'GET', '/intent/stats/');
    const statsData = await statsResponse.json();
    expect(statsData.success).toBe(true);
    expect(statsData.statistics.is_enabled).toBe(true);
  });
});

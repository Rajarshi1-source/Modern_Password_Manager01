/**
 * AI-Powered Security Assistant - E2E Tests
 * ==========================================
 * 
 * End-to-end tests using Playwright for:
 * - Dashboard / Welcome screen rendering
 * - Session management (create, select, delete)
 * - Chat interface interactions
 * - Error handling & resilience
 * - Accessibility compliance
 * - API integration & response handling
 * 
 * @author Password Manager Team
 * @created 2026-03-13
 */

const { test, expect } = require('@playwright/test');

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Test user credentials
const TEST_USER = {
  email: 'e2e-assistant@test.com',
  password: 'TestPassword123!',
};


// =============================================================================
// Setup & Helpers
// =============================================================================

/**
 * Helper to login before tests
 */
async function loginUser(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[name="email"]', TEST_USER.email);
  await page.fill('input[name="password"]', TEST_USER.password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/**`, { timeout: 10000 });
}


// =============================================================================
// AI Assistant Dashboard / Welcome Screen Tests
// =============================================================================

test.describe('AI Assistant Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should navigate to AI Assistant page', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Main container should be visible
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });
  });

  test('should display welcome screen with header', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Welcome screen should be visible when no session is active
    await expect(page.locator('#sa-welcome')).toBeVisible({ timeout: 10000 });

    // Welcome title should be present
    await expect(page.locator('.sa-welcome h2')).toHaveText('Security Assistant');

    // Welcome description should be present
    await expect(page.locator('.sa-welcome p')).toContainText('Ask me anything about your password security');
  });

  test('should display starter prompt buttons', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Wait for welcome screen
    await expect(page.locator('#sa-welcome')).toBeVisible({ timeout: 10000 });

    // Starter prompts should be visible
    await expect(page.locator('.sa-starter-prompts')).toBeVisible();

    // Should have 6 starter prompts
    const promptCount = await page.locator('.sa-starter-prompt').count();
    expect(promptCount).toBe(6);

    // First prompt should have correct text
    await expect(page.locator('#sa-starter-0')).toContainText('Why is my GitHub password weak?');
  });

  test('should display health badge when score available', async ({ page }) => {
    // Mock the suggestions API to return a health score
    await page.route('**/api/ai-assistant/suggestions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          suggestions: [],
          health_score: 75,
          total_passwords: 10,
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.sa-health-badge')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.sa-health-badge')).toContainText('75/100');
  });

  test('should display chat header with title', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Chat header should be visible
    await expect(page.locator('.sa-chat-header')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sa-chat-header h3')).toHaveText('Security Assistant');
  });

  test('should display message input area', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Input area should be visible
    await expect(page.locator('.sa-input-area')).toBeVisible({ timeout: 10000 });

    // Textarea and send button should be present
    await expect(page.locator('#sa-message-input')).toBeVisible();
    await expect(page.locator('#sa-send-button')).toBeVisible();

    // Input hint should be present
    await expect(page.locator('.sa-input-hint')).toContainText('Press Enter to send');
  });

  test('should display sidebar with session header', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Sidebar should exist
    await expect(page.locator('.sa-sidebar')).toBeAttached({ timeout: 10000 });

    // Sidebar header should have title
    await expect(page.locator('.sa-sidebar-header h2')).toContainText('Security Assistant');

    // New chat button should be visible
    await expect(page.locator('#sa-new-chat')).toBeVisible();
    await expect(page.locator('#sa-new-chat')).toContainText('New Conversation');
  });
});


// =============================================================================
// Session Management Tests
// =============================================================================

test.describe('AI Assistant Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should show empty state when no sessions exist', async ({ page }) => {
    // Mock empty sessions
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.sa-session-list')).toContainText('No conversations yet', { timeout: 10000 });
  });

  test('should create a new session', async ({ page }) => {
    const mockSessionId = 'test-session-uuid-123';

    // Mock session creation
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: {
              id: mockSessionId,
              title: 'New Conversation',
              message_count: 0,
              last_activity: new Date().toISOString(),
            },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('#sa-new-chat')).toBeVisible({ timeout: 10000 });

    // Click new conversation button
    await page.click('#sa-new-chat');

    // Session should appear in sidebar
    await expect(page.locator('.sa-session-item')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.sa-session-title')).toContainText('New Conversation');
  });

  test('should display sessions list with metadata', async ({ page }) => {
    // Mock sessions list
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            count: 2,
            sessions: [
              {
                id: 'session-1',
                title: 'Password Security Discussion',
                message_count: 5,
                last_activity: new Date().toISOString(),
              },
              {
                id: 'session-2',
                title: 'Breach Risk Analysis',
                message_count: 3,
                last_activity: new Date(Date.now() - 86400000).toISOString(),
              },
            ],
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Should display both sessions
    await expect(page.locator('.sa-session-item')).toHaveCount(2, { timeout: 10000 });

    // First session should show title and message count
    await expect(page.locator('.sa-session-item').first()).toContainText('Password Security Discussion');
    await expect(page.locator('.sa-session-meta').first()).toContainText('5 messages');
  });

  test('should select a session and load messages', async ({ page }) => {
    const sessionId = 'session-123';

    // Mock sessions
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'GET' && !route.request().url().includes(sessionId)) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            count: 1,
            sessions: [{
              id: sessionId,
              title: 'Test Session',
              message_count: 2,
              last_activity: new Date().toISOString(),
            }],
          }),
        });
      } else {
        route.continue();
      }
    });

    // Mock session detail
    await page.route(`**/api/ai-assistant/sessions/${sessionId}/`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          session: {
            id: sessionId,
            title: 'Test Session',
            messages: [
              { id: 'msg-1', role: 'user', content: 'How secure is my vault?', timestamp: new Date().toISOString() },
              { id: 'msg-2', role: 'assistant', content: 'Your vault has a health score of 85/100.', timestamp: new Date().toISOString() },
            ],
          },
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Click on the session
    await page.locator('.sa-session-item').first().click();

    // Messages should appear
    await expect(page.locator('.sa-message')).toHaveCount(2, { timeout: 5000 });
    await expect(page.locator('.sa-message.user .sa-message-content')).toContainText('How secure is my vault?');
    await expect(page.locator('.sa-message.assistant .sa-message-content')).toContainText('health score of 85/100');
  });

  test('should delete a session', async ({ page }) => {
    const sessionId = 'session-to-delete';

    // Mock sessions
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            count: 1,
            sessions: [{
              id: sessionId,
              title: 'Session to Delete',
              message_count: 1,
              last_activity: new Date().toISOString(),
            }],
          }),
        });
      } else {
        route.continue();
      }
    });

    // Mock delete
    await page.route(`**/api/ai-assistant/sessions/${sessionId}/`, route => {
      if (route.request().method() === 'DELETE') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'deleted', message: 'Session deleted.' }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Session should be visible
    await expect(page.locator('.sa-session-item')).toBeVisible({ timeout: 10000 });

    // Click delete button
    await page.click('.sa-session-delete');

    // Session should disappear
    await expect(page.locator('.sa-session-item')).toHaveCount(0, { timeout: 5000 });
  });
});


// =============================================================================
// Chat Interface Tests
// =============================================================================

test.describe('AI Assistant Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should send button be disabled when input is empty', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('#sa-send-button')).toBeDisabled({ timeout: 10000 });
  });

  test('should enable send button when text entered', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Type in the input
    await page.fill('#sa-message-input', 'Test message');

    // Send button should now be enabled
    await expect(page.locator('#sa-send-button')).toBeEnabled();
  });

  test('should send a message via button click', async ({ page }) => {
    // Mock session creation
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: {
              id: 'new-session-id',
              title: 'New Conversation',
              message_count: 0,
              last_activity: new Date().toISOString(),
            },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    // Mock send message
    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user_message: {
            id: 'user-msg-1',
            role: 'user',
            content: 'How is my password security?',
            timestamp: new Date().toISOString(),
          },
          assistant_message: {
            id: 'assistant-msg-1',
            role: 'assistant',
            content: 'Your overall password security score is **82/100**. Here are the key findings:\n- 3 passwords are weak\n- 2 passwords are reused\n- 15 passwords are strong',
            timestamp: new Date().toISOString(),
          },
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Type and send
    await page.fill('#sa-message-input', 'How is my password security?');
    await page.click('#sa-send-button');

    // User message should appear
    await expect(page.locator('.sa-message.user')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.sa-message.user .sa-message-content')).toContainText('How is my password security?');

    // Assistant response should appear
    await expect(page.locator('.sa-message.assistant')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sa-message.assistant .sa-message-content')).toContainText('82/100');
  });

  test('should send a message by clicking a starter prompt', async ({ page }) => {
    // Mock session creation
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'prompt-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    // Mock send message
    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user_message: {
            id: 'user-prompt-msg',
            role: 'user',
            content: 'Why is my GitHub password weak?',
            timestamp: new Date().toISOString(),
          },
          assistant_message: {
            id: 'assistant-prompt-msg',
            role: 'assistant',
            content: 'Your GitHub password is considered weak because it is only 8 characters long.',
            timestamp: new Date().toISOString(),
          },
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Click the first starter prompt
    await page.click('#sa-starter-0');

    // User message from the prompt should appear
    await expect(page.locator('.sa-message.user')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.sa-message.user .sa-message-content')).toContainText('GitHub password weak');
  });

  test('should clear input after sending message', async ({ page }) => {
    // Mock APIs
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'input-clear-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user_message: { id: 'u-1', role: 'user', content: 'Test', timestamp: new Date().toISOString() },
          assistant_message: { id: 'a-1', role: 'assistant', content: 'Response', timestamp: new Date().toISOString() },
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    await page.fill('#sa-message-input', 'Test message');
    await page.click('#sa-send-button');

    // Input should be cleared
    await expect(page.locator('#sa-message-input')).toHaveValue('', { timeout: 3000 });
  });

  test('should show placeholder text in input', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    await expect(page.locator('#sa-message-input')).toHaveAttribute(
      'placeholder',
      'Ask about your password security...',
      { timeout: 10000 }
    );
  });
});


// =============================================================================
// Suggestion Cards Tests
// =============================================================================

test.describe('AI Assistant Suggestion Cards', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should display suggestion cards when available', async ({ page }) => {
    // Mock suggestions
    await page.route('**/api/ai-assistant/suggestions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          suggestions: [
            {
              type: 'warning',
              icon: '⚠️',
              title: 'Weak Passwords Detected',
              description: '3 passwords need strengthening',
              action: 'Show me my weak passwords',
            },
            {
              type: 'info',
              icon: '🔄',
              title: 'Reused Passwords',
              description: '2 passwords are shared across accounts',
              action: 'Which passwords are reused?',
            },
          ],
          health_score: 65,
          total_passwords: 20,
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Suggestions container should be visible
    await expect(page.locator('#sa-suggestions')).toBeVisible({ timeout: 10000 });

    // Should have 2 suggestion cards
    await expect(page.locator('.sa-suggestion-card')).toHaveCount(2);

    // Cards should show content
    await expect(page.locator('.sa-suggestion-card').first()).toContainText('Weak Passwords Detected');
  });

  test('should not show suggestions when a session is active', async ({ page }) => {
    const sessionId = 'active-session';

    // Mock sessions
    await page.route('**/api/ai-assistant/sessions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          count: 1,
          sessions: [{ id: sessionId, title: 'Active Chat', message_count: 1, last_activity: new Date().toISOString() }],
        }),
      });
    });

    // Mock session detail
    await page.route(`**/api/ai-assistant/sessions/${sessionId}/`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          session: {
            id: sessionId,
            title: 'Active Chat',
            messages: [{ id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date().toISOString() }],
          },
        }),
      });
    });

    // Mock suggestions
    await page.route('**/api/ai-assistant/suggestions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', suggestions: [{ type: 'info', icon: '🔍', title: 'Test', description: 'Test', action: 'test' }], health_score: 80 }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await page.locator('.sa-session-item').first().click();

    // Wait for messages to load
    await expect(page.locator('.sa-message')).toBeVisible({ timeout: 5000 });

    // Suggestions should NOT be visible when session is active
    await expect(page.locator('#sa-suggestions')).not.toBeVisible();
  });
});


// =============================================================================
// Error Handling Tests
// =============================================================================

test.describe('AI Assistant Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should handle API errors gracefully - page does not crash', async ({ page }) => {
    // Intercept all AI assistant API calls to return 500
    await page.route('**/api/ai-assistant/**', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Page should still render without crashing
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });
  });

  test('should display error when message send fails', async ({ page }) => {
    // Mock session creation success
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'error-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    // Mock send message failure
    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Rate limit exceeded. Try again in 5 minutes.' }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    await page.fill('#sa-message-input', 'Test error handling');
    await page.click('#sa-send-button');

    // Error message should be displayed
    await expect(page.locator('#sa-error')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sa-error-text')).toContainText('Failed to get a response');
  });

  test('should dismiss error when clicking dismiss button', async ({ page }) => {
    // Mock APIs for error scenario
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'dismiss-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Something went wrong' }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    await page.fill('#sa-message-input', 'Trigger error');
    await page.click('#sa-send-button');

    // Wait for error
    await expect(page.locator('#sa-error')).toBeVisible({ timeout: 10000 });

    // Click dismiss
    await page.click('.sa-error-retry');

    // Error should disappear
    await expect(page.locator('#sa-error')).not.toBeVisible({ timeout: 3000 });
  });

  test('should handle network offline gracefully', async ({ page }) => {
    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Go offline
    await page.context().setOffline(true);

    // Try to create a new session
    await page.click('#sa-new-chat');

    // Page should not crash
    await expect(page.locator('.security-assistant')).toBeVisible();

    // Restore
    await page.context().setOffline(false);
  });

  test('should handle feature disabled state', async ({ page }) => {
    // Mock feature disabled
    await page.route('**/api/ai-assistant/**', route => {
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'AI Assistant feature is disabled.' }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Page should still render
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });
  });
});


// =============================================================================
// Accessibility Tests
// =============================================================================

test.describe('AI Assistant Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto(`${BASE_URL}/security/ai-assistant`);
  });

  test('should have proper heading structure', async ({ page }) => {
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Should have h2 headings
    const h2Count = await page.locator('.security-assistant h2').count();
    expect(h2Count).toBeGreaterThan(0);

    // Should have h3 heading in chat header
    const h3Count = await page.locator('.sa-chat-header h3').count();
    expect(h3Count).toBeGreaterThan(0);
  });

  test('should be keyboard navigable', async ({ page }) => {
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Tab through elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Should be able to navigate with keyboard
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(['INPUT', 'BUTTON', 'TEXTAREA', 'A']).toContain(focusedElement);
  });

  test('should have unique IDs for interactive elements', async ({ page }) => {
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Check key elements have IDs
    await expect(page.locator('#sa-message-input')).toBeAttached();
    await expect(page.locator('#sa-send-button')).toBeAttached();
    await expect(page.locator('#sa-new-chat')).toBeAttached();
    await expect(page.locator('#security-assistant')).toBeAttached();
  });

  test('should have accessible send button with title', async ({ page }) => {
    await expect(page.locator('#sa-send-button')).toBeAttached({ timeout: 10000 });
    await expect(page.locator('#sa-send-button')).toHaveAttribute('title', 'Send message');
  });

  test('should have accessible delete buttons with title', async ({ page }) => {
    // Mock sessions
    await page.route('**/api/ai-assistant/sessions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          count: 1,
          sessions: [{ id: 'acc-session', title: 'Test', message_count: 0, last_activity: new Date().toISOString() }],
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.sa-session-delete')).toBeAttached({ timeout: 10000 });
    await expect(page.locator('.sa-session-delete')).toHaveAttribute('title', 'Delete conversation');
  });

  test('should support Enter key to send message', async ({ page }) => {
    // Mock APIs
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'enter-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user_message: { id: 'u-enter', role: 'user', content: 'Enter key test', timestamp: new Date().toISOString() },
          assistant_message: { id: 'a-enter', role: 'assistant', content: 'Response', timestamp: new Date().toISOString() },
        }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Type and press Enter
    await page.fill('#sa-message-input', 'Enter key test');
    await page.press('#sa-message-input', 'Enter');

    // Message should be sent (input cleared)
    await expect(page.locator('#sa-message-input')).toHaveValue('', { timeout: 3000 });
  });
});


// =============================================================================
// API Integration Tests (Mocked)
// =============================================================================

test.describe('AI Assistant API Integration', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should call sessions API on page load', async ({ page }) => {
    let sessionsApiCalled = false;

    await page.route('**/api/ai-assistant/sessions/', route => {
      sessionsApiCalled = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    expect(sessionsApiCalled).toBe(true);
  });

  test('should call suggestions API on page load', async ({ page }) => {
    let suggestionsApiCalled = false;

    await page.route('**/api/ai-assistant/suggestions/', route => {
      suggestionsApiCalled = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', suggestions: [], health_score: null }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    expect(suggestionsApiCalled).toBe(true);
  });

  test('should handle concurrent API calls without race conditions', async ({ page }) => {
    // Mock both APIs with delays
    await page.route('**/api/ai-assistant/sessions/', route => {
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            count: 1,
            sessions: [{ id: 'race-session', title: 'Delayed Session', message_count: 0, last_activity: new Date().toISOString() }],
          }),
        });
      }, 500);
    });

    await page.route('**/api/ai-assistant/suggestions/', route => {
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', suggestions: [], health_score: 90 }),
        });
      }, 300);
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Both should resolve without errors
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sa-session-item')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.sa-health-badge')).toBeVisible({ timeout: 5000 });
  });

  test('API response times should be acceptable', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    const endTime = Date.now();
    const loadTime = endTime - startTime;

    // Page should load within 8 seconds
    expect(loadTime).toBeLessThan(8000);
  });
});


// =============================================================================
// Mobile / Responsive Tests
// =============================================================================

test.describe('AI Assistant Mobile Responsiveness', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('should show sidebar toggle on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Mobile toggle should be visible
    await expect(page.locator('#sa-sidebar-toggle')).toBeVisible({ timeout: 10000 });
  });

  test('should toggle sidebar on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Toggle sidebar open
    await page.click('#sa-sidebar-toggle');

    // Sidebar should have 'open' class
    await expect(page.locator('.sa-sidebar.open')).toBeVisible({ timeout: 3000 });
  });
});


// =============================================================================
// Security Tests
// =============================================================================

test.describe('AI Assistant Security', () => {
  test('should require authentication for AI assistant page', async ({ page }) => {
    // Try to access without login
    await page.goto(`${BASE_URL}/security/ai-assistant`);

    // Should redirect to login/home
    await expect(page).not.toHaveURL(/security\/ai-assistant/);
  });

  test('should not leak sensitive data in console logs', async ({ page }) => {
    const consoleLogs = [];
    page.on('console', msg => consoleLogs.push(msg.text()));

    await loginUser(page);

    // Mock APIs
    await page.route('**/api/ai-assistant/sessions/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
      });
    });

    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Check that no passwords are leaked in console
    const hasLeakedPassword = consoleLogs.some(log =>
      log.toLowerCase().includes('password') &&
      !log.toLowerCase().includes('password security') &&
      !log.toLowerCase().includes('password health')
    );
    expect(hasLeakedPassword).toBe(false);
  });
});


// =============================================================================
// Full Workflow Integration Test
// =============================================================================

test.describe('AI Assistant Full Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
  });

  test('complete conversation workflow: navigate → create session → send message → view response', async ({ page }) => {
    // Mock session creation
    await page.route('**/api/ai-assistant/sessions/', route => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'created',
            session: { id: 'workflow-session', title: 'New Conversation', message_count: 0, last_activity: new Date().toISOString() },
          }),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success', count: 0, sessions: [] }),
        });
      }
    });

    // Mock send message
    await page.route('**/api/ai-assistant/sessions/*/send/', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          user_message: {
            id: 'wf-user-msg',
            role: 'user',
            content: 'Give me a security overview of my vault',
            timestamp: new Date().toISOString(),
          },
          assistant_message: {
            id: 'wf-assistant-msg',
            role: 'assistant',
            content: '## Security Overview\n\nYour vault contains **20 passwords** with an overall health score of **82/100**.\n\n### Findings:\n- 3 passwords are weak\n- 2 passwords are reused\n- 15 passwords are strong\n\n### Recommendations:\n1. Update your weak passwords immediately\n2. Enable 2FA on critical accounts',
            timestamp: new Date().toISOString(),
          },
        }),
      });
    });

    // Step 1: Navigate to AI Assistant
    await page.goto(`${BASE_URL}/security/ai-assistant`);
    await expect(page.locator('.security-assistant')).toBeVisible({ timeout: 10000 });

    // Step 2: See welcome screen
    await expect(page.locator('#sa-welcome')).toBeVisible();

    // Step 3: Click a starter prompt
    await page.click('#sa-starter-4'); // "Give me a security overview of my vault"

    // Step 4: Message should be sent
    await expect(page.locator('.sa-message.user')).toBeVisible({ timeout: 5000 });

    // Step 5: Assistant response should appear with markdown rendering
    await expect(page.locator('.sa-message.assistant')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sa-message.assistant .sa-message-content')).toContainText('Security Overview');

    // Step 6: Welcome should no longer be visible
    await expect(page.locator('#sa-welcome')).not.toBeVisible();

    // Step 7: Input should be cleared and ready for next message
    await expect(page.locator('#sa-message-input')).toHaveValue('');
    await expect(page.locator('#sa-message-input')).toBeEnabled();
  });
});

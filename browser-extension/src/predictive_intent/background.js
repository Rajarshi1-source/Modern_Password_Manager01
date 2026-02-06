/**
 * Predictive Intent - Browser Extension Background Script
 * ========================================================
 *
 * Background service worker for:
 * - Tab change detection
 * - Context signal batching and sending
 * - WebSocket connection management
 * - Prediction caching
 * - Credential retrieval from vault
 *
 * @author Password Manager Team
 * @created 2026-02-07
 */

// Configuration
const CONFIG = {
  API_BASE: 'https://localhost:8000/api/ml-security',
  WS_URL: 'wss://localhost:8000/ws/predictions/',
  CACHE_EXPIRY_MS: 15 * 60 * 1000, // 15 minutes
  CONTEXT_BATCH_DELAY: 300,
};

// State
let authToken = null;
let wsConnection = null;
let predictionCache = new Map();
let contextQueue = [];
let contextBatchTimer = null;
let isEnabled = true;

// ===========================================================================
// Initialization
// ===========================================================================

chrome.runtime.onInstalled.addListener(() => {
  console.log('[PredictiveIntent] Extension installed');
  initializeExtension();
});

chrome.runtime.onStartup.addListener(() => {
  console.log('[PredictiveIntent] Extension started');
  initializeExtension();
});

async function initializeExtension() {
  // Load settings and auth token
  const stored = await chrome.storage.local.get(['authToken', 'isEnabled']);
  authToken = stored.authToken;
  isEnabled = stored.isEnabled !== false;

  if (authToken && isEnabled) {
    connectWebSocket();
  }

  // Set up tab listeners
  setupTabListeners();
}

// ===========================================================================
// Message Handlers
// ===========================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then(sendResponse)
    .catch((error) => {
      console.error('[PredictiveIntent] Message error:', error);
      sendResponse({ success: false, error: error.message });
    });

  return true; // Keep channel open for async response
});

async function handleMessage(message, sender) {
  switch (message.type) {
    case 'CONTEXT_SIGNAL':
      return handleContextSignal(message.data, sender.tab?.id);

    case 'LOGIN_FORM_DETECTED':
      return handleLoginFormDetected(message.data, sender.tab?.id);

    case 'FILL_CREDENTIAL':
      return handleFillCredential(message.data);

    case 'RECORD_FEEDBACK':
      return handleRecordFeedback(message.data);

    case 'AUTOFILL_READY':
      return handleAutofillReady(message.data, sender.tab?.id);

    case 'GET_PREDICTIONS':
      return handleGetPredictions(message.data);

    case 'SET_AUTH_TOKEN':
      authToken = message.token;
      await chrome.storage.local.set({ authToken: message.token });
      connectWebSocket();
      return { success: true };

    case 'TOGGLE_ENABLED':
      isEnabled = message.enabled;
      await chrome.storage.local.set({ isEnabled: message.enabled });
      if (isEnabled) {
        connectWebSocket();
      } else {
        disconnectWebSocket();
      }
      return { success: true };

    default:
      return { success: false, error: 'Unknown message type' };
  }
}

// ===========================================================================
// Context Signal Handling
// ===========================================================================

async function handleContextSignal(data, tabId) {
  if (!isEnabled || !authToken) {
    return { success: false, error: 'Not enabled or not authenticated' };
  }

  // Add to batch queue
  contextQueue.push({
    ...data,
    tabId,
    timestamp: Date.now(),
  });

  // Debounce - send batch after delay
  if (contextBatchTimer) {
    clearTimeout(contextBatchTimer);
  }

  contextBatchTimer = setTimeout(() => {
    sendContextBatch();
  }, CONFIG.CONTEXT_BATCH_DELAY);

  // Return cached predictions immediately if available
  const cached = getCachedPredictions(data.domain);
  if (cached) {
    return { success: true, predictions: cached, fromCache: true };
  }

  return { success: true, predictions: [], pending: true };
}

async function sendContextBatch() {
  if (contextQueue.length === 0) return;

  // Take the most recent context signal
  const latestContext = contextQueue[contextQueue.length - 1];
  contextQueue = [];

  try {
    const response = await apiRequest('/intent/context/', {
      method: 'POST',
      body: JSON.stringify({
        domain: latestContext.domain,
        url_hash: latestContext.urlHash,
        page_title: latestContext.pageTitle,
        form_fields: latestContext.formFields,
        time_on_page: latestContext.timeOnPage,
        is_new_tab: latestContext.isNewTab,
        device_type: 'extension',
      }),
    });

    if (response.success && response.predictions) {
      cachePredictions(latestContext.domain, response.predictions);

      // Send predictions to the tab
      if (latestContext.tabId) {
        chrome.tabs.sendMessage(latestContext.tabId, {
          type: 'PREDICTIONS_UPDATE',
          predictions: response.predictions,
        });
      }
    }
  } catch (error) {
    console.error('[PredictiveIntent] Context batch failed:', error);
  }
}

// ===========================================================================
// Login Form Detection
// ===========================================================================

async function handleLoginFormDetected(data, tabId) {
  if (!isEnabled || !authToken) {
    return { success: false };
  }

  try {
    const response = await apiRequest('/intent/context/', {
      method: 'POST',
      body: JSON.stringify({
        domain: data.domain,
        url_hash: data.urlHash,
        page_title: data.pageTitle,
        form_fields: ['password'],
        time_on_page: data.timeOnPage,
        is_new_tab: data.isNewTab,
        device_type: 'extension',
      }),
    });

    if (response.success) {
      if (response.predictions) {
        cachePredictions(data.domain, response.predictions);
      }

      return {
        success: true,
        predictions: response.predictions || [],
        loginProbability: response.login_probability,
      };
    }

    return { success: false };
  } catch (error) {
    console.error('[PredictiveIntent] Login form detection failed:', error);
    return { success: false, error: error.message };
  }
}

// ===========================================================================
// Credential Filling
// ===========================================================================

async function handleFillCredential(data) {
  if (!authToken) {
    return { success: false, error: 'Not authenticated' };
  }

  try {
    // Request credential from vault API
    const response = await apiRequest(`/vault/items/${data.vaultItemId}/decrypt/`, {
      method: 'POST',
    });

    if (response.success && response.credential) {
      return {
        success: true,
        credential: response.credential,
      };
    }

    return { success: false, error: 'Failed to decrypt credential' };
  } catch (error) {
    console.error('[PredictiveIntent] Credential fill failed:', error);
    return { success: false, error: error.message };
  }
}

async function handleAutofillReady(data, tabId) {
  // Show notification that autofill is ready
  chrome.action.setBadgeText({ text: '1', tabId });
  chrome.action.setBadgeBackgroundColor({ color: '#00ff88', tabId });

  // Clear badge after 5 seconds
  setTimeout(() => {
    chrome.action.setBadgeText({ text: '', tabId });
  }, 5000);

  return { success: true };
}

// ===========================================================================
// Get Predictions
// ===========================================================================

async function handleGetPredictions(data) {
  // First check cache
  const cached = getCachedPredictions(data.domain);
  if (cached) {
    return { success: true, predictions: cached, fromCache: true };
  }

  // Fetch from API
  try {
    const queryParams = data.domain
      ? `?domain=${encodeURIComponent(data.domain)}`
      : '';
    const response = await apiRequest(`/intent/predictions/${queryParams}`);

    if (response.success) {
      cachePredictions(data.domain, response.predictions);
      return { success: true, predictions: response.predictions };
    }

    return { success: false };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// ===========================================================================
// Feedback Recording
// ===========================================================================

async function handleRecordFeedback(data) {
  if (!authToken) {
    return { success: false };
  }

  try {
    const response = await apiRequest('/intent/feedback/', {
      method: 'POST',
      body: JSON.stringify({
        prediction_id: data.predictionId,
        feedback_type: data.feedbackType,
        time_to_use_ms: data.timeToUseMs,
      }),
    });

    return { success: response.success };
  } catch (error) {
    console.error('[PredictiveIntent] Feedback failed:', error);
    return { success: false };
  }
}

// ===========================================================================
// Tab Listeners
// ===========================================================================

function setupTabListeners() {
  // Listen for tab activation
  chrome.tabs.onActivated.addListener(async (activeInfo) => {
    if (!isEnabled) return;

    try {
      const tab = await chrome.tabs.get(activeInfo.tabId);
      if (tab.url) {
        const domain = new URL(tab.url).hostname;
        triggerPredictionRefresh(domain, activeInfo.tabId);
      }
    } catch (error) {
      // Tab may not exist anymore
    }
  });

  // Listen for tab URL changes
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!isEnabled || changeInfo.status !== 'complete') return;

    if (tab.url) {
      try {
        const domain = new URL(tab.url).hostname;
        triggerPredictionRefresh(domain, tabId);
      } catch (error) {
        // Invalid URL
      }
    }
  });
}

async function triggerPredictionRefresh(domain, tabId) {
  // Check if we have cached predictions
  const cached = getCachedPredictions(domain);

  if (!cached) {
    // Fetch new predictions
    const response = await handleGetPredictions({ domain });

    if (response.success && response.predictions?.length > 0) {
      chrome.tabs.sendMessage(tabId, {
        type: 'PREDICTIONS_UPDATE',
        predictions: response.predictions,
      });
    }
  }
}

// ===========================================================================
// Prediction Cache
// ===========================================================================

function cachePredictions(domain, predictions) {
  predictionCache.set(domain, {
    predictions,
    timestamp: Date.now(),
  });
}

function getCachedPredictions(domain) {
  const cached = predictionCache.get(domain);

  if (cached) {
    const age = Date.now() - cached.timestamp;
    if (age < CONFIG.CACHE_EXPIRY_MS) {
      return cached.predictions;
    } else {
      predictionCache.delete(domain);
    }
  }

  return null;
}

// ===========================================================================
// WebSocket Connection
// ===========================================================================

function connectWebSocket() {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    return;
  }

  if (!authToken) {
    console.log('[PredictiveIntent] No auth token, skipping WebSocket');
    return;
  }

  try {
    wsConnection = new WebSocket(`${CONFIG.WS_URL}?token=${authToken}`);

    wsConnection.onopen = () => {
      console.log('[PredictiveIntent] WebSocket connected');
    };

    wsConnection.onmessage = (event) => {
      handleWebSocketMessage(JSON.parse(event.data));
    };

    wsConnection.onerror = (error) => {
      console.error('[PredictiveIntent] WebSocket error:', error);
    };

    wsConnection.onclose = () => {
      console.log('[PredictiveIntent] WebSocket closed, reconnecting...');
      setTimeout(connectWebSocket, 5000);
    };
  } catch (error) {
    console.error('[PredictiveIntent] WebSocket connection failed:', error);
  }
}

function disconnectWebSocket() {
  if (wsConnection) {
    wsConnection.close();
    wsConnection = null;
  }
}

function handleWebSocketMessage(message) {
  switch (message.type) {
    case 'prediction_push':
      // Cache and broadcast to active tabs
      if (message.trigger_domain) {
        cachePredictions(message.trigger_domain, message.predictions);
      }
      broadcastToActiveTabs({
        type: 'PREDICTIONS_UPDATE',
        predictions: message.predictions,
      });
      break;

    case 'credential_ready':
      // Notify about ready credential
      chrome.action.setBadgeText({ text: '!' });
      chrome.action.setBadgeBackgroundColor({ color: '#00ffff' });
      break;

    case 'pong':
      // Heartbeat response
      break;
  }
}

async function broadcastToActiveTabs(message) {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  tabs.forEach((tab) => {
    chrome.tabs.sendMessage(tab.id, message).catch(() => {});
  });
}

// ===========================================================================
// API Requests
// ===========================================================================

async function apiRequest(endpoint, options = {}) {
  const url = `${CONFIG.API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

// ===========================================================================
// Heartbeat
// ===========================================================================

setInterval(() => {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    wsConnection.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);

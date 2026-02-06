/**
 * Predictive Intent - Browser Extension Content Script
 * =====================================================
 *
 * Injected into web pages to:
 * - Detect login forms
 * - Send context signals to backend
 * - Receive predicted credentials
 * - Auto-fill when confidence is high
 *
 * @author Password Manager Team
 * @created 2026-02-07
 */

(function () {
  'use strict';

  // Configuration
  const CONFIG = {
    MIN_AUTOFILL_CONFIDENCE: 0.9,
    CONTEXT_SIGNAL_DELAY: 500,
    FORM_DETECTION_INTERVAL: 1000,
  };

  // State
  let lastContextSignal = null;
  let predictions = [];
  let isEnabled = true;
  let popupVisible = false;

  // ===========================================================================
  // Initialization
  // ===========================================================================

  function init() {
    console.log('[PredictiveIntent] Content script initialized');

    // Listen for messages from background script
    chrome.runtime.onMessage.addListener(handleBackgroundMessage);

    // Start form detection
    detectLoginForms();

    // Observe DOM changes for dynamic forms
    observeDOMChanges();

    // Send initial context signal
    sendContextSignal();
  }

  // ===========================================================================
  // Form Detection
  // ===========================================================================

  function detectLoginForms() {
    const forms = document.querySelectorAll('form');
    const loginForms = [];

    forms.forEach((form) => {
      const formFields = analyzeForm(form);
      if (formFields.isLoginForm) {
        loginForms.push({
          element: form,
          fields: formFields,
        });
      }
    });

    // Also check for standalone inputs (not in form)
    const standaloneInputs = detectStandaloneInputs();
    if (standaloneInputs.length > 0) {
      loginForms.push({
        element: null,
        fields: {
          isLoginForm: true,
          hasUsername: true,
          hasPassword: standaloneInputs.some((i) => i.type === 'password'),
          inputs: standaloneInputs,
        },
      });
    }

    if (loginForms.length > 0) {
      handleLoginFormDetected(loginForms);
    }

    return loginForms;
  }

  function analyzeForm(form) {
    const inputs = form.querySelectorAll('input');
    const result = {
      isLoginForm: false,
      hasUsername: false,
      hasPassword: false,
      hasEmail: false,
      fields: [],
    };

    inputs.forEach((input) => {
      const type = input.type.toLowerCase();
      const name = (input.name || input.id || '').toLowerCase();
      const placeholder = (input.placeholder || '').toLowerCase();
      const autocomplete = (input.autocomplete || '').toLowerCase();

      if (type === 'password') {
        result.hasPassword = true;
        result.fields.push('password');
      } else if (
        type === 'email' ||
        name.includes('email') ||
        autocomplete === 'email' ||
        placeholder.includes('email')
      ) {
        result.hasEmail = true;
        result.fields.push('email');
      } else if (
        type === 'text' &&
        (name.includes('user') ||
          name.includes('login') ||
          autocomplete === 'username' ||
          placeholder.includes('username') ||
          placeholder.includes('user'))
      ) {
        result.hasUsername = true;
        result.fields.push('username');
      }
    });

    result.isLoginForm =
      result.hasPassword && (result.hasUsername || result.hasEmail);

    return result;
  }

  function detectStandaloneInputs() {
    const passwordInputs = document.querySelectorAll(
      'input[type="password"]:not(form input)'
    );
    const usernameInputs = document.querySelectorAll(
      'input[autocomplete="username"]:not(form input), input[name*="user"]:not(form input)'
    );

    const inputs = [];
    passwordInputs.forEach((input) =>
      inputs.push({ type: 'password', element: input })
    );
    usernameInputs.forEach((input) =>
      inputs.push({ type: 'username', element: input })
    );

    return inputs;
  }

  function observeDOMChanges() {
    const observer = new MutationObserver((mutations) => {
      let shouldCheck = false;

      mutations.forEach((mutation) => {
        if (mutation.addedNodes.length > 0) {
          mutation.addedNodes.forEach((node) => {
            if (
              node.nodeName === 'FORM' ||
              node.nodeName === 'INPUT' ||
              (node.querySelector && node.querySelector('form, input'))
            ) {
              shouldCheck = true;
            }
          });
        }
      });

      if (shouldCheck) {
        setTimeout(detectLoginForms, 100);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  // ===========================================================================
  // Context Signals
  // ===========================================================================

  function sendContextSignal() {
    const now = Date.now();

    // Debounce - don't send more than once per second
    if (lastContextSignal && now - lastContextSignal < 1000) {
      return;
    }

    lastContextSignal = now;

    const contextData = {
      domain: window.location.hostname,
      urlHash: hashString(window.location.href),
      pageTitle: document.title,
      formFields: detectFormFieldTypes(),
      timeOnPage: Math.floor(performance.now() / 1000),
      isNewTab: false,
    };

    // Send to background script
    chrome.runtime.sendMessage(
      {
        type: 'CONTEXT_SIGNAL',
        data: contextData,
      },
      (response) => {
        if (response && response.success) {
          handlePredictionsReceived(response.predictions);
        }
      }
    );
  }

  function detectFormFieldTypes() {
    const fields = [];
    const forms = document.querySelectorAll('form');

    forms.forEach((form) => {
      const inputs = form.querySelectorAll('input');
      inputs.forEach((input) => {
        const type = input.type.toLowerCase();
        if (['text', 'email', 'password', 'tel'].includes(type)) {
          fields.push(type);
        }
      });
    });

    return [...new Set(fields)];
  }

  function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash;
    }
    return hash.toString(16);
  }

  // ===========================================================================
  // Prediction Handling
  // ===========================================================================

  function handleLoginFormDetected(forms) {
    console.log('[PredictiveIntent] Login form detected:', forms.length);

    // Send context signal with form detected
    const contextData = {
      domain: window.location.hostname,
      urlHash: hashString(window.location.href),
      pageTitle: document.title,
      formFields: ['password'],
      timeOnPage: Math.floor(performance.now() / 1000),
      isNewTab: false,
    };

    chrome.runtime.sendMessage(
      {
        type: 'LOGIN_FORM_DETECTED',
        data: contextData,
      },
      (response) => {
        if (response && response.success) {
          handlePredictionsReceived(response.predictions);

          // Show prediction popup if we have high-confidence predictions
          if (response.predictions && response.predictions.length > 0) {
            showPredictionPopup(response.predictions, forms[0]);
          }
        }
      }
    );
  }

  function handlePredictionsReceived(newPredictions) {
    if (!newPredictions || newPredictions.length === 0) {
      return;
    }

    predictions = newPredictions;
    console.log(
      '[PredictiveIntent] Received predictions:',
      predictions.length
    );

    // Check for auto-fill if confidence is very high
    const highConfidence = predictions.filter(
      (p) => p.confidence >= CONFIG.MIN_AUTOFILL_CONFIDENCE
    );

    if (highConfidence.length === 1) {
      // Only one high-confidence match - consider auto-filling
      notifyAutoFillReady(highConfidence[0]);
    }
  }

  function notifyAutoFillReady(prediction) {
    chrome.runtime.sendMessage({
      type: 'AUTOFILL_READY',
      data: {
        predictionId: prediction.id,
        vaultItemId: prediction.vault_item_id,
        confidence: prediction.confidence,
        domain: window.location.hostname,
      },
    });
  }

  // ===========================================================================
  // Prediction Popup UI
  // ===========================================================================

  function showPredictionPopup(predictions, form) {
    if (popupVisible) return;

    const popup = createPopupElement(predictions);

    // Position near the form
    if (form.element) {
      const rect = form.element.getBoundingClientRect();
      popup.style.top = `${rect.bottom + window.scrollY + 5}px`;
      popup.style.left = `${rect.left + window.scrollX}px`;
    }

    document.body.appendChild(popup);
    popupVisible = true;

    // Auto-hide after 10 seconds
    setTimeout(() => {
      removePopup();
    }, 10000);
  }

  function createPopupElement(predictions) {
    const popup = document.createElement('div');
    popup.id = 'pm-prediction-popup';
    popup.style.cssText = `
      position: absolute;
      z-index: 999999;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border-radius: 12px;
      padding: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #e0e0e0;
      max-width: 300px;
      border: 1px solid rgba(0, 255, 255, 0.3);
    `;

    popup.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-size: 12px; color: #00ffff; font-weight: 600;">🔮 Predicted Passwords</span>
        <button id="pm-popup-close" style="
          background: none;
          border: none;
          color: #888;
          cursor: pointer;
          font-size: 16px;
          padding: 2px 6px;
        ">×</button>
      </div>
      ${predictions
        .slice(0, 3)
        .map(
          (pred, i) => `
        <div class="pm-prediction-item" data-id="${pred.id}" data-vault="${pred.vault_item_id}" style="
          padding: 8px;
          margin: 4px 0;
          background: rgba(255,255,255,0.05);
          border-radius: 6px;
          cursor: pointer;
          transition: background 0.2s;
        " onmouseover="this.style.background='rgba(0,255,255,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">
          <div style="font-size: 13px; font-weight: 500;">
            ${pred.vault_item_name || 'Credential ' + (i + 1)}
          </div>
          <div style="display: flex; justify-content: space-between; margin-top: 4px;">
            <span style="font-size: 11px; color: #888;">${pred.reason || 'Predicted'}</span>
            <span style="font-size: 11px; color: ${pred.confidence > 0.8 ? '#00ff88' : '#ffbb00'};">
              ${Math.round(pred.confidence * 100)}% match
            </span>
          </div>
        </div>
      `
        )
        .join('')}
    `;

    // Add event listeners
    popup.querySelector('#pm-popup-close').addEventListener('click', removePopup);

    popup.querySelectorAll('.pm-prediction-item').forEach((item) => {
      item.addEventListener('click', () => {
        const predictionId = item.dataset.id;
        const vaultItemId = item.dataset.vault;
        requestCredentialFill(predictionId, vaultItemId);
      });
    });

    return popup;
  }

  function removePopup() {
    const popup = document.getElementById('pm-prediction-popup');
    if (popup) {
      popup.remove();
    }
    popupVisible = false;
  }

  function requestCredentialFill(predictionId, vaultItemId) {
    chrome.runtime.sendMessage(
      {
        type: 'FILL_CREDENTIAL',
        data: {
          predictionId,
          vaultItemId,
          domain: window.location.hostname,
        },
      },
      (response) => {
        if (response && response.success) {
          fillCredential(response.credential);
          recordFeedback(predictionId, 'used', {
            timeToUseMs: Date.now() - lastContextSignal,
          });
        }
      }
    );

    removePopup();
  }

  // ===========================================================================
  // Credential Filling
  // ===========================================================================

  function fillCredential(credential) {
    if (!credential) return;

    const usernameFields = document.querySelectorAll(
      'input[type="text"][autocomplete="username"], input[type="email"], input[name*="user"], input[name*="email"], input[id*="user"], input[id*="email"]'
    );
    const passwordFields = document.querySelectorAll('input[type="password"]');

    usernameFields.forEach((field) => {
      if (credential.username) {
        field.value = credential.username;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    passwordFields.forEach((field) => {
      if (credential.password) {
        field.value = credential.password;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    console.log('[PredictiveIntent] Credential filled');
  }

  // ===========================================================================
  // Feedback
  // ===========================================================================

  function recordFeedback(predictionId, feedbackType, options = {}) {
    chrome.runtime.sendMessage({
      type: 'RECORD_FEEDBACK',
      data: {
        predictionId,
        feedbackType,
        ...options,
      },
    });
  }

  // ===========================================================================
  // Background Message Handler
  // ===========================================================================

  function handleBackgroundMessage(message, sender, sendResponse) {
    switch (message.type) {
      case 'PREDICTIONS_UPDATE':
        handlePredictionsReceived(message.predictions);
        sendResponse({ success: true });
        break;

      case 'TOGGLE_ENABLED':
        isEnabled = message.enabled;
        if (!isEnabled) {
          removePopup();
        }
        sendResponse({ success: true });
        break;

      case 'FILL_CREDENTIAL_RESPONSE':
        if (message.success) {
          fillCredential(message.credential);
        }
        break;

      default:
        sendResponse({ success: false, error: 'Unknown message type' });
    }

    return true; // Keep channel open for async response
  }

  // ===========================================================================
  // Start
  // ===========================================================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

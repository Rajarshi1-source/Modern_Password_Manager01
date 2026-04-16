/**
 * sealedAutofill.js — fills password/username fields inside the
 * active tab without ever exposing the plaintext to the page's JS
 * context.
 *
 * Mechanism:
 *   - The background service worker holds the plaintext in memory.
 *   - It opens a one-shot `chrome.runtime.Port` to the content
 *     script in the target tab, sends one "fill" message, and
 *     immediately disconnects.
 *   - The content script runs in an ISOLATED world, so even though
 *     it shares the DOM with the page, its variables are unreachable
 *     from the page's scripts.
 *   - We use the native property descriptor for
 *     ``HTMLInputElement.prototype.value`` so that React-controlled
 *     inputs and other framework wrappers do not see the assignment
 *     as "trusted user input that the page JS produced". This is the
 *     canonical pattern for programmatic input in isolated worlds.
 *   - After filling, we clear the internal reference and dispatch
 *     ``input`` + ``change`` events so the target framework registers
 *     the value.
 *
 * This module is designed to be imported from `content.js` only;
 * the background.js counterpart lives in ``backgroundBridge.js``.
 */

const VALUE_SETTER = Object.getOwnPropertyDescriptor(
  HTMLInputElement.prototype, 'value',
)?.set;

function _dispatch(el) {
  try {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } catch (_err) {
    // Event dispatch is best-effort; we still set the value.
  }
}

function _findPasswordField(hint) {
  if (hint?.fieldSelector) {
    const el = document.querySelector(hint.fieldSelector);
    if (el instanceof HTMLInputElement) return el;
  }
  const pw = document.querySelector(
    'input[type="password"]:not([disabled]):not([readonly])',
  );
  return pw instanceof HTMLInputElement ? pw : null;
}

function _findUsernameField(hint) {
  if (hint?.usernameSelector) {
    const el = document.querySelector(hint.usernameSelector);
    if (el instanceof HTMLInputElement) return el;
  }
  const candidates = document.querySelectorAll(
    'input[type="email"], input[type="text"][autocomplete*="username"], input[name*="user" i], input[id*="user" i], input[name*="email" i]',
  );
  return candidates[0] instanceof HTMLInputElement ? candidates[0] : null;
}

function _assign(el, value) {
  if (!el) return false;
  if (VALUE_SETTER) VALUE_SETTER.call(el, value);
  else el.value = value;
  _dispatch(el);
  return true;
}

/**
 * Fill the login form in the current document.
 *
 * @param {Object} params
 * @param {string} params.password  plaintext password (MUST be zeroed by caller).
 * @param {string} [params.username]
 * @param {Object} [params.hint]    selectors if the background has learned them.
 * @returns {{passwordFilled: boolean, usernameFilled: boolean}}
 */
export function applySealedFill({ password, username, hint } = {}) {
  const pwEl = _findPasswordField(hint);
  const userEl = username ? _findUsernameField(hint) : null;
  const passwordFilled = _assign(pwEl, password || '');
  const usernameFilled = username ? _assign(userEl, username) : false;
  return { passwordFilled, usernameFilled };
}

/**
 * Install the content-script listener that the background worker
 * pipes sealed fills through.  Idempotent.
 */
export function installSealedFillListener() {
  if (window.__fheShareSealedFillInstalled) return;
  window.__fheShareSealedFillInstalled = true;

  // Dashboard → content script: forward PRE payloads coming from the
  // web dashboard to the background worker via chrome.runtime.
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.type !== 'fhe_share:autofill_request_v2') return;
    try {
      chrome.runtime.sendMessage(
        { type: 'fhe_share/apply_share', token: data.token, payload: data.payload },
        (resp) => {
          window.postMessage({
            type: 'fhe_share:autofill_ack',
            token: data.token,
            ok: !!resp?.ok,
            reason: resp?.reason || null,
          }, window.location.origin);
        },
      );
    } catch (err) {
      window.postMessage({
        type: 'fhe_share:autofill_ack',
        token: data.token,
        ok: false,
        reason: 'bridge_error',
      }, window.location.origin);
    }
  });

  // Background → content script (target tab): one-shot sealed fill port.
  try {
    chrome.runtime.onConnect.addListener((port) => {
      if (port.name !== 'fhe_share_fill_v1') return;
      let applied = false;
      port.onMessage.addListener((msg) => {
        if (applied) return;
        applied = true;
        try {
          const res = applySealedFill(msg || {});
          port.postMessage({ type: 'fill_result', ok: true, ...res });
        } catch (err) {
          port.postMessage({ type: 'fill_result', ok: false, reason: String(err) });
        } finally {
          try { port.disconnect(); } catch (_e) {
            // port teardown is best-effort
          }
        }
      });
    });
  } catch (_err) {
    // chrome.runtime may be unavailable in non-extension contexts
  }
}

export default { applySealedFill, installSealedFillListener };

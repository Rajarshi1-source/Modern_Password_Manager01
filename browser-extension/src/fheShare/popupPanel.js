/**
 * popupPanel.js — tiny UI fragment rendered inside the extension
 * popup that shows:
 *
 *   - Whether an Umbral identity is provisioned in the extension.
 *   - A button to pull the identity from the dashboard's
 *     ``localStorage`` via a scripted tab.
 *   - (Future) a list of received `umbral-v1` shares waiting for
 *     an active tab match.
 *
 * The purpose is not a full share management UI; the web dashboard
 * remains the source of truth.  The popup only needs to confirm
 * "your extension can decrypt umbral-v1 autofill tokens".
 */

const EXTENSION_ORIGIN_HINTS = [
  'http://localhost:3000',
  'http://localhost:8000',
  'https://your-password-manager.com',
];

async function _askBackground(type, extras = {}) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage({ type, ...extras }, (resp) => resolve(resp || null));
    } catch (_e) {
      resolve(null);
    }
  });
}

async function _findDashboardTab() {
  return new Promise((resolve) => {
    try {
      chrome.tabs.query({}, (tabs) => {
        for (const t of tabs) {
          if (!t.url) continue;
          if (EXTENSION_ORIGIN_HINTS.some((o) => t.url.startsWith(o))) {
            return resolve(t);
          }
        }
        resolve(null);
      });
    } catch (_e) {
      resolve(null);
    }
  });
}

async function _fetchIdentityFromDashboardTab(tab) {
  return new Promise((resolve) => {
    try {
      chrome.scripting.executeScript(
        {
          target: { tabId: tab.id },
          func: () => {
            const raw = window.localStorage.getItem('fhe:pre:umbral_identity_v1');
            return raw ? JSON.parse(raw) : null;
          },
        },
        (injection) => {
          const record = injection?.[0]?.result;
          if (!record || record.wrapped) return resolve(null);
          resolve(record);
        },
      );
    } catch (_e) {
      resolve(null);
    }
  });
}

function _renderStatus(host, message, tone) {
  const colors = {
    ok: '#4CAF50',
    warn: '#f59e0b',
    err: '#cc0000',
  };
  host.innerHTML = `
    <div style="display:flex;align-items:center;gap:0.5rem;font-size:12px;color:${colors[tone] || '#666'};">
      <span style="width:8px;height:8px;border-radius:50%;background:${colors[tone] || '#666'};"></span>
      <span>${message}</span>
    </div>`;
}

/**
 * Initialise the popup panel.  Expects a host element to paint into.
 * Safe to call multiple times; idempotent on the DOM.
 */
export async function initFheSharePanel(host) {
  if (!host) return;
  host.dataset.fheShareInit = '1';

  const title = document.createElement('div');
  title.style.cssText = 'font-weight:600;font-size:13px;margin-bottom:4px;';
  title.textContent = 'Homomorphic Share (PRE)';

  const status = document.createElement('div');
  status.style.cssText = 'margin-bottom:6px;';

  const button = document.createElement('button');
  button.textContent = 'Sync identity from dashboard';
  button.style.cssText = 'padding:6px 10px;font-size:12px;border-radius:6px;border:1px solid #ddd;background:#fff;cursor:pointer;';

  host.innerHTML = '';
  host.appendChild(title);
  host.appendChild(status);
  host.appendChild(button);

  async function refresh() {
    const resp = await _askBackground('fhe_share/get_public_keys');
    if (resp?.public?.umbralPublicKey) {
      _renderStatus(status, 'Identity provisioned — ready to receive sealed fills', 'ok');
    } else {
      _renderStatus(status, 'No Umbral identity yet. Click below while the dashboard tab is open.', 'warn');
    }
  }

  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const tab = await _findDashboardTab();
      if (!tab) {
        _renderStatus(status, 'Open the Homomorphic Sharing dashboard first.', 'err');
        return;
      }
      const record = await _fetchIdentityFromDashboardTab(tab);
      if (!record) {
        _renderStatus(status, 'Identity is locked on dashboard; unlock vault and retry.', 'err');
        return;
      }
      await _askBackground('fhe_share/set_identity', {
        identity: {
          publicKeys: record.publicKeys,
          secretB64: record.payload,
        },
      });
      _renderStatus(status, 'Identity synced — ready to receive sealed fills', 'ok');
    } finally {
      button.disabled = false;
    }
  });

  await refresh();
}

export default { initFheSharePanel };

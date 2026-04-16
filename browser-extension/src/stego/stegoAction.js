/**
 * "Unlock from stego image" popup action.
 *
 * Wires the extension popup UI to the local PNG-LSB + HiddenVaultBlob
 * pipeline so the user can pick a stego PNG, enter a password, and
 * hydrate the extension's in-memory vault without ever sending the
 * ciphertext or plaintext across the network.
 *
 * The module deliberately keeps its surface small so it's easy to
 * stub in unit tests: ``initStegoAction(container)`` wires up a button
 * + file picker, and ``unlockFromStegoImage({ bytes, password })``
 * performs the cryptographic work.
 */

import { extractBlobFromPng } from './pngLsb';
import { decode as decodeBlob, bytesToJson } from './hiddenVaultEnvelope';

const DEFAULT_STEGO_KEY = new TextEncoder().encode('default-png-lsb-key');

export async function unlockFromStegoImage({ bytes, password, stegoKey = null }) {
  if (!(bytes instanceof Uint8Array)) {
    throw new TypeError('bytes must be a Uint8Array');
  }
  if (!password) {
    throw new Error('password is required');
  }
  const blob = await extractBlobFromPng(bytes, {
    stegoKey: stegoKey || DEFAULT_STEGO_KEY,
  });
  const { slotIndex, payload } = await decodeBlob(blob, password);
  return { slotIndex, payload, json: bytesToJson(payload) };
}

/**
 * Attach a minimal stego UI to ``container``. Safe to call multiple
 * times (it's a no-op after the first mount).
 */
export function initStegoAction(container) {
  if (!container || container.dataset.stegoInitialized === '1') return;
  container.dataset.stegoInitialized = '1';

  const wrap = document.createElement('div');
  wrap.className = 'stego-action';
  wrap.style.marginTop = '12px';
  wrap.style.padding = '12px';
  wrap.style.background = '#fff';
  wrap.style.border = '1px solid #e5e7eb';
  wrap.style.borderRadius = '6px';
  wrap.innerHTML = `
    <div style="font-size:13px;font-weight:600;margin-bottom:6px;">🖼️ Unlock from stego image</div>
    <input type="file" accept="image/png" id="stego-file" style="width:100%;margin-bottom:6px;" />
    <input type="password" placeholder="Password" id="stego-pass"
      style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;margin-bottom:6px;" />
    <button id="stego-go"
      style="width:100%;padding:8px;background:#7B68EE;color:#fff;border:none;border-radius:4px;cursor:pointer;">
      Unlock
    </button>
    <div id="stego-status" style="margin-top:6px;font-size:12px;color:#475569;"></div>
  `;
  container.appendChild(wrap);

  const fileInput = wrap.querySelector('#stego-file');
  const passInput = wrap.querySelector('#stego-pass');
  const goBtn = wrap.querySelector('#stego-go');
  const statusDiv = wrap.querySelector('#stego-status');

  goBtn.addEventListener('click', async () => {
    const file = fileInput.files && fileInput.files[0];
    const password = passInput.value;
    if (!file) {
      statusDiv.textContent = 'Pick a stego PNG first.';
      statusDiv.style.color = '#b91c1c';
      return;
    }
    if (!password) {
      statusDiv.textContent = 'Password is required.';
      statusDiv.style.color = '#b91c1c';
      return;
    }
    statusDiv.style.color = '#475569';
    statusDiv.textContent = 'Unlocking…';
    goBtn.disabled = true;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const { slotIndex, json } = await unlockFromStegoImage({ bytes, password });
      statusDiv.style.color = '#166534';
      statusDiv.textContent = `Unlocked slot ${slotIndex} (${
        json && json.items ? `${json.items.length} items` : 'payload decoded'
      }).`;
      // Hand the decrypted vault JSON off to the background service
      // worker so it can hydrate the live autofill vault. We wrap it
      // in a message instead of writing directly to chrome.storage so
      // that existing lock/unlock plumbing stays authoritative.
      if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
        try {
          chrome.runtime.sendMessage({
            action: 'stego_hydrate_vault',
            slotIndex,
            vault: json,
          });
        } catch (e) {
          // best-effort
        }
      }
      passInput.value = '';
    } catch (err) {
      statusDiv.style.color = '#b91c1c';
      statusDiv.textContent = `Failed: ${err.message || 'wrong password or corrupt image.'}`;
    } finally {
      goBtn.disabled = false;
    }
  });
}

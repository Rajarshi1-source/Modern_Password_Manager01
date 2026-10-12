/**
 * Copy a secret, then clear it from the clipboard after the user's
 * "Clear Clipboard Automatically" timeout (Settings > Security).
 *
 * F12 in docs/pqc-hybrid-architecture-review.md: the setting
 * (`security.clearClipboard`, `security.clipboardTimeout`) used to be shown
 * in the UI but read by nothing, so copied passwords stayed on the clipboard.
 *
 * The clear only happens if the clipboard still holds the copied value,
 * checked with readText() where the browser permits it, so something the
 * user copied afterwards is left alone. Where reading is not permitted the
 * clear is best-effort. Browsers can also refuse the write (for example
 * Chromium when the page is not focused); that is logged, not thrown.
 */

import preferencesService from '../services/preferencesService';
import { copyToClipboard } from './clipboard';

export const DEFAULT_CLIPBOARD_TIMEOUT_SECONDS = 30;

let pendingTimer = null;

/** The user's clipboard-clear settings, with the defaults applied. */
export function getClipboardClearSettings(prefs = preferencesService) {
  const enabled = prefs.get('security.clearClipboard', true) !== false;
  const seconds = Number(prefs.get('security.clipboardTimeout', DEFAULT_CLIPBOARD_TIMEOUT_SECONDS));
  const timeoutSeconds =
    Number.isFinite(seconds) && seconds > 0 ? seconds : DEFAULT_CLIPBOARD_TIMEOUT_SECONDS;
  return { enabled, timeoutMs: timeoutSeconds * 1000 };
}

/** Clear the clipboard now if it still holds `value` (or unconditionally if value is null). */
export async function clearClipboardIfUnchanged(value) {
  const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
  if (!clipboard?.writeText) return false;
  if (value != null && typeof clipboard.readText === 'function') {
    try {
      if ((await clipboard.readText()) !== value) return false;
    } catch {
      // Reading not permitted: fall through and clear anyway (best-effort).
    }
  }
  try {
    await clipboard.writeText('');
    return true;
  } catch (err) {
    console.warn('Could not clear the clipboard:', err?.message || err);
    return false;
  }
}

/**
 * Schedule the clear for a value that is already on the clipboard (for
 * example, copied by a sandboxed iframe). Pass null when the value is not
 * known; the clear is then unconditional. A newer schedule replaces an older
 * one. Returns false when the user turned auto-clear off.
 */
export function scheduleClipboardClear(value, { prefs } = {}) {
  cancelScheduledClipboardClear();
  const { enabled, timeoutMs } = getClipboardClearSettings(prefs);
  if (!enabled) return false;
  pendingTimer = setTimeout(() => {
    pendingTimer = null;
    clearClipboardIfUnchanged(value);
  }, timeoutMs);
  return true;
}

export function cancelScheduledClipboardClear() {
  if (pendingTimer !== null) {
    clearTimeout(pendingTimer);
    pendingTimer = null;
  }
}

/** Copy `text` and schedule its clear. Rejects if the copy itself fails. */
export async function copySecret(text, options = {}) {
  await copyToClipboard(text);
  scheduleClipboardClear(text, options);
}

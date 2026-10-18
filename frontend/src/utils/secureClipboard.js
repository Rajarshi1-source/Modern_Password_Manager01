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
 * clear is best-effort. Browsers can also refuse the write (Firefox and
 * Safari need a fresh user gesture; Chromium a focused page). A refused clear
 * is told to the user, and remembered so Settings can say so too.
 *
 * The timer lives in this page, so it cannot run after the tab is closed or
 * discarded (desktop and extension password managers clear from a process
 * that outlives the window; a web page has none). Closing the tab therefore
 * attempts one best-effort clear on `pagehide`, which browsers usually drop,
 * and, because nothing after hiding is guaranteed to run, records the clear
 * as not done until a later clear succeeds. Nothing is cleared when the page
 * is merely hidden: that is the user switching away to paste.
 */

import preferencesService from '../services/preferencesService';
import { toast } from 'react-hot-toast';
import { copyToClipboard } from './clipboard';

export const DEFAULT_CLIPBOARD_TIMEOUT_SECONDS = 30;

let pendingTimer = null;
// Advanced whenever a clear is scheduled or cancelled. A clear captures it
// and re-checks it after awaiting readText(), so an older clear that was
// already running cannot erase a newer copy (even of the same secret).
let scheduleGeneration = 0;
let pendingValue = null;
let pageExitListening = false;

const CLEAR_FAILED_KEY = 'clipboardAutoClearFailed';
const CLEAR_HINT_KEY = 'clipboardClearHintShown';

/**
 * True if the most recent automatic clear did not happen: the browser refused
 * it, or the page was hidden or closed while it was still pending.
 */
export function clipboardAutoClearFailed() {
  try {
    return localStorage.getItem(CLEAR_FAILED_KEY) === '1';
  } catch {
    return false;
  }
}

function recordClearOutcome(cleared, { silent = false } = {}) {
  try {
    if (cleared) localStorage.removeItem(CLEAR_FAILED_KEY);
    else localStorage.setItem(CLEAR_FAILED_KEY, '1');
  } catch {
    // Storage unavailable: the toast below still tells the user.
  }
  if (!cleared && !silent) {
    toast.error(
      'Your browser blocked clearing the clipboard. The copied password may '
      + 'still be there: copy something else to replace it.',
      { id: 'clipboard-clear-failed', duration: 10000 },
    );
  }
}

/** The user's clipboard-clear settings, with the defaults applied. */
export function getClipboardClearSettings(prefs = preferencesService) {
  const enabled = prefs.get('security.clearClipboard', true) !== false;
  const seconds = Number(prefs.get('security.clipboardTimeout', DEFAULT_CLIPBOARD_TIMEOUT_SECONDS));
  const timeoutSeconds =
    Number.isFinite(seconds) && seconds > 0 ? seconds : DEFAULT_CLIPBOARD_TIMEOUT_SECONDS;
  return { enabled, timeoutMs: timeoutSeconds * 1000 };
}

// Mirror of copyToClipboard's execCommand fallback (no Clipboard API, or not a
// secure context): a `copy` event whose data we replace with ''. Browsers may
// refuse execCommand outside a user gesture, so this is best-effort, and the
// clipboard cannot be read first to check it still holds the secret.
function clearViaExecCommand() {
  if (typeof document === 'undefined' || typeof document.execCommand !== 'function') return false;
  const onCopy = (event) => {
    event.clipboardData?.setData('text/plain', '');
    event.preventDefault();
  };
  document.addEventListener('copy', onCopy);
  try {
    return document.execCommand('copy') === true;
  } catch {
    return false;
  } finally {
    document.removeEventListener('copy', onCopy);
  }
}

/**
 * Clear the clipboard now if it still holds `value` (or unconditionally if
 * value is null). `generation`, when given, must still be current after the
 * clipboard read, or the clear is abandoned as superseded.
 */
export async function clearClipboardIfUnchanged(value, generation) {
  const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
  if (!clipboard?.writeText || (typeof window !== 'undefined' && window.isSecureContext === false)) {
    const cleared = clearViaExecCommand();
    recordClearOutcome(cleared);
    return cleared;
  }
  if (value != null && typeof clipboard.readText === 'function') {
    try {
      if ((await clipboard.readText()) !== value) {
        // Already replaced: the secret is off the clipboard, which is the
        // outcome a clear is for (no toast, nothing was attempted).
        if (generation === undefined || generation === scheduleGeneration) recordClearOutcome(true);
        return false;
      }
    } catch {
      // Reading not permitted: fall through and clear anyway (best-effort).
    }
    if (generation !== undefined && generation !== scheduleGeneration) return false;
  }
  try {
    await clipboard.writeText('');
    recordClearOutcome(true);
    return true;
  } catch (err) {
    console.warn('Could not clear the clipboard:', err?.message || err);
    recordClearOutcome(false);
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
  const generation = scheduleGeneration;
  pendingValue = value;
  listenForPageExit();
  pendingTimer = setTimeout(() => {
    pendingTimer = null;
    pendingValue = null;
    clearClipboardIfUnchanged(value, generation);
  }, timeoutMs);
  return true;
}

export function cancelScheduledClipboardClear() {
  scheduleGeneration += 1;
  pendingValue = null;
  if (pendingTimer !== null) {
    clearTimeout(pendingTimer);
    pendingTimer = null;
  }
}

// Hidden: record the pending clear as not done, synchronously, since a hidden
// tab may be discarded without another event (mobile). Do not clear: the user
// is most likely pasting elsewhere. If the page comes back, the timer still
// fires and its outcome replaces this record.
// pagehide (close, reload, navigation): also try the clear now. Best-effort;
// the timer keeps running if the page is only entering the back/forward cache.
function onPageHidden(event) {
  if (pendingTimer === null) return;
  if (event.type === 'visibilitychange' && document.visibilityState !== 'hidden') return;
  recordClearOutcome(false, { silent: true });
  if (event.type === 'pagehide') clearClipboardIfUnchanged(pendingValue, scheduleGeneration);
}

function listenForPageExit() {
  if (pageExitListening || typeof window === 'undefined') return;
  pageExitListening = true;
  window.addEventListener('pagehide', onPageHidden);
  document.addEventListener('visibilitychange', onPageHidden);
}

// Shown once per browser, the first time a secret is copied: the limit is a
// property of a web page, so say it where the user relies on it.
function hintOnce(timeoutMs) {
  try {
    if (localStorage.getItem(CLEAR_HINT_KEY)) return;
    localStorage.setItem(CLEAR_HINT_KEY, '1');
  } catch {
    return;
  }
  toast(
    `The clipboard is cleared after ${Math.round(timeoutMs / 1000)} seconds while this tab `
    + 'stays open. Closing the tab first may leave the copied value on the clipboard.',
    { id: 'clipboard-clear-hint', duration: 8000 },
  );
}

/** Copy `text` and schedule its clear. Rejects if the copy itself fails. */
export async function copySecret(text, options = {}) {
  await copyToClipboard(text);
  if (scheduleClipboardClear(text, options)) {
    hintOnce(getClipboardClearSettings(options.prefs).timeoutMs);
  }
}

/**
 * Copy a non-secret value (username, URL, email): no clear of its own. A
 * successful copy has replaced any secret still waiting to be cleared, so
 * that pending clear is cancelled; where readText() is refused it would
 * otherwise erase this value instead.
 */
export async function copyPlain(text) {
  await copyToClipboard(text);
  cancelScheduledClipboardClear();
}

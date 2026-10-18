/**
 * F12 (docs/pqc-hybrid-architecture-review.md): copying a secret must clear
 * it after the user's "Clear Clipboard Automatically" timeout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/preferencesService', () => ({
  default: { get: (_path, fallback) => fallback },
}));

vi.mock('react-hot-toast', () => ({ toast: Object.assign(vi.fn(), { error: vi.fn() }) }));

import { toast } from 'react-hot-toast';
import {
  cancelScheduledClipboardClear,
  clipboardAutoClearFailed,
  copyPlain,
  copySecret,
  getClipboardClearSettings,
  scheduleClipboardClear,
} from '../secureClipboard';

function prefsWith(security) {
  return {
    get: (path, fallback) => {
      const key = path.replace(/^security\./, '');
      return key in security ? security[key] : fallback;
    },
  };
}

let clipboardText;
let readAllowed;

beforeEach(() => {
  vi.useFakeTimers();
  clipboardText = '';
  readAllowed = true;
  Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: vi.fn(async (text) => { clipboardText = text; }),
      readText: vi.fn(async () => {
        if (!readAllowed) throw new DOMException('denied', 'NotAllowedError');
        return clipboardText;
      }),
    },
  });
});

afterEach(() => {
  cancelScheduledClipboardClear();
  vi.useRealTimers();
});

describe('getClipboardClearSettings', () => {
  it('defaults to on, 30 seconds', () => {
    expect(getClipboardClearSettings(prefsWith({}))).toEqual({ enabled: true, timeoutMs: 30000 });
  });

  it('uses the configured timeout and ignores nonsense', () => {
    expect(getClipboardClearSettings(prefsWith({ clipboardTimeout: 10 })).timeoutMs).toBe(10000);
    expect(getClipboardClearSettings(prefsWith({ clipboardTimeout: 0 })).timeoutMs).toBe(30000);
    expect(getClipboardClearSettings(prefsWith({ clipboardTimeout: 'x' })).timeoutMs).toBe(30000);
  });
});

describe('copySecret', () => {
  it('copies, then clears after the configured timeout', async () => {
    const prefs = prefsWith({ clearClipboard: true, clipboardTimeout: 10 });
    await copySecret('hunter2-secret', { prefs });
    expect(clipboardText).toBe('hunter2-secret');

    await vi.advanceTimersByTimeAsync(9999);
    expect(clipboardText).toBe('hunter2-secret');

    await vi.advanceTimersByTimeAsync(1);
    expect(clipboardText).toBe('');
  });

  it('does not clear when the setting is off', async () => {
    await copySecret('keep-me', { prefs: prefsWith({ clearClipboard: false }) });
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000);
    expect(clipboardText).toBe('keep-me');
  });

  it('leaves something the user copied afterwards alone', async () => {
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    clipboardText = 'an address the user copied later';
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('an address the user copied later');
  });

  it('clears best-effort when reading the clipboard is not permitted', async () => {
    readAllowed = false;
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('');
  });

  it('a newer copy restarts the timer', async () => {
    const prefs = prefsWith({ clipboardTimeout: 10 });
    await copySecret('first', { prefs });
    await vi.advanceTimersByTimeAsync(8000);
    await copySecret('second', { prefs });
    await vi.advanceTimersByTimeAsync(8000);
    expect(clipboardText).toBe('second');
    await vi.advanceTimersByTimeAsync(2000);
    expect(clipboardText).toBe('');
  });
});

describe('copyPlain', () => {
  it('is never cleared, even after a secret where reading is refused', async () => {
    readAllowed = false;
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    await copyPlain('alice@example.com');
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000);
    expect(clipboardText).toBe('alice@example.com');
  });

  it('a failed plain copy keeps the secret\'s clear', async () => {
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    navigator.clipboard.writeText.mockRejectedValueOnce(new Error('denied'));
    await expect(copyPlain('alice')).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('');
  });
});

describe('scheduleClipboardClear', () => {
  it('clears unconditionally when the copied value is unknown', async () => {
    clipboardText = 'copied by an iframe';
    scheduleClipboardClear(null, { prefs: prefsWith({ clipboardTimeout: 3 }) });
    await vi.advanceTimersByTimeAsync(3000);
    expect(navigator.clipboard.readText).not.toHaveBeenCalled();
    expect(clipboardText).toBe('');
  });

  it('reports when auto-clear is disabled', () => {
    expect(scheduleClipboardClear('x', { prefs: prefsWith({ clearClipboard: false }) })).toBe(false);
  });
});

describe('execCommand fallback (no Clipboard API)', () => {
  it('clears a secret that was copied through the fallback', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
    let fallbackClipboard = null;
    document.execCommand = vi.fn(() => {
      const data = { setData: (_type, text) => { fallbackClipboard = text; } };
      const event = new Event('copy', { cancelable: true });
      event.clipboardData = data;
      document.dispatchEvent(event);
      // No listener intervened: behave like copying the current selection.
      if (!event.defaultPrevented) fallbackClipboard = document.getSelection()?.toString() ?? '';
      return true;
    });
    try {
      await copySecret('fallback-secret', { prefs: prefsWith({ clipboardTimeout: 5 }) });
      expect(document.execCommand).toHaveBeenCalledTimes(1);

      await vi.advanceTimersByTimeAsync(5000);
      expect(document.execCommand).toHaveBeenCalledTimes(2);
      expect(fallbackClipboard).toBe('');
    } finally {
      delete document.execCommand;
    }
  });
});

describe('a clear the browser refuses', () => {
  beforeEach(() => {
    localStorage.clear();
    toast.error.mockClear();
  });

  it('tells the user and records it', async () => {
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    navigator.clipboard.writeText.mockRejectedValueOnce(new DOMException('no gesture', 'NotAllowedError'));
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('the-password');
    expect(toast.error).toHaveBeenCalledTimes(1);
    expect(clipboardAutoClearFailed()).toBe(true);
  });

  it('a later successful clear resets the record', async () => {
    localStorage.setItem('clipboardAutoClearFailed', '1');
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('');
    expect(clipboardAutoClearFailed()).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('skipping because the user copied something else is not a failure', async () => {
    await copySecret('the-password', { prefs: prefsWith({ clipboardTimeout: 5 }) });
    clipboardText = 'something newer';
    await vi.advanceTimersByTimeAsync(5000);
    expect(toast.error).not.toHaveBeenCalled();
    expect(clipboardAutoClearFailed()).toBe(false);
  });
});

describe('leaving the page before the timeout', () => {
  const prefs = prefsWith({ clipboardTimeout: 30 });
  const setVisibility = (state) => {
    Object.defineProperty(document, 'visibilityState', { value: state, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  };

  beforeEach(() => {
    localStorage.clear();
    toast.error.mockClear();
  });
  afterEach(() => setVisibility('visible'));

  it('closing the tab tries the clear at once and records it as not done', async () => {
    await copySecret('the-password', { prefs });
    window.dispatchEvent(new Event('pagehide'));
    // Recorded synchronously: nothing after pagehide is guaranteed to run.
    expect(clipboardAutoClearFailed()).toBe(true);
    // If the page lives long enough for the attempt to finish, the record clears.
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('');
    expect(clipboardAutoClearFailed()).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('switching away to paste does not clear, and the timer still does later', async () => {
    await copySecret('the-password', { prefs });
    setVisibility('hidden');
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('the-password');
    expect(clipboardAutoClearFailed()).toBe(true); // in case the hidden tab is discarded

    setVisibility('visible');
    await vi.advanceTimersByTimeAsync(30000);
    expect(clipboardText).toBe('');
    expect(clipboardAutoClearFailed()).toBe(false);
  });

  it('records nothing when no clear is pending', async () => {
    await copySecret('the-password', { prefs });
    await vi.advanceTimersByTimeAsync(30000);
    window.dispatchEvent(new Event('pagehide'));
    setVisibility('hidden');
    expect(clipboardAutoClearFailed()).toBe(false);
  });

  it('a later clear that finds the secret already replaced resets the record', async () => {
    await copySecret('the-password', { prefs });
    setVisibility('hidden');
    setVisibility('visible');
    clipboardText = 'something the user copied later';
    await vi.advanceTimersByTimeAsync(30000);
    expect(clipboardAutoClearFailed()).toBe(false);
  });
});

describe('a clear refused while the user is away', () => {
  const prefs = prefsWith({ clipboardTimeout: 5 });
  let focused;
  const refuseWhileUnfocused = async (text) => {
    if (!focused) throw new DOMException('Document is not focused.', 'NotAllowedError');
    clipboardText = text;
  };
  const comeBack = () => {
    focused = true;
    window.dispatchEvent(new Event('focus'));
  };

  beforeEach(() => {
    localStorage.clear();
    toast.error.mockClear();
    focused = false;
    document.hasFocus = () => focused;
  });
  afterEach(() => { delete document.hasFocus; });

  it('is retried when the page has focus again, still checking the value', async () => {
    await copySecret('the-password', { prefs });
    navigator.clipboard.writeText.mockImplementation(refuseWhileUnfocused);
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('the-password');
    expect(clipboardAutoClearFailed()).toBe(true);

    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('');
    expect(clipboardAutoClearFailed()).toBe(false);
  });

  it('visible but not yet focused waits for focus', async () => {
    await copySecret('the-password', { prefs });
    navigator.clipboard.writeText.mockImplementation(refuseWhileUnfocused);
    await vi.advanceTimersByTimeAsync(5000);
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('the-password');
    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('');
  });

  it('leaves alone something copied elsewhere in the meantime', async () => {
    await copySecret('the-password', { prefs });
    navigator.clipboard.writeText.mockImplementation(refuseWhileUnfocused);
    await vi.advanceTimersByTimeAsync(5000);
    clipboardText = 'copied in another app';
    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('copied in another app');
  });

  it('is retried only once', async () => {
    await copySecret('the-password', { prefs });
    navigator.clipboard.writeText.mockRejectedValue(new DOMException('no', 'NotAllowedError'));
    await vi.advanceTimersByTimeAsync(5000);
    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(3); // copy, clear, one retry
  });

  it('a newer copy cancels the retry', async () => {
    await copySecret('the-password', { prefs });
    navigator.clipboard.writeText.mockImplementation(refuseWhileUnfocused);
    await vi.advanceTimersByTimeAsync(5000);
    focused = true;
    await copyPlain('alice');
    comeBack();
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('alice');
  });
});

describe('the first copy of a secret', () => {
  beforeEach(() => {
    localStorage.clear();
    toast.mockClear();
  });

  it('says once that clearing needs the tab to stay open', async () => {
    const prefs = prefsWith({ clipboardTimeout: 15 });
    await copySecret('a', { prefs });
    await copySecret('b', { prefs });
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast.mock.calls[0][0]).toMatch(/15 seconds while this tab stays open/);
  });

  it('says nothing when auto-clear is off', async () => {
    await copySecret('a', { prefs: prefsWith({ clearClipboard: false }) });
    expect(toast).not.toHaveBeenCalled();
  });
});

describe('an older clear that is already running', () => {
  it('does not erase a newer copy of the same secret', async () => {
    const prefs = prefsWith({ clipboardTimeout: 5 });
    // The first clear's readText() stays pending until we release it.
    let releaseRead;
    navigator.clipboard.readText.mockImplementationOnce(
      () => new Promise((resolve) => { releaseRead = () => resolve(clipboardText); }),
    );
    await copySecret('the-password', { prefs });
    await vi.advanceTimersByTimeAsync(5000); // first clear starts and awaits the read

    await copySecret('the-password', { prefs }); // user copies it again
    releaseRead();
    await vi.advanceTimersByTimeAsync(0);
    expect(clipboardText).toBe('the-password');

    // The newer copy still gets its own clear, on its own timer.
    await vi.advanceTimersByTimeAsync(5000);
    expect(clipboardText).toBe('');
  });
});

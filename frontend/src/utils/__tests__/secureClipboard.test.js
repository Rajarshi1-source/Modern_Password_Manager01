/**
 * F12 (docs/pqc-hybrid-architecture-review.md): copying a secret must clear
 * it after the user's "Clear Clipboard Automatically" timeout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/preferencesService', () => ({
  default: { get: (_path, fallback) => fallback },
}));

import {
  cancelScheduledClipboardClear,
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

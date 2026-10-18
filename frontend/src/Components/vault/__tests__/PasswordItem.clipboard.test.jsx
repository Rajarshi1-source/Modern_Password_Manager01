/**
 * Only the password is auto-cleared (F12); a copied username or URL stays.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render } from '@testing-library/react';

vi.mock('../../../services/preferencesService', () => ({
  default: { get: (_path, fallback) => fallback },
}));
vi.mock('react-hot-toast', () => ({ toast: Object.assign(vi.fn(), { error: vi.fn() }) }));

import PasswordItem from '../PasswordItem';
import { cancelScheduledClipboardClear } from '../../../utils/secureClipboard';

const data = { username: 'alice', password: 'hunter2-secret', url: 'https://example.com' };
let clipboardText;

beforeEach(() => {
  vi.useFakeTimers();
  clipboardText = '';
  Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: vi.fn(async (text) => { clipboardText = text; }),
      readText: vi.fn(async () => clipboardText),
    },
  });
});

afterEach(() => {
  cancelScheduledClipboardClear();
  vi.useRealTimers();
});

async function copyField(container, index) {
  const buttons = container.querySelectorAll('button');
  // Field order: username copy, password eye, password copy, url copy, url open.
  await act(async () => { fireEvent.click(buttons[index]); });
}

describe('PasswordItem copy', () => {
  it('clears a copied password after the timeout', async () => {
    const { container } = render(<PasswordItem data={data} />);
    await copyField(container, 2);
    expect(clipboardText).toBe('hunter2-secret');
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(clipboardText).toBe('');
  });

  it('leaves a copied username and URL alone', async () => {
    for (const [index, value] of [[0, 'alice'], [3, 'https://example.com']]) {
      const { container, unmount } = render(<PasswordItem data={data} />);
      await copyField(container, index);
      expect(clipboardText).toBe(value);
      await act(async () => { await vi.advanceTimersByTimeAsync(10 * 60 * 1000); });
      expect(clipboardText).toBe(value);
      unmount();
    }
  });
});

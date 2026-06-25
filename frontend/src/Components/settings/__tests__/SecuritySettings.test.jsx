/**
 * SecuritySettings — preference persistence contract
 * ==================================================
 *
 * Regression guard for the 3-arg preferencesService.set() misuse. The service's
 * set(path, value) takes exactly two arguments; calling set('security', key,
 * value) ignored `value` and overwrote the entire `security` preferences object
 * with the key string. This test asserts a changed setting is saved via the
 * dot-path form set('security.<key>', value).
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import preferencesService from '../../../services/preferencesService';
import SecuritySettings from '../SecuritySettings';

describe('SecuritySettings preference persistence', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('saves a changed setting via set(`security.<key>`, value), not the 3-arg form', () => {
    const setSpy = vi.spyOn(preferencesService, 'set').mockImplementation(() => {});

    render(<SecuritySettings />);

    // The first <Select> is "Auto-Lock Timeout" → updateSecurity('autoLockTimeout', N).
    const timeoutSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(timeoutSelect, { target: { value: '600' } });

    expect(setSpy).toHaveBeenCalledTimes(1);
    const callArgs = setSpy.mock.calls[0];
    // The bug passed three args (section, key, value); the fix passes two.
    expect(callArgs).toHaveLength(2);
    expect(callArgs[0]).toBe('security.autoLockTimeout');
    expect(callArgs[1]).toBe(600);
  });
});

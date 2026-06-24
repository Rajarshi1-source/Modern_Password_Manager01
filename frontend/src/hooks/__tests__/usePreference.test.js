/**
 * usePreference tests
 * ===================
 *
 * Confirms the hook reads through preferencesService, writes back via its
 * setter, and stays in sync when the preference changes elsewhere.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import preferencesService from '../../services/preferencesService';
import usePreference from '../usePreference';

const PATH = 'test.usePreferenceValue';

describe('usePreference', () => {
  // Reset the shared preference key between cases so tests stay independent of
  // order and of leftover localStorage/sync side effects.
  afterEach(() => {
    preferencesService.reset(PATH);
  });

  it('returns the default when the preference is unset', () => {
    const { result } = renderHook(() => usePreference('test.neverSet.path', 'fallback'));
    expect(result.current[0]).toBe('fallback');
  });

  it('reflects an existing preference value', () => {
    preferencesService.set(PATH, 'hello');
    const { result } = renderHook(() => usePreference(PATH, 'fallback'));
    expect(result.current[0]).toBe('hello');
  });

  it('update() writes through the service and re-renders with the new value', () => {
    preferencesService.set(PATH, false);
    const { result } = renderHook(() => usePreference(PATH, false));
    expect(result.current[0]).toBe(false);

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    expect(preferencesService.get(PATH)).toBe(true);
  });

  it('reflects external changes made directly through the service', () => {
    preferencesService.set(PATH, 1);
    const { result } = renderHook(() => usePreference(PATH, 0));
    expect(result.current[0]).toBe(1);

    act(() => preferencesService.set(PATH, 42));

    expect(result.current[0]).toBe(42);
  });
});

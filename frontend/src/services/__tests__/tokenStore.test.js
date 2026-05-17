import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  setAccessToken,
  getAccessToken,
  isAuthenticated,
  isAccessTokenExpired,
  clearAccessToken,
  subscribe,
  __resetForTests,
} from '../tokenStore.js';

afterEach(() => {
  __resetForTests();
});

describe('tokenStore — in-memory access token', () => {
  it('starts unauthenticated', () => {
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
    expect(isAccessTokenExpired()).toBe(true);
  });

  it('round-trips a token through set/get', () => {
    setAccessToken('jwt-abc');
    expect(getAccessToken()).toBe('jwt-abc');
    expect(isAuthenticated()).toBe(true);
  });

  it('clears the token on setAccessToken(null)', () => {
    setAccessToken('jwt-abc');
    expect(isAuthenticated()).toBe(true);
    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it('clearAccessToken is equivalent to setAccessToken(null)', () => {
    setAccessToken('jwt-abc');
    clearAccessToken();
    expect(isAuthenticated()).toBe(false);
  });

  it('isAccessTokenExpired honours the provided TTL hint', () => {
    setAccessToken('jwt-abc', 900); // 15 minutes
    expect(isAccessTokenExpired()).toBe(false);
    // Past the grace window — fake the clock forward.
    vi.useFakeTimers();
    try {
      vi.advanceTimersByTime(900 * 1000 + 1000);
      expect(isAccessTokenExpired()).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('isAccessTokenExpired returns false when expiry is unknown', () => {
    // Setting without a TTL hint means "rely on reactive 401 refresh"
    setAccessToken('jwt-abc');
    expect(isAccessTokenExpired()).toBe(false);
  });

  it('notifies subscribers on transitions', () => {
    const seen = [];
    const unsub = subscribe((authed) => seen.push(authed));
    setAccessToken('jwt-abc');
    setAccessToken(null);
    setAccessToken('jwt-def');
    unsub();
    setAccessToken(null); // post-unsub — should not be observed
    expect(seen).toEqual([true, false, true]);
  });

  it('NEVER writes the token to localStorage', () => {
    const spy = vi.spyOn(window.localStorage, 'setItem');
    try {
      setAccessToken('jwt-abc', 900);
      clearAccessToken();
      // The single most important invariant of this module:
      // tokens must not leak into any persistent store.
      expect(spy).not.toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });

  it('subscribe rejects non-function listeners', () => {
    expect(() => subscribe(undefined)).toThrow(TypeError);
    expect(() => subscribe('not a function')).toThrow(TypeError);
  });

  it('a listener that throws does not corrupt the store', () => {
    subscribe(() => { throw new Error('listener bug'); });
    // Set should still succeed and update internal state even though
    // the listener threw. We assert by reading getAccessToken back —
    // if the throw had aborted the notify loop we'd still want the
    // token written (it was already written before notify ran), but
    // we also don't want the throw to bubble out to the caller.
    expect(() => setAccessToken('jwt-abc')).not.toThrow();
    expect(getAccessToken()).toBe('jwt-abc');
  });
});

/**
 * authStorage.js unit tests.
 *
 * Guards the "exactly one access-token key set" invariant: setSessionToken must
 * remove the alternate localStorage key, and clearStoredTokens must wipe both
 * localStorage keys, the refresh token, and the in-memory cookie-flow token.
 */
import { describe, it, expect, beforeEach } from 'vitest';

import { setSessionToken, clearStoredTokens } from './authStorage';
import {
  setAccessToken,
  getAccessToken,
  __resetForTests,
} from '../services/tokenStore';

describe('authStorage', () => {
  beforeEach(() => {
    __resetForTests();
    localStorage.clear();
  });

  describe('setSessionToken', () => {
    it('writes `accessToken` and clears the alternate `token`', () => {
      localStorage.setItem('token', 'stale-t');
      setSessionToken('accessToken', 'fresh-a');
      expect(localStorage.getItem('accessToken')).toBe('fresh-a');
      expect(localStorage.getItem('token')).toBeNull();
    });

    it('writes `token` and clears the alternate `accessToken`', () => {
      localStorage.setItem('accessToken', 'stale-a');
      setSessionToken('token', 'fresh-t');
      expect(localStorage.getItem('token')).toBe('fresh-t');
      expect(localStorage.getItem('accessToken')).toBeNull();
    });

    it('leaves at most one access-token key set after a flow switch', () => {
      // Simulate: email/pw login, then re-auth via OAuth-callback flow
      // without a clean logout in between.
      setSessionToken('accessToken', 'a1');
      setSessionToken('token', 't1');
      expect(localStorage.getItem('accessToken')).toBeNull();
      expect(localStorage.getItem('token')).toBe('t1');
    });
  });

  describe('clearStoredTokens', () => {
    it('wipes both localStorage keys, refreshToken, and the in-memory token', () => {
      localStorage.setItem('accessToken', 'a');
      localStorage.setItem('token', 't');
      localStorage.setItem('refreshToken', 'r');
      setAccessToken('mem');

      clearStoredTokens();

      expect(localStorage.getItem('accessToken')).toBeNull();
      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
      expect(getAccessToken()).toBeNull();
    });

    it('is idempotent / safe when nothing is stored', () => {
      expect(() => clearStoredTokens()).not.toThrow();
      expect(getAccessToken()).toBeNull();
    });
  });
});

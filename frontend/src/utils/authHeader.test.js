/**
 * authHeader.js unit tests.
 *
 * Guards the token-resolution order (in-memory tokenStore -> localStorage
 * accessToken -> localStorage token) and the omit-when-absent behaviour, since
 * the helper is now shared by multiple request paths.
 */
import { describe, it, expect, beforeEach } from 'vitest';

import { authHeader } from './authHeader';
import { setAccessToken, __resetForTests } from '../services/tokenStore';

describe('authHeader', () => {
  beforeEach(() => {
    __resetForTests();
    localStorage.clear();
  });

  it('omits the header when unauthenticated', () => {
    expect(authHeader()).toEqual({});
  });

  it('reads the localStorage `accessToken` key', () => {
    localStorage.setItem('accessToken', 'jwt-a');
    expect(authHeader()).toEqual({ Authorization: 'Bearer jwt-a' });
  });

  it('falls back to the legacy `token` key', () => {
    localStorage.setItem('token', 'jwt-t');
    expect(authHeader()).toEqual({ Authorization: 'Bearer jwt-t' });
  });

  it('prefers `accessToken` over `token` when both are set', () => {
    localStorage.setItem('accessToken', 'jwt-a');
    localStorage.setItem('token', 'jwt-t');
    expect(authHeader()).toEqual({ Authorization: 'Bearer jwt-a' });
  });

  it('prefers the in-memory tokenStore (cookie flow) over localStorage', () => {
    setAccessToken('jwt-mem');
    localStorage.setItem('accessToken', 'jwt-a');
    expect(authHeader()).toEqual({ Authorization: 'Bearer jwt-mem' });
  });
});

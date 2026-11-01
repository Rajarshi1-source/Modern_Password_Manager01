import { describe, expect, it, vi } from 'vitest';
import ApiService from './api';

describe('ApiService.handleError', () => {
  it('leaves the page for a 401 on a call that opted out of the login redirect', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const before = window.location.href;
    localStorage.setItem('token', 'kept');
    const data = { error: 'Invalid recovery key' };
    const answer = ApiService.handleError({
      response: { status: 401, data },
      config: { _noAuthRedirect: true },
    });
    expect(answer).toBe(data);
    expect(window.location.href).toBe(before);
    expect(localStorage.getItem('token')).toBe('kept');
    localStorage.removeItem('token');
  });
});

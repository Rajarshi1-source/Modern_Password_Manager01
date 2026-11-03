import { describe, expect, it, vi } from 'vitest';
import ApiService from './api';

describe('ApiService.handleError', () => {
  it('shows a key store message as written, not as a failed request', () => {
    const err = Object.assign(new Error('Start recovery again.'), { name: 'KeyStorageError' });
    expect(ApiService.handleError(err)).toEqual({ error: 'Start recovery again.' });
  });

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

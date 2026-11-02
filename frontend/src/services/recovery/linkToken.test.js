import { afterEach, describe, expect, it } from 'vitest';
import { captureLinkToken, linkToken } from './linkToken';

const openAt = (url) => {
  window.history.replaceState(null, '', url);
  captureLinkToken();
};

afterEach(() => window.history.replaceState(null, '', '/'));

describe('captureLinkToken', () => {
  it.each(['/recovery/guardian-approve', '/recovery/guardian-invite'])(
    'moves the token from %s into memory and off the address bar', (path) => {
      openAt(`${path}#tok-${path}`);
      expect(linkToken()).toBe(`tok-${path}`);
      expect(window.location.href).not.toContain('tok-');
      expect(window.location.pathname).toBe(path);
    },
  );

  it('keeps the token when the page re-reads a bare address', () => {
    openAt('/recovery/guardian-approve#kept');
    captureLinkToken();
    expect(linkToken()).toBe('kept');
  });

  it("leaves every other page's fragment alone", () => {
    openAt('/recovery/guardian-approve#kept');
    openAt('/vault#section');
    expect(window.location.hash).toBe('#section');
    expect(linkToken()).toBe('kept');
  });
});

import { afterEach, describe, expect, it } from 'vitest';
import { captureLinkToken, linkToken } from './linkToken';

const TOKEN = 'aB3_-'.repeat(8) + 'xyz'; // the shape of secrets.token_urlsafe(32)
const OTHER = 'Zz9-_'.repeat(8) + 'abc';

const openAt = (url) => {
  window.history.replaceState(null, '', url);
  captureLinkToken();
};

afterEach(() => window.history.replaceState(null, '', '/'));

describe('captureLinkToken', () => {
  it.each(['/recovery/guardian-approve', '/recovery/guardian-invite'])(
    'moves the token from %s into memory and off the address bar', (path) => {
      openAt(`${path}#${TOKEN}`);
      expect(linkToken()).toBe(TOKEN);
      expect(window.location.href).not.toContain(TOKEN);
      expect(window.location.pathname).toBe(path);
      openAt('/');
    },
  );

  it('keeps the token when the page re-reads a bare address', () => {
    openAt(`/recovery/guardian-approve#${TOKEN}`);
    captureLinkToken();
    expect(linkToken()).toBe(TOKEN);
  });

  it("leaves every other page's fragment alone", () => {
    openAt(`/recovery/guardian-approve#${TOKEN}`);
    openAt(`/vault#${OTHER}`);
    expect(window.location.hash).toBe(`#${OTHER}`);
    expect(linkToken()).toBe(TOKEN);
  });

  it.each([
    ['the skip link', 'main-content'],
    ['a truncated token', TOKEN.slice(0, 42)],
    ['too long a token', `${TOKEN}a`],
    ['characters a token never has', `${TOKEN.slice(0, 42)}.`],
  ])('does not take %s for the token', (_, fragment) => {
    openAt(`/recovery/guardian-approve#${TOKEN}`);
    openAt(`/recovery/guardian-approve#${fragment}`);
    expect(window.location.hash).toBe(`#${fragment}`);
    expect(linkToken()).toBe(TOKEN);
  });
});

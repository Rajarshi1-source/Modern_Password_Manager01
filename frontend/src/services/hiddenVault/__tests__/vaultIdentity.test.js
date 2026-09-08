/**
 * One derivation, used by every consumer of device-local vault state.
 *
 * The envelope, the wrapped DEK and the decoy contents are three separate
 * localStorage keys that are only usable TOGETHER, so they must agree on the
 * id they are suffixed with. These tests pin the precedence rather than the
 * expression, because the failure mode of getting it wrong is silent: state
 * written under one id and read under another looks exactly like "nothing was
 * ever configured".
 */
import { describe, test, expect } from 'vitest';
import { vaultUserId } from '../vaultIdentity';
import vaultIdentityDefault from '../vaultIdentity';

describe('vaultUserId', () => {
  test('prefers id, which survives an email change', () => {
    expect(vaultUserId({ id: 7, email: 'a@b.com' })).toBe(7);
  });

  test('falls back to email for identities carrying no id', () => {
    expect(vaultUserId({ email: 'a@b.com' })).toBe('a@b.com');
  });

  test('returns null rather than a usable-looking key when neither exists', () => {
    // Consumers all branch on falsy to mean "no vault state available"; a
    // string like "undefined" would instead become a real storage key.
    expect(vaultUserId({})).toBeNull();
    expect(vaultUserId(null)).toBeNull();
    expect(vaultUserId(undefined)).toBeNull();
  });

  test('an id of 0 still wins over email', () => {
    // `??` and not `||`: a falsy-but-present id is a real account id, and
    // `||` would silently key that account's vault off its email instead.
    expect(vaultUserId({ id: 0, email: 'a@b.com' })).toBe(0);
  });

  test('the default export is the same function', () => {
    expect(vaultIdentityDefault).toBe(vaultUserId);
  });
});

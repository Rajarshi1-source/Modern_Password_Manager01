import { describe, it, expect } from 'vitest';
import { logSafe } from '../logSafe';

const ch = (code) => String.fromCharCode(code);

describe('logSafe', () => {
  it('removes CR/LF so a value cannot start a new log line', () => {
    expect(logSafe('ok' + ch(13) + ch(10) + '[ERROR] forged')).toBe('ok[ERROR] forged');
    expect(logSafe('a' + ch(10) + 'b')).toBe('ab');
  });

  it('removes Unicode line boundaries', () => {
    for (const code of [0x2028, 0x2029, 0x85, 0x0b, 0x0c]) {
      expect(logSafe('a' + ch(code) + 'b')).toBe('ab');
    }
  });

  it('stringifies non-strings', () => {
    expect(logSafe(undefined)).toBe('undefined');
    expect(logSafe(42)).toBe('42');
    expect(logSafe({ type: 'x' })).toBe('[object Object]');
  });
});

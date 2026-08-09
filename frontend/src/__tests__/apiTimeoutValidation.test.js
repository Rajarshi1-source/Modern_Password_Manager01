/**
 * The "validate VITE_API_TIMEOUT, fall back to 30000" contract shared by
 * TypingPatternCapture.jsx's exported `ADAPTIVE_API_TIMEOUT_MS` and
 * services/api.js's configured axios instance.
 *
 * PR #474 round 2 fixed a real bug here (VITE_API_TIMEOUT=0 silently
 * disabled the whole timeout, since the string '0' is truthy and survives
 * a `x || '30000'` fallback) but never added a test exercising the
 * validation logic itself against different env values -- the existing
 * tests only proved callers use whatever constant the module happened to
 * compute at import time. CodeRabbit, PR #474 round 3.
 *
 * Both target values are computed once at module load, so each case here
 * stubs the env var, forces a fresh module evaluation (`vi.resetModules`),
 * and re-imports.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';

const DEFAULT_TIMEOUT_MS = 30000;

afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
});

// [label, raw env value, expected resolved timeout]
const CASES = [
    ['unset', undefined, DEFAULT_TIMEOUT_MS],
    ['empty string', '', DEFAULT_TIMEOUT_MS],
    ['zero — the actual bug this file exists to pin shut', '0', DEFAULT_TIMEOUT_MS],
    ['negative', '-1', DEFAULT_TIMEOUT_MS],
    ['fractional', '0.5', DEFAULT_TIMEOUT_MS],
    ['non-numeric', 'abc', DEFAULT_TIMEOUT_MS],
    ['exceeds Number.MAX_SAFE_INTEGER', '1e300', DEFAULT_TIMEOUT_MS],
    ['a normal positive integer', '10000', 10000],
    ['scientific notation for a valid integer', '1e2', 100],
];

describe('TypingPatternCapture — ADAPTIVE_API_TIMEOUT_MS', () => {
    it.each(CASES)('VITE_API_TIMEOUT %s -> %s', async (_label, envValue, expected) => {
        vi.stubEnv('VITE_API_TIMEOUT', envValue);
        vi.resetModules();
        const { ADAPTIVE_API_TIMEOUT_MS } = await import(
            '../Components/security/TypingPatternCapture'
        );
        expect(ADAPTIVE_API_TIMEOUT_MS).toBe(expected);
    });
});

describe('services/api.js — configured instance timeout', () => {
    it.each(CASES)('VITE_API_TIMEOUT %s -> %s', async (_label, envValue, expected) => {
        vi.stubEnv('VITE_API_TIMEOUT', envValue);
        vi.resetModules();
        const { api } = await import('../services/api');
        expect(api.defaults.timeout).toBe(expected);
    });
});

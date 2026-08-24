import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

import duressSignalService, {
    generateSignalToken,
    registerSignalToken,
    reportUnlock,
    reportUnlockForSlot,
    DECOY_SLOT_INDEX,
} from './duressSignalService';

const AUTH = 'test-jwt';

/** Capture every fetch call so we can assert on request shape. */
let calls;

beforeEach(() => {
    calls = [];
    global.fetch = vi.fn((url, options) => {
        calls.push({ url, options });
        return Promise.resolve({
            ok: true,
            status: 204,
            json: () => Promise.resolve({ success: true, signal_id: 'abc' }),
        });
    });
});

afterEach(() => {
    vi.restoreAllMocks();
});

const bodyOf = (call) => JSON.parse(call.options.body);

describe('generateSignalToken', () => {
    test('produces base64 of 32 bytes (44 chars)', () => {
        // The server validates this exact length; decoy noise and real tokens
        // must be the same size or the wire distinguishes them.
        expect(generateSignalToken()).toHaveLength(44);
    });

    test('produces a different value each call', () => {
        const tokens = new Set(
            Array.from({ length: 50 }, () => generateSignalToken()),
        );

        expect(tokens.size).toBe(50);
    });
});

describe('registerSignalToken', () => {
    test('posts the token to the register endpoint', async () => {
        const token = generateSignalToken();

        await registerSignalToken(AUTH, token);

        expect(calls).toHaveLength(1);
        expect(calls[0].url).toBe('/api/security/duress/signal/register/');
        expect(bodyOf(calls[0])).toEqual({ token });
    });

    test('throws when the server rejects the token', async () => {
        global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 400 }));

        await expect(registerSignalToken(AUTH, 'bad')).rejects.toThrow();
    });
});

describe('reportUnlock', () => {
    test('sends the real token when one is supplied', async () => {
        const token = generateSignalToken();

        await reportUnlock(AUTH, token);

        expect(bodyOf(calls[0])).toEqual({ signal: token });
    });

    test('sends noise of identical length on a normal unlock', async () => {
        await reportUnlock(AUTH, null);

        expect(calls).toHaveLength(1);
        expect(bodyOf(calls[0]).signal).toHaveLength(44);
    });

    test('duress and normal unlocks are indistinguishable on the wire', async () => {
        // The whole feature rests on this: same URL, same method, same body
        // shape, same field, same length. Anything that differs hands a
        // coercer an oracle for whether the extracted password was real.
        await reportUnlock(AUTH, generateSignalToken());
        await reportUnlock(AUTH, null);

        const [duress, normal] = calls;
        expect(duress.url).toBe(normal.url);
        expect(duress.options.method).toBe(normal.options.method);
        expect(Object.keys(bodyOf(duress))).toEqual(Object.keys(bodyOf(normal)));
        expect(bodyOf(duress).signal).toHaveLength(bodyOf(normal).signal.length);
        expect(duress.options.body.length).toBe(normal.options.body.length);
    });

    test('never throws when the network fails', async () => {
        // A coerced user cannot act on an error, and surfacing one would make
        // the duress path observably different.
        global.fetch = vi.fn(() => Promise.reject(new Error('offline')));

        await expect(reportUnlock(AUTH, generateSignalToken())).resolves.toBeUndefined();
    });

    test('never throws when noise generation fails on a normal unlock', async () => {
        // generateSignalToken() -- called here to produce noise, since
        // duressToken is null -- calls window.crypto.getRandomValues(),
        // which can throw in an unusual browser/extension environment. That
        // must be swallowed exactly like a fetch failure, not reject and
        // propagate to whatever awaited this call (e.g. StegoVaultDashboard's
        // onExtract, which would otherwise show "Extraction failed" after an
        // extraction that actually succeeded).
        const spy = vi
            .spyOn(window.crypto, 'getRandomValues')
            .mockImplementation(() => {
                throw new Error('crypto unavailable');
            });

        await expect(reportUnlock(AUTH, null)).resolves.toBeUndefined();
        expect(calls).toHaveLength(0);

        spy.mockRestore();
    });

    test('never sends a password field', async () => {
        await reportUnlock(AUTH, generateSignalToken());

        const body = bodyOf(calls[0]);
        expect(body).not.toHaveProperty('password');
        expect(body).not.toHaveProperty('master_password');
        expect(Object.keys(body)).toEqual(['signal']);
    });
});

describe('reportUnlockForSlot', () => {
    test('releases the embedded token when the decode landed on the decoy slot', async () => {
        const token = generateSignalToken();

        await reportUnlockForSlot(AUTH, DECOY_SLOT_INDEX, { __duress_signal: token });

        expect(bodyOf(calls[0])).toEqual({ signal: token });
    });

    test('sends noise when the decode landed on the real slot', async () => {
        const token = generateSignalToken();

        // Slot 0 is the real vault (hiddenVault/SPEC.md). Even if a token is
        // present in the payload it must NOT be released here.
        await reportUnlockForSlot(AUTH, 0, { __duress_signal: token });

        expect(bodyOf(calls[0]).signal).not.toBe(token);
        expect(bodyOf(calls[0]).signal).toHaveLength(44);
    });

    test('sends noise when the decoy payload carries no token', async () => {
        await reportUnlockForSlot(AUTH, DECOY_SLOT_INDEX, {});

        expect(bodyOf(calls[0]).signal).toHaveLength(44);
    });

    test('still reports when the payload is missing entirely', async () => {
        await reportUnlockForSlot(AUTH, DECOY_SLOT_INDEX, null);

        expect(calls).toHaveLength(1);
        expect(bodyOf(calls[0]).signal).toHaveLength(44);
    });
});

describe('default export', () => {
    test('exposes the documented surface', () => {
        expect(Object.keys(duressSignalService).sort()).toEqual([
            'DECOY_SLOT_INDEX',
            'generateSignalToken',
            'registerSignalToken',
            'reportUnlock',
            'reportUnlockForSlot',
        ]);
    });
});

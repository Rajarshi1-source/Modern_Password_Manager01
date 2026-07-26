/**
 * Tests for biometricLivenessService WebSocket message routing.
 *
 * The consumer sends a 'challenge_result' envelope after each
 * submit_challenge_response, which the service previously dropped. These pin that
 * challenge_result is delivered to the new onChallengeResult handler, that
 * frame_result/session_complete still route correctly, and that a
 * challenge_result is harmless when no handler was supplied (backward compat).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../wsTicket', () => ({ getWsTicket: vi.fn() }));

import { getWsTicket } from '../wsTicket';
import livenessService from '../biometricLivenessService';

describe('biometricLivenessService message routing', () => {
    let sockets;
    let originalWebSocket;

    beforeEach(() => {
        sockets = [];
        originalWebSocket = global.WebSocket;
        class FakeWebSocket {
            constructor(url) {
                this.url = url;
                this.readyState = 1; // OPEN
                sockets.push(this);
            }
            close() {
                this.readyState = 3;
            }
            send() {}
        }
        FakeWebSocket.OPEN = 1;
        global.WebSocket = FakeWebSocket;
        vi.clearAllMocks();
    });

    afterEach(() => {
        livenessService.disconnect();
        global.WebSocket = originalWebSocket;
    });

    const connect = async (handlers) => {
        getWsTicket.mockResolvedValueOnce('tkt');
        const ok = await livenessService.connectWebSocket(
            's1',
            handlers.onFrame,
            handlers.onComplete,
            handlers.onError,
            handlers.onChallenge
        );
        expect(ok).toBe(true);
        return sockets[0];
    };

    it('routes a challenge_result envelope to onChallengeResult', async () => {
        const onChallenge = vi.fn();
        const ws = await connect({
            onFrame: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onChallenge,
        });

        ws.onmessage({
            data: JSON.stringify({
                type: 'challenge_result',
                challenge_type: 'gaze',
                sequence: 0,
                passed: false,
                reason: 'no_gaze_observed',
            }),
        });

        expect(onChallenge).toHaveBeenCalledWith(
            expect.objectContaining({ type: 'challenge_result', challenge_type: 'gaze', sequence: 0 })
        );
    });

    it('still routes frame_result and session_complete to their handlers', async () => {
        const onFrame = vi.fn();
        const onComplete = vi.fn();
        const ws = await connect({
            onFrame, onComplete, onError: vi.fn(), onChallenge: vi.fn(),
        });

        ws.onmessage({
            data: JSON.stringify({ type: 'frame_result', results: { pulse: { heart_rate: 72 } }, current_challenge: 0 }),
        });
        expect(onFrame).toHaveBeenCalledWith(expect.objectContaining({ type: 'frame_result' }));

        ws.onmessage({
            data: JSON.stringify({ type: 'session_complete', is_verified: false, verdict: 'INSUFFICIENT_SIGNAL' }),
        });
        expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ type: 'session_complete' }));
    });

    it('does not route a retryable error to onError (transient lock conflict)', async () => {
        // session_busy means another worker briefly holds the session's
        // cross-process lock. onError halts capture and shows the terminal error
        // screen, so treating it as fatal would abort a verification over a
        // collision that clears in milliseconds.
        const onError = vi.fn();
        const onRetryable = vi.fn();
        const ws = await connect({
            onFrame: vi.fn(), onComplete: vi.fn(), onError, onChallenge: vi.fn(),
        });
        livenessService.onRetryableError = onRetryable;

        ws.onmessage({
            data: JSON.stringify({
                type: 'error', message: 'session_busy', retryable: true,
            }),
        });

        expect(onError).not.toHaveBeenCalled();
        expect(onRetryable).toHaveBeenCalledWith('session_busy');
        livenessService.onRetryableError = null;
    });

    it('still routes a non-retryable error to onError', async () => {
        const onError = vi.fn();
        const ws = await connect({
            onFrame: vi.fn(), onComplete: vi.fn(), onError, onChallenge: vi.fn(),
        });

        ws.onmessage({
            data: JSON.stringify({ type: 'error', message: 'internal_error' }),
        });

        expect(onError).toHaveBeenCalledWith('internal_error');
    });

    it('does not throw when a challenge_result arrives and no handler was provided', async () => {
        // Legacy 4-arg call (no onChallengeResult) must stay backward-compatible.
        getWsTicket.mockResolvedValueOnce('tkt');
        const ok = await livenessService.connectWebSocket('s2', vi.fn(), vi.fn(), vi.fn());
        expect(ok).toBe(true);
        const ws = sockets[0];

        expect(() =>
            ws.onmessage({ data: JSON.stringify({ type: 'challenge_result', sequence: 0 }) })
        ).not.toThrow();
    });

    it('submitHardwareSpo2 relays a hardware_spo2 frame over the session socket', async () => {
        const ws = await connect({
            onFrame: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onChallenge: vi.fn(),
        });
        ws.send = vi.fn();

        livenessService.submitHardwareSpo2(98, 0.9);

        expect(ws.send).toHaveBeenCalledTimes(1);
        expect(JSON.parse(ws.send.mock.calls[0][0])).toEqual({
            type: 'hardware_spo2', spo2: 98, quality: 0.9,
        });
    });
});

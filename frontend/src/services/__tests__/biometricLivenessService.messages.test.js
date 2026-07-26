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
        // livenessService is a module singleton, so an assertion that throws
        // mid-test would otherwise leak a spy into every later test.
        livenessService.onRetryableError = null;
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
    });

    it('re-sends a conflicted one-shot op instead of dropping it', async () => {
        // session_busy means the server never processed the request. Nothing
        // else re-drives a `complete`, so without a retry the UI waits forever
        // on a verdict that will never be produced.
        vi.useFakeTimers();
        try {
            const ws = await connect({
                onFrame: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onChallenge: vi.fn(),
            });
            ws.send = vi.fn();

            livenessService.completeSession();
            expect(JSON.parse(ws.send.mock.calls[0][0])).toEqual({ type: 'complete' });

            ws.onmessage({
                data: JSON.stringify({ type: 'error', message: 'session_busy', retryable: true, op: 'complete' }),
            });
            await vi.advanceTimersByTimeAsync(200);

            expect(ws.send).toHaveBeenCalledTimes(2);
            expect(JSON.parse(ws.send.mock.calls[1][0])).toEqual({ type: 'complete' });
        } finally {
            vi.useRealTimers();
        }
    });

    it('escalates to onError once a one-shot op stays conflicted', async () => {
        // Sustained contention is not transient; better a visible failure than
        // an indefinite spinner.
        vi.useFakeTimers();
        try {
            const onError = vi.fn();
            const ws = await connect({
                onFrame: vi.fn(), onComplete: vi.fn(), onError, onChallenge: vi.fn(),
            });
            ws.send = vi.fn();
            livenessService.completeSession();

            const busy = {
                data: JSON.stringify({ type: 'error', message: 'session_busy', retryable: true, op: 'complete' }),
            };
            for (let i = 0; i < 5; i += 1) {
                ws.onmessage(busy);
                await vi.advanceTimersByTimeAsync(5_000);
            }

            expect(onError).toHaveBeenCalledWith('session_busy');
        } finally {
            vi.useRealTimers();
        }
    });

    it('does not retry a conflicted frame (lossy by design)', async () => {
        const ws = await connect({
            onFrame: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onChallenge: vi.fn(),
        });
        ws.send = vi.fn();

        livenessService.sendFrame('AAAA', 64, 64, 1);
        ws.onmessage({
            data: JSON.stringify({ type: 'error', message: 'session_busy', retryable: true, op: 'frame' }),
        });

        // Only the original frame; the next one is milliseconds away anyway.
        expect(ws.send).toHaveBeenCalledTimes(1);
    });

    it('does not auto-resend on required_challenge_incomplete', async () => {
        // Also retryable, but it means the USER must answer a challenge -- not
        // that the server dropped the request. Resending would burn the retry
        // budget on identical refusals and then report a terminal failure.
        vi.useFakeTimers();
        try {
            const onError = vi.fn();
            const ws = await connect({
                onFrame: vi.fn(), onComplete: vi.fn(), onError, onChallenge: vi.fn(),
            });
            ws.send = vi.fn();
            livenessService.completeSession();

            ws.onmessage({
                data: JSON.stringify({
                    type: 'error', message: 'required_challenge_incomplete', retryable: true,
                }),
            });
            await vi.advanceTimersByTimeAsync(5_000);

            expect(ws.send).toHaveBeenCalledTimes(1);   // the original only
            expect(onError).not.toHaveBeenCalled();     // not terminal either
        } finally {
            vi.useRealTimers();
        }
    });

    it('a conflicted frame does not consume the pending one-shot retry budget', async () => {
        // A socket multiplexes frames and control ops. Without the `op`
        // correlation, frame contention would spend the complete's attempts and
        // escalate it to a terminal error prematurely.
        vi.useFakeTimers();
        try {
            const onError = vi.fn();
            const ws = await connect({
                onFrame: vi.fn(), onComplete: vi.fn(), onError, onChallenge: vi.fn(),
            });
            ws.send = vi.fn();
            livenessService.completeSession();

            const frameBusy = {
                data: JSON.stringify({
                    type: 'error', message: 'session_busy', retryable: true, op: 'frame',
                }),
            };
            for (let i = 0; i < 6; i += 1) {
                ws.onmessage(frameBusy);
                await vi.advanceTimersByTimeAsync(5_000);
            }

            expect(ws.send).toHaveBeenCalledTimes(1);   // complete not re-sent
            expect(onError).not.toHaveBeenCalled();     // nor escalated
        } finally {
            vi.useRealTimers();
        }
    });

    it('a streaming SpO2 reading never evicts a pending one-shot', async () => {
        // submitHardwareSpo2 is deliberately NOT a tracked one-shot: readings
        // arrive continuously, and _sendOneShot has a single pending slot, so
        // routing them through it would evict a `complete` awaiting its verdict
        // and leave it unretried -- the silent hang the retry path prevents.
        vi.useFakeTimers();
        try {
            const ws = await connect({
                onFrame: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onChallenge: vi.fn(),
            });
            ws.send = vi.fn();

            livenessService.completeSession();
            livenessService.submitHardwareSpo2(98, 0.9);   // stream arrives meanwhile

            ws.onmessage({
                data: JSON.stringify({
                    type: 'error', message: 'session_busy', retryable: true, op: 'complete',
                }),
            });
            await vi.advanceTimersByTimeAsync(200);

            // complete, spo2, then the RETRIED complete -- still tracked.
            expect(ws.send).toHaveBeenCalledTimes(3);
            expect(JSON.parse(ws.send.mock.calls[2][0])).toEqual({ type: 'complete' });
        } finally {
            vi.useRealTimers();
        }
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

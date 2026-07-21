/**
 * Tests for the LivenessVerification challenge-response orchestration.
 *
 * The backend has had the full challenge-response scoring machinery for a while,
 * but the UI never drove it. These tests pin the newly-wired flow: each
 * challenge's prompt runs, its completion notifies the server with the correct
 * sequence number, the sequence advances, and after the last challenge the
 * session is completed. The interactive challenge children are stubbed so the
 * flow is deterministic (no timers) and we test the orchestration, not the
 * child prompts' internal pacing.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';

// Mock the BLE oximeter so the pairing UI is available and a "device" can be
// connected/dropped deterministically. The class tracks its latest instance so
// tests can assert disconnect() and re-pairing.
vi.mock('../../../../services/bleOximeter', () => {
    class MockBleOximeter {
        constructor() {
            MockBleOximeter.last = this;
            this.disconnect = vi.fn();
        }
        connect(onReading, onDisconnect) {
            this.onReading = onReading;
            this.onDisconnect = onDisconnect;
            // When asked, keep connect() pending so a test can supersede it and
            // then resolve it late (simulating a slow picker / GATT handshake).
            if (MockBleOximeter.deferNextConnect) {
                MockBleOximeter.deferNextConnect = false;
                return new Promise((resolve) => { this.resolveConnect = resolve; });
            }
            return Promise.resolve({});
        }
    }
    MockBleOximeter.last = null;
    MockBleOximeter.deferNextConnect = false;
    return { isBleOximeterSupported: () => true, BleOximeter: MockBleOximeter };
});

// Stub the interactive challenge children with a single button that fires
// onComplete, so we can step through the sequence deterministically.
vi.mock('../GazeChallenge', () => ({
    default: ({ onComplete }) => (
        <button data-testid="done-gaze" onClick={onComplete}>done gaze</button>
    ),
}));
vi.mock('../ExpressionChallenge', () => ({
    default: ({ onComplete }) => (
        <button data-testid="done-expression" onClick={onComplete}>done expression</button>
    ),
}));
vi.mock('../PulseChallenge', () => ({
    default: ({ onComplete }) => (
        <button data-testid="done-pulse" onClick={onComplete}>done pulse</button>
    ),
}));

// Mock the service + camera utils. connectWebSocket captures the callbacks so
// tests can drive session_complete; the challenge/complete calls are spies.
vi.mock('../../../../services/biometricLivenessService', () => {
    const callbacks = {};
    return {
        default: {
            startSession: vi.fn().mockResolvedValue({
                session_id: 'sess-1',
                challenges: [
                    { type: 'gaze', instruction: 'g', data: { target_positions: [[0.2, 0.3]], time_limit_ms: 5000 } },
                    { type: 'expression', instruction: 'e', data: { expressions: ['happy', 'surprise'] } },
                    { type: 'pulse', instruction: 'p', data: { duration_seconds: 10 } },
                ],
            }),
            connectWebSocket: vi.fn((sessionId, onFrame, onComplete, onError, onChallengeResult) => {
                Object.assign(callbacks, { onFrame, onComplete, onError, onChallengeResult });
                return Promise.resolve(true);
            }),
            sendFrame: vi.fn(),
            submitChallengeResponse: vi.fn(),
            submitHardwareSpo2: vi.fn(),
            completeSession: vi.fn(),
            disconnect: vi.fn(),
            __callbacks: callbacks,
        },
        CameraUtils: {
            startCamera: vi.fn().mockResolvedValue({ getTracks: () => [] }),
            stopCamera: vi.fn(),
            captureFrame: vi.fn(() => ({ base64: 'x', width: 2, height: 2 })),
        },
        TimingUtils: { getHighResTime: () => 0 },
    };
});

import LivenessVerification from '../LivenessVerification';
import livenessService, { CameraUtils } from '../../../../services/biometricLivenessService';
import { BleOximeter as MockBleOximeter } from '../../../../services/bleOximeter';

describe('LivenessVerification challenge orchestration', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        MockBleOximeter.last = null;
        MockBleOximeter.deferNextConnect = false;
    });

    // Walk the mocked challenge sequence to completion, driving the server's
    // per-challenge consumption (advance is server-gated).
    const runToCompletion = async () => {
        fireEvent.click(await screen.findByTestId('done-gaze'));
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 0 }); });
        fireEvent.click(await screen.findByTestId('done-expression'));
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 1 }); });
        fireEvent.click(await screen.findByTestId('done-pulse'));
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 2 }); });
    };

    it('drives the challenge sequence, submits each with the right sequence, then completes', async () => {
        render(<LivenessVerification />);

        // Gaze (sequence 0) is the first challenge. The UI advances only after
        // the server confirms it consumed the challenge (challenge_result).
        fireEvent.click(await screen.findByTestId('done-gaze'));
        expect(livenessService.submitChallengeResponse).toHaveBeenNthCalledWith(1, { sequence: 0 });
        expect(screen.queryByTestId('done-expression')).toBeNull(); // not advanced yet
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 0 }); });

        // Expression (sequence 1).
        fireEvent.click(await screen.findByTestId('done-expression'));
        expect(livenessService.submitChallengeResponse).toHaveBeenNthCalledWith(2, { sequence: 1 });
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 1 }); });

        // Pulse (sequence 2) is last -> completes the session, but only once the
        // server has consumed it.
        fireEvent.click(await screen.findByTestId('done-pulse'));
        expect(livenessService.submitChallengeResponse).toHaveBeenNthCalledWith(3, { sequence: 2 });
        expect(livenessService.completeSession).not.toHaveBeenCalled();
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 2 }); });
        expect(livenessService.completeSession).toHaveBeenCalledTimes(1);

        // The final verdict from the server is rendered honestly, verbatim.
        act(() => {
            livenessService.__callbacks.onComplete({
                type: 'session_complete',
                is_verified: false,
                liveness_score: 0.4,
                confidence: 0.5,
                verdict: 'INSUFFICIENT_SIGNAL',
            });
        });
        expect(await screen.findByText(/Verification Failed/i)).toBeInTheDocument();
        expect(screen.getByText('INSUFFICIENT_SIGNAL')).toBeInTheDocument();
    });

    it('never reports a client-measured gaze track (only the sequence number)', async () => {
        render(<LivenessVerification />);

        fireEvent.click(await screen.findByTestId('done-gaze'));

        // The gaze challenge response must carry ONLY the sequence -- no gaze
        // coordinates. The server scores its own frame observation; a
        // client-supplied track could be synthesized from the known targets.
        const [payload] = livenessService.submitChallengeResponse.mock.calls[0];
        expect(payload).toEqual({ sequence: 0 });
        expect(payload).not.toHaveProperty('gaze_data');
        expect(payload).not.toHaveProperty('gazeData');
    });

    it('passes an onChallengeResult handler so the server verdict per challenge is received', async () => {
        render(<LivenessVerification />);
        await screen.findByTestId('done-gaze');

        // connectWebSocket must be called with all five args incl. the challenge
        // result handler (regression guard for the service wiring).
        expect(livenessService.connectWebSocket).toHaveBeenCalledTimes(1);
        expect(livenessService.connectWebSocket.mock.calls[0]).toHaveLength(5);
        expect(typeof livenessService.connectWebSocket.mock.calls[0][4]).toBe('function');
    });

    it('does not advance on a non-consumed response; re-submits the same sequence', async () => {
        render(<LivenessVerification />);
        fireEvent.click(await screen.findByTestId('done-gaze'));
        expect(livenessService.submitChallengeResponse).toHaveBeenNthCalledWith(1, { sequence: 0 });

        vi.useFakeTimers();
        try {
            // Server could not evaluate the challenge yet (window still open) ->
            // must NOT advance past gaze.
            act(() => {
                livenessService.__callbacks.onChallengeResult({ sequence: 0, next_challenge: true });
            });
            expect(screen.queryByTestId('done-expression')).toBeNull();

            // The retry timer re-submits the SAME sequence (0), not the next one.
            act(() => { vi.advanceTimersByTime(600); });
            expect(livenessService.submitChallengeResponse).toHaveBeenNthCalledWith(2, { sequence: 0 });
        } finally {
            vi.useRealTimers();
        }

        // Once the server consumes it, the flow advances to the next challenge.
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 0 }); });
        expect(await screen.findByTestId('done-expression')).toBeInTheDocument();
    });

    it('releases the camera on completion, not only on cancel (privacy)', async () => {
        render(<LivenessVerification />);

        fireEvent.click(await screen.findByTestId('done-gaze'));
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 0 }); });
        fireEvent.click(await screen.findByTestId('done-expression'));
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 1 }); });
        fireEvent.click(await screen.findByTestId('done-pulse'));

        // The webcam must not be released until the last challenge is consumed,
        // then be released as soon as the session completes (no waiting for Close).
        expect(CameraUtils.stopCamera).not.toHaveBeenCalled();
        act(() => { livenessService.__callbacks.onChallengeResult({ sequence: 2 }); });
        expect(CameraUtils.stopCamera).toHaveBeenCalledTimes(1);
    });

    it('disconnects the oximeter on completion so a late reading cannot error the result screen', async () => {
        render(<LivenessVerification />);
        // Pair an oximeter, then run to completion.
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await screen.findByText(/Pulse oximeter connected/i);
        const oximeter = MockBleOximeter.last;

        await runToCompletion();

        expect(oximeter.disconnect).toHaveBeenCalled();
    });

    it('clears the oximeter ref on a device drop so the user can reconnect', async () => {
        render(<LivenessVerification />);
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await screen.findByText(/Pulse oximeter connected/i);
        const first = MockBleOximeter.last;

        // Device drops -> the connect button returns and a fresh instance can pair.
        act(() => { first.onDisconnect(); });
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await waitFor(() => expect(MockBleOximeter.last).not.toBe(first));
    });

    it('ignores a reading from an oximeter after its connection is torn down', async () => {
        render(<LivenessVerification />);
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await screen.findByText(/Pulse oximeter connected/i);
        const oximeter = MockBleOximeter.last;

        // Completion tears down the connection (ref cleared).
        await runToCompletion();

        // A late BLE notification for the torn-down connection must NOT relay --
        // otherwise the backend would reject it post-completion and error the screen.
        act(() => { oximeter.onReading({ spo2: 98, quality: 1 }); });
        expect(livenessService.submitHardwareSpo2).not.toHaveBeenCalled();
    });

    it('releases a connection that resolves after being superseded (no orphaned GATT)', async () => {
        render(<LivenessVerification />);
        await screen.findByTestId('done-gaze'); // in the challenge view

        // Start pairing but keep connect() pending (slow picker / GATT handshake).
        MockBleOximeter.deferNextConnect = true;
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        const oximeter = MockBleOximeter.last;

        // The session completes while the connect() is still in flight ->
        // disconnectOximeter() clears the ref (1st disconnect call).
        await runToCompletion();
        expect(oximeter.disconnect).toHaveBeenCalledTimes(1);

        // The pending connect() now resolves successfully. Since the instance was
        // superseded, it must be disconnected rather than left dangling.
        await act(async () => { oximeter.resolveConnect({}); });
        expect(oximeter.disconnect).toHaveBeenCalledTimes(2);
    });

    it('tears down camera + oximeter when the session errors out', async () => {
        render(<LivenessVerification />);
        await screen.findByTestId('done-gaze'); // in the challenge view
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await screen.findByText(/Pulse oximeter connected/i);
        const oximeter = MockBleOximeter.last;

        // A WS-level error terminates the session -> capture must stop, not keep
        // streaming behind the "Verification Error" screen.
        act(() => { livenessService.__callbacks.onError('internal_error'); });
        expect(oximeter.disconnect).toHaveBeenCalled();
        expect(CameraUtils.stopCamera).toHaveBeenCalled();
    });

    it('resets the oximeter status on retry so the user can re-pair', async () => {
        render(<LivenessVerification />);
        await screen.findByTestId('done-gaze');
        fireEvent.click((await screen.findAllByText(/Connect pulse oximeter/i))[0]);
        await screen.findByText(/Pulse oximeter connected/i);

        // Session errors (oximeter torn down, ref cleared, but status was stale).
        act(() => { livenessService.__callbacks.onError('internal_error'); });

        // Retry re-inits: the panel must offer the Connect button again, not a
        // stale "connected" that hides it and silently drops hardware SpO2.
        fireEvent.click(await screen.findByText(/Try Again/i));
        expect((await screen.findAllByText(/Connect pulse oximeter/i)).length).toBeGreaterThan(0);
        expect(screen.queryByText(/Pulse oximeter connected/i)).toBeNull();
    });
});

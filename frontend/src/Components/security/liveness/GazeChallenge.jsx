/**
 * GazeChallenge Component
 *
 * Gaze tracking cognitive task for liveness verification. The user follows a
 * moving dot with their eyes; the dot visits the SERVER's randomized target
 * positions in order.
 *
 * IMPORTANT — where the liveness signal actually comes from: this component only
 * renders the prompt (the moving target). The gaze signal is measured
 * SERVER-SIDE from the camera frames the session is already streaming, scored
 * against these exact randomized targets within the challenge's time window. A
 * client-reported gaze track is deliberately NOT sent as evidence: it could be
 * synthesized from the known target positions and would not prove liveness, so
 * the backend ignores it. The randomized targets + server-side window are what a
 * pre-recorded / deepfake stream cannot follow in real time.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './GazeChallenge.css';

// Fallback 9-point calibration grid (percentages) used only if the server did
// not supply target positions. Real sessions always carry randomized targets.
const FALLBACK_TARGETS = [
    { x: 15, y: 15 }, { x: 50, y: 15 }, { x: 85, y: 15 },
    { x: 15, y: 50 }, { x: 50, y: 50 }, { x: 85, y: 50 },
    { x: 15, y: 85 }, { x: 50, y: 85 }, { x: 85, y: 85 },
];

/**
 * Normalize the server's target positions to on-screen percentages.
 * The backend sends target_positions as normalized [x, y] pairs in [0, 1].
 */
const toScreenTargets = (positions) => {
    if (!Array.isArray(positions) || positions.length === 0) return FALLBACK_TARGETS;
    return positions
        .map((p) => (Array.isArray(p) ? { x: p[0], y: p[1] } : p))
        .filter((p) => p && Number.isFinite(p.x) && Number.isFinite(p.y))
        .map((p) => ({ x: p.x * 100, y: p.y * 100 }));
};

const GazeChallenge = ({
    challenge,
    onComplete,
    autoStart = true,
    duration = 5000,
}) => {
    const data = challenge?.data || {};
    const targets = toScreenTargets(data.target_positions);
    // Prefer the server-advertised window so the on-screen prompt lines up with
    // the window the backend scores the gaze track against.
    const windowMs = Number.isFinite(data.time_limit_ms) ? data.time_limit_ms : duration;

    const [currentTarget, setCurrentTarget] = useState(0);
    const [timeLeft, setTimeLeft] = useState(Math.ceil(windowMs / 1000));
    const [status, setStatus] = useState(autoStart ? 'active' : 'ready');

    // onComplete must fire exactly once even though several timers can race to
    // the end of the window.
    const completedRef = useRef(false);

    const handleComplete = useCallback(() => {
        if (completedRef.current) return;
        completedRef.current = true;
        setStatus('complete');
        if (onComplete) {
            // No client-measured gaze track is reported: the server scores its
            // own observation of the streamed frames (see the file header).
            onComplete({ success: true, targetsShown: targets.length });
        }
    }, [onComplete, targets.length]);

    // Countdown + hard stop at the end of the window.
    useEffect(() => {
        if (status !== 'active') return undefined;
        const started = Date.now();
        const timer = setInterval(() => {
            const remaining = windowMs - (Date.now() - started);
            if (remaining <= 0) {
                clearInterval(timer);
                setTimeLeft(0);
                handleComplete();
            } else {
                setTimeLeft(Math.ceil(remaining / 1000));
            }
        }, 250);
        return () => clearInterval(timer);
    }, [status, windowMs, handleComplete]);

    // Walk the dot through every target, spread evenly across the window.
    useEffect(() => {
        if (status !== 'active' || targets.length === 0) return undefined;
        const step = Math.max(400, Math.floor(windowMs / targets.length));
        const targetTimer = setInterval(() => {
            setCurrentTarget((prev) => {
                const next = prev + 1;
                if (next >= targets.length) {
                    clearInterval(targetTimer);
                    return prev;
                }
                return next;
            });
        }, step);
        return () => clearInterval(targetTimer);
    }, [status, targets.length, windowMs]);

    return (
        <div className="gaze-challenge">
            <div className="challenge-header">
                <h3>👁️ Gaze Tracking Challenge</h3>
                {status === 'active' && <div className="timer">{timeLeft}s</div>}
            </div>

            {status === 'ready' && (
                <div className="ready-screen">
                    <p>Follow the moving dot with your eyes.</p>
                    <p className="hint">Keep your head still, only move your eyes.</p>
                    <button className="btn-start" onClick={() => setStatus('active')}>
                        Start Challenge
                    </button>
                </div>
            )}

            {status === 'active' && (
                <div className="gaze-area">
                    {targets.map((pos, idx) => (
                        <div
                            key={idx}
                            className={`target-point ${idx === currentTarget ? 'active' : ''} ${idx < currentTarget ? 'completed' : ''}`}
                            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                        >
                            {idx === currentTarget && <div className="target-pulse"></div>}
                        </div>
                    ))}

                    <div className="gaze-instruction">Look at the highlighted dot</div>

                    <div className="progress-bar">
                        <div
                            className="progress-fill"
                            style={{ width: `${((currentTarget + 1) / targets.length) * 100}%` }}
                        />
                    </div>
                </div>
            )}

            {status === 'complete' && (
                <div className="complete-screen">
                    <div className="success-icon">✓</div>
                    <h3>Challenge Complete!</h3>
                    <p>Analyzing your gaze…</p>
                </div>
            )}
        </div>
    );
};

export default GazeChallenge;

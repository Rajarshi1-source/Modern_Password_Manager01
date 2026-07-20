/**
 * PulseChallenge Component
 *
 * "Stay still" challenge: the user holds still and looks at the camera for a
 * fixed window while the session streams frames. Heart rate is measured
 * SERVER-SIDE from those frames (rPPG); this component only shows the countdown
 * and the live readout, then reports completion. A photo or replayed screen
 * yields no coherent pulse, which is what makes this contribute to the verdict.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import PulseReadout from './PulseReadout';
import './PulseChallenge.css';

const PulseChallenge = ({
    challenge,
    pulseData,
    onComplete,
    autoStart = true,
}) => {
    const durationSeconds = Number.isFinite(challenge?.data?.duration_seconds)
        ? challenge.data.duration_seconds
        : 10;

    const [timeLeft, setTimeLeft] = useState(durationSeconds);
    const [status, setStatus] = useState(autoStart ? 'active' : 'ready');
    const completedRef = useRef(false);

    const handleComplete = useCallback(() => {
        if (completedRef.current) return;
        completedRef.current = true;
        setStatus('complete');
        if (onComplete) onComplete({ success: true });
    }, [onComplete]);

    useEffect(() => {
        if (status !== 'active') return undefined;
        const started = Date.now();
        const total = durationSeconds * 1000;
        const timer = setInterval(() => {
            const remaining = total - (Date.now() - started);
            if (remaining <= 0) {
                clearInterval(timer);
                setTimeLeft(0);
                handleComplete();
            } else {
                setTimeLeft(Math.ceil(remaining / 1000));
            }
        }, 250);
        return () => clearInterval(timer);
    }, [status, durationSeconds, handleComplete]);

    return (
        <div className="pulse-challenge">
            <div className="challenge-header">
                <h3>❤️ Pulse Detection</h3>
                {status === 'active' && <div className="timer">{timeLeft}s</div>}
            </div>

            {status === 'ready' && (
                <div className="ready-screen">
                    <p>Stay still and look at the camera.</p>
                    <button className="btn-start" onClick={() => setStatus('active')}>
                        Start
                    </button>
                </div>
            )}

            {status !== 'ready' && (
                <>
                    <p className="pulse-instruction">
                        Hold still and look at the camera while we measure your pulse.
                    </p>
                    <PulseReadout pulseData={pulseData} isActive={status === 'active'} />
                </>
            )}

            {status === 'complete' && (
                <div className="complete-screen">
                    <div className="success-icon">✓</div>
                    <h3>Done</h3>
                </div>
            )}
        </div>
    );
};

export default PulseChallenge;

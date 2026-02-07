/**
 * GazeChallenge Component
 * 
 * Gaze tracking cognitive task for liveness verification.
 * User follows moving target points on screen.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './GazeChallenge.css';

const GazeChallenge = ({
    challenge,
    onComplete,
    onGazeUpdate,
    duration = 10000
}) => {
    const [currentTarget, setCurrentTarget] = useState(0);
    const [targets, setTargets] = useState([]);
    const [timeLeft, setTimeLeft] = useState(duration / 1000);
    const [gazeHistory, setGazeHistory] = useState([]);
    const [status, setStatus] = useState('ready'); // ready, active, complete

    useEffect(() => {
        // Generate target positions (9-point calibration pattern)
        const positions = generateTargetPositions();
        setTargets(positions);
    }, []);

    useEffect(() => {
        if (status !== 'active') return;

        const timer = setInterval(() => {
            setTimeLeft(prev => {
                if (prev <= 1) {
                    clearInterval(timer);
                    handleComplete();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [status]);

    useEffect(() => {
        if (status !== 'active' || targets.length === 0) return;

        // Move to next target every 1.5 seconds
        const targetTimer = setInterval(() => {
            setCurrentTarget(prev => {
                const next = (prev + 1) % targets.length;
                return next;
            });
        }, 1500);

        return () => clearInterval(targetTimer);
    }, [status, targets]);

    const generateTargetPositions = () => {
        // 9-point calibration grid
        return [
            { x: 15, y: 15 },
            { x: 50, y: 15 },
            { x: 85, y: 15 },
            { x: 15, y: 50 },
            { x: 50, y: 50 },
            { x: 85, y: 50 },
            { x: 15, y: 85 },
            { x: 50, y: 85 },
            { x: 85, y: 85 },
        ];
    };

    const handleStart = () => {
        setStatus('active');
    };

    const handleComplete = useCallback(() => {
        setStatus('complete');
        if (onComplete) {
            onComplete({
                success: gazeHistory.length > 0,
                gazeData: gazeHistory,
                targetsCompleted: currentTarget + 1,
            });
        }
    }, [onComplete, gazeHistory, currentTarget]);

    const recordGaze = (x, y) => {
        const target = targets[currentTarget];
        if (!target) return;

        const gazePoint = {
            timestamp: Date.now(),
            targetX: target.x,
            targetY: target.y,
            gazeX: x,
            gazeY: y,
            error: Math.sqrt(Math.pow(x - target.x, 2) + Math.pow(y - target.y, 2)),
        };

        setGazeHistory(prev => [...prev, gazePoint]);
        if (onGazeUpdate) onGazeUpdate(gazePoint);
    };

    return (
        <div className="gaze-challenge">
            <div className="challenge-header">
                <h3>👁️ Gaze Tracking Challenge</h3>
                {status === 'active' && (
                    <div className="timer">{timeLeft}s</div>
                )}
            </div>

            {status === 'ready' && (
                <div className="ready-screen">
                    <p>Follow the moving dot with your eyes.</p>
                    <p className="hint">Keep your head still, only move your eyes.</p>
                    <button className="btn-start" onClick={handleStart}>
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
                            {idx === currentTarget && (
                                <div className="target-pulse"></div>
                            )}
                        </div>
                    ))}

                    <div className="gaze-instruction">
                        Look at the highlighted dot
                    </div>

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
                    <p>Tracked {gazeHistory.length} gaze points</p>
                </div>
            )}
        </div>
    );
};

export default GazeChallenge;

/**
 * LivenessVerification Component
 *
 * Main UI for experimental biometric liveness verification. Orchestrates camera
 * capture, the interactive challenge sequence, and results.
 *
 * The camera frames are streamed to the backend the whole time; each challenge
 * (gaze / expression / pulse) is rendered here only as a PROMPT. The actual
 * liveness signals are measured server-side from those frames and scored against
 * the server's randomized targets. When a challenge's prompt finishes we notify
 * the server (submit_challenge_response) so it can score/close that challenge,
 * then advance; after the last challenge we complete the session.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import biometricLivenessService, { CameraUtils, TimingUtils } from '../../../services/biometricLivenessService';
import { BleOximeter, isBleOximeterSupported } from '../../../services/bleOximeter';
import GazeChallenge from './GazeChallenge';
import ExpressionChallenge from './ExpressionChallenge';
import PulseChallenge from './PulseChallenge';
import './LivenessVerification.css';

const LivenessVerification = ({ onComplete, onCancel, context = 'login' }) => {
    const [status, setStatus] = useState('initializing'); // initializing, challenge, processing, complete, error
    const [challenges, setChallenges] = useState([]);
    const [challengeIndex, setChallengeIndex] = useState(0);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);
    const [frameCount, setFrameCount] = useState(0);
    const [livenessIndicators, setLivenessIndicators] = useState({});
    // SpO2 comes ONLY from a real paired oximeter (never the webcam): idle,
    // connecting, connected, unsupported, error.
    const [spo2Status, setSpo2Status] = useState(
        isBleOximeterSupported() ? 'idle' : 'unsupported'
    );

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const captureIntervalRef = useRef(null);
    // Mirror the challenge list/index into refs so the once-per-challenge
    // completion handler reads the current values without being re-created (and
    // can guard against a duplicate completion for a challenge already advanced
    // past — re-submitting a sequence would trip the server's replay guard).
    const challengesRef = useRef([]);
    const challengeIndexRef = useRef(0);
    // Pending re-submit for a challenge the server hasn't consumed yet.
    const retryTimerRef = useRef(null);
    // Paired BLE pulse oximeter (if the user connects one).
    const oximeterRef = useRef(null);
    // Cancellation token bumped by cleanup(). An unmount/retry mid-init must
    // invalidate an initSession still awaiting startCamera()/startSession() —
    // the service generation guard only covers the WS ticket fetch.
    const initAttemptRef = useRef(0);

    // Initialize session and camera. Mount-only: initSession/cleanup are
    // re-created each render, so listing them would re-run the effect (and
    // re-open the camera) on every render.
    useEffect(() => {
        initSession();
        return () => cleanup();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const initSession = async () => {
        // Release any leftovers from a prior attempt (camera stream, capture
        // loop, socket) so a "Try Again" after a post-connect error starts
        // clean rather than stacking a second stream. All no-ops on first mount.
        cleanup();
        // cleanup() bumped the token; capture it and re-check after every await
        // so an unmount/retry mid-init can't assign a stream or open a socket
        // once cleanup has already run.
        const attempt = initAttemptRef.current;
        try {
            setStatus('initializing');
            setResults(null);
            setError(null);
            setFrameCount(0);
            setLivenessIndicators({});

            // Start camera
            if (videoRef.current) {
                const stream = await CameraUtils.startCamera(videoRef.current);
                if (attempt !== initAttemptRef.current) {
                    CameraUtils.stopCamera(stream); // canceled while starting — release it
                    return;
                }
                streamRef.current = stream;
            }

            // Start liveness session
            const sessionData = await biometricLivenessService.startSession(context);
            if (attempt !== initAttemptRef.current) return;

            // Connect WebSocket (async: fetches a single-use ws-ticket first).
            // On failure it already set the 'error' status via handleError, so
            // bail out rather than overwrite it with the capturing state.
            const connected = await biometricLivenessService.connectWebSocket(
                sessionData.session_id,
                handleFrameResult,
                handleSessionComplete,
                handleError,
                handleChallengeResult
            );
            if (attempt !== initAttemptRef.current) return;
            if (!connected) {
                // connectWebSocket already surfaced the error via handleError;
                // release the camera + session so "Try Again" starts clean
                // instead of stacking a second camera stream.
                cleanup();
                return;
            }

            // Set up the challenge sequence. The server returns the challenges in
            // sequence order, so the array index doubles as the challenge's
            // sequence number when we submit responses.
            const nextChallenges = Array.isArray(sessionData.challenges) ? sessionData.challenges : [];
            challengesRef.current = nextChallenges;
            challengeIndexRef.current = 0;
            setChallenges(nextChallenges);
            setChallengeIndex(0);

            setStatus('challenge');
            startFrameCapture();
        } catch (err) {
            // Superseded/unmounted attempt — the cleanup() that bumped the token
            // already released resources; don't touch state.
            if (attempt !== initAttemptRef.current) return;
            // Release the camera so the error screen doesn't keep it live and a
            // retry doesn't stack a second stream.
            cleanup();
            setError(err.message);
            setStatus('error');
        }
    };

    const startFrameCapture = () => {
        if (captureIntervalRef.current) return;

        captureIntervalRef.current = setInterval(() => {
            if (videoRef.current && canvasRef.current) {
                const { base64, width, height } = CameraUtils.captureFrame(
                    videoRef.current,
                    canvasRef.current
                );
                biometricLivenessService.sendFrame(
                    base64,
                    width,
                    height,
                    TimingUtils.getHighResTime()
                );
                setFrameCount(prev => prev + 1);
            }
        }, 100); // 10 FPS
    };

    const stopFrameCapture = () => {
        if (captureIntervalRef.current) {
            clearInterval(captureIntervalRef.current);
            captureIntervalRef.current = null;
        }
    };

    // Release the webcam. Called as soon as frames are no longer needed (on
    // completion) so the camera doesn't stay live through the processing/result
    // screens -- a privacy concern for a biometric feature. Idempotent.
    const releaseCamera = () => {
        if (streamRef.current) {
            CameraUtils.stopCamera(streamRef.current);
            streamRef.current = null;
        }
    };

    // Disconnect the BLE oximeter. Called as soon as readings are no longer
    // needed (on completion / cleanup) so it can't relay a hardware_spo2 message
    // after 'complete' -- the backend would reject it and the resulting error
    // frame would overwrite the result screen. Idempotent.
    const disconnectOximeter = () => {
        const oximeter = oximeterRef.current;
        if (oximeter) {
            // Clear the ref BEFORE disconnecting so any callback that fires
            // during teardown sees it is no longer the active instance and bails.
            oximeterRef.current = null;
            oximeter.disconnect();
        }
    };

    const handleFrameResult = useCallback((data) => {
        setLivenessIndicators(prev => ({
            ...prev,
            ...data.results,
        }));
    }, []);

    const clearRetry = () => {
        if (retryTimerRef.current) {
            clearTimeout(retryTimerRef.current);
            retryTimerRef.current = null;
        }
    };

    // Fires once per challenge when its on-screen prompt finishes: submit the
    // response. Only the sequence number is sent — the client never reports its
    // own gaze/expression track (the server scores its own observation of the
    // streamed frames; a client-supplied track could be synthesized from the
    // known targets and is ignored). Advancing is deferred to
    // handleChallengeResult so the UI only moves on once the SERVER has actually
    // consumed the challenge.
    const handleChallengeComplete = useCallback((index) => {
        // Ignore a stale/duplicate completion for a challenge already advanced past.
        if (index !== challengeIndexRef.current) return;
        biometricLivenessService.submitChallengeResponse({ sequence: index });
    }, []);

    const advanceToNext = useCallback((index) => {
        const next = index + 1;
        challengeIndexRef.current = next;
        if (next >= challengesRef.current.length) {
            // Last challenge consumed. Stop streaming/relaying BEFORE completing
            // so no frame or SpO2 message races the completion (the server
            // rejects both once done, and a rejection error would clobber the
            // result screen), and release the webcam now that it's unneeded.
            stopFrameCapture();
            releaseCamera();
            disconnectOximeter();
            setStatus('processing');
            biometricLivenessService.completeSession();
            return;
        }
        setChallengeIndex(next);
    }, []);

    // Per-challenge outcome from the server. Advance ONLY when the challenge was
    // actually consumed; a not-yet-consumed response (next_challenge: the gaze
    // window isn't open yet, or no gaze was observed while it's still running)
    // leaves the same sequence current server-side, so advancing here would skip
    // the challenge and later fail completion with required_challenge_incomplete
    // once gaze is measurable. Instead re-submit shortly — frames keep streaming
    // and the window has a hard deadline after which the server consumes it, so
    // this converges without looping forever.
    const handleChallengeResult = useCallback((data) => {
        const seq = data && data.sequence;
        // Ignore results for a challenge we've already moved past.
        if (seq == null || seq !== challengeIndexRef.current) return;
        if (data.next_challenge) {
            clearRetry();
            retryTimerRef.current = setTimeout(() => {
                if (seq === challengeIndexRef.current) {
                    biometricLivenessService.submitChallengeResponse({ sequence: seq });
                }
            }, 500);
            return;
        }
        clearRetry();
        advanceToNext(seq);
    }, [advanceToNext]);

    const handleSessionComplete = useCallback((data) => {
        stopFrameCapture();
        releaseCamera(); // ensure the webcam is off on the result screen
        disconnectOximeter(); // and stop the oximeter relaying past completion
        setResults(data);
        setStatus('complete');

        if (onComplete) {
            onComplete(data);
        }
    }, [onComplete]);

    const handleError = useCallback((message) => {
        setError(message);
        setStatus('error');
    }, []);

    const handleManualComplete = () => {
        stopFrameCapture();
        releaseCamera();
        disconnectOximeter();
        setStatus('processing');
        biometricLivenessService.completeSession();
    };

    // Pair a BLE pulse oximeter (must be a user gesture) and relay each real
    // reading to the backend. SpO2 is never derived from the webcam; with no
    // device the tile stays hidden and SpO2 is excluded from scoring.
    const connectOximeter = async () => {
        if (!isBleOximeterSupported() || oximeterRef.current) return;
        const oximeter = new BleOximeter();
        oximeterRef.current = oximeter;
        setSpo2Status('connecting');
        // Every async callback is guarded by `oximeterRef.current === oximeter`
        // so a superseded/torn-down connection can't relay a stale reading (the
        // backend would reject it post-completion and error the result screen)
        // or clobber a newer connection's ref.
        try {
            await oximeter.connect(
                (reading) => {
                    if (oximeterRef.current === oximeter) {
                        biometricLivenessService.submitHardwareSpo2(reading.spo2, reading.quality);
                    }
                },
                () => {
                    // Device dropped: clear the ref so the reconnect button can
                    // create a fresh instance (the guard blocks while it is set).
                    if (oximeterRef.current === oximeter) {
                        oximeterRef.current = null;
                        setSpo2Status('idle');
                    }
                }
            );
            if (oximeterRef.current === oximeter) {
                setSpo2Status('connected');
            } else {
                // Superseded (e.g. the session completed) while the picker / GATT
                // handshake was still pending: the connection succeeded after the
                // fact, so release it rather than leaving the radio open with no
                // reference left to close it.
                oximeter.disconnect();
            }
        } catch {
            // User cancelled the chooser, or pairing failed: stay honest (no SpO2).
            // A superseded rejection already tore itself down inside connect().
            if (oximeterRef.current === oximeter) {
                oximeterRef.current = null;
                setSpo2Status('error');
            }
        }
    };

    const cleanup = () => {
        initAttemptRef.current++; // invalidate any in-flight initSession
        clearRetry();
        stopFrameCapture();
        releaseCamera();
        disconnectOximeter();
        biometricLivenessService.disconnect();
    };

    const handleCancel = () => {
        cleanup();
        if (onCancel) onCancel();
    };

    const renderChallenge = () => {
        const challenge = challenges.at(challengeIndex);
        if (!challenge) {
            // No/unknown challenge configured: fall back to a manual completion
            // so a misconfigured session isn't a dead end.
            return (
                <div className="challenge-panel">
                    <p>Look at the camera to capture liveness signals.</p>
                    <button className="btn-complete" onClick={handleManualComplete}>
                        Complete Verification
                    </button>
                </div>
            );
        }

        // Keyed by index so each challenge remounts fresh (its internal timers
        // reset) as the sequence advances.
        const commonProps = {
            challenge,
            onComplete: () => handleChallengeComplete(challengeIndex),
        };

        switch (challenge.type) {
            case 'gaze':
                return <GazeChallenge key={challengeIndex} {...commonProps} />;
            case 'expression':
                return <ExpressionChallenge key={challengeIndex} {...commonProps} />;
            case 'pulse':
                return (
                    <PulseChallenge
                        key={challengeIndex}
                        {...commonProps}
                        pulseData={livenessIndicators.pulse}
                    />
                );
            default:
                // Unknown challenge type: acknowledge it and move on rather than
                // stalling the sequence.
                return (
                    <div className="challenge-panel">
                        <h3>{challenge.type} Challenge</h3>
                        <p>{challenge.instruction}</p>
                        <button
                            className="btn-complete"
                            onClick={() => handleChallengeComplete(challengeIndex)}
                        >
                            Continue
                        </button>
                    </div>
                );
        }
    };

    // Render based on status
    const renderContent = () => {
        switch (status) {
            case 'initializing':
                return (
                    <div className="liveness-loading">
                        <div className="spinner"></div>
                        <p>Initializing camera...</p>
                    </div>
                );

            case 'challenge':
                return (
                    <div className="liveness-capture">
                        {challenges.length > 0 && (
                            <div className="challenge-progress">
                                Challenge {Math.min(challengeIndex + 1, challenges.length)} of {challenges.length}
                            </div>
                        )}

                        {renderChallenge()}

                        <div className="indicators-panel">
                            <div className="indicator">
                                <span className="indicator-label">Frames</span>
                                <span className="indicator-value">{frameCount}</span>
                            </div>
                            {livenessIndicators.pulse && (
                                <div className="indicator">
                                    <span className="indicator-label">Heart Rate</span>
                                    <span className="indicator-value">
                                        {livenessIndicators.pulse.heart_rate?.toFixed(0) || '--'} BPM
                                    </span>
                                </div>
                            )}
                            {livenessIndicators.deepfake && (
                                <div className={`indicator ${livenessIndicators.deepfake.is_fake ? 'warning' : 'success'}`}>
                                    <span className="indicator-label">Liveness</span>
                                    <span className="indicator-value">
                                        {livenessIndicators.deepfake.is_fake ? '⚠️ Suspicious' : '✓ Live'}
                                    </span>
                                </div>
                            )}
                        </div>

                        {spo2Status !== 'unsupported' && (
                            <div className="oximeter-panel">
                                {spo2Status === 'connected' ? (
                                    <span className="oximeter-status connected">
                                        ✓ Pulse oximeter connected
                                        {livenessIndicators.pulse?.spo2 != null &&
                                            ` — SpO₂ ${Math.round(livenessIndicators.pulse.spo2)}%`}
                                    </span>
                                ) : (
                                    <button
                                        className="btn-secondary"
                                        onClick={connectOximeter}
                                        disabled={spo2Status === 'connecting'}
                                    >
                                        {spo2Status === 'connecting'
                                            ? 'Connecting…'
                                            : 'Connect pulse oximeter (optional)'}
                                    </button>
                                )}
                                {spo2Status === 'error' && (
                                    <span className="oximeter-hint">Could not connect — SpO₂ stays off.</span>
                                )}
                            </div>
                        )}

                        <div className="action-buttons">
                            <button className="btn-cancel" onClick={handleCancel}>
                                Cancel
                            </button>
                        </div>
                    </div>
                );

            case 'processing':
                return (
                    <div className="liveness-processing">
                        <div className="spinner"></div>
                        <p>Analyzing biometric data...</p>
                    </div>
                );

            case 'complete':
                return (
                    <div className={`liveness-result ${results?.is_verified ? 'success' : 'failed'}`}>
                        <div className="result-icon">
                            {results?.is_verified ? '✓' : '✗'}
                        </div>
                        <h2>{results?.is_verified ? 'Verification Successful' : 'Verification Failed'}</h2>
                        <div className="result-details">
                            <div className="score-row">
                                <span>Liveness Score</span>
                                <span className="score-value">{(results?.liveness_score * 100)?.toFixed(1)}%</span>
                            </div>
                            <div className="score-row">
                                <span>Confidence</span>
                                <span className="score-value">{(results?.confidence * 100)?.toFixed(1)}%</span>
                            </div>
                            <div className="verdict">
                                Verdict: <strong>{results?.verdict}</strong>
                            </div>
                        </div>
                        <button className="btn-primary" onClick={handleCancel}>
                            Close
                        </button>
                    </div>
                );

            case 'error':
                return (
                    <div className="liveness-error">
                        <div className="error-icon">⚠️</div>
                        <h2>Verification Error</h2>
                        <p>{error}</p>
                        <button className="btn-primary" onClick={initSession}>
                            Try Again
                        </button>
                        <button className="btn-secondary" onClick={handleCancel}>
                            Cancel
                        </button>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="liveness-verification">
            <div className="liveness-header">
                <h1>🎭 Biometric Liveness Verification</h1>
                <p>Experimental liveness checks — not a security guarantee</p>
            </div>
            {/* Camera elements are mounted for the whole session (not just the
                capture view) so videoRef exists when initSession starts the
                camera, and so the stream stays attached to the SAME element
                across status changes instead of being lost on remount. Shown
                only while capturing challenges. */}
            <div
                className="camera-container"
                style={{ display: status === 'challenge' ? undefined : 'none' }}
            >
                <video ref={videoRef} autoPlay playsInline muted />
                <canvas ref={canvasRef} style={{ display: 'none' }} />
                <div className="face-overlay">
                    <div className="face-guide"></div>
                </div>
            </div>
            {renderContent()}
        </div>
    );
};

export default LivenessVerification;

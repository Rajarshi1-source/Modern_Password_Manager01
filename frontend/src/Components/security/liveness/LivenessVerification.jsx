/**
 * LivenessVerification Component
 * 
 * Main UI for deepfake-resistant biometric liveness verification.
 * Orchestrates camera capture, challenge display, and results.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import biometricLivenessService, { CameraUtils, TimingUtils } from '../../../services/biometricLivenessService';
import './LivenessVerification.css';

const LivenessVerification = ({ onComplete, onCancel, context = 'login' }) => {
    const [status, setStatus] = useState('initializing'); // initializing, capturing, challenge, processing, complete
    const [session, setSession] = useState(null);
    const [currentChallenge, setCurrentChallenge] = useState(null);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);
    const [frameCount, setFrameCount] = useState(0);
    const [livenessIndicators, setLivenessIndicators] = useState({});

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const captureIntervalRef = useRef(null);

    // Initialize session and camera
    useEffect(() => {
        initSession();
        return () => cleanup();
    }, []);

    const initSession = async () => {
        try {
            setStatus('initializing');

            // Start camera
            if (videoRef.current) {
                streamRef.current = await CameraUtils.startCamera(videoRef.current);
            }

            // Start liveness session
            const sessionData = await biometricLivenessService.startSession(context);
            setSession(sessionData);

            // Connect WebSocket
            biometricLivenessService.connectWebSocket(
                sessionData.session_id,
                handleFrameResult,
                handleSessionComplete,
                handleError
            );

            // Set first challenge
            if (sessionData.challenges && sessionData.challenges.length > 0) {
                setCurrentChallenge(sessionData.challenges[0]);
            }

            setStatus('capturing');
            startFrameCapture();
        } catch (err) {
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

    const handleFrameResult = useCallback((data) => {
        setLivenessIndicators(prev => ({
            ...prev,
            ...data.results,
        }));
    }, []);

    const handleSessionComplete = useCallback((data) => {
        stopFrameCapture();
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

    const handleCompleteClick = () => {
        setStatus('processing');
        biometricLivenessService.completeSession();
    };

    const cleanup = () => {
        stopFrameCapture();
        if (streamRef.current) {
            CameraUtils.stopCamera(streamRef.current);
        }
        biometricLivenessService.disconnect();
    };

    const handleCancel = () => {
        cleanup();
        if (onCancel) onCancel();
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

            case 'capturing':
            case 'challenge':
                return (
                    <div className="liveness-capture">
                        <div className="camera-container">
                            <video ref={videoRef} autoPlay playsInline muted />
                            <canvas ref={canvasRef} style={{ display: 'none' }} />
                            <div className="face-overlay">
                                <div className="face-guide"></div>
                            </div>
                        </div>

                        {currentChallenge && (
                            <div className="challenge-panel">
                                <h3>{currentChallenge.type} Challenge</h3>
                                <p>{currentChallenge.instruction}</p>
                            </div>
                        )}

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

                        <div className="action-buttons">
                            <button className="btn-complete" onClick={handleCompleteClick}>
                                Complete Verification
                            </button>
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
                <p>Advanced anti-spoofing authentication</p>
            </div>
            {renderContent()}
        </div>
    );
};

export default LivenessVerification;

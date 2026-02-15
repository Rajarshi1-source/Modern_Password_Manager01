/**
 * Cognitive Verification Component
 * =================================
 * 
 * Main verification interface for cognitive password testing.
 * Presents challenges and captures timing data for implicit memory detection.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import './CognitiveVerification.css';
import cognitiveAuthService from '../../../services/cognitiveAuthService';
import ScrambledRecognition from './ScrambledRecognition';
import StroopTest from './StroopTest';
import PrimingChallenge from './PrimingChallenge';
import PartialReveal from './PartialReveal';

const CognitiveVerification = ({
    password,
    onComplete,
    onCancel,
    context = 'login',
    isCalibration = false
}) => {
    // Session state
    const [session, setSession] = useState(null);
    const [currentChallenge, setCurrentChallenge] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    // Progress tracking
    const [completedCount, setCompletedCount] = useState(0);
    const [passedCount, setPassedCount] = useState(0);
    const [totalCount, setTotalCount] = useState(0);

    // Results state
    const [sessionResult, setSessionResult] = useState(null);

    // Timing
    const timerRef = useRef(null);
    const wsConnectedRef = useRef(false);

    // Initialize session
    useEffect(() => {
        const initSession = async () => {
            try {
                setIsLoading(true);
                setError(null);

                let response;
                if (isCalibration) {
                    response = await cognitiveAuthService.startCalibration(password);
                } else {
                    response = await cognitiveAuthService.startSession(password, { context });
                }

                setSession(response);
                setTotalCount(response.total_challenges);

                if (response.first_challenge) {
                    setCurrentChallenge(response.first_challenge);
                }

                // Connect WebSocket for real-time challenges
                await cognitiveAuthService.connectWebSocket(response.session_id, {
                    onConnected: () => {
                        wsConnectedRef.current = true;
                    },
                    onChallenge: (data) => {
                        setCurrentChallenge(data);
                    },
                    onResult: (data) => {
                        setCompletedCount(data.challenges_completed);
                        setPassedCount(data.challenges_passed);

                        if (!data.is_session_complete && data.next_challenge) {
                            setCurrentChallenge(data.next_challenge);
                        }
                    },
                    onComplete: (data) => {
                        setSessionResult(data);
                    },
                    onError: (err) => {
                        console.error('WebSocket error:', err);
                    },
                });

                setIsLoading(false);
            } catch (err) {
                setError(err.message);
                setIsLoading(false);
            }
        };

        initSession();

        return () => {
            cognitiveAuthService.disconnect();
        };
    }, [password, context, isCalibration]);

    // Start timer when challenge is presented
    useEffect(() => {
        if (currentChallenge && !timerRef.current) {
            timerRef.current = cognitiveAuthService.createTimer();
            timerRef.current.start();
        }
    }, [currentChallenge]);

    // Handle challenge response
    const handleResponse = useCallback(async (response) => {
        if (!timerRef.current) return;

        const timing = timerRef.current.stop();
        timerRef.current = null;

        try {
            if (wsConnectedRef.current) {
                cognitiveAuthService.submitWsResponse(
                    currentChallenge.id,
                    response,
                    timing
                );
            } else {
                const result = await cognitiveAuthService.submitResponse(
                    currentChallenge.id,
                    response,
                    timing
                );

                setCompletedCount(result.challenges_completed);
                setPassedCount(result.challenges_passed);

                if (result.is_session_complete) {
                    setSessionResult(result.session_result);
                } else if (result.next_challenge) {
                    setCurrentChallenge(result.next_challenge);
                }
            }
        } catch (err) {
            setError(err.message);
        }
    }, [currentChallenge]);

    // Handle keystroke for timing
    const handleKeystroke = useCallback((isBackspace = false) => {
        if (timerRef.current) {
            timerRef.current.recordKeystroke(isBackspace);
        }
    }, []);

    // Handle completion
    const handleComplete = useCallback(() => {
        if (onComplete) {
            onComplete(sessionResult);
        }
    }, [onComplete, sessionResult]);

    // Render challenge component based on type
    const renderChallenge = () => {
        if (!currentChallenge) return null;

        const commonProps = {
            challenge: currentChallenge,
            onResponse: handleResponse,
            onKeystroke: handleKeystroke,
            timer: timerRef.current,
        };

        switch (currentChallenge.type) {
            case 'scrambled':
                return <ScrambledRecognition {...commonProps} />;
            case 'stroop':
                return <StroopTest {...commonProps} />;
            case 'priming':
                return <PrimingChallenge {...commonProps} />;
            case 'partial':
                return <PartialReveal {...commonProps} />;
            default:
                return <div className="unknown-challenge">Unknown challenge type</div>;
        }
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="cognitive-verification loading">
                <div className="loading-spinner" />
                <p>Preparing verification challenges...</p>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="cognitive-verification error">
                <div className="error-icon">⚠️</div>
                <p>{error}</p>
                <button onClick={() => window.location.reload()}>Retry</button>
                <button onClick={onCancel} className="secondary">Cancel</button>
            </div>
        );
    }

    // Results state
    if (sessionResult) {
        return (
            <div className="cognitive-verification results">
                <div className={`result-icon ${sessionResult.status === 'passed' ? 'success' : 'failed'}`}>
                    {sessionResult.status === 'passed' ? '✓' : '✗'}
                </div>

                <h2>
                    {sessionResult.status === 'passed'
                        ? 'Verification Successful'
                        : 'Verification Failed'}
                </h2>

                <div className="result-details">
                    <div className="score-circle">
                        <svg viewBox="0 0 100 100">
                            <circle cx="50" cy="50" r="45" className="bg" />
                            <circle
                                cx="50" cy="50" r="45"
                                className="progress"
                                strokeDasharray={`${sessionResult.overall_score * 283} 283`}
                            />
                        </svg>
                        <span className="score-value">
                            {Math.round(sessionResult.overall_score * 100)}%
                        </span>
                    </div>

                    <div className="metrics">
                        <div className="metric">
                            <label>Accuracy</label>
                            <span>{Math.round(sessionResult.overall_score * 100)}%</span>
                        </div>
                        <div className="metric">
                            <label>Confidence</label>
                            <span>{Math.round(sessionResult.confidence * 100)}%</span>
                        </div>
                        <div className="metric">
                            <label>Creator Match</label>
                            <span>{Math.round(sessionResult.creator_probability * 100)}%</span>
                        </div>
                    </div>

                    {isCalibration && sessionResult.status === 'passed' && (
                        <div className="calibration-success">
                            <p>✓ Your cognitive profile has been calibrated successfully.</p>
                        </div>
                    )}

                    {sessionResult.anomalies?.length > 0 && (
                        <div className="anomalies-warning">
                            <strong>Note:</strong> Some response patterns were flagged for review.
                        </div>
                    )}
                </div>

                <div className="result-actions">
                    <button onClick={handleComplete} className="primary">
                        Continue
                    </button>
                    {sessionResult.status === 'failed' && (
                        <button onClick={() => window.location.reload()} className="secondary">
                            Try Again
                        </button>
                    )}
                </div>
            </div>
        );
    }

    // Challenge state
    return (
        <div className="cognitive-verification">
            <div className="verification-header">
                <h3>
                    {isCalibration ? 'Cognitive Profile Calibration' : 'Password Verification'}
                </h3>
                <button className="close-button" onClick={onCancel}>×</button>
            </div>

            <div className="progress-bar">
                <div
                    className="progress-fill"
                    style={{ width: `${(completedCount / totalCount) * 100}%` }}
                />
                <span className="progress-text">
                    {completedCount} / {totalCount}
                </span>
            </div>

            <div className="challenge-container">
                {renderChallenge()}
            </div>

            <div className="verification-footer">
                <div className="timer-indicator" />
                <span className="instruction">
                    Respond as quickly as possible
                </span>
            </div>
        </div>
    );
};

export default CognitiveVerification;

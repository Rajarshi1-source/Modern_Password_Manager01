/**
 * Password Trainer Component
 * 
 * Interactive password memorization training with real-time
 * neurofeedback visualization.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import neuroFeedbackService from '../../services/neuroFeedbackService';
import './PasswordTrainer.css';

const PasswordTrainer = ({ session, onEnd }) => {
    const [phase, setPhase] = useState('connecting'); // connecting, ready, learning, testing, results
    const [currentChunk, setCurrentChunk] = useState(null);
    const [brainState, setBrainState] = useState('unfocused');
    const [memoryReadiness, setMemoryReadiness] = useState(0);
    const [feedback, setFeedback] = useState(null);
    const [userInput, setUserInput] = useState('');
    const [recallStartTime, setRecallStartTime] = useState(null);
    const [sessionStats, setSessionStats] = useState({
        chunksLearned: 0,
        successfulRecalls: 0,
        failedRecalls: 0,
    });
    const [showResult, setShowResult] = useState(null);

    const inputRef = useRef(null);
    const passwordRef = useRef(session.program?.password || '');

    // Connect to WebSocket
    useEffect(() => {
        const ws = neuroFeedbackService.connectWebSocket(session.session_id);

        neuroFeedbackService.on('session_ready', handleSessionReady);
        neuroFeedbackService.on('feedback', handleFeedback);
        neuroFeedbackService.on('training_started', handleTrainingStarted);
        neuroFeedbackService.on('chunk_ready', handleChunkReady);
        neuroFeedbackService.on('recall_result', handleRecallResult);
        neuroFeedbackService.on('error', handleError);

        return () => {
            neuroFeedbackService.off('session_ready', handleSessionReady);
            neuroFeedbackService.off('feedback', handleFeedback);
            neuroFeedbackService.off('training_started', handleTrainingStarted);
            neuroFeedbackService.off('chunk_ready', handleChunkReady);
            neuroFeedbackService.off('recall_result', handleRecallResult);
            neuroFeedbackService.off('error', handleError);
            neuroFeedbackService.disconnectWebSocket();
        };
    }, [session.session_id]);

    const handleSessionReady = useCallback(() => {
        setPhase('ready');
    }, []);

    const handleFeedback = useCallback((data) => {
        setBrainState(data.metrics?.brain_state || 'unfocused');
        setMemoryReadiness(data.metrics?.memory_readiness || 0);
        setFeedback(data.feedback);

        // Show content when brain is ready
        if (data.feedback?.show_content && phase === 'learning') {
            // Content is shown via currentChunk
        }
    }, [phase]);

    const handleTrainingStarted = useCallback((data) => {
        setPhase('learning');
        neuroFeedbackService.requestNextChunk();
    }, []);

    const handleChunkReady = useCallback((data) => {
        setCurrentChunk(data.chunk);
        if (data.chunk.content) {
            setPhase('learning');
        }
    }, []);

    const handleRecallResult = useCallback((data) => {
        setShowResult(data);

        setSessionStats(prev => ({
            ...prev,
            successfulRecalls: data.success ? prev.successfulRecalls + 1 : prev.successfulRecalls,
            failedRecalls: !data.success ? prev.failedRecalls + 1 : prev.failedRecalls,
            chunksLearned: data.success && data.new_strength >= 0.5 ? prev.chunksLearned + 1 : prev.chunksLearned,
        }));

        // Clear result after 2 seconds and get next chunk
        setTimeout(() => {
            setShowResult(null);
            setUserInput('');
            setPhase('learning');
            neuroFeedbackService.requestNextChunk();
        }, 2500);
    }, []);

    const handleError = useCallback((data) => {
        console.error('Training error:', data);
    }, []);

    const startTraining = () => {
        // In real use, password would be fetched securely
        const mockPassword = 'MyStr0ng!P@ssw0rd#2026';
        passwordRef.current = mockPassword;
        neuroFeedbackService.startTraining(session.program.program_id, mockPassword);
    };

    const startRecall = () => {
        setPhase('testing');
        setRecallStartTime(Date.now());
        setTimeout(() => inputRef.current?.focus(), 100);
    };

    const submitRecall = () => {
        if (!userInput.trim()) return;

        const responseTime = Date.now() - recallStartTime;
        neuroFeedbackService.submitRecall(
            currentChunk.index,
            userInput,
            responseTime
        );
        setPhase('results');
    };

    const endSession = () => {
        neuroFeedbackService.endSession();
        onEnd();
    };

    const getBrainStateColor = () => {
        const colors = {
            unfocused: '#808080',
            relaxed: '#4A90D9',
            focused: '#50C878',
            memory_ready: '#FFD700',
            encoding: '#FF8C00',
            recall: '#9370DB',
            fatigue: '#CD5C5C',
            distracted: '#A9A9A9',
        };
        return colors[brainState] || '#808080';
    };

    const renderPhase = () => {
        switch (phase) {
            case 'connecting':
                return (
                    <div className="phase-connecting">
                        <div className="pulse-circle" />
                        <h2>Connecting to EEG Device...</h2>
                        <p>Please ensure your headset is properly positioned</p>
                    </div>
                );

            case 'ready':
                return (
                    <div className="phase-ready">
                        <div className="ready-icon">🧠</div>
                        <h2>Ready to Train</h2>
                        <p>Your EEG device is connected and calibrated</p>
                        <div className="tips">
                            <h4>Training Tips:</h4>
                            <ul>
                                <li>Find a quiet, comfortable space</li>
                                <li>Breathe deeply and relax</li>
                                <li>Focus on each chunk one at a time</li>
                            </ul>
                        </div>
                        <button className="btn-start" onClick={startTraining}>
                            Begin Training
                        </button>
                    </div>
                );

            case 'learning':
                return (
                    <div className="phase-learning">
                        <div className="brain-indicator">
                            <div
                                className="brain-circle"
                                style={{
                                    borderColor: getBrainStateColor(),
                                    boxShadow: `0 0 ${20 + memoryReadiness * 30}px ${getBrainStateColor()}40`
                                }}
                            >
                                <div className="readiness-fill" style={{ height: `${memoryReadiness * 100}%` }} />
                                <span className="brain-emoji">🧠</span>
                            </div>
                            <div className="brain-status">
                                <span className="state-label">{brainState.replace('_', ' ')}</span>
                                <span className="readiness-label">{Math.round(memoryReadiness * 100)}% ready</span>
                            </div>
                        </div>

                        <div className="chunk-display">
                            {currentChunk?.content ? (
                                <>
                                    <div className="chunk-label">Memorize this chunk:</div>
                                    <div className="chunk-content">
                                        {currentChunk.display_content}
                                    </div>
                                    <div className="chunk-index">
                                        Chunk {currentChunk.index + 1} • Strength: {Math.round(currentChunk.strength * 100)}%
                                    </div>
                                </>
                            ) : (
                                <div className="waiting-message">
                                    <p>{feedback?.message || 'Focus your attention...'}</p>
                                    <div className="focus-animation" />
                                </div>
                            )}
                        </div>

                        {currentChunk?.content && (
                            <button className="btn-ready" onClick={startRecall}>
                                I've Memorized It – Test Me!
                            </button>
                        )}
                    </div>
                );

            case 'testing':
                return (
                    <div className="phase-testing">
                        <h2>Type the Chunk</h2>
                        <p className="test-instruction">Type what you remember:</p>
                        <input
                            ref={inputRef}
                            type="text"
                            value={userInput}
                            onChange={(e) => setUserInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && submitRecall()}
                            placeholder="Type here..."
                            className="recall-input"
                            autoComplete="off"
                        />
                        <button
                            className="btn-submit"
                            onClick={submitRecall}
                            disabled={!userInput.trim()}
                        >
                            Submit
                        </button>
                    </div>
                );

            case 'results':
                return (
                    <div className="phase-results">
                        {showResult && (
                            <div className={`result-display ${showResult.success ? 'success' : 'failure'}`}>
                                <div className="result-icon">
                                    {showResult.success ? '✅' : '❌'}
                                </div>
                                <h2>{showResult.success ? 'Correct!' : 'Not Quite'}</h2>
                                <p>{showResult.feedback}</p>
                                <div className="strength-change">
                                    Memory Strength: {Math.round(showResult.new_strength * 100)}%
                                    <span className={showResult.strength_delta > 0 ? 'positive' : 'negative'}>
                                        ({showResult.strength_delta > 0 ? '+' : ''}{Math.round(showResult.strength_delta * 100)}%)
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="password-trainer">
            <header className="trainer-header">
                <div className="session-info">
                    <span>Session Active</span>
                    <span className="device-indicator">
                        🟢 {session.device_name}
                    </span>
                </div>
                <button className="btn-end" onClick={endSession}>
                    End Session
                </button>
            </header>

            <div className="trainer-content">
                {renderPhase()}
            </div>

            <footer className="trainer-stats">
                <div className="stat">
                    <span className="stat-value">{sessionStats.chunksLearned}</span>
                    <span className="stat-label">Chunks Learned</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{sessionStats.successfulRecalls}</span>
                    <span className="stat-label">Successful</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{sessionStats.failedRecalls}</span>
                    <span className="stat-label">Needs Practice</span>
                </div>
            </footer>
        </div>
    );
};

export default PasswordTrainer;

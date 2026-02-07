/**
 * ExpressionChallenge Component
 * 
 * Micro-expression challenge for liveness verification.
 * Prompts user to make specific facial expressions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './ExpressionChallenge.css';

const EXPRESSIONS = [
    { id: 'smile', label: 'Smile', emoji: '😊', instruction: 'Show a natural smile' },
    { id: 'surprise', label: 'Surprise', emoji: '😮', instruction: 'Look surprised' },
    { id: 'blink', label: 'Blink', emoji: '😌', instruction: 'Blink your eyes twice' },
    { id: 'neutral', label: 'Neutral', emoji: '😐', instruction: 'Keep a neutral expression' },
    { id: 'left_turn', label: 'Turn Left', emoji: '👈', instruction: 'Turn your head slightly left' },
    { id: 'right_turn', label: 'Turn Right', emoji: '👉', instruction: 'Turn your head slightly right' },
];

const ExpressionChallenge = ({
    onComplete,
    onExpressionDetected,
    expressionTypes = ['smile', 'blink', 'neutral'],
    duration = 15000,
}) => {
    const [currentExpression, setCurrentExpression] = useState(0);
    const [expressions, setExpressions] = useState([]);
    const [timeLeft, setTimeLeft] = useState(duration / 1000);
    const [status, setStatus] = useState('ready'); // ready, active, complete
    const [detectedExpressions, setDetectedExpressions] = useState([]);
    const [currentProgress, setCurrentProgress] = useState(0);

    useEffect(() => {
        // Filter expressions based on requested types
        const selected = EXPRESSIONS.filter(e => expressionTypes.includes(e.id));
        setExpressions(selected);
    }, [expressionTypes]);

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
        if (status !== 'active' || expressions.length === 0) return;

        // Progress bar animation
        const progressTimer = setInterval(() => {
            setCurrentProgress(prev => {
                if (prev >= 100) {
                    // Move to next expression
                    setCurrentExpression(curr => {
                        const next = curr + 1;
                        if (next >= expressions.length) {
                            handleComplete();
                            return curr;
                        }
                        return next;
                    });
                    return 0;
                }
                return prev + 2;
            });
        }, 50);

        return () => clearInterval(progressTimer);
    }, [status, expressions]);

    const handleStart = () => {
        setStatus('active');
        setCurrentProgress(0);
    };

    const handleComplete = useCallback(() => {
        setStatus('complete');
        if (onComplete) {
            onComplete({
                success: detectedExpressions.length > 0,
                expressionsCompleted: detectedExpressions.length,
                totalExpressions: expressions.length,
                data: detectedExpressions,
            });
        }
    }, [onComplete, detectedExpressions, expressions.length]);

    const recordExpression = (expressionType, score) => {
        const event = {
            timestamp: Date.now(),
            type: expressionType,
            score,
            expected: expressions[currentExpression]?.id,
        };
        setDetectedExpressions(prev => [...prev, event]);
        if (onExpressionDetected) onExpressionDetected(event);
    };

    const currentExp = expressions[currentExpression];

    return (
        <div className="expression-challenge">
            <div className="challenge-header">
                <h3>🎭 Expression Challenge</h3>
                {status === 'active' && (
                    <div className="timer">{timeLeft}s</div>
                )}
            </div>

            {status === 'ready' && (
                <div className="ready-screen">
                    <p>You'll be asked to make {expressions.length} facial expressions.</p>
                    <p className="hint">Try to be natural and hold each expression briefly.</p>
                    <button className="btn-start" onClick={handleStart}>
                        Start Challenge
                    </button>
                </div>
            )}

            {status === 'active' && currentExp && (
                <div className="expression-prompt">
                    <div className="expression-counter">
                        {currentExpression + 1} / {expressions.length}
                    </div>

                    <div className="expression-display">
                        <span className="expression-emoji">{currentExp.emoji}</span>
                        <h2 className="expression-label">{currentExp.label}</h2>
                        <p className="expression-instruction">{currentExp.instruction}</p>
                    </div>

                    <div className="expression-progress">
                        <div
                            className="progress-fill"
                            style={{ width: `${currentProgress}%` }}
                        />
                    </div>

                    <div className="expression-dots">
                        {expressions.map((_, idx) => (
                            <div
                                key={idx}
                                className={`dot ${idx < currentExpression ? 'completed' : ''} ${idx === currentExpression ? 'active' : ''}`}
                            />
                        ))}
                    </div>
                </div>
            )}

            {status === 'complete' && (
                <div className="complete-screen">
                    <div className="success-icon">✓</div>
                    <h3>Challenge Complete!</h3>
                    <p>{expressions.length} expressions analyzed</p>
                </div>
            )}
        </div>
    );
};

export default ExpressionChallenge;

/**
 * ExpressionChallenge Component
 *
 * Micro-expression challenge for liveness verification. Prompts the user to make
 * a short sequence of facial expressions.
 *
 * As with the gaze challenge, the prompt is rendered here but the expression
 * signal is captured SERVER-SIDE from the streamed camera frames (face-mesh
 * action units). This component only tells the user what to do and paces the
 * sequence; it does not itself measure the face. Expression is currently
 * captured-but-not-scored (it does not gate the verdict) until the real
 * MediaPipe action-unit path lands.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import './ExpressionChallenge.css';

const EXPRESSIONS = [
    { id: 'smile', label: 'Smile', emoji: '😊', instruction: 'Show a natural smile' },
    { id: 'surprise', label: 'Surprise', emoji: '😮', instruction: 'Look surprised' },
    { id: 'blink', label: 'Blink', emoji: '😌', instruction: 'Blink your eyes twice' },
    { id: 'neutral', label: 'Neutral', emoji: '😐', instruction: 'Keep a neutral expression' },
    { id: 'left_turn', label: 'Turn Left', emoji: '👈', instruction: 'Turn your head slightly left' },
    { id: 'right_turn', label: 'Turn Right', emoji: '👉', instruction: 'Turn your head slightly right' },
];

// The backend labels expressions with action-unit names (e.g. 'happy'); map
// them onto the prompts this component knows how to render.
const SERVER_EXPRESSION_ALIASES = {
    happy: 'smile',
    smile: 'smile',
    surprise: 'surprise',
    surprised: 'surprise',
    blink: 'blink',
    neutral: 'neutral',
    left_turn: 'left_turn',
    right_turn: 'right_turn',
};

const resolveExpressionIds = (requested) => {
    if (!Array.isArray(requested) || requested.length === 0) {
        return ['smile', 'blink', 'neutral'];
    }
    const ids = requested
        .map((e) => SERVER_EXPRESSION_ALIASES[String(e).toLowerCase()])
        .filter(Boolean);
    return ids.length > 0 ? ids : ['smile', 'blink', 'neutral'];
};

const ExpressionChallenge = ({
    challenge,
    onComplete,
    autoStart = true,
    holdMsPerExpression = 3000,
}) => {
    const requestedIds = resolveExpressionIds(challenge?.data?.expressions);
    const expressions = EXPRESSIONS.filter((e) => requestedIds.includes(e.id));

    const [currentExpression, setCurrentExpression] = useState(0);
    const [currentProgress, setCurrentProgress] = useState(0);
    const [status, setStatus] = useState(autoStart ? 'active' : 'ready');

    const completedRef = useRef(false);

    const handleComplete = useCallback(() => {
        if (completedRef.current) return;
        completedRef.current = true;
        setStatus('complete');
        if (onComplete) {
            onComplete({ success: true, expressionsShown: expressions.length });
        }
    }, [onComplete, expressions.length]);

    // Fill the current expression's progress bar. The updater stays PURE (it
    // only computes progress): advancing to the next expression is done in a
    // separate effect below. Doing the advance inside this updater would let
    // React 18 StrictMode's dev double-invocation enqueue setCurrentExpression
    // twice and skip an expression.
    useEffect(() => {
        if (status !== 'active' || expressions.length === 0) return undefined;
        const tick = Math.max(20, Math.floor(holdMsPerExpression / 50));
        const progressTimer = setInterval(() => {
            setCurrentProgress((prev) => (prev < 100 ? prev + 2 : 100));
        }, tick);
        return () => clearInterval(progressTimer);
    }, [status, expressions.length, holdMsPerExpression]);

    // When a bar fills, advance to the next expression (or finish). Kept out of
    // the progress updater so that updater is pure (see above).
    useEffect(() => {
        if (status !== 'active' || currentProgress < 100) return;
        if (currentExpression + 1 >= expressions.length) {
            handleComplete();
        } else {
            setCurrentExpression((c) => c + 1);
            setCurrentProgress(0);
        }
    }, [status, currentProgress, currentExpression, expressions.length, handleComplete]);

    const currentExp = expressions.at(currentExpression);

    return (
        <div className="expression-challenge">
            <div className="challenge-header">
                <h3>🎭 Expression Challenge</h3>
            </div>

            {status === 'ready' && (
                <div className="ready-screen">
                    <p>You&apos;ll be asked to make {expressions.length} facial expressions.</p>
                    <p className="hint">Try to be natural and hold each expression briefly.</p>
                    <button className="btn-start" onClick={() => setStatus('active')}>
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
                        <div className="progress-fill" style={{ width: `${currentProgress}%` }} />
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
                    <p>{expressions.length} expressions recorded</p>
                </div>
            )}
        </div>
    );
};

export default ExpressionChallenge;

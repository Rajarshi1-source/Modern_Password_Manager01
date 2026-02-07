/**
 * Partial Reveal Challenge
 * =========================
 * 
 * Displays password with gaps to complete.
 * Creators fill gaps faster with characteristic typing patterns.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './ChallengeStyles.css';

const PartialReveal = ({ challenge, onResponse, onKeystroke }) => {
    const [inputs, setInputs] = useState([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [timeLeft, setTimeLeft] = useState(challenge.time_limit_ms / 1000);
    const inputRefs = useRef([]);

    const data = challenge.data;
    const hiddenPositions = data.hidden_positions || [];
    const maskedPassword = data.masked_password || '';

    // Initialize input states
    useEffect(() => {
        setInputs(new Array(hiddenPositions.length).fill(''));
        inputRefs.current = inputRefs.current.slice(0, hiddenPositions.length);

        // Focus first input
        setTimeout(() => {
            if (inputRefs.current[0]) {
                inputRefs.current[0].focus();
            }
        }, 100);
    }, [hiddenPositions.length]);

    // Timer
    useEffect(() => {
        const timer = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 0) {
                    clearInterval(timer);
                    if (!isSubmitting) {
                        handleSubmit();
                    }
                    return 0;
                }
                return prev - 0.1;
            });
        }, 100);

        return () => clearInterval(timer);
    }, []);

    const handleInputChange = (index, value) => {
        if (isSubmitting) return;

        // Only allow single character
        const char = value.slice(-1);

        const newInputs = [...inputs];
        newInputs[index] = char;
        setInputs(newInputs);

        onKeystroke && onKeystroke();

        // Auto-advance to next input
        if (char && index < hiddenPositions.length - 1) {
            inputRefs.current[index + 1]?.focus();
        }

        // Auto-submit if all filled
        if (char && newInputs.every(i => i)) {
            setTimeout(() => handleSubmit(), 100);
        }
    };

    const handleKeyDown = (index, e) => {
        if (e.key === 'Backspace') {
            onKeystroke && onKeystroke(true);

            if (!inputs[index] && index > 0) {
                inputRefs.current[index - 1]?.focus();
            }
        } else if (e.key === 'Enter') {
            handleSubmit();
        }
    };

    const handleSubmit = useCallback(async () => {
        if (isSubmitting) return;
        setIsSubmitting(true);

        const response = inputs.join('');
        await onResponse(response);
    }, [isSubmitting, inputs, onResponse]);

    // Build display with inputs
    const renderMaskedPassword = () => {
        let inputIndex = 0;
        const elements = [];

        for (let i = 0; i < maskedPassword.length; i++) {
            if (maskedPassword[i] === '_') {
                const currentInputIndex = inputIndex;
                elements.push(
                    <input
                        key={i}
                        ref={(el) => (inputRefs.current[currentInputIndex] = el)}
                        type="text"
                        className="gap-input"
                        value={inputs[currentInputIndex] || ''}
                        onChange={(e) => handleInputChange(currentInputIndex, e.target.value)}
                        onKeyDown={(e) => handleKeyDown(currentInputIndex, e)}
                        maxLength={2}
                        disabled={isSubmitting}
                        autoComplete="off"
                        autoCorrect="off"
                        autoCapitalize="off"
                        spellCheck="false"
                    />
                );
                inputIndex++;
            } else {
                elements.push(
                    <span key={i} className="visible-char">
                        {maskedPassword[i]}
                    </span>
                );
            }
        }

        return elements;
    };

    return (
        <div className="challenge partial-challenge">
            <div className="challenge-header">
                <h4>Complete the Password</h4>
                <div className="time-display">
                    <span className={timeLeft < 5 ? 'warning' : ''}>
                        {timeLeft.toFixed(1)}s
                    </span>
                </div>
            </div>

            <p className="partial-instruction">{data.instruction}</p>

            <div className="masked-password-display">
                {renderMaskedPassword()}
            </div>

            <button
                className="submit-button"
                onClick={handleSubmit}
                disabled={isSubmitting || inputs.some(i => !i)}
            >
                Submit
            </button>
        </div>
    );
};

export default PartialReveal;

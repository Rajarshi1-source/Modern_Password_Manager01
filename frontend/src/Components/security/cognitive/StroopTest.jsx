/**
 * Stroop Test Challenge
 * ======================
 * 
 * Displays Stroop-effect stimuli for cognitive verification.
 * Measures interference patterns unique to password creators.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './ChallengeStyles.css';

const StroopTest = ({ challenge, onResponse, onKeystroke }) => {
    const [phase, setPhase] = useState('fixation'); // fixation, stimulus, response
    const [selectedOption, setSelectedOption] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [timeLeft, setTimeLeft] = useState(challenge.time_limit_ms / 1000);

    const data = challenge.data;
    const displayDuration = challenge.display_duration_ms || 750;

    // Phase progression
    useEffect(() => {
        // Show fixation cross first
        const fixationTimer = setTimeout(() => {
            setPhase('stimulus');
        }, 500);

        return () => clearTimeout(fixationTimer);
    }, []);

    // Stimulus display duration
    useEffect(() => {
        if (phase === 'stimulus') {
            const stimulusTimer = setTimeout(() => {
                setPhase('response');
            }, displayDuration);

            return () => clearTimeout(stimulusTimer);
        }
    }, [phase, displayDuration]);

    // Response timer
    useEffect(() => {
        if (phase !== 'response') return;

        const timer = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 0) {
                    clearInterval(timer);
                    if (!isSubmitting) {
                        handleSubmit(null);
                    }
                    return 0;
                }
                return prev - 0.1;
            });
        }, 100);

        return () => clearInterval(timer);
    }, [phase]);

    const handleOptionClick = (option, index) => {
        if (isSubmitting || phase !== 'response') return;

        setSelectedOption(index);
        onKeystroke && onKeystroke();

        setTimeout(() => handleSubmit(option), 100);
    };

    const handleSubmit = useCallback(async (response) => {
        if (isSubmitting) return;
        setIsSubmitting(true);

        await onResponse(response || '');
    }, [isSubmitting, onResponse]);

    // Fixation phase
    if (phase === 'fixation') {
        return (
            <div className="challenge stroop-challenge">
                <div className="fixation-cross">+</div>
            </div>
        );
    }

    // Stimulus phase
    if (phase === 'stimulus') {
        return (
            <div className="challenge stroop-challenge">
                <div className="stroop-stimulus">
                    <span
                        className="stroop-word"
                        style={{ color: data.color_hex }}
                    >
                        {data.stroop_word}
                    </span>
                </div>
            </div>
        );
    }

    // Response phase
    return (
        <div className="challenge stroop-challenge">
            <div className="challenge-header">
                <h4>What character was shown?</h4>
                <div className="time-display">
                    <span className={timeLeft < 3 ? 'warning' : ''}>
                        {timeLeft.toFixed(1)}s
                    </span>
                </div>
            </div>

            <p className="stroop-instruction">{data.instruction}</p>

            <div className="options-grid">
                {data.options?.map((option, index) => (
                    <button
                        key={index}
                        className={`option-button ${selectedOption === index ? 'selected' : ''}`}
                        onClick={() => handleOptionClick(option, index)}
                        disabled={isSubmitting}
                    >
                        <span className="option-text">{option}</span>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default StroopTest;

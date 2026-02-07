/**
 * Scrambled Recognition Challenge
 * ================================
 * 
 * Displays scrambled password fragments for pattern recognition.
 * Creators recognize patterns faster due to implicit memory.
 */

import React, { useState, useEffect } from 'react';
import './ChallengeStyles.css';

const ScrambledRecognition = ({ challenge, onResponse, onKeystroke }) => {
    const [selectedOption, setSelectedOption] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [timeLeft, setTimeLeft] = useState(challenge.time_limit_ms / 1000);

    const data = challenge.data;

    // Countdown timer
    useEffect(() => {
        const timer = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 0) {
                    clearInterval(timer);
                    // Auto-submit empty if time runs out
                    if (!isSubmitting) {
                        handleSubmit(null);
                    }
                    return 0;
                }
                return prev - 0.1;
            });
        }, 100);

        return () => clearInterval(timer);
    }, []);

    const handleOptionClick = (option, index) => {
        if (isSubmitting) return;

        setSelectedOption(index);
        onKeystroke && onKeystroke();

        // Auto-submit for multiple choice
        setTimeout(() => handleSubmit(option), 100);
    };

    const handleSubmit = async (response) => {
        if (isSubmitting) return;
        setIsSubmitting(true);

        await onResponse(response || '');
    };

    return (
        <div className="challenge scrambled-challenge">
            <div className="challenge-header">
                <h4>Pattern Recognition</h4>
                <div className="time-display">
                    <span className={timeLeft < 3 ? 'warning' : ''}>
                        {timeLeft.toFixed(1)}s
                    </span>
                </div>
            </div>

            <div className="scrambled-display">
                <span className="scrambled-text">{data.scrambled_text}</span>
                <p className="hint">Which option matches the unscrambled pattern?</p>
            </div>

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

export default ScrambledRecognition;

/**
 * Priming Challenge Component
 * ============================
 * 
 * Displays priming stimuli for implicit memory detection.
 * Creators show faster recognition after password-related primes.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './ChallengeStyles.css';

const PrimingChallenge = ({ challenge, onResponse, onKeystroke }) => {
    const [phase, setPhase] = useState('mask_before'); // mask_before, prime, mask_after, response
    const [selectedOption, setSelectedOption] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [timeLeft, setTimeLeft] = useState(challenge.time_limit_ms / 1000);

    const data = challenge.data;
    const primeStimulus = data.prime_stimulus;
    const primeDuration = data.prime_duration_ms || 100;

    // Phase progression
    useEffect(() => {
        let timeouts = [];

        // Pre-prime mask
        timeouts.push(setTimeout(() => {
            setPhase('prime');
        }, 300));

        // Prime display
        timeouts.push(setTimeout(() => {
            setPhase('mask_after');
        }, 300 + primeDuration));

        // Post-prime mask
        timeouts.push(setTimeout(() => {
            setPhase('response');
        }, 300 + primeDuration + 200));

        return () => timeouts.forEach(t => clearTimeout(t));
    }, [primeDuration]);

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

    // Pre-prime mask
    if (phase === 'mask_before') {
        return (
            <div className="challenge priming-challenge">
                <div className="mask-display">
                    <span className="mask-text">{primeStimulus?.mask_before || '####'}</span>
                </div>
            </div>
        );
    }

    // Prime display
    if (phase === 'prime') {
        return (
            <div className="challenge priming-challenge">
                <div className="prime-display">
                    <span
                        className="prime-text"
                        style={{
                            fontSize: primeStimulus?.font_size === 'large' ? '48px' : '36px',
                            opacity: primeStimulus?.highlight ? 1 : 0.8
                        }}
                    >
                        {primeStimulus?.text}
                    </span>
                </div>
            </div>
        );
    }

    // Post-prime mask
    if (phase === 'mask_after') {
        return (
            <div className="challenge priming-challenge">
                <div className="mask-display">
                    <span className="mask-text">{primeStimulus?.mask_after || '####'}</span>
                </div>
            </div>
        );
    }

    // Response phase
    return (
        <div className="challenge priming-challenge">
            <div className="challenge-header">
                <h4>Identify the Character</h4>
                <div className="time-display">
                    <span className={timeLeft < 3 ? 'warning' : ''}>
                        {timeLeft.toFixed(1)}s
                    </span>
                </div>
            </div>

            <p className="priming-instruction">{data.instruction}</p>

            <div className="options-grid">
                {data.target_options?.map((option, index) => (
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

export default PrimingChallenge;

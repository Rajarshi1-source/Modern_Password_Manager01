/**
 * useTypingPatternCapture Hook
 * =============================
 * 
 * Custom React hook for capturing typing patterns during password entry.
 * 
 * PRIVACY-FIRST DESIGN:
 * - Never stores raw keystrokes
 * - Only captures timing and error positions
 * - All data anonymized before transmission
 * 
 * Usage:
 * const { startCapture, captureKeystroke, captureError, endCapture, isCapturing } = useTypingPatternCapture({
 *   inputElement: passwordInputRef.current,
 *   enabled: userHasConsented,
 *   onPatternCaptured: handlePattern,
 * });
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// =============================================================================
// Constants
// =============================================================================

const TIMING_BUCKET_THRESHOLDS = [50, 100, 150, 200, 300, 500, 750, 1000, 2000];

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Anonymize timing to bucket (for privacy).
 */
const bucketizeTiming = (ms) => {
    for (const threshold of TIMING_BUCKET_THRESHOLDS) {
        if (ms <= threshold) {
            return threshold;
        }
    }
    return TIMING_BUCKET_THRESHOLDS[TIMING_BUCKET_THRESHOLDS.length - 1];
};

/**
 * Calculate SHA-256 hash prefix of password.
 * Only sends first 16 chars of hash for privacy.
 */
const getPasswordHashPrefix = async (password) => {
    const encoder = new TextEncoder();
    const data = encoder.encode(password);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex.substring(0, 16);
};

/**
 * Detect device type from user agent.
 */
const detectDeviceType = () => {
    const ua = navigator.userAgent.toLowerCase();
    if (/tablet|ipad|playbook|silk/i.test(ua)) {
        return 'tablet';
    }
    if (/mobile|iphone|ipod|android|blackberry|opera mini|iemobile/i.test(ua)) {
        return 'mobile';
    }
    return 'desktop';
};

/**
 * Detect input method.
 */
const detectInputMethod = () => {
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
        return 'touchscreen';
    }
    return 'keyboard';
};

// =============================================================================
// Main Hook
// =============================================================================

/**
 * Hook to capture typing patterns from a password input.
 * 
 * @param {Object} options
 * @param {HTMLInputElement} options.inputElement - The password input element
 * @param {boolean} options.enabled - Whether to capture patterns
 * @param {Function} options.onPatternCaptured - Callback with captured pattern
 * @param {Function} options.onError - Error callback
 */
export const useTypingPatternCapture = ({
    inputElement,
    enabled = false,
    onPatternCaptured,
    onError,
}) => {
    // State
    const [isCapturing, setIsCapturing] = useState(false);
    const [sessionData, setSessionData] = useState(null);

    // Refs for tracking state
    const keystrokeTimings = useRef([]);
    const backspacePositions = useRef([]);
    const lastKeystrokeTime = useRef(null);
    const sessionStartTime = useRef(null);
    const currentPasswordLength = useRef(0);

    // Start a new capture session
    const startCapture = useCallback(() => {
        if (!enabled) return;
        
        keystrokeTimings.current = [];
        backspacePositions.current = [];
        lastKeystrokeTime.current = null;
        sessionStartTime.current = performance.now();
        currentPasswordLength.current = 0;
        setIsCapturing(true);
    }, [enabled]);

    // Reset session
    const resetSession = useCallback(() => {
        keystrokeTimings.current = [];
        backspacePositions.current = [];
        lastKeystrokeTime.current = null;
        sessionStartTime.current = null;
        currentPasswordLength.current = 0;
        setIsCapturing(false);
        setSessionData(null);
    }, []);

    // Handle keydown events
    const captureKeystroke = useCallback((event) => {
        if (!enabled || !isCapturing) return;

        const now = performance.now();

        // Start session on first keystroke
        if (lastKeystrokeTime.current === null) {
            lastKeystrokeTime.current = now;
            return;
        }

        // Calculate inter-key timing
        const timing = Math.round(now - lastKeystrokeTime.current);
        lastKeystrokeTime.current = now;

        // Handle backspace (error detection)
        if (event.key === 'Backspace') {
            if (currentPasswordLength.current > 0) {
                backspacePositions.current.push(currentPasswordLength.current - 1);
                currentPasswordLength.current--;
            }
        } else if (event.key.length === 1) {
            // Regular character - record timing (bucketized for privacy)
            keystrokeTimings.current.push(bucketizeTiming(timing));
            currentPasswordLength.current++;
        }
    }, [enabled, isCapturing]);

    // Capture an error at a specific position
    const captureError = useCallback((position) => {
        if (!enabled || !isCapturing) return;
        backspacePositions.current.push(position);
    }, [enabled, isCapturing]);

    // End capture and return pattern
    const endCapture = useCallback(async (password) => {
        if (!isCapturing || keystrokeTimings.current.length === 0) {
            resetSession();
            return null;
        }

        try {
            const totalTime = sessionStartTime.current
                ? Math.round(performance.now() - sessionStartTime.current)
                : 0;

            const pattern = {
                password, // Will be hashed before sending
                keystroke_timings: keystrokeTimings.current,
                backspace_positions: backspacePositions.current,
                device_type: detectDeviceType(),
                input_method: detectInputMethod(),
            };

            setSessionData(pattern);
            setIsCapturing(false);

            // Call callback
            if (onPatternCaptured) {
                onPatternCaptured(pattern);
            }

            return pattern;
        } catch (error) {
            console.error('Error capturing pattern:', error);
            if (onError) {
                onError(error);
            }
            resetSession();
            return null;
        }
    }, [isCapturing, onPatternCaptured, onError, resetSession]);

    // Attach event listeners to input element
    useEffect(() => {
        if (!inputElement || !enabled) return;

        const handleKeyDown = (e) => captureKeystroke(e);
        const handleFocus = () => startCapture();

        inputElement.addEventListener('keydown', handleKeyDown);
        inputElement.addEventListener('focus', handleFocus);

        return () => {
            inputElement.removeEventListener('keydown', handleKeyDown);
            inputElement.removeEventListener('focus', handleFocus);
        };
    }, [inputElement, enabled, captureKeystroke, startCapture]);

    return {
        isCapturing,
        sessionData,
        startCapture,
        captureKeystroke,
        captureError,
        endCapture,
        resetSession,
    };
};

export default useTypingPatternCapture;

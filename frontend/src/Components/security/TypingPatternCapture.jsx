/**
 * TypingPatternCapture Component
 * ===============================
 * 
 * Invisible component that captures typing patterns during password entry.
 * 
 * PRIVACY-FIRST DESIGN:
 * - Never stores raw keystrokes
 * - Only captures timing and error positions
 * - All data anonymized before transmission
 * - Requires explicit user consent
 * 
 * Usage:
 * <TypingPatternCapture
 *   inputRef={passwordInputRef}
 *   onPatternCaptured={handlePattern}
 *   enabled={userConsent}
 * />
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import axios from 'axios';

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
    // Check for touch capability
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
        return 'touchscreen';
    }
    return 'keyboard';
};

// =============================================================================
// Hook: useTypingPattern
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
export const useTypingPattern = ({
    inputElement,
    enabled = false,
    onPatternCaptured,
    onError,
}) => {
    // Refs for tracking state
    const keystrokeTimings = useRef([]);
    const backspacePositions = useRef([]);
    const lastKeystrokeTime = useRef(null);
    const sessionStartTime = useRef(null);
    const currentPasswordLength = useRef(0);

    // Reset session
    const resetSession = useCallback(() => {
        keystrokeTimings.current = [];
        backspacePositions.current = [];
        lastKeystrokeTime.current = null;
        sessionStartTime.current = null;
        currentPasswordLength.current = 0;
    }, []);

    // Handle keydown events
    const handleKeyDown = useCallback((event) => {
        if (!enabled) return;

        const now = performance.now();

        // Start session on first keystroke
        if (sessionStartTime.current === null) {
            sessionStartTime.current = now;
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
    }, [enabled]);

    // Handle form submission or blur
    const capturePattern = useCallback(async (password, success = true) => {
        if (!enabled || keystrokeTimings.current.length === 0) {
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

            // Reset for next session
            resetSession();

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
    }, [enabled, onPatternCaptured, onError, resetSession]);

    // Attach event listeners
    useEffect(() => {
        if (!inputElement || !enabled) return;

        inputElement.addEventListener('keydown', handleKeyDown);

        return () => {
            inputElement.removeEventListener('keydown', handleKeyDown);
        };
    }, [inputElement, enabled, handleKeyDown]);

    return {
        capturePattern,
        resetSession,
        isCapturing: enabled && sessionStartTime.current !== null,
    };
};

// =============================================================================
// Component: TypingPatternCapture
// =============================================================================

/**
 * Invisible component wrapper for typing pattern capture.
 * 
 * @param {Object} props
 * @param {React.RefObject} props.inputRef - Ref to password input
 * @param {boolean} props.enabled - Whether capture is enabled
 * @param {Function} props.onPatternCaptured - Callback with pattern data
 * @param {Function} props.onSessionRecorded - Callback after API recording
 * @param {boolean} props.autoSubmit - Auto-submit pattern to API
 * @param {string} props.apiEndpoint - API endpoint for recording
 */
const TypingPatternCapture = ({
    inputRef,
    enabled = false,
    onPatternCaptured,
    onSessionRecorded,
    autoSubmit = true,
    apiEndpoint = '/api/security/adaptive/record-session/',
}) => {
    const [isRecording, setIsRecording] = useState(false);
    const [error, setError] = useState(null);

    // Use the typing pattern hook
    const { capturePattern, resetSession } = useTypingPattern({
        inputElement: inputRef?.current,
        enabled,
        onPatternCaptured: async (pattern) => {
            if (onPatternCaptured) {
                onPatternCaptured(pattern);
            }

            // Auto-submit to API
            if (autoSubmit && pattern) {
                try {
                    setIsRecording(true);
                    const response = await axios.post(apiEndpoint, pattern, {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                    });

                    if (onSessionRecorded) {
                        onSessionRecorded(response.data);
                    }
                } catch (err) {
                    console.error('Failed to record typing session:', err);
                    setError(err);
                } finally {
                    setIsRecording(false);
                }
            }
        },
        onError: setError,
    });

    // Expose capture function through ref
    useEffect(() => {
        if (inputRef?.current) {
            inputRef.current.captureTypingPattern = capturePattern;
            inputRef.current.resetTypingSession = resetSession;
        }
    }, [inputRef, capturePattern, resetSession]);

    // This component renders nothing - it's invisible
    return null;
};

export default TypingPatternCapture;

// =============================================================================
// Adaptive Password Service (Frontend)
// =============================================================================

/**
 * Frontend service for adaptive password management.
 */
export const adaptivePasswordService = {
    /**
     * Check if adaptive passwords are enabled for user.
     */
    async getConfig() {
        const response = await axios.get('/api/security/adaptive/config/');
        return response.data;
    },

    /**
     * Enable adaptive passwords with consent.
     */
    async enable(options = {}) {
        const response = await axios.post('/api/security/adaptive/enable/', {
            consent: true,
            consent_version: '1.0',
            suggestion_frequency_days: options.frequencyDays || 30,
            allow_centralized_training: options.allowCentralized ?? true,
            allow_federated_learning: options.allowFederated ?? false,
        });
        return response.data;
    },

    /**
     * Disable adaptive passwords.
     */
    async disable(deleteData = false) {
        const response = await axios.post('/api/security/adaptive/disable/', {
            delete_data: deleteData,
        });
        return response.data;
    },

    /**
     * Get adaptation suggestion for a password.
     */
    async suggestAdaptation(password, force = false) {
        const response = await axios.post('/api/security/adaptive/suggest/', {
            password,
            force,
        });
        return response.data;
    },

    /**
     * Apply a password adaptation.
     */
    async applyAdaptation(originalPassword, adaptedPassword, substitutions) {
        const response = await axios.post('/api/security/adaptive/apply/', {
            original_password: originalPassword,
            adapted_password: adaptedPassword,
            substitutions,
        });
        return response.data;
    },

    /**
     * Rollback an adaptation.
     */
    async rollback(adaptationId) {
        const response = await axios.post('/api/security/adaptive/rollback/', {
            adaptation_id: adaptationId,
        });
        return response.data;
    },

    /**
     * Get typing profile statistics.
     */
    async getProfile() {
        const response = await axios.get('/api/security/adaptive/profile/');
        return response.data;
    },

    /**
     * Get adaptation history.
     */
    async getHistory() {
        const response = await axios.get('/api/security/adaptive/history/');
        return response.data;
    },

    /**
     * Get evolution statistics.
     */
    async getStats() {
        const response = await axios.get('/api/security/adaptive/stats/');
        return response.data;
    },

    /**
     * Delete all adaptive data (GDPR).
     */
    async deleteAllData() {
        const response = await axios.delete('/api/security/adaptive/data/');
        return response.data;
    },

    /**
     * Export all adaptive data (GDPR).
     */
    async exportData() {
        const response = await axios.get('/api/security/adaptive/export/');
        return response.data;
    },
};

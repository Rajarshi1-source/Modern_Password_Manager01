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
import {
    extractFeatures,
    generateCandidates,
    rankSuggestions,
    applySubstitutions,
    maskPreview,
    filterByStrength,
    detectSubstitutionClasses,
} from '../../services/adaptive/adaptiveFeatures';

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

// NOTE: the legacy bare-SHA-256 `getPasswordHashPrefix` was removed in the
// zero-knowledge v2 cutover. A bare hash of the password is offline-guessable;
// the client now computes a *keyed* fingerprint via cryptoService and injects
// it through the `fingerprint` option below (see remediation plan §1, §5).

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
 * @param {Function} options.fingerprint - Keyed password-fingerprint function
 * @param {number} options.fpKeyVersion - Fingerprint key era the `fingerprint`
 *   function was derived under (from GET /adaptive/config/). The server rejects
 *   a mismatch with HTTP 409 rather than recording under the wrong era.
 */
export const useTypingPattern = ({
    inputElement,
    enabled = false,
    onPatternCaptured,
    onError,
    fingerprint,
    fpKeyVersion,
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

    // Handle form submission or blur.
    // Zero-knowledge v2: emit a keyed fingerprint + coarse length bucket — the
    // raw password is used only to compute these locally and is NEVER included
    // in the pattern object (and so never reaches the server).
    //
    // Phase 3 (plan §3.3, gap B2) additionally emits the substitution
    // *classes* already present in the password and an explicit `success`
    // outcome. Without the classes the server's `_record_substitution_classes`
    // was unreachable from the real client path; without `success` the service
    // fell back to a "no backspaces" heuristic its own docstring warns against
    // (a corrected typo is not a failed attempt).
    //
    // @param {string} password - The password just entered (stays on device).
    // @param {{ success?: boolean }} [outcome] - Whether the password was
    //   ultimately accepted. Omit only when the caller genuinely cannot know;
    //   the server then falls back to the heuristic.
    const capturePattern = useCallback(async (password, { success } = {}) => {
        if (!enabled || keystrokeTimings.current.length === 0) {
            return null;
        }

        try {
            if (typeof fingerprint !== 'function') {
                throw new Error(
                    'capturePattern requires a fingerprint() function (zero-knowledge v2).'
                );
            }
            // Fail closed rather than guessing an era: recording under the wrong
            // fp_key_version would write fingerprints from a dead key into a
            // live profile, which no later request can detect or undo.
            if (!Number.isInteger(fpKeyVersion) || fpKeyVersion < 1) {
                throw new Error(
                    'capturePattern requires fpKeyVersion (see GET /adaptive/config/).'
                );
            }

            const { length_bucket } = extractFeatures(password);
            const pattern = {
                schema_version: 2,
                fp_key_version: fpKeyVersion,
                password_fingerprint: await fingerprint(password),
                length_bucket,
                keystroke_timings: keystrokeTimings.current,
                backspace_positions: backspacePositions.current,
                device_type: detectDeviceType(),
                input_method: detectInputMethod(),
                substitution_classes_used: detectSubstitutionClasses(password),
                // Only sent when the caller actually knows. Omitting the key
                // is meaningfully different from sending `false`: the
                // serializer treats absence as "fall back to the heuristic",
                // and a wrong explicit `false` would train the bandit that a
                // successful entry failed.
                ...(typeof success === 'boolean' ? { success } : {}),
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
    }, [enabled, fingerprint, fpKeyVersion, onPatternCaptured, onError, resetSession]);

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
 * @param {boolean} [props.enabled] - Whether capture is enabled
 * @param {Function} [props.onPatternCaptured] - Callback with pattern data
 * @param {Function} [props.onSessionRecorded] - Callback after API recording
 * @param {boolean} [props.autoSubmit] - Auto-submit pattern to API (defaults to true)
 * @param {string} [props.apiEndpoint] - API endpoint for recording
 * @param {Function} [props.fingerprint] - Keyed password-fingerprint function
 * @param {number} [props.fpKeyVersion] - Fingerprint key era (from /adaptive/config/).
 *   Optional only in the sense that the prop itself can be omitted; if
 *   `enabled` is true, `capturePattern` requires an integer >= 1 and throws
 *   otherwise (fail-closed, see useTypingPattern above).
 */
const TypingPatternCapture = ({
    inputRef,
    enabled = false,
    onPatternCaptured,
    onSessionRecorded,
    autoSubmit = true,
    apiEndpoint = '/api/security/adaptive/record-session/',
    fingerprint,
    fpKeyVersion,
}) => {
    const [isRecording, setIsRecording] = useState(false);
    const [error, setError] = useState(null);

    // Use the typing pattern hook
    const { capturePattern, resetSession } = useTypingPattern({
        inputElement: inputRef?.current,
        enabled,
        fingerprint,
        fpKeyVersion,
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
     *
     * Also the source of `fingerprint_salt` + `fp_key_version`, which the client
     * needs before it can compute any fingerprint at all.
     */
    async getConfig() {
        const response = await axios.get('/api/security/adaptive/config/');
        return response.data;
    },

    /**
     * Build the keyed fingerprint function every other call site expects.
     *
     * Takes the caller's *unlocked* CryptoService instance rather than owning
     * one, because deriving the key needs the in-memory master password, which
     * only the unlocked session holds. The derived key is cached on that
     * instance (Argon2id is expensive; the per-call HMAC is not).
     *
     * @param {import('../../services/cryptoService').CryptoService} cryptoService
     *   An unlocked CryptoService.
     * @param {string} fingerprintSalt - `fingerprint_salt` from {@link getConfig}.
     * @returns {(password: string) => Promise<string>} Fingerprint function.
     */
    makeFingerprinter(cryptoService, fingerprintSalt) {
        if (!cryptoService || typeof cryptoService.passwordFingerprint !== 'function') {
            throw new Error('makeFingerprinter requires an unlocked CryptoService.');
        }
        if (typeof fingerprintSalt !== 'string' || fingerprintSalt.length === 0) {
            throw new Error(
                'makeFingerprinter requires the per-user fingerprint_salt from /adaptive/config/.'
            );
        }
        return (password) => cryptoService.passwordFingerprint(password, fingerprintSalt);
    },

    /**
     * Re-base the fingerprint key after a master-password change.
     *
     * Returns the new `{ fingerprint_salt, fp_key_version }`; the caller must
     * rebuild its fingerprinter from them. Prior-era rows stay in the database
     * for audit but drop out of history, stats and rollback.
     */
    async rotateFingerprintKey() {
        const response = await axios.post(
            '/api/security/adaptive/rotate-fingerprint-key/',
            { confirm: true },
        );
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
     * Record a captured typing session (zero-knowledge v2 payload).
     * The pattern carries a keyed fingerprint + coarse features only.
     */
    async record(pattern) {
        const response = await axios.post('/api/security/adaptive/record-session/', pattern);
        return response.data;
    },

    /**
     * Generate an adaptation suggestion entirely client-side (zero-knowledge v2).
     *
     * Fetches the learned preference model, then generates + ranks substitution
     * candidates locally, runs them through the Phase-2 strength gate, and
     * builds masked previews. The password NEVER leaves the device (no POST of
     * the password). Returns the same shape the AdaptivePasswordSuggestion
     * modal consumes, plus the gate's before/after `guesses_log10`.
     *
     * `has_suggestion: false` is a normal, expected outcome here — the gate
     * rejects roughly three quarters of candidate substitutions (measured over
     * a 200-password corpus, see plan §4.5). Callers must present it as "no
     * change needed", never as an error.
     *
     * Fails closed: if the strength estimator cannot be loaded or throws, no
     * suggestion is returned at all, because an ungated suggestion is exactly
     * the defect (gap C1) this gate exists to prevent.
     *
     * Ranking Thompson-samples from the model's `exploration` posteriors
     * (Phase 3): the bandit only learns about a class if it is occasionally
     * suggested despite not currently ranking first, and the sampling happens
     * here rather than server-side so `/preference-model/` stays deterministic
     * and cacheable.
     *
     * @param {string} password - The current password (stays on the device).
     * @param {{ estimator?: Function, explore?: boolean, rng?: Function }} [options={}]
     *   `estimator` overrides the lazily-loaded zxcvbn default (tests, or a
     *   pre-warmed instance); `explore` (default true) toggles Thompson
     *   sampling; `rng` injects a uniform source for reproducible tests.
     */
    async suggestAdaptation(password, { estimator, explore = true, rng } = {}) {
        let model;
        try {
            ({ data: model } = await axios.get('/api/security/adaptive/preference-model/'));
        } catch (error) {
            console.error('Adaptive preference model unavailable:', error);
            return {
                has_suggestion: false,
                preference_model_error: true,
                reason: 'Could not load your preference model, so no adaptation was suggested.',
            };
        }
        const ranked = rankSuggestions(generateCandidates(password), model, {
            explore,
            ...(rng ? { rng } : {}),
        });

        if (ranked.length === 0) {
            return {
                has_suggestion: false,
                reason: 'No memorability-improving substitutions found.',
            };
        }

        let gate;
        try {
            gate = await filterByStrength(password, ranked, { estimator });
        } catch (error) {
            console.error('Adaptive strength gate unavailable:', error);
            return {
                has_suggestion: false,
                strength_gate_error: true,
                reason:
                    'Could not verify that an adaptation would keep this password '
                    + 'as hard to guess, so none was suggested.',
            };
        }

        // Only counts and reason codes are carried out of the gate — never the
        // rejected substitutions themselves. They are password-positional data
        // and nothing downstream needs them.
        const rejected_count = gate.rejected.length;
        const rejected_reasons = Array.from(
            new Set(gate.rejected.map((r) => r.rejected_because)),
        );
        const guesses_log10_before = gate.originalGuessesLog10;
        const guesses_log10_after = gate.adaptedGuessesLog10;
        const guesses_log10_delta = guesses_log10_after - guesses_log10_before;

        const substitutions = gate.subs;
        if (substitutions.length === 0) {
            return {
                has_suggestion: false,
                reason:
                    'Every candidate adaptation would have made this password easier '
                    + 'to guess, so none was suggested.',
                guesses_log10_before,
                guesses_log10_after,
                guesses_log10_delta,
                rejected_count,
                rejected_reasons,
            };
        }

        const adapted = applySubstitutions(password, substitutions);
        const confidence_score =
            substitutions.reduce((sum, s) => sum + s.confidence, 0) / substitutions.length;
        // Local, transparent estimate — the server no longer scores the password.
        const memorability_improvement = Math.min(
            0.3,
            Number((confidence_score * 0.15 + substitutions.length * 0.03).toFixed(2))
        );

        return {
            has_suggestion: true,
            substitutions,
            original_preview: maskPreview(password),
            adapted_preview: maskPreview(adapted),
            confidence_score,
            memorability_improvement,
            guesses_log10_before,
            guesses_log10_after,
            guesses_log10_delta,
            rejected_count,
            rejected_reasons,
            adaptation_type: 'substitution',
            reason: `Based on your learned preference model (v${model.model_version}).`,
            model_version: model.model_version,
        };
    },

    /**
     * Apply a password adaptation (zero-knowledge v2).
     *
     * Computes the adapted password locally, then POSTs only the original/adapted
     * *fingerprints*, the substitution *classes* (from→to), and masked previews —
     * never the raw passwords.
     *
     * @param {string} originalPassword - The current password (stays on device).
     * @param {Array} substitutions - Ranked subs from {@link suggestAdaptation}.
     * @param {Object} opts
     * @param {(pw: string) => Promise<string>} opts.fingerprint - Keyed fingerprint fn.
     * @param {number} opts.fpKeyVersion - Era the fingerprint fn was derived under.
     * @param {number} [opts.memorabilityImprovement] - Optional client estimate.
     */
    async applyAdaptation(
        originalPassword,
        substitutions,
        { fingerprint, fpKeyVersion, memorabilityImprovement } = {},
    ) {
        if (typeof fingerprint !== 'function') {
            throw new Error('applyAdaptation requires a fingerprint() function (zero-knowledge v2).');
        }
        // Fail closed: an adaptation recorded under the wrong era would be
        // chained onto — or orphaned from — the wrong rollback history.
        if (!Number.isInteger(fpKeyVersion) || fpKeyVersion < 1) {
            throw new Error(
                'applyAdaptation requires fpKeyVersion (see GET /adaptive/config/).'
            );
        }

        const adaptedPassword = applySubstitutions(originalPassword, substitutions);
        const [original_fingerprint, adapted_fingerprint] = await Promise.all([
            fingerprint(originalPassword),
            fingerprint(adaptedPassword),
        ]);

        // Class-level substitutions only ({from, to, confidence}) — no positions
        // or password characters, matching the v2 serializer's strict contract.
        const classes = substitutions
            .map((s) => ({
                from: s.original_char ?? s.from,
                to: s.suggested_char ?? s.to,
                ...(typeof s.confidence === 'number' ? { confidence: s.confidence } : {}),
            }))
            .filter((c) => c.from && c.to);

        const response = await axios.post('/api/security/adaptive/apply/', {
            schema_version: 2,
            fp_key_version: fpKeyVersion,
            original_fingerprint,
            adapted_fingerprint,
            substitutions: classes,
            previews: {
                original_masked: maskPreview(originalPassword),
                adapted_masked: maskPreview(adaptedPassword),
            },
            ...(typeof memorabilityImprovement === 'number'
                ? { memorability_improvement: memorabilityImprovement }
                : {}),
        });
        // Return the locally-computed adapted password alongside the server
        // record so the caller can update the stored credential. It is held in
        // memory only — never sent to the server (only fingerprints are).
        return { ...response.data, adaptedPassword };
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

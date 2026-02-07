/**
 * LivenessResults Component
 * 
 * Displays liveness verification results with detailed breakdown.
 */

import React from 'react';
import './LivenessResults.css';

const LivenessResults = ({ results, onClose, onRetry }) => {
    if (!results) return null;

    const {
        is_verified,
        liveness_score,
        confidence,
        verdict,
        verdict_reason,
        micro_expression_score,
        gaze_tracking_score,
        pulse_oximetry_score,
        deepfake_probability,
        total_frames_processed,
    } = results;

    const getScoreColor = (score) => {
        if (score >= 0.8) return 'excellent';
        if (score >= 0.6) return 'good';
        if (score >= 0.4) return 'fair';
        return 'poor';
    };

    const formatScore = (score) => {
        if (score === null || score === undefined) return '--';
        return `${Math.round(score * 100)}%`;
    };

    return (
        <div className={`liveness-results ${is_verified ? 'verified' : 'failed'}`}>
            <div className="results-header">
                <div className={`result-icon ${is_verified ? 'success' : 'failure'}`}>
                    {is_verified ? '✓' : '✗'}
                </div>
                <h2>{is_verified ? 'Verification Successful' : 'Verification Failed'}</h2>
                <p className="verdict">{verdict}</p>
            </div>

            <div className="main-scores">
                <div className="score-circle">
                    <svg viewBox="0 0 100 100">
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke="rgba(255,255,255,0.1)"
                            strokeWidth="8"
                        />
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke={is_verified ? '#00c897' : '#ff6b6b'}
                            strokeWidth="8"
                            strokeLinecap="round"
                            strokeDasharray={`${liveness_score * 283} 283`}
                            transform="rotate(-90 50 50)"
                        />
                    </svg>
                    <div className="score-value">
                        {formatScore(liveness_score)}
                    </div>
                    <div className="score-label">Liveness</div>
                </div>

                <div className="score-circle">
                    <svg viewBox="0 0 100 100">
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke="rgba(255,255,255,0.1)"
                            strokeWidth="8"
                        />
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke="#00d4ff"
                            strokeWidth="8"
                            strokeLinecap="round"
                            strokeDasharray={`${confidence * 283} 283`}
                            transform="rotate(-90 50 50)"
                        />
                    </svg>
                    <div className="score-value">
                        {formatScore(confidence)}
                    </div>
                    <div className="score-label">Confidence</div>
                </div>
            </div>

            <div className="breakdown-section">
                <h3>Detection Breakdown</h3>

                <div className="breakdown-item">
                    <span className="breakdown-label">🎭 Expression Analysis</span>
                    <div className="breakdown-bar-container">
                        <div
                            className={`breakdown-bar ${getScoreColor(micro_expression_score)}`}
                            style={{ width: formatScore(micro_expression_score) }}
                        />
                    </div>
                    <span className="breakdown-value">{formatScore(micro_expression_score)}</span>
                </div>

                <div className="breakdown-item">
                    <span className="breakdown-label">👁️ Gaze Tracking</span>
                    <div className="breakdown-bar-container">
                        <div
                            className={`breakdown-bar ${getScoreColor(gaze_tracking_score)}`}
                            style={{ width: formatScore(gaze_tracking_score) }}
                        />
                    </div>
                    <span className="breakdown-value">{formatScore(gaze_tracking_score)}</span>
                </div>

                <div className="breakdown-item">
                    <span className="breakdown-label">❤️ Pulse Detection</span>
                    <div className="breakdown-bar-container">
                        <div
                            className={`breakdown-bar ${getScoreColor(pulse_oximetry_score)}`}
                            style={{ width: formatScore(pulse_oximetry_score) }}
                        />
                    </div>
                    <span className="breakdown-value">{formatScore(pulse_oximetry_score)}</span>
                </div>

                <div className="breakdown-item">
                    <span className="breakdown-label">🛡️ Deepfake Detection</span>
                    <div className="breakdown-bar-container">
                        <div
                            className={`breakdown-bar ${deepfake_probability < 0.3 ? 'excellent' : deepfake_probability < 0.5 ? 'fair' : 'poor'}`}
                            style={{ width: `${100 - (deepfake_probability || 0) * 100}%` }}
                        />
                    </div>
                    <span className="breakdown-value">{formatScore(1 - (deepfake_probability || 0))}</span>
                </div>
            </div>

            <div className="stats-row">
                <div className="stat">
                    <span className="stat-value">{total_frames_processed || 0}</span>
                    <span className="stat-label">Frames Analyzed</span>
                </div>
            </div>

            {verdict_reason && (
                <div className="reason-box">
                    <strong>Details:</strong> {verdict_reason}
                </div>
            )}

            <div className="action-buttons">
                {!is_verified && onRetry && (
                    <button className="btn-retry" onClick={onRetry}>
                        Try Again
                    </button>
                )}
                <button className="btn-close" onClick={onClose}>
                    {is_verified ? 'Continue' : 'Close'}
                </button>
            </div>
        </div>
    );
};

export default LivenessResults;

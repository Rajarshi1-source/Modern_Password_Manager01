/**
 * Cognitive Profile Card Component
 * ==================================
 * 
 * Displays user's cognitive profile status and calibration progress.
 */

import React, { useState, useEffect } from 'react';
import './CognitiveProfileCard.css';
import cognitiveAuthService from '../../services/cognitiveAuthService';

const CognitiveProfileCard = ({ onCalibrate }) => {
    const [profile, setProfile] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadProfile();
    }, []);

    const loadProfile = async () => {
        try {
            setIsLoading(true);
            const data = await cognitiveAuthService.getProfile();
            setProfile(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    if (isLoading) {
        return (
            <div className="cognitive-profile-card loading">
                <div className="loading-skeleton" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="cognitive-profile-card error">
                <span className="error-message">{error}</span>
            </div>
        );
    }

    return (
        <div className="cognitive-profile-card">
            <div className="card-header">
                <div className="icon-container">
                    <span className="brain-icon">🧠</span>
                </div>
                <div className="header-text">
                    <h4>Cognitive Profile</h4>
                    <span className={`status-badge ${profile?.is_calibrated ? 'active' : 'pending'}`}>
                        {profile?.is_calibrated ? 'Calibrated' : 'Not Calibrated'}
                    </span>
                </div>
            </div>

            {profile?.is_calibrated ? (
                <div className="profile-metrics">
                    <div className="metric">
                        <label>Confidence</label>
                        <div className="metric-bar">
                            <div
                                className="metric-fill"
                                style={{ width: `${(profile.profile_confidence || 0) * 100}%` }}
                            />
                        </div>
                        <span className="metric-value">
                            {Math.round((profile.profile_confidence || 0) * 100)}%
                        </span>
                    </div>

                    <div className="metric">
                        <label>Baseline RT</label>
                        <span className="metric-value">
                            {Math.round(profile.baseline_reaction_time || 0)}ms
                        </span>
                    </div>

                    <div className="type-coverage">
                        <label>Challenge Types</label>
                        <div className="types">
                            {['scrambled', 'stroop', 'priming', 'partial'].map(type => (
                                <span
                                    key={type}
                                    className={`type-badge ${profile.type_coverage?.[type] ? 'active' : ''}`}
                                >
                                    {type}
                                </span>
                            ))}
                        </div>
                    </div>

                    {profile.needs_recalibration && (
                        <div className="recalibration-notice">
                            <span className="notice-icon">⚠️</span>
                            <span>Profile needs recalibration</span>
                        </div>
                    )}
                </div>
            ) : (
                <div className="calibration-prompt">
                    <p>
                        Calibrate your cognitive profile to enable implicit memory verification.
                        This helps distinguish you as the password creator from potential attackers.
                    </p>

                    <div className="progress-indicator">
                        <div className="progress-bar">
                            <div
                                className="progress-fill"
                                style={{ width: `${profile?.calibration_progress || 0}%` }}
                            />
                        </div>
                        <span>{profile?.calibration_progress || 0}%</span>
                    </div>
                </div>
            )}

            <div className="card-actions">
                <button
                    className="calibrate-button"
                    onClick={onCalibrate}
                >
                    {profile?.is_calibrated ? 'Recalibrate' : 'Start Calibration'}
                </button>
            </div>
        </div>
    );
};

export default CognitiveProfileCard;

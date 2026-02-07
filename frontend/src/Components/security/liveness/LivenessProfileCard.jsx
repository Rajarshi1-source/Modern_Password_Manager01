/**
 * LivenessProfileCard Component
 * 
 * Displays user's liveness verification profile status and settings.
 */

import React, { useState, useEffect } from 'react';
import biometricLivenessService from '../../../services/biometricLivenessService';
import './LivenessProfileCard.css';

const LivenessProfileCard = ({ onStartVerification }) => {
    const [profile, setProfile] = useState(null);
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            const [profileData, settingsData] = await Promise.all([
                biometricLivenessService.getProfile(),
                biometricLivenessService.getSettings(),
            ]);
            setProfile(profileData);
            setSettings(settingsData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const toggleSetting = async (key) => {
        if (!settings) return;
        const updated = { ...settings, [key]: !settings[key] };
        try {
            await biometricLivenessService.updateSettings(updated);
            setSettings(updated);
        } catch (err) {
            console.error('Failed to update setting:', err);
        }
    };

    if (loading) {
        return (
            <div className="liveness-profile-card loading">
                <div className="spinner-small"></div>
                <span>Loading...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="liveness-profile-card error">
                <span>⚠️ {error}</span>
                <button onClick={loadData}>Retry</button>
            </div>
        );
    }

    return (
        <div className="liveness-profile-card">
            <div className="card-header">
                <span className="card-icon">🎭</span>
                <div className="card-title">
                    <h3>Biometric Liveness</h3>
                    <p>Deepfake-resistant verification</p>
                </div>
                <div className={`status-badge ${profile?.is_calibrated ? 'active' : 'inactive'}`}>
                    {profile?.is_calibrated ? 'Calibrated' : 'Not Calibrated'}
                </div>
            </div>

            {profile?.is_calibrated ? (
                <div className="profile-stats">
                    <div className="stat">
                        <span className="stat-value">{profile.calibration_samples}</span>
                        <span className="stat-label">Samples</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{(profile.profile_confidence * 100).toFixed(0)}%</span>
                        <span className="stat-label">Confidence</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{(profile.liveness_threshold * 100).toFixed(0)}%</span>
                        <span className="stat-label">Threshold</span>
                    </div>
                </div>
            ) : (
                <div className="calibration-prompt">
                    <p>Complete initial calibration to enable liveness verification</p>
                    <button className="btn-calibrate" onClick={onStartVerification}>
                        Start Calibration
                    </button>
                </div>
            )}

            <div className="settings-section">
                <h4>Quick Settings</h4>
                <div className="setting-row">
                    <span>Require on login</span>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={settings?.enable_on_login || false}
                            onChange={() => toggleSetting('enable_on_login')}
                        />
                        <span className="slider"></span>
                    </label>
                </div>
                <div className="setting-row">
                    <span>Require for sensitive actions</span>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={settings?.enable_on_sensitive_actions || false}
                            onChange={() => toggleSetting('enable_on_sensitive_actions')}
                        />
                        <span className="slider"></span>
                    </label>
                </div>
                <div className="setting-row">
                    <span>Enable pulse detection</span>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={settings?.enable_pulse_detection || false}
                            onChange={() => toggleSetting('enable_pulse_detection')}
                        />
                        <span className="slider"></span>
                    </label>
                </div>
            </div>

            {profile?.is_calibrated && (
                <button className="btn-verify" onClick={onStartVerification}>
                    Run Verification
                </button>
            )}
        </div>
    );
};

export default LivenessProfileCard;

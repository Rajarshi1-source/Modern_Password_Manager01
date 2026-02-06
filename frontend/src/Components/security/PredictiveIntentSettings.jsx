/**
 * Predictive Intent Settings
 * 
 * Settings panel for AI password prediction:
 * - Enable/disable predictions
 * - Confidence threshold slider
 * - Data retention preferences
 * - Pattern learning toggles
 * 
 * @author Password Manager Team
 * @created 2026-02-06
 */

import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import predictiveIntentService from '../../services/predictiveIntentService';
import './PredictiveIntentSettings.css';

const PredictiveIntentSettings = () => {
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [newExcludedDomain, setNewExcludedDomain] = useState('');

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            setLoading(true);
            const data = await predictiveIntentService.getSettings();
            setSettings(data);
        } catch (err) {
            toast.error('Failed to load settings');
        } finally {
            setLoading(false);
        }
    };

    const saveSettings = async (updates) => {
        try {
            setSaving(true);
            const newSettings = await predictiveIntentService.updateSettings(updates);
            setSettings(newSettings);
            toast.success('Settings saved');
        } catch (err) {
            toast.error('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleToggle = (field) => {
        saveSettings({ [field]: !settings[field] });
    };

    const handleSliderChange = (field, value) => {
        setSettings(prev => ({ ...prev, [field]: value }));
    };

    const handleSliderCommit = (field, value) => {
        saveSettings({ [field]: value });
    };

    const handleAddExcludedDomain = () => {
        if (!newExcludedDomain.trim()) return;

        const domain = newExcludedDomain.toLowerCase().trim();
        if (settings.excluded_domains.includes(domain)) {
            toast.error('Domain already excluded');
            return;
        }

        const newList = [...settings.excluded_domains, domain];
        saveSettings({ excluded_domains: newList });
        setNewExcludedDomain('');
    };

    const handleRemoveExcludedDomain = (domain) => {
        const newList = settings.excluded_domains.filter(d => d !== domain);
        saveSettings({ excluded_domains: newList });
    };

    if (loading) {
        return (
            <div className="predictive-settings loading">
                <div className="spinner"></div>
                <p>Loading settings...</p>
            </div>
        );
    }

    if (!settings) {
        return (
            <div className="predictive-settings error">
                <p>Failed to load settings</p>
                <button onClick={loadSettings}>Retry</button>
            </div>
        );
    }

    return (
        <div className="predictive-settings">
            {/* Header */}
            <div className="settings-header">
                <div className="header-content">
                    <span className="header-icon">🔮</span>
                    <div>
                        <h1>Predictive Intent Settings</h1>
                        <p>Configure AI-powered password predictions</p>
                    </div>
                </div>
            </div>

            {/* Main Toggle */}
            <div className="settings-section">
                <div className="setting-row main-toggle">
                    <div className="setting-info">
                        <h3>Enable Predictions</h3>
                        <p>Allow AI to predict which passwords you'll need based on your usage patterns</p>
                    </div>
                    <button
                        className={`toggle ${settings.is_enabled ? 'active' : ''}`}
                        onClick={() => handleToggle('is_enabled')}
                        disabled={saving}
                    >
                        <span className="toggle-slider"></span>
                    </button>
                </div>
            </div>

            {/* Learning Settings */}
            <div className="settings-section">
                <h2>Learning</h2>

                <div className="setting-row">
                    <div className="setting-info">
                        <h3>Learn from Vault Access</h3>
                        <p>Track which passwords you access to improve predictions</p>
                    </div>
                    <button
                        className={`toggle ${settings.learn_from_vault_access ? 'active' : ''}`}
                        onClick={() => handleToggle('learn_from_vault_access')}
                        disabled={saving || !settings.is_enabled}
                    >
                        <span className="toggle-slider"></span>
                    </button>
                </div>

                <div className="setting-row">
                    <div className="setting-info">
                        <h3>Learn from Autofill</h3>
                        <p>Track browser autofill usage for better predictions</p>
                    </div>
                    <button
                        className={`toggle ${settings.learn_from_autofill ? 'active' : ''}`}
                        onClick={() => handleToggle('learn_from_autofill')}
                        disabled={saving || !settings.is_enabled}
                    >
                        <span className="toggle-slider"></span>
                    </button>
                </div>
            </div>

            {/* Confidence Thresholds */}
            <div className="settings-section">
                <h2>Confidence Thresholds</h2>

                <div className="setting-row slider-row">
                    <div className="setting-info">
                        <h3>Minimum Confidence</h3>
                        <p>Only show predictions above this confidence level</p>
                    </div>
                    <div className="slider-control">
                        <input
                            type="range"
                            min="0.5"
                            max="0.95"
                            step="0.05"
                            value={settings.min_confidence_threshold}
                            onChange={(e) => handleSliderChange('min_confidence_threshold', parseFloat(e.target.value))}
                            onMouseUp={(e) => handleSliderCommit('min_confidence_threshold', parseFloat(e.target.value))}
                            onTouchEnd={(e) => handleSliderCommit('min_confidence_threshold', parseFloat(e.target.value))}
                            disabled={saving || !settings.is_enabled}
                        />
                        <span className="slider-value">{(settings.min_confidence_threshold * 100).toFixed(0)}%</span>
                    </div>
                </div>

                <div className="setting-row slider-row">
                    <div className="setting-info">
                        <h3>Preload Confidence</h3>
                        <p>Pre-cache credentials above this confidence for instant access</p>
                    </div>
                    <div className="slider-control">
                        <input
                            type="range"
                            min="0.7"
                            max="0.99"
                            step="0.05"
                            value={settings.preload_confidence_threshold}
                            onChange={(e) => handleSliderChange('preload_confidence_threshold', parseFloat(e.target.value))}
                            onMouseUp={(e) => handleSliderCommit('preload_confidence_threshold', parseFloat(e.target.value))}
                            onTouchEnd={(e) => handleSliderCommit('preload_confidence_threshold', parseFloat(e.target.value))}
                            disabled={saving || !settings.is_enabled}
                        />
                        <span className="slider-value">{(settings.preload_confidence_threshold * 100).toFixed(0)}%</span>
                    </div>
                </div>
            </div>

            {/* Limits */}
            <div className="settings-section">
                <h2>Limits</h2>

                <div className="setting-row slider-row">
                    <div className="setting-info">
                        <h3>Max Predictions Shown</h3>
                        <p>Maximum number of predictions to display</p>
                    </div>
                    <div className="slider-control">
                        <input
                            type="range"
                            min="1"
                            max="10"
                            step="1"
                            value={settings.max_predictions_shown}
                            onChange={(e) => handleSliderChange('max_predictions_shown', parseInt(e.target.value))}
                            onMouseUp={(e) => handleSliderCommit('max_predictions_shown', parseInt(e.target.value))}
                            onTouchEnd={(e) => handleSliderCommit('max_predictions_shown', parseInt(e.target.value))}
                            disabled={saving || !settings.is_enabled}
                        />
                        <span className="slider-value">{settings.max_predictions_shown}</span>
                    </div>
                </div>

                <div className="setting-row slider-row">
                    <div className="setting-info">
                        <h3>Pattern Retention</h3>
                        <p>Days to keep usage patterns for learning</p>
                    </div>
                    <div className="slider-control">
                        <input
                            type="range"
                            min="30"
                            max="365"
                            step="30"
                            value={settings.pattern_retention_days}
                            onChange={(e) => handleSliderChange('pattern_retention_days', parseInt(e.target.value))}
                            onMouseUp={(e) => handleSliderCommit('pattern_retention_days', parseInt(e.target.value))}
                            onTouchEnd={(e) => handleSliderCommit('pattern_retention_days', parseInt(e.target.value))}
                            disabled={saving || !settings.is_enabled}
                        />
                        <span className="slider-value">{settings.pattern_retention_days} days</span>
                    </div>
                </div>
            </div>

            {/* Excluded Domains */}
            <div className="settings-section">
                <h2>Excluded Domains</h2>
                <p className="section-description">
                    Domains where predictions will not be made and patterns will not be learned
                </p>

                <div className="add-domain-row">
                    <input
                        type="text"
                        placeholder="Enter domain (e.g., bank.com)"
                        value={newExcludedDomain}
                        onChange={(e) => setNewExcludedDomain(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleAddExcludedDomain()}
                        disabled={saving || !settings.is_enabled}
                    />
                    <button
                        onClick={handleAddExcludedDomain}
                        disabled={saving || !settings.is_enabled || !newExcludedDomain.trim()}
                    >
                        Add
                    </button>
                </div>

                {settings.excluded_domains.length > 0 ? (
                    <div className="excluded-domains-list">
                        {settings.excluded_domains.map(domain => (
                            <div key={domain} className="excluded-domain">
                                <span>{domain}</span>
                                <button
                                    onClick={() => handleRemoveExcludedDomain(domain)}
                                    disabled={saving}
                                    className="remove-btn"
                                >
                                    ✕
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="no-excluded">No domains excluded</p>
                )}
            </div>

            {/* Notifications */}
            <div className="settings-section">
                <h2>Notifications</h2>

                <div className="setting-row">
                    <div className="setting-info">
                        <h3>High Confidence Alerts</h3>
                        <p>Push notification when a high-confidence prediction is available</p>
                    </div>
                    <button
                        className={`toggle ${settings.notify_high_confidence ? 'active' : ''}`}
                        onClick={() => handleToggle('notify_high_confidence')}
                        disabled={saving || !settings.is_enabled}
                    >
                        <span className="toggle-slider"></span>
                    </button>
                </div>
            </div>

            {/* Back Link */}
            <div className="settings-footer">
                <a href="/settings/security/predictive-intent/dashboard" className="back-link">
                    ← Back to Dashboard
                </a>
            </div>
        </div>
    );
};

export default PredictiveIntentSettings;

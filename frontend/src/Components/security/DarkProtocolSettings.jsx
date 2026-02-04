/**
 * Dark Protocol Settings Component
 * ==================================
 * 
 * Configuration UI for the Dark Protocol anonymous vault access network.
 * Provides controls for privacy settings and network preferences.
 * 
 * @author Password Manager Team
 * @created 2026-02-02
 */

import React, { useState, useEffect } from 'react';
import darkProtocolService from '../../services/darkProtocolService';
import './DarkProtocolSettings.css';

const DarkProtocolSettings = ({ onSave, onClose }) => {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);

    // Form state
    const [formData, setFormData] = useState({
        is_enabled: true,
        min_hops: 3,
        max_hops: 5,
        preferred_regions: [],
        cover_traffic_enabled: true,
        cover_traffic_intensity: 0.5,
        auto_path_rotation: true,
        path_rotation_interval_minutes: 5,
        use_bridge_nodes: false,
        require_verified_nodes: true,
        session_timeout_minutes: 30,
        auto_connect_on_suspicious: true,
    });

    const AVAILABLE_REGIONS = [
        { code: 'NA', name: 'North America' },
        { code: 'EU', name: 'Europe' },
        { code: 'AS', name: 'Asia Pacific' },
        { code: 'SA', name: 'South America' },
        { code: 'AF', name: 'Africa' },
        { code: 'OC', name: 'Oceania' },
    ];

    useEffect(() => {
        loadConfig();
    }, []);

    const loadConfig = async () => {
        try {
            const data = await darkProtocolService.getConfig();
            setConfig(data);
            setFormData({
                is_enabled: data.is_enabled ?? true,
                min_hops: data.min_hops ?? 3,
                max_hops: data.max_hops ?? 5,
                preferred_regions: data.preferred_regions ?? [],
                cover_traffic_enabled: data.cover_traffic_enabled ?? true,
                cover_traffic_intensity: data.cover_traffic_intensity ?? 0.5,
                auto_path_rotation: data.auto_path_rotation ?? true,
                path_rotation_interval_minutes: data.path_rotation_interval_minutes ?? 5,
                use_bridge_nodes: data.use_bridge_nodes ?? false,
                require_verified_nodes: data.require_verified_nodes ?? true,
                session_timeout_minutes: data.session_timeout_minutes ?? 30,
                auto_connect_on_suspicious: data.auto_connect_on_suspicious ?? true,
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleRegionToggle = (regionCode) => {
        const current = formData.preferred_regions;
        if (current.includes(regionCode)) {
            handleChange('preferred_regions', current.filter(r => r !== regionCode));
        } else {
            handleChange('preferred_regions', [...current, regionCode]);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);

        try {
            const updatedConfig = await darkProtocolService.updateConfig(formData);
            setConfig(updatedConfig);
            if (onSave) onSave(updatedConfig);
            if (onClose) onClose();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        setFormData({
            is_enabled: true,
            min_hops: 3,
            max_hops: 5,
            preferred_regions: [],
            cover_traffic_enabled: true,
            cover_traffic_intensity: 0.5,
            auto_path_rotation: true,
            path_rotation_interval_minutes: 5,
            use_bridge_nodes: false,
            require_verified_nodes: true,
            session_timeout_minutes: 30,
            auto_connect_on_suspicious: true,
        });
    };

    if (loading) {
        return (
            <div className="dp-settings">
                <div className="dp-settings-loading">
                    <div className="dp-spinner"></div>
                    <p>Loading settings...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dp-settings">
            <div className="dp-settings-header">
                <h2>🌑 Dark Protocol Settings</h2>
                {onClose && (
                    <button className="dp-close-btn" onClick={onClose}>×</button>
                )}
            </div>

            {error && (
                <div className="dp-settings-error">
                    <span>⚠️</span> {error}
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            <div className="dp-settings-body">
                {/* Master Toggle */}
                <div className="dp-settings-section">
                    <div className="dp-master-toggle">
                        <div className="dp-toggle-info">
                            <h3>Enable Dark Protocol</h3>
                            <p>Route vault access through anonymous network</p>
                        </div>
                        <label className="dp-switch">
                            <input
                                type="checkbox"
                                checked={formData.is_enabled}
                                onChange={(e) => handleChange('is_enabled', e.target.checked)}
                            />
                            <span className="dp-switch-slider"></span>
                        </label>
                    </div>
                </div>

                {/* Anonymity Level */}
                <div className="dp-settings-section">
                    <h4>🔒 Anonymity Level</h4>

                    <div className="dp-setting-row">
                        <label>Minimum Hops</label>
                        <div className="dp-range-container">
                            <input
                                type="range"
                                min="2"
                                max="7"
                                value={formData.min_hops}
                                onChange={(e) => handleChange('min_hops', parseInt(e.target.value))}
                            />
                            <span className="dp-range-value">{formData.min_hops}</span>
                        </div>
                        <p className="dp-setting-desc">More hops = more anonymous, slower speed</p>
                    </div>

                    <div className="dp-setting-row">
                        <label>Maximum Hops</label>
                        <div className="dp-range-container">
                            <input
                                type="range"
                                min={formData.min_hops}
                                max="7"
                                value={formData.max_hops}
                                onChange={(e) => handleChange('max_hops', parseInt(e.target.value))}
                            />
                            <span className="dp-range-value">{formData.max_hops}</span>
                        </div>
                    </div>

                    <div className="dp-setting-row checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.require_verified_nodes}
                                onChange={(e) => handleChange('require_verified_nodes', e.target.checked)}
                            />
                            <span className="dp-checkbox-label">Require Verified Nodes Only</span>
                        </label>
                        <p className="dp-setting-desc">Only use trusted, verified relay nodes</p>
                    </div>
                </div>

                {/* Preferred Regions */}
                <div className="dp-settings-section">
                    <h4>🌍 Preferred Regions</h4>
                    <p className="dp-section-desc">Select regions for routing (empty = all)</p>

                    <div className="dp-region-grid">
                        {AVAILABLE_REGIONS.map(region => (
                            <button
                                key={region.code}
                                className={`dp-region-btn ${formData.preferred_regions.includes(region.code) ? 'active' : ''}`}
                                onClick={() => handleRegionToggle(region.code)}
                            >
                                {region.name}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Cover Traffic */}
                <div className="dp-settings-section">
                    <h4>🎭 Cover Traffic</h4>

                    <div className="dp-setting-row checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.cover_traffic_enabled}
                                onChange={(e) => handleChange('cover_traffic_enabled', e.target.checked)}
                            />
                            <span className="dp-checkbox-label">Enable Cover Traffic</span>
                        </label>
                        <p className="dp-setting-desc">Generate fake operations to mask real activity</p>
                    </div>

                    {formData.cover_traffic_enabled && (
                        <div className="dp-setting-row">
                            <label>Traffic Intensity</label>
                            <div className="dp-range-container">
                                <input
                                    type="range"
                                    min="0.1"
                                    max="1"
                                    step="0.1"
                                    value={formData.cover_traffic_intensity}
                                    onChange={(e) => handleChange('cover_traffic_intensity', parseFloat(e.target.value))}
                                />
                                <span className="dp-range-value">{Math.round(formData.cover_traffic_intensity * 100)}%</span>
                            </div>
                            <p className="dp-setting-desc">Higher intensity = more cover traffic, more bandwidth</p>
                        </div>
                    )}
                </div>

                {/* Path Rotation */}
                <div className="dp-settings-section">
                    <h4>🔄 Path Rotation</h4>

                    <div className="dp-setting-row checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.auto_path_rotation}
                                onChange={(e) => handleChange('auto_path_rotation', e.target.checked)}
                            />
                            <span className="dp-checkbox-label">Automatic Path Rotation</span>
                        </label>
                        <p className="dp-setting-desc">Periodically change routing path for security</p>
                    </div>

                    {formData.auto_path_rotation && (
                        <div className="dp-setting-row">
                            <label>Rotation Interval</label>
                            <select
                                value={formData.path_rotation_interval_minutes}
                                onChange={(e) => handleChange('path_rotation_interval_minutes', parseInt(e.target.value))}
                            >
                                <option value="1">Every 1 minute</option>
                                <option value="5">Every 5 minutes</option>
                                <option value="10">Every 10 minutes</option>
                                <option value="15">Every 15 minutes</option>
                                <option value="30">Every 30 minutes</option>
                            </select>
                        </div>
                    )}
                </div>

                {/* Censorship Resistance */}
                <div className="dp-settings-section">
                    <h4>🛡️ Censorship Resistance</h4>

                    <div className="dp-setting-row checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.use_bridge_nodes}
                                onChange={(e) => handleChange('use_bridge_nodes', e.target.checked)}
                            />
                            <span className="dp-checkbox-label">Use Bridge Nodes</span>
                        </label>
                        <p className="dp-setting-desc">Use obfuscated bridges for censored networks</p>
                    </div>

                    <div className="dp-setting-row checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.auto_connect_on_suspicious}
                                onChange={(e) => handleChange('auto_connect_on_suspicious', e.target.checked)}
                            />
                            <span className="dp-checkbox-label">Auto-Connect on Suspicious Activity</span>
                        </label>
                        <p className="dp-setting-desc">Automatically enable when threats detected</p>
                    </div>
                </div>

                {/* Session Settings */}
                <div className="dp-settings-section">
                    <h4>⏱️ Session Settings</h4>

                    <div className="dp-setting-row">
                        <label>Session Timeout</label>
                        <select
                            value={formData.session_timeout_minutes}
                            onChange={(e) => handleChange('session_timeout_minutes', parseInt(e.target.value))}
                        >
                            <option value="15">15 minutes</option>
                            <option value="30">30 minutes</option>
                            <option value="60">1 hour</option>
                            <option value="120">2 hours</option>
                        </select>
                        <p className="dp-setting-desc">Automatically disconnect after inactivity</p>
                    </div>
                </div>
            </div>

            <div className="dp-settings-footer">
                <button className="dp-btn dp-btn-text" onClick={handleReset}>
                    Reset to Defaults
                </button>
                <div className="dp-footer-actions">
                    {onClose && (
                        <button className="dp-btn dp-btn-secondary" onClick={onClose}>
                            Cancel
                        </button>
                    )}
                    <button
                        className="dp-btn dp-btn-primary"
                        onClick={handleSave}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : 'Save Settings'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DarkProtocolSettings;

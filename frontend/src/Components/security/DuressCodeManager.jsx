/**
 * DuressCodeManager.jsx
 * 
 * Component for managing existing duress codes.
 * Allows viewing, editing, deleting codes and viewing activation history.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as duressService from '../../services/duressCodeService';
import './DuressCodeManager.css';

const DuressCodeManager = ({ onSetupClick }) => {
    const { getAccessToken } = useAuth();
    const authToken = getAccessToken();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Data state
    const [config, setConfig] = useState(null);
    const [codes, setCodes] = useState([]);
    const [events, setEvents] = useState([]);
    const [selectedCode, setSelectedCode] = useState(null);

    // Modal state
    const [showEditModal, setShowEditModal] = useState(false);
    const [showEventModal, setShowEventModal] = useState(false);
    const [editingCode, setEditingCode] = useState(null);

    // Load data
    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            const [configData, codesData, eventsData] = await Promise.all([
                duressService.getConfig(authToken),
                duressService.getCodes(authToken),
                duressService.getEvents(authToken, { limit: 10 })
            ]);

            setConfig(configData.config || {});
            setCodes(codesData.codes || []);
            setEvents(eventsData.events || []);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Toggle duress protection
    const toggleProtection = async () => {
        try {
            setLoading(true);
            const result = await duressService.updateConfig(authToken, {
                is_enabled: !config.is_enabled
            });
            setConfig(result.config);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Delete a duress code
    const handleDeleteCode = async (codeId) => {
        if (!window.confirm('Are you sure you want to delete this duress code?')) {
            return;
        }

        try {
            setLoading(true);
            await duressService.deleteCode(authToken, codeId);
            setCodes(codes.filter(c => c.id !== codeId));
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Open edit modal
    const openEditModal = (code) => {
        setEditingCode({
            id: code.id,
            threatLevel: code.threat_level,
            codeHint: code.code_hint || '',
            newCode: ''
        });
        setShowEditModal(true);
    };

    // Save edited code
    const saveEditedCode = async () => {
        try {
            setLoading(true);
            await duressService.updateCode(authToken, editingCode.id, {
                code: editingCode.newCode || null,
                threatLevel: editingCode.threatLevel,
                codeHint: editingCode.codeHint
            });
            await loadData();
            setShowEditModal(false);
            setEditingCode(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Format date
    const formatDate = (dateString) => {
        if (!dateString) return 'Never';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (loading && !config) {
        return (
            <div className="duress-manager-loading">
                <div className="spinner" />
                <span>Loading duress protection...</span>
            </div>
        );
    }

    // If duress not yet configured
    if (!config?.is_enabled && codes.length === 0) {
        return (
            <div className="duress-manager-empty">
                <span className="empty-icon">🎖️</span>
                <h2>Duress Protection Not Configured</h2>
                <p>
                    Set up military-grade duress codes to protect yourself
                    in coerced access scenarios.
                </p>
                <button className="setup-btn" onClick={onSetupClick}>
                    Configure Duress Protection →
                </button>
            </div>
        );
    }

    return (
        <div className="duress-manager">
            {/* Header */}
            <div className="manager-header">
                <div className="header-info">
                    <h2>🎖️ Duress Protection</h2>
                    <p className="protection-status">
                        Status:
                        <span className={`status-badge ${config?.is_enabled ? 'active' : 'inactive'}`}>
                            {config?.is_enabled ? '🛡️ Active' : '⚪ Disabled'}
                        </span>
                    </p>
                </div>

                <div className="header-actions">
                    <button
                        className={`toggle-btn ${config?.is_enabled ? 'active' : ''}`}
                        onClick={toggleProtection}
                        disabled={loading}
                    >
                        {config?.is_enabled ? 'Disable' : 'Enable'} Protection
                    </button>
                    <button className="settings-btn" onClick={onSetupClick}>
                        ⚙️ Settings
                    </button>
                </div>
            </div>

            {/* Error Display */}
            {error && (
                <div className="manager-error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Stats Grid */}
            <div className="stats-grid">
                <div className="stat-card">
                    <span className="stat-icon">🔐</span>
                    <div className="stat-content">
                        <span className="stat-value">{codes.length}</span>
                        <span className="stat-label">Active Codes</span>
                    </div>
                </div>

                <div className="stat-card">
                    <span className="stat-icon">🚨</span>
                    <div className="stat-content">
                        <span className="stat-value">{events.length}</span>
                        <span className="stat-label">Total Activations</span>
                    </div>
                </div>

                <div className="stat-card">
                    <span className="stat-icon">📞</span>
                    <div className="stat-content">
                        <span className="stat-value">
                            {config?.silent_alarm_enabled ? '✓' : '✗'}
                        </span>
                        <span className="stat-label">Silent Alarms</span>
                    </div>
                </div>

                <div className="stat-card">
                    <span className="stat-icon">📦</span>
                    <div className="stat-content">
                        <span className="stat-value">
                            {config?.evidence_preservation_enabled ? '✓' : '✗'}
                        </span>
                        <span className="stat-label">Evidence Capture</span>
                    </div>
                </div>
            </div>

            {/* Duress Codes Section */}
            <section className="codes-section">
                <div className="section-header">
                    <h3>Duress Codes</h3>
                    <button className="add-btn" onClick={onSetupClick}>
                        + Add Code
                    </button>
                </div>

                <div className="codes-list">
                    {codes.map(code => {
                        const levelInfo = duressService.formatThreatLevel(code.threat_level);
                        return (
                            <div key={code.id} className="code-card">
                                <div className="code-header">
                                    <span
                                        className="threat-indicator"
                                        style={{ backgroundColor: levelInfo.color }}
                                    />
                                    <span className="threat-level">{levelInfo.label} Threat</span>
                                    <span className="code-menu">
                                        <button
                                            className="menu-btn"
                                            onClick={() => openEditModal(code)}
                                        >
                                            ✏️
                                        </button>
                                        <button
                                            className="menu-btn delete"
                                            onClick={() => handleDeleteCode(code.id)}
                                        >
                                            🗑️
                                        </button>
                                    </span>
                                </div>

                                <div className="code-body">
                                    <div className="code-info-row">
                                        <span className="info-label">Hint:</span>
                                        <span className="info-value">
                                            {code.code_hint || 'No hint set'}
                                        </span>
                                    </div>
                                    <div className="code-info-row">
                                        <span className="info-label">Activations:</span>
                                        <span className="info-value">
                                            {code.activation_count || 0}
                                        </span>
                                    </div>
                                    <div className="code-info-row">
                                        <span className="info-label">Created:</span>
                                        <span className="info-value">
                                            {formatDate(code.created_at)}
                                        </span>
                                    </div>
                                </div>

                                <div className="code-actions">
                                    <span className="action-description">
                                        {levelInfo.description}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Recent Events Section */}
            {events.length > 0 && (
                <section className="events-section">
                    <div className="section-header">
                        <h3>Recent Activations</h3>
                        <button
                            className="view-all-btn"
                            onClick={() => setShowEventModal(true)}
                        >
                            View All →
                        </button>
                    </div>

                    <div className="events-list">
                        {events.slice(0, 5).map(event => {
                            const levelInfo = duressService.formatThreatLevel(event.threat_level);
                            return (
                                <div key={event.id} className="event-item">
                                    <span
                                        className="event-indicator"
                                        style={{ backgroundColor: levelInfo.color }}
                                    />
                                    <div className="event-info">
                                        <span className="event-type">
                                            {event.event_type === 'test' ? '🧪 Test' : '🚨 Activation'}
                                        </span>
                                        <span className="event-level">
                                            {levelInfo.label} Threat
                                        </span>
                                    </div>
                                    <div className="event-meta">
                                        <span className="event-ip">{event.ip_address}</span>
                                        <span className="event-time">{formatDate(event.timestamp)}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            {/* Edit Modal */}
            {showEditModal && editingCode && (
                <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Edit Duress Code</h3>
                            <button className="close-btn" onClick={() => setShowEditModal(false)}>
                                ×
                            </button>
                        </div>

                        <div className="modal-body">
                            <div className="form-group">
                                <label>New Code (leave empty to keep current)</label>
                                <input
                                    type="password"
                                    placeholder="Enter new code"
                                    value={editingCode.newCode}
                                    onChange={(e) => setEditingCode({
                                        ...editingCode,
                                        newCode: e.target.value
                                    })}
                                />
                            </div>

                            <div className="form-group">
                                <label>Threat Level</label>
                                <select
                                    value={editingCode.threatLevel}
                                    onChange={(e) => setEditingCode({
                                        ...editingCode,
                                        threatLevel: e.target.value
                                    })}
                                >
                                    <option value="low">🟢 Low</option>
                                    <option value="medium">🟡 Medium</option>
                                    <option value="high">🟠 High</option>
                                    <option value="critical">🔴 Critical</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Code Hint</label>
                                <input
                                    type="text"
                                    placeholder="Optional hint"
                                    value={editingCode.codeHint}
                                    onChange={(e) => setEditingCode({
                                        ...editingCode,
                                        codeHint: e.target.value
                                    })}
                                />
                            </div>
                        </div>

                        <div className="modal-footer">
                            <button
                                className="cancel-btn"
                                onClick={() => setShowEditModal(false)}
                            >
                                Cancel
                            </button>
                            <button
                                className="save-btn"
                                onClick={saveEditedCode}
                                disabled={loading}
                            >
                                {loading ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DuressCodeManager;

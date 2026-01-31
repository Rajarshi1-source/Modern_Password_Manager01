/**
 * Honeypot Dashboard Component
 * 
 * Main dashboard for managing honeypot email addresses for breach detection.
 * Displays active honeypots, breach alerts, and quick actions.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    FiMail,
    FiAlertTriangle,
    FiShield,
    FiActivity,
    FiPlus,
    FiRefreshCw,
    FiSettings,
    FiTrash2,
    FiCheck,
    FiClock,
    FiEye
} from 'react-icons/fi';
import honeypotService from '../../services/honeypotService';
import HoneypotCreator from './HoneypotCreator';
import BreachTimeline from './BreachTimeline';
import './HoneypotDashboard.css';

const HoneypotDashboard = () => {
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState(null);
    const [activeTab, setActiveTab] = useState('honeypots');
    const [showCreator, setShowCreator] = useState(false);
    const [selectedBreach, setSelectedBreach] = useState(null);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);

    const loadDashboard = useCallback(async () => {
        try {
            setError(null);
            const data = await honeypotService.getDashboardStats();
            setStats(data);
        } catch (err) {
            setError('Failed to load honeypot dashboard');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadDashboard();
    }, [loadDashboard]);

    const handleRefresh = async () => {
        setRefreshing(true);
        try {
            await honeypotService.checkAllHoneypots();
            await loadDashboard();
        } catch (err) {
            setError('Failed to refresh honeypots');
        } finally {
            setRefreshing(false);
        }
    };

    const handleDeleteHoneypot = async (honeypotId) => {
        if (!window.confirm('Are you sure you want to delete this honeypot?')) return;

        try {
            await honeypotService.deleteHoneypot(honeypotId);
            await loadDashboard();
        } catch (err) {
            setError('Failed to delete honeypot');
        }
    };

    const handleAcknowledgeBreach = async (breachId) => {
        try {
            await honeypotService.updateBreach(breachId, { acknowledge: true });
            await loadDashboard();
        } catch (err) {
            setError('Failed to acknowledge breach');
        }
    };

    const handleRotateCredentials = async (breachId) => {
        try {
            await honeypotService.initiateRotation(breachId);
            await loadDashboard();
        } catch (err) {
            setError('Failed to initiate rotation');
        }
    };

    const getStatusBadge = (status) => {
        const badges = {
            active: { color: 'green', label: 'Active' },
            triggered: { color: 'orange', label: 'Triggered' },
            breached: { color: 'red', label: 'Breached' },
            disabled: { color: 'gray', label: 'Disabled' },
            expired: { color: 'gray', label: 'Expired' }
        };
        const badge = badges[status] || badges.active;
        return <span className={`status-badge status-${badge.color}`}>{badge.label}</span>;
    };

    const getSeverityIcon = (severity) => {
        const icons = {
            critical: '🔴',
            high: '🟠',
            medium: '🟡',
            low: '🟢'
        };
        return icons[severity] || '⚪';
    };

    if (loading) {
        return (
            <div className="honeypot-dashboard loading">
                <div className="loading-spinner">
                    <FiRefreshCw className="spin" size={32} />
                    <p>Loading Honeypot Dashboard...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="honeypot-dashboard">
            {/* Header */}
            <header className="dashboard-header">
                <div className="header-left">
                    <FiMail size={28} className="header-icon" />
                    <div>
                        <h1>Honeypot Email Protection</h1>
                        <p>Detect data breaches before they're public</p>
                    </div>
                </div>
                <div className="header-actions">
                    <button
                        className="btn btn-secondary"
                        onClick={handleRefresh}
                        disabled={refreshing}
                    >
                        <FiRefreshCw className={refreshing ? 'spin' : ''} />
                        {refreshing ? 'Checking...' : 'Check All'}
                    </button>
                    <button
                        className="btn btn-primary"
                        onClick={() => setShowCreator(true)}
                    >
                        <FiPlus />
                        Add Honeypot
                    </button>
                </div>
            </header>

            {/* Stats Cards */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon green">
                        <FiShield size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{stats?.activeHoneypots || 0}</span>
                        <span className="stat-label">Active Honeypots</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon orange">
                        <FiActivity size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{stats?.triggeredHoneypots || 0}</span>
                        <span className="stat-label">Triggered</span>
                    </div>
                </div>

                <div className="stat-card warning">
                    <div className="stat-icon red">
                        <FiAlertTriangle size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{stats?.unresolvedBreaches || 0}</span>
                        <span className="stat-label">Unresolved Breaches</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon blue">
                        <FiMail size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{stats?.totalHoneypots || 0}/{stats?.config?.max_honeypots || 50}</span>
                        <span className="stat-label">Total Honeypots</span>
                    </div>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="error-banner">
                    <FiAlertTriangle />
                    <span>{error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Tabs */}
            <div className="tab-container">
                <div className="tabs">
                    <button
                        className={`tab ${activeTab === 'honeypots' ? 'active' : ''}`}
                        onClick={() => setActiveTab('honeypots')}
                    >
                        <FiMail /> Honeypots ({stats?.totalHoneypots || 0})
                    </button>
                    <button
                        className={`tab ${activeTab === 'breaches' ? 'active' : ''}`}
                        onClick={() => setActiveTab('breaches')}
                    >
                        <FiAlertTriangle /> Breaches ({stats?.unresolvedBreaches || 0})
                    </button>
                    <button
                        className={`tab ${activeTab === 'settings' ? 'active' : ''}`}
                        onClick={() => setActiveTab('settings')}
                    >
                        <FiSettings /> Settings
                    </button>
                </div>

                {/* Honeypots Tab */}
                {activeTab === 'honeypots' && (
                    <div className="tab-content">
                        {stats?.honeypots?.length === 0 ? (
                            <div className="empty-state">
                                <FiMail size={48} />
                                <h3>No Honeypots Yet</h3>
                                <p>Create honeypot emails to protect your accounts and detect breaches early.</p>
                                <button
                                    className="btn btn-primary"
                                    onClick={() => setShowCreator(true)}
                                >
                                    <FiPlus /> Create First Honeypot
                                </button>
                            </div>
                        ) : (
                            <div className="honeypot-list">
                                {stats.honeypots.map(honeypot => (
                                    <div
                                        key={honeypot.id}
                                        className={`honeypot-card ${honeypot.breach_detected ? 'breached' : ''}`}
                                    >
                                        <div className="honeypot-header">
                                            <h3>{honeypot.service_name}</h3>
                                            {getStatusBadge(honeypot.status)}
                                        </div>
                                        <div className="honeypot-details">
                                            <p className="honeypot-email">
                                                <FiMail size={14} />
                                                {honeypot.honeypot_address}
                                            </p>
                                            <div className="honeypot-meta">
                                                <span>
                                                    <FiClock size={12} />
                                                    {honeypot.days_active} days active
                                                </span>
                                                {honeypot.total_emails_received > 0 && (
                                                    <span className="activity-count">
                                                        📧 {honeypot.total_emails_received} emails
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        {honeypot.breach_detected && (
                                            <div className="breach-warning">
                                                <FiAlertTriangle />
                                                <span>Breach detected! Confidence: {(honeypot.breach_confidence * 100).toFixed(0)}%</span>
                                            </div>
                                        )}
                                        <div className="honeypot-actions">
                                            <button
                                                className="btn btn-sm btn-ghost"
                                                title="View details"
                                            >
                                                <FiEye />
                                            </button>
                                            <button
                                                className="btn btn-sm btn-ghost danger"
                                                onClick={() => handleDeleteHoneypot(honeypot.id)}
                                                title="Delete honeypot"
                                            >
                                                <FiTrash2 />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Breaches Tab */}
                {activeTab === 'breaches' && (
                    <div className="tab-content">
                        {stats?.breaches?.length === 0 ? (
                            <div className="empty-state success">
                                <FiShield size={48} />
                                <h3>No Breaches Detected</h3>
                                <p>Your honeypots are monitoring for suspicious activity. Stay protected!</p>
                            </div>
                        ) : (
                            <div className="breach-list">
                                {stats.breaches.map(breach => (
                                    <div
                                        key={breach.id}
                                        className={`breach-card severity-${breach.severity}`}
                                    >
                                        <div className="breach-header">
                                            <div className="breach-title">
                                                <span className="severity-icon">{getSeverityIcon(breach.severity)}</span>
                                                <h3>{breach.service_name}</h3>
                                            </div>
                                            <span className={`status-badge status-${breach.status}`}>
                                                {breach.status_display}
                                            </span>
                                        </div>
                                        <div className="breach-details">
                                            <p>
                                                <strong>Detected:</strong> {new Date(breach.detected_at).toLocaleDateString()}
                                            </p>
                                            <p>
                                                <strong>Confidence:</strong> {(breach.confidence_score * 100).toFixed(0)}%
                                            </p>
                                            {breach.days_before_public && (
                                                <p className="early-detection">
                                                    🎯 Detected {breach.days_before_public} days before public disclosure!
                                                </p>
                                            )}
                                        </div>
                                        <div className="breach-actions">
                                            <button
                                                className="btn btn-sm"
                                                onClick={() => setSelectedBreach(breach.id)}
                                            >
                                                <FiClock /> View Timeline
                                            </button>
                                            {!breach.user_acknowledged && (
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    onClick={() => handleAcknowledgeBreach(breach.id)}
                                                >
                                                    <FiCheck /> Acknowledge
                                                </button>
                                            )}
                                            {!breach.credentials_rotated && (
                                                <button
                                                    className="btn btn-sm btn-primary"
                                                    onClick={() => handleRotateCredentials(breach.id)}
                                                >
                                                    <FiRefreshCw /> Rotate Credentials
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Settings Tab */}
                {activeTab === 'settings' && (
                    <div className="tab-content">
                        <div className="settings-section">
                            <h3>Honeypot Configuration</h3>
                            <div className="settings-form">
                                <div className="setting-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={stats?.config?.is_enabled}
                                            onChange={async (e) => {
                                                await honeypotService.updateConfig({ is_enabled: e.target.checked });
                                                loadDashboard();
                                            }}
                                        />
                                        <span>Enable Honeypot Protection</span>
                                    </label>
                                </div>

                                <div className="setting-item">
                                    <label>Email Provider</label>
                                    <select
                                        value={stats?.config?.email_provider || 'simplelogin'}
                                        onChange={async (e) => {
                                            await honeypotService.updateConfig({ email_provider: e.target.value });
                                            loadDashboard();
                                        }}
                                    >
                                        <option value="simplelogin">SimpleLogin</option>
                                        <option value="anonaddy">AnonAddy</option>
                                        <option value="custom">Custom SMTP</option>
                                    </select>
                                </div>

                                <div className="setting-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={stats?.config?.auto_rotate_on_breach}
                                            onChange={async (e) => {
                                                await honeypotService.updateConfig({ auto_rotate_on_breach: e.target.checked });
                                                loadDashboard();
                                            }}
                                        />
                                        <span>Auto-rotate credentials on breach</span>
                                    </label>
                                    <small>When enabled, automatically initiate credential rotation when breach detected</small>
                                </div>

                                <div className="setting-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={stats?.config?.require_confirmation}
                                            onChange={async (e) => {
                                                await honeypotService.updateConfig({ require_confirmation: e.target.checked });
                                                loadDashboard();
                                            }}
                                        />
                                        <span>Require confirmation before rotation</span>
                                    </label>
                                </div>

                                <div className="setting-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={stats?.config?.suggest_honeypot_creation}
                                            onChange={async (e) => {
                                                await honeypotService.updateConfig({ suggest_honeypot_creation: e.target.checked });
                                                loadDashboard();
                                            }}
                                        />
                                        <span>Suggest honeypot creation when adding vault items</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Creator Modal */}
            {showCreator && (
                <HoneypotCreator
                    onClose={() => setShowCreator(false)}
                    onCreated={() => {
                        setShowCreator(false);
                        loadDashboard();
                    }}
                />
            )}

            {/* Breach Timeline Modal */}
            {selectedBreach && (
                <BreachTimeline
                    breachId={selectedBreach}
                    onClose={() => setSelectedBreach(null)}
                />
            )}
        </div>
    );
};

export default HoneypotDashboard;

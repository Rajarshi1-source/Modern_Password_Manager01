/**
 * Predictive Password Expiration Dashboard
 * ==========================================
 * 
 * Main dashboard component for the predictive expiration feature.
 * Shows risk overview, at-risk credentials, and active threats.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Shield,
    AlertTriangle,
    Clock,
    TrendingUp,
    RefreshCw,
    ChevronRight,
    Lock,
    Unlock,
    Eye,
    Settings,
    Activity,
    Target,
    Zap,
    AlertCircle,
    CheckCircle,
    XCircle
} from 'lucide-react';
import predictiveExpirationService from '../../services/predictiveExpirationService';
import './PredictiveExpirationDashboard.css';

// Risk level badge component
const RiskBadge = ({ level, score }) => {
    const getColor = () => {
        switch (level) {
            case 'critical': return 'badge-critical';
            case 'high': return 'badge-high';
            case 'medium': return 'badge-medium';
            case 'low': return 'badge-low';
            default: return 'badge-minimal';
        }
    };

    return (
        <span className={`risk-badge ${getColor()}`}>
            {level?.toUpperCase()} {score && `(${(score * 100).toFixed(0)}%)`}
        </span>
    );
};

// Credential risk card component
const CredentialRiskCard = ({ credential, onRotate, onAcknowledge, onView }) => {
    const getDaysUntil = (date) => {
        if (!date) return null;
        const now = new Date();
        const target = new Date(date);
        const diffTime = target - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
    };

    const daysUntil = getDaysUntil(credential.predicted_compromise_date);

    return (
        <div className={`credential-risk-card risk-${credential.risk_level}`}>
            <div className="credential-header">
                <Lock size={20} />
                <span className="credential-domain">{credential.credential_domain}</span>
                <RiskBadge level={credential.risk_level} score={credential.risk_score} />
            </div>

            <div className="credential-body">
                {daysUntil !== null && (
                    <div className="prediction-info">
                        <Clock size={14} />
                        <span>
                            {daysUntil > 0
                                ? `${daysUntil} days until predicted compromise`
                                : 'Compromise predicted - action required'}
                        </span>
                    </div>
                )}

                <div className="action-recommendation">
                    <AlertCircle size={14} />
                    <span>
                        {credential.recommended_action?.replace(/_/g, ' ') || 'Monitor'}
                    </span>
                </div>
            </div>

            <div className="credential-actions">
                <button
                    className="btn-view"
                    onClick={() => onView(credential.credential_id)}
                    title="View details"
                >
                    <Eye size={16} />
                </button>

                {!credential.user_acknowledged && (
                    <button
                        className="btn-acknowledge"
                        onClick={() => onAcknowledge(credential.credential_id)}
                        title="Acknowledge risk"
                    >
                        <CheckCircle size={16} />
                    </button>
                )}

                {['rotate_immediately', 'rotate_soon'].includes(credential.recommended_action) && (
                    <button
                        className="btn-rotate"
                        onClick={() => onRotate(credential.credential_id)}
                        title="Rotate password"
                    >
                        <RefreshCw size={16} />
                        Rotate
                    </button>
                )}
            </div>
        </div>
    );
};

// Threat actor card component
const ThreatActorCard = ({ threat }) => {
    return (
        <div className={`threat-actor-card threat-${threat.threat_level}`}>
            <div className="threat-header">
                <Target size={20} />
                <span className="threat-name">{threat.name}</span>
                <RiskBadge level={threat.threat_level} />
            </div>

            <div className="threat-body">
                <span className="threat-type">{threat.actor_type}</span>
                {threat.is_currently_active && (
                    <span className="active-indicator">
                        <Activity size={12} />
                        Active
                    </span>
                )}
            </div>
        </div>
    );
};

// Main dashboard component
const PredictiveExpirationDashboard = () => {
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);
    const [dashboard, setDashboard] = useState(null);
    const [threatSummary, setThreatSummary] = useState(null);
    const [settings, setSettings] = useState(null);
    const [showSettings, setShowSettings] = useState(false);

    // Fetch dashboard data
    const fetchDashboard = useCallback(async () => {
        try {
            const [dashData, threatData, settingsData] = await Promise.all([
                predictiveExpirationService.getDashboard(),
                predictiveExpirationService.getThreatSummary(),
                predictiveExpirationService.getSettings()
            ]);

            setDashboard(dashData);
            setThreatSummary(threatData);
            setSettings(settingsData);
            setError(null);
        } catch (err) {
            console.error('Error fetching dashboard:', err);
            setError('Failed to load dashboard data');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchDashboard();
    }, [fetchDashboard]);

    const handleRefresh = () => {
        setRefreshing(true);
        fetchDashboard();
    };

    const handleRotate = async (credentialId) => {
        try {
            await predictiveExpirationService.forceRotation(credentialId, {
                reason: 'Manual rotation from dashboard'
            });
            fetchDashboard();
        } catch (err) {
            console.error('Error rotating credential:', err);
        }
    };

    const handleAcknowledge = async (credentialId) => {
        try {
            await predictiveExpirationService.acknowledgeRisk(credentialId);
            fetchDashboard();
        } catch (err) {
            console.error('Error acknowledging risk:', err);
        }
    };

    const handleView = (credentialId) => {
        // Navigate to credential detail view
        console.log('View credential:', credentialId);
    };

    const handleToggleFeature = async () => {
        if (!settings) return;

        try {
            const updated = await predictiveExpirationService.updateSettings({
                is_enabled: !settings.is_enabled
            });
            setSettings(updated);
        } catch (err) {
            console.error('Error updating settings:', err);
        }
    };

    if (loading) {
        return (
            <div className="predictive-dashboard loading">
                <div className="loading-spinner">
                    <Shield size={48} />
                    <p>Loading predictive analysis...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="predictive-dashboard error">
                <AlertTriangle size={48} />
                <h2>Error Loading Dashboard</h2>
                <p>{error}</p>
                <button onClick={fetchDashboard} className="btn-retry">
                    <RefreshCw size={16} />
                    Retry
                </button>
            </div>
        );
    }

    const getRiskColor = (score) => {
        if (score >= 0.8) return 'var(--risk-critical)';
        if (score >= 0.6) return 'var(--risk-high)';
        if (score >= 0.4) return 'var(--risk-medium)';
        if (score >= 0.2) return 'var(--risk-low)';
        return 'var(--risk-minimal)';
    };

    const getRiskLevel = (score) => {
        if (score >= 0.8) return 'Critical';
        if (score >= 0.6) return 'High';
        if (score >= 0.4) return 'Medium';
        if (score >= 0.2) return 'Low';
        return 'Minimal';
    };

    return (
        <div className="predictive-dashboard">
            {/* Header */}
            <header className="dashboard-header">
                <div className="header-title">
                    <Shield size={32} />
                    <div>
                        <h1>Predictive Password Expiration</h1>
                        <p>AI-powered threat intelligence and password rotation</p>
                    </div>
                </div>

                <div className="header-actions">
                    <button
                        className={`btn-toggle ${settings?.is_enabled ? 'enabled' : 'disabled'}`}
                        onClick={handleToggleFeature}
                    >
                        {settings?.is_enabled ? <Unlock size={16} /> : <Lock size={16} />}
                        {settings?.is_enabled ? 'Enabled' : 'Disabled'}
                    </button>

                    <button
                        className="btn-settings"
                        onClick={() => setShowSettings(!showSettings)}
                    >
                        <Settings size={20} />
                    </button>

                    <button
                        className={`btn-refresh ${refreshing ? 'spinning' : ''}`}
                        onClick={handleRefresh}
                        disabled={refreshing}
                    >
                        <RefreshCw size={20} />
                    </button>
                </div>
            </header>

            {/* Risk Overview */}
            <section className="risk-overview">
                <div className="overall-risk-score">
                    <div
                        className="risk-circle"
                        style={{
                            '--risk-color': getRiskColor(dashboard?.overall_risk_score || 0)
                        }}
                    >
                        <span className="risk-value">
                            {((dashboard?.overall_risk_score || 0) * 100).toFixed(0)}%
                        </span>
                        <span className="risk-label">
                            {getRiskLevel(dashboard?.overall_risk_score || 0)}
                        </span>
                    </div>
                    <h3>Overall Risk Score</h3>
                </div>

                <div className="risk-stats">
                    <div className="stat-card">
                        <div className="stat-icon critical">
                            <XCircle size={24} />
                        </div>
                        <div className="stat-content">
                            <span className="stat-value">{dashboard?.critical_count || 0}</span>
                            <span className="stat-label">Critical</span>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon high">
                            <AlertTriangle size={24} />
                        </div>
                        <div className="stat-content">
                            <span className="stat-value">{dashboard?.high_count || 0}</span>
                            <span className="stat-label">High Risk</span>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon medium">
                            <AlertCircle size={24} />
                        </div>
                        <div className="stat-content">
                            <span className="stat-value">{dashboard?.medium_count || 0}</span>
                            <span className="stat-label">Medium Risk</span>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon pending">
                            <Clock size={24} />
                        </div>
                        <div className="stat-content">
                            <span className="stat-value">{dashboard?.pending_rotations || 0}</span>
                            <span className="stat-label">Pending</span>
                        </div>
                    </div>
                </div>
            </section>

            {/* Main Content Grid */}
            <div className="dashboard-grid">
                {/* At-Risk Credentials */}
                <section className="credentials-section">
                    <div className="section-header">
                        <h2>
                            <Lock size={20} />
                            At-Risk Credentials
                        </h2>
                        <span className="count-badge">{dashboard?.at_risk_count || 0}</span>
                    </div>

                    <div className="credentials-list">
                        {dashboard?.credentials_at_risk?.length > 0 ? (
                            dashboard.credentials_at_risk.map((cred) => (
                                <CredentialRiskCard
                                    key={cred.credential_id}
                                    credential={cred}
                                    onRotate={handleRotate}
                                    onAcknowledge={handleAcknowledge}
                                    onView={handleView}
                                />
                            ))
                        ) : (
                            <div className="empty-state">
                                <CheckCircle size={48} />
                                <p>No credentials at risk!</p>
                            </div>
                        )}
                    </div>

                    {dashboard?.at_risk_count > 5 && (
                        <button className="btn-view-all">
                            View All Credentials
                            <ChevronRight size={16} />
                        </button>
                    )}
                </section>

                {/* Active Threats */}
                <section className="threats-section">
                    <div className="section-header">
                        <h2>
                            <Target size={20} />
                            Active Threats
                        </h2>
                        <span className="count-badge">
                            {threatSummary?.total_active_actors || 0}
                        </span>
                    </div>

                    <div className="threat-summary">
                        <div className="threat-stat">
                            <Zap size={16} />
                            <span>{threatSummary?.critical_threats || 0} Critical</span>
                        </div>
                        <div className="threat-stat">
                            <AlertTriangle size={16} />
                            <span>{threatSummary?.high_threats || 0} High</span>
                        </div>
                        <div className="threat-stat">
                            <Activity size={16} />
                            <span>{threatSummary?.ransomware_active || 0} Ransomware</span>
                        </div>
                        <div className="threat-stat">
                            <Target size={16} />
                            <span>{threatSummary?.apt_active || 0} APT</span>
                        </div>
                    </div>

                    <div className="threats-list">
                        {dashboard?.active_threats?.length > 0 ? (
                            dashboard.active_threats.map((threat) => (
                                <ThreatActorCard key={threat.actor_id} threat={threat} />
                            ))
                        ) : (
                            <div className="empty-state">
                                <Shield size={48} />
                                <p>No high-priority threats detected</p>
                            </div>
                        )}
                    </div>

                    <button className="btn-view-all">
                        View Threat Landscape
                        <ChevronRight size={16} />
                    </button>
                </section>

                {/* Industry Context */}
                {dashboard?.industry_threat && (
                    <section className="industry-section">
                        <div className="section-header">
                            <h2>
                                <TrendingUp size={20} />
                                Industry Threat Level
                            </h2>
                        </div>

                        <div className="industry-card">
                            <div className="industry-header">
                                <span className="industry-name">
                                    {dashboard.industry_threat.industry_name}
                                </span>
                                <RiskBadge level={dashboard.industry_threat.current_threat_level} />
                            </div>

                            <div className="industry-stats">
                                <div className="industry-stat">
                                    <span className="label">Active Campaigns</span>
                                    <span className="value">
                                        {dashboard.industry_threat.active_campaigns_count}
                                    </span>
                                </div>
                                <div className="industry-stat">
                                    <span className="label">Recent Breaches</span>
                                    <span className="value">
                                        {dashboard.industry_threat.recent_breaches_count}
                                    </span>
                                </div>
                                <div className="industry-stat">
                                    <span className="label">Threat Trend</span>
                                    <span className={`value trend-${dashboard.industry_threat.threat_trend}`}>
                                        {dashboard.industry_threat.threat_trend}
                                    </span>
                                </div>
                            </div>

                            {dashboard.industry_threat.advisory_message && (
                                <div className="advisory">
                                    <AlertCircle size={16} />
                                    <p>{dashboard.industry_threat.advisory_message}</p>
                                </div>
                            )}
                        </div>
                    </section>
                )}

                {/* Recent Rotations */}
                <section className="rotations-section">
                    <div className="section-header">
                        <h2>
                            <RefreshCw size={20} />
                            Recent Activity
                        </h2>
                    </div>

                    <div className="activity-summary">
                        <div className="activity-stat">
                            <span className="label">Rotations (30 days)</span>
                            <span className="value">{dashboard?.recent_rotations || 0}</span>
                        </div>
                        <div className="activity-stat">
                            <span className="label">Total Credentials</span>
                            <span className="value">{dashboard?.total_credentials || 0}</span>
                        </div>
                        <div className="activity-stat">
                            <span className="label">Last Scan</span>
                            <span className="value">
                                {dashboard?.last_scan_at
                                    ? new Date(dashboard.last_scan_at).toLocaleDateString()
                                    : 'Never'}
                            </span>
                        </div>
                    </div>

                    <button className="btn-view-all">
                        View Rotation History
                        <ChevronRight size={16} />
                    </button>
                </section>
            </div>

            {/* Settings Panel (Slide-out) */}
            {showSettings && (
                <div className="settings-overlay" onClick={() => setShowSettings(false)}>
                    <div className="settings-panel" onClick={e => e.stopPropagation()}>
                        <div className="settings-header">
                            <h2>Settings</h2>
                            <button onClick={() => setShowSettings(false)}>×</button>
                        </div>

                        <div className="settings-content">
                            <div className="setting-item">
                                <label>Auto Rotation</label>
                                <input
                                    type="checkbox"
                                    checked={settings?.auto_rotation_enabled || false}
                                    onChange={async (e) => {
                                        const updated = await predictiveExpirationService.updateSettings({
                                            auto_rotation_enabled: e.target.checked
                                        });
                                        setSettings(updated);
                                    }}
                                />
                            </div>

                            <div className="setting-item">
                                <label>Force Rotation Threshold</label>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={(settings?.force_rotation_threshold || 0.8) * 100}
                                    onChange={async (e) => {
                                        const updated = await predictiveExpirationService.updateSettings({
                                            force_rotation_threshold: e.target.value / 100
                                        });
                                        setSettings(updated);
                                    }}
                                />
                                <span>{((settings?.force_rotation_threshold || 0.8) * 100).toFixed(0)}%</span>
                            </div>

                            <div className="setting-item">
                                <label>Industry</label>
                                <select
                                    value={settings?.industry || ''}
                                    onChange={async (e) => {
                                        const updated = await predictiveExpirationService.updateSettings({
                                            industry: e.target.value
                                        });
                                        setSettings(updated);
                                    }}
                                >
                                    <option value="">Select Industry</option>
                                    <option value="finance">Finance & Banking</option>
                                    <option value="healthcare">Healthcare</option>
                                    <option value="technology">Technology</option>
                                    <option value="government">Government</option>
                                    <option value="retail">Retail</option>
                                    <option value="education">Education</option>
                                </select>
                            </div>

                            <div className="setting-item">
                                <label>High Risk Notifications</label>
                                <input
                                    type="checkbox"
                                    checked={settings?.notify_on_high_risk || false}
                                    onChange={async (e) => {
                                        const updated = await predictiveExpirationService.updateSettings({
                                            notify_on_high_risk: e.target.checked
                                        });
                                        setSettings(updated);
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PredictiveExpirationDashboard;

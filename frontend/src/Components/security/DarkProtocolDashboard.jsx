/**
 * Dark Protocol Dashboard
 * ========================
 * 
 * Main dashboard for managing anonymous vault access.
 * Shows connection status, network health, and session info.
 * 
 * @author Password Manager Team
 * @created 2026-02-02
 */

import React, { useState, useEffect, useCallback } from 'react';
import darkProtocolService from '../../services/darkProtocolService';
import './DarkProtocolDashboard.css';

const DarkProtocolDashboard = () => {
    // State
    const [config, setConfig] = useState(null);
    const [session, setSession] = useState(null);
    const [networkHealth, setNetworkHealth] = useState(null);
    const [stats, setStats] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [routes, setRoutes] = useState([]);
    const [connectionState, setConnectionState] = useState('disconnected');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showSettings, setShowSettings] = useState(false);

    // Load initial data
    useEffect(() => {
        loadData();

        // Subscribe to connection events
        const unsubscribe = darkProtocolService.addConnectionListener(handleConnectionEvent);

        return () => {
            unsubscribe();
        };
    }, []);

    const loadData = async () => {
        setLoading(true);
        setError(null);

        try {
            const [configData, sessionData, healthData, statsData, nodesData, routesData] = await Promise.all([
                darkProtocolService.getConfig(),
                darkProtocolService.getSession(),
                darkProtocolService.getNetworkHealth(),
                darkProtocolService.getStats(),
                darkProtocolService.getNodes(),
                darkProtocolService.getRoutes(),
            ]);

            setConfig(configData);
            setSession(sessionData);
            setNetworkHealth(healthData);
            setStats(statsData);
            setNodes(nodesData.nodes || []);
            setRoutes(routesData.paths || []);

            if (sessionData.has_active_session) {
                setConnectionState('connected');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleConnectionEvent = useCallback((event) => {
        switch (event.type) {
            case 'connected':
                setConnectionState('connected');
                break;
            case 'disconnected':
                setConnectionState('disconnected');
                break;
            case 'connecting':
                setConnectionState('connecting');
                break;
            case 'session_expired':
                setConnectionState('disconnected');
                setSession({ has_active_session: false });
                break;
            default:
                break;
        }
    }, []);

    const handleConnect = async () => {
        setLoading(true);
        setError(null);

        try {
            const newSession = await darkProtocolService.establishSession({
                hopCount: config?.min_hops || 3,
                preferredRegions: config?.preferred_regions || [],
            });

            setSession({ has_active_session: true, ...newSession });
            setConnectionState('connected');

            if (config?.cover_traffic_enabled) {
                darkProtocolService.startCoverTraffic(config.cover_traffic_intensity);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDisconnect = async () => {
        setLoading(true);

        try {
            await darkProtocolService.terminateSession();
            setSession({ has_active_session: false });
            setConnectionState('disconnected');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleToggleProtocol = async () => {
        try {
            const newConfig = await darkProtocolService.updateConfig({
                is_enabled: !config.is_enabled,
            });
            setConfig({ ...config, is_enabled: newConfig.is_enabled });
        } catch (err) {
            setError(err.message);
        }
    };

    const handleRotatePath = async () => {
        try {
            const newRoute = await darkProtocolService.requestNewRoute();
            setRoutes([newRoute, ...routes.filter(r => !r.is_primary)]);
        } catch (err) {
            setError(err.message);
        }
    };

    const formatBytes = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    if (loading && !config) {
        return (
            <div className="dark-protocol-dashboard">
                <div className="dp-loading">
                    <div className="dp-loading-spinner"></div>
                    <p>Initializing Dark Protocol...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dark-protocol-dashboard">
            {/* Header */}
            <div className="dp-header">
                <div className="dp-header-left">
                    <div className="dp-icon">🌑</div>
                    <div className="dp-title">
                        <h1>Dark Protocol Network</h1>
                        <p>Anonymous Vault Access</p>
                    </div>
                </div>
                <div className="dp-header-right">
                    <button
                        className="dp-settings-btn"
                        onClick={() => setShowSettings(!showSettings)}
                    >
                        ⚙️ Settings
                    </button>
                    <label className="dp-toggle">
                        <input
                            type="checkbox"
                            checked={config?.is_enabled || false}
                            onChange={handleToggleProtocol}
                        />
                        <span className="dp-toggle-slider"></span>
                    </label>
                </div>
            </div>

            {error && (
                <div className="dp-error">
                    <span>⚠️</span>
                    {error}
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Connection Status */}
            <div className="dp-connection-section">
                <div className={`dp-connection-status ${connectionState}`}>
                    <div className="dp-status-indicator"></div>
                    <div className="dp-status-text">
                        <h3>Connection Status</h3>
                        <span className="dp-status-value">
                            {connectionState === 'connected' ? 'Protected' :
                                connectionState === 'connecting' ? 'Connecting...' :
                                    'Not Connected'}
                        </span>
                    </div>
                </div>

                <div className="dp-connection-actions">
                    {connectionState === 'connected' ? (
                        <>
                            <button className="dp-btn dp-btn-secondary" onClick={handleRotatePath}>
                                🔄 Rotate Path
                            </button>
                            <button className="dp-btn dp-btn-danger" onClick={handleDisconnect}>
                                Disconnect
                            </button>
                        </>
                    ) : (
                        <button
                            className="dp-btn dp-btn-primary"
                            onClick={handleConnect}
                            disabled={loading || !config?.is_enabled}
                        >
                            {loading ? 'Connecting...' : 'Connect Anonymously'}
                        </button>
                    )}
                </div>
            </div>

            {/* Session Info */}
            {session?.has_active_session && (
                <div className="dp-session-card">
                    <h3>🔐 Active Session</h3>
                    <div className="dp-session-grid">
                        <div className="dp-session-item">
                            <label>Session ID</label>
                            <span>{session.session_id?.slice(0, 16)}...</span>
                        </div>
                        <div className="dp-session-item">
                            <label>Path Length</label>
                            <span>{session.path_length} hops</span>
                        </div>
                        <div className="dp-session-item">
                            <label>Data Sent</label>
                            <span>{formatBytes(session.bytes_sent || 0)}</span>
                        </div>
                        <div className="dp-session-item">
                            <label>Messages</label>
                            <span>{session.messages_sent || 0}</span>
                        </div>
                        <div className="dp-session-item">
                            <label>Expires</label>
                            <span>{new Date(session.expires_at).toLocaleTimeString()}</span>
                        </div>
                        <div className="dp-session-item">
                            <label>Verified</label>
                            <span>{session.is_verified ? '✅' : '⚠️'}</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Network Health */}
            <div className="dp-network-section">
                <div className="dp-network-card">
                    <h3>🌐 Network Health</h3>
                    <div className="dp-health-stats">
                        <div className="dp-health-item">
                            <div className="dp-health-value">{networkHealth?.active_nodes || 0}</div>
                            <div className="dp-health-label">Active Nodes</div>
                        </div>
                        <div className="dp-health-item">
                            <div className="dp-health-value">{networkHealth?.health_percentage?.toFixed(0) || 0}%</div>
                            <div className="dp-health-label">Network Health</div>
                        </div>
                        <div className="dp-health-item">
                            <div className="dp-health-value">{networkHealth?.average_latency_ms || 0}ms</div>
                            <div className="dp-health-label">Avg Latency</div>
                        </div>
                    </div>

                    {/* Node Distribution */}
                    <div className="dp-node-distribution">
                        <h4>Node Distribution</h4>
                        <div className="dp-distribution-bars">
                            {Object.entries(networkHealth?.node_distribution || {}).map(([type, count]) => (
                                <div key={type} className="dp-distribution-item">
                                    <span className="dp-dist-label">{type}</span>
                                    <div className="dp-dist-bar">
                                        <div
                                            className={`dp-dist-fill dp-dist-${type}`}
                                            style={{ width: `${Math.min(100, count * 10)}%` }}
                                        ></div>
                                    </div>
                                    <span className="dp-dist-count">{count}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Usage Stats */}
                <div className="dp-stats-card">
                    <h3>📊 Usage Statistics</h3>
                    <div className="dp-stats-grid">
                        <div className="dp-stat-item">
                            <div className="dp-stat-icon">🔗</div>
                            <div className="dp-stat-info">
                                <span className="dp-stat-value">{stats?.sessions?.total || 0}</span>
                                <span className="dp-stat-label">Total Sessions</span>
                            </div>
                        </div>
                        <div className="dp-stat-item">
                            <div className="dp-stat-icon">📨</div>
                            <div className="dp-stat-info">
                                <span className="dp-stat-value">{formatBytes(stats?.traffic?.bytes_sent || 0)}</span>
                                <span className="dp-stat-label">Data Sent</span>
                            </div>
                        </div>
                        <div className="dp-stat-item">
                            <div className="dp-stat-icon">📬</div>
                            <div className="dp-stat-info">
                                <span className="dp-stat-value">{stats?.traffic?.messages_sent || 0}</span>
                                <span className="dp-stat-label">Messages Sent</span>
                            </div>
                        </div>
                        <div className="dp-stat-item">
                            <div className="dp-stat-icon">🛤️</div>
                            <div className="dp-stat-info">
                                <span className="dp-stat-value">{stats?.paths?.currently_active || 0}</span>
                                <span className="dp-stat-label">Active Paths</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Active Routes */}
            {routes.length > 0 && (
                <div className="dp-routes-section">
                    <h3>🛤️ Active Routes</h3>
                    <div className="dp-routes-list">
                        {routes.map(route => (
                            <div key={route.path_id} className={`dp-route-item ${route.is_primary ? 'primary' : ''}`}>
                                <div className="dp-route-info">
                                    <span className="dp-route-id">{route.path_id.slice(0, 8)}...</span>
                                    <span className="dp-route-hops">{route.hop_count} hops</span>
                                    <span className="dp-route-latency">{route.estimated_latency_ms}ms</span>
                                </div>
                                <div className="dp-route-meta">
                                    <span className="dp-route-uses">{route.times_used} uses</span>
                                    {route.is_primary && <span className="dp-route-badge">Primary</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Settings Panel */}
            {showSettings && (
                <DarkProtocolSettings
                    config={config}
                    onUpdate={(newConfig) => setConfig(newConfig)}
                    onClose={() => setShowSettings(false)}
                />
            )}
        </div>
    );
};

/**
 * Settings Panel Component
 */
const DarkProtocolSettings = ({ config, onUpdate, onClose }) => {
    const [formData, setFormData] = useState({
        min_hops: config?.min_hops || 3,
        max_hops: config?.max_hops || 5,
        cover_traffic_enabled: config?.cover_traffic_enabled || true,
        cover_traffic_intensity: config?.cover_traffic_intensity || 0.5,
        auto_path_rotation: config?.auto_path_rotation || true,
        path_rotation_interval_minutes: config?.path_rotation_interval_minutes || 5,
        use_bridge_nodes: config?.use_bridge_nodes || false,
        require_verified_nodes: config?.require_verified_nodes || true,
    });
    const [saving, setSaving] = useState(false);

    const handleChange = (field, value) => {
        setFormData({ ...formData, [field]: value });
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const newConfig = await darkProtocolService.updateConfig(formData);
            onUpdate({ ...config, ...newConfig });
            onClose();
        } catch (err) {
            console.error('Failed to save settings:', err);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="dp-settings-overlay">
            <div className="dp-settings-panel">
                <div className="dp-settings-header">
                    <h2>⚙️ Dark Protocol Settings</h2>
                    <button className="dp-close-btn" onClick={onClose}>×</button>
                </div>

                <div className="dp-settings-content">
                    <div className="dp-setting-group">
                        <h4>Anonymity Level</h4>

                        <div className="dp-setting-row">
                            <label>Minimum Hops</label>
                            <input
                                type="range"
                                min="2"
                                max="7"
                                value={formData.min_hops}
                                onChange={(e) => handleChange('min_hops', parseInt(e.target.value))}
                            />
                            <span>{formData.min_hops}</span>
                        </div>

                        <div className="dp-setting-row">
                            <label>Maximum Hops</label>
                            <input
                                type="range"
                                min="2"
                                max="7"
                                value={formData.max_hops}
                                onChange={(e) => handleChange('max_hops', parseInt(e.target.value))}
                            />
                            <span>{formData.max_hops}</span>
                        </div>

                        <div className="dp-setting-row checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.require_verified_nodes}
                                    onChange={(e) => handleChange('require_verified_nodes', e.target.checked)}
                                />
                                Require Verified Nodes
                            </label>
                        </div>
                    </div>

                    <div className="dp-setting-group">
                        <h4>Cover Traffic</h4>

                        <div className="dp-setting-row checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.cover_traffic_enabled}
                                    onChange={(e) => handleChange('cover_traffic_enabled', e.target.checked)}
                                />
                                Enable Cover Traffic
                            </label>
                        </div>

                        <div className="dp-setting-row">
                            <label>Traffic Intensity</label>
                            <input
                                type="range"
                                min="0.1"
                                max="1"
                                step="0.1"
                                value={formData.cover_traffic_intensity}
                                onChange={(e) => handleChange('cover_traffic_intensity', parseFloat(e.target.value))}
                            />
                            <span>{(formData.cover_traffic_intensity * 100).toFixed(0)}%</span>
                        </div>
                    </div>

                    <div className="dp-setting-group">
                        <h4>Path Rotation</h4>

                        <div className="dp-setting-row checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.auto_path_rotation}
                                    onChange={(e) => handleChange('auto_path_rotation', e.target.checked)}
                                />
                                Automatic Path Rotation
                            </label>
                        </div>

                        <div className="dp-setting-row">
                            <label>Rotation Interval</label>
                            <select
                                value={formData.path_rotation_interval_minutes}
                                onChange={(e) => handleChange('path_rotation_interval_minutes', parseInt(e.target.value))}
                            >
                                <option value="1">1 minute</option>
                                <option value="5">5 minutes</option>
                                <option value="10">10 minutes</option>
                                <option value="15">15 minutes</option>
                                <option value="30">30 minutes</option>
                            </select>
                        </div>
                    </div>

                    <div className="dp-setting-group">
                        <h4>Censorship Resistance</h4>

                        <div className="dp-setting-row checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.use_bridge_nodes}
                                    onChange={(e) => handleChange('use_bridge_nodes', e.target.checked)}
                                />
                                Use Bridge Nodes (for censored regions)
                            </label>
                        </div>
                    </div>
                </div>

                <div className="dp-settings-footer">
                    <button className="dp-btn dp-btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="dp-btn dp-btn-primary" onClick={handleSave} disabled={saving}>
                        {saving ? 'Saving...' : 'Save Settings'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DarkProtocolDashboard;

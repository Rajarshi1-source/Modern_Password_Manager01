/**
 * Dark Protocol Dashboard
 * ========================
 *
 * Main dashboard for anonymous vault access over Tor.
 *
 * The dashboard leads with one question — is anonymity actually available
 * right now? — and takes the answer from the server's capability report,
 * which is verified against a running Tor daemon. Everything else on the page
 * (cover-traffic sessions, routes, counters) describes the obfuscation layer
 * and is labelled as such, so it can never be read as evidence of anonymity.
 *
 * A failed capability fetch renders as Unavailable, not as available.
 *
 * @author Password Manager Team
 * @created 2026-02-02
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import darkProtocolService from '../../services/darkProtocolService';
import './DarkProtocolDashboard.css';

// Reasons the server can give for anonymity being unavailable, rendered as
// something an operator or user can act on. An unrecognised reason falls
// through to its raw token rather than being hidden, so a new server-side
// reason is visible rather than silently reported as "unknown problem".
const UNAVAILABLE_REASONS = Object.assign(Object.create(null), {
    not_configured: 'No Tor transport is configured for this deployment.',
    stem_unavailable: 'The Tor control library is not installed on the server.',
    controller_unreachable: 'The Tor daemon is not reachable.',
    not_bootstrapped: 'Tor is still bootstrapping.',
    no_circuit: 'Tor has not established a circuit yet.',
    no_onion_address: 'No onion service address has been provisioned.',
    onion_not_published: 'The onion service descriptor is not published.',
    probe_failed: 'The Tor capability check failed.',
});

// How often the capability report is re-read while the dashboard is open. The
// server caches its Tor probe for ~15s, so polling faster than this would only
// re-read the same cached answer.
const CAPABILITY_REFRESH_MS = 30000;

const DarkProtocolDashboard = () => {
    // State
    const [config, setConfig] = useState(null);
    const [capabilities, setCapabilities] = useState(null);
    const [session, setSession] = useState(null);
    const [networkHealth, setNetworkHealth] = useState(null);
    const [stats, setStats] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [routes, setRoutes] = useState([]);
    const [connectionState, setConnectionState] = useState('disconnected');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showSettings, setShowSettings] = useState(false);

    // Capability fetches overlap: the 30s timer, the initial load, and the
    // post-connect/disconnect refresh can all be in flight at once. Without a
    // token the last response to ARRIVE wins, so a slow older "available" reply
    // landing after a newer "unavailable" one would put the green banner back —
    // reintroducing exactly the stale anonymity claim the refresh was added to
    // prevent. Every write is stamped and only the newest is applied.
    const capabilityGenerationRef = useRef(0);

    // Re-read only the capability report. Deliberately separate from loadData()
    // so it can run on a timer without the loading spinner or clearing errors,
    // and so a failure here cannot leave the banner asserting stale anonymity.
    const refreshCapabilities = useCallback(async () => {
        const generation = ++capabilityGenerationRef.current;
        try {
            const data = await darkProtocolService.getCapabilities();
            if (generation === capabilityGenerationRef.current) {
                setCapabilities(data);
            }
        } catch {
            // Fail closed: an unreadable capability report is not evidence that
            // anonymity is available, so drop to the Unavailable state.
            if (generation === capabilityGenerationRef.current) {
                setCapabilities(null);
            }
        }
    }, []);

    // Load initial data
    useEffect(() => {
        loadData();

        // Subscribe to connection events
        const unsubscribe = darkProtocolService.addConnectionListener(handleConnectionEvent);

        // Re-check the capability while the dashboard is open. Without this the
        // banner is decided by the initial fetch alone, so a Tor daemon that
        // later loses its bootstrap, circuit or descriptor would leave the page
        // claiming anonymity is available until a full reload — the "middle
        // state" this feature exists to eliminate.
        const capabilityTimer = setInterval(refreshCapabilities, CAPABILITY_REFRESH_MS);

        return () => {
            unsubscribe();
            clearInterval(capabilityTimer);
        };
    }, [refreshCapabilities]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        const generation = ++capabilityGenerationRef.current;

        try {
            const [capabilityData, configData, sessionData, healthData, statsData, nodesData, routesData] = await Promise.all([
                // Fails closed: a rejected capability fetch leaves `capabilities`
                // null, which every consumer below reads as "not available".
                darkProtocolService.getCapabilities().catch(() => null),
                darkProtocolService.getConfig(),
                darkProtocolService.getSession(),
                darkProtocolService.getNetworkHealth(),
                darkProtocolService.getStats(),
                darkProtocolService.getNodes(),
                darkProtocolService.getRoutes(),
            ]);

            if (generation === capabilityGenerationRef.current) {
                setCapabilities(capabilityData);
            }
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

            // Connection actions can change what the server reports, so do not
            // wait for the next poll to find out.
            await refreshCapabilities();
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
            await refreshCapabilities();
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

    // Anonymity is a server-verified fact, never an inference from local
    // state. Absent capabilities => unavailable.
    const anonymity = capabilities?.anonymity || null;
    const anonymityAvailable = anonymity?.available === true;
    const connectionIsAnonymous = anonymity?.current_connection_is_anonymous === true;
    const unavailableReason = anonymity?.reason
        ? (UNAVAILABLE_REASONS[anonymity.reason] || anonymity.reason)
        : 'The capability report could not be loaded.';

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
                        <p>Vault access over the Tor network as a v3 onion service</p>
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

            {/* Anonymity status — the headline claim, and the only one on this
                page that describes anonymity. Everything below it describes the
                obfuscation layer. */}
            <div className={`dp-anonymity-banner ${anonymityAvailable ? 'available' : 'unavailable'}`}>
                <div className="dp-anonymity-header">
                    <span className="dp-anonymity-icon">{anonymityAvailable ? '🧅' : '⛔'}</span>
                    <h3>
                        {anonymityAvailable
                            ? 'Anonymous access available'
                            : 'Anonymous access unavailable'}
                    </h3>
                </div>

                {anonymityAvailable ? (
                    <div className="dp-anonymity-body">
                        <p>
                            This deployment is published as a Tor v3 onion service. Reaching it
                            over the address below keeps the connection inside the Tor network —
                            there is no exit node, and this server does not learn your IP address.
                        </p>
                        {anonymity?.onion_address && (
                            <div className="dp-onion-address">
                                <label>Onion address</label>
                                <code>{anonymity.onion_address}</code>
                            </div>
                        )}
                        <p className={`dp-current-connection ${connectionIsAnonymous ? 'anonymous' : 'clearnet'}`}>
                            {connectionIsAnonymous
                                ? 'This connection arrived over the onion service, so vault access is anonymous.'
                                : 'This connection did not arrive over the onion service. Vault operations through Dark Protocol are refused until you connect via the onion address.'}
                        </p>
                    </div>
                ) : (
                    <div className="dp-anonymity-body">
                        <p>{unavailableReason}</p>
                        <p>
                            Cover traffic and padding remain available, but they are
                            traffic-analysis resistance only — not anonymity. No feature on this
                            page will hide your IP address until the Tor transport is active.
                        </p>
                    </div>
                )}
            </div>

            {/* Cover-traffic session status. Deliberately NOT labelled
                "Protected": a session here is padding, not anonymity. */}
            <div className="dp-connection-section">
                <div className={`dp-connection-status ${connectionState}`}>
                    <div className="dp-status-indicator"></div>
                    <div className="dp-status-text">
                        <h3>Cover-traffic session</h3>
                        <span className="dp-status-value">
                            {connectionState === 'connected' ? 'Active' :
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
                            {loading ? 'Connecting...' : 'Connect'}
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
                    <h3>🧅 Tor circuits</h3>
                    <div className="dp-health-stats">
                        <div className="dp-health-item">
                            <div className="dp-health-value">{networkHealth?.circuits?.built || 0}</div>
                            <div className="dp-health-label">Built Circuits</div>
                        </div>
                        <div className="dp-health-item">
                            <div className="dp-health-value">{networkHealth?.circuits?.relays || 0}</div>
                            <div className="dp-health-label">Relays</div>
                        </div>
                        <div className="dp-health-item">
                            <div className="dp-health-value">
                                {networkHealth?.tor?.bootstrap_progress ?? 0}%
                            </div>
                            <div className="dp-health-label">Tor Bootstrap</div>
                        </div>
                    </div>

                    {/* Real relays of the live circuits. Empty when Tor is down —
                        an empty list is the honest answer, and this panel says so
                        rather than rendering a placeholder topology. */}
                    <div className="dp-node-distribution">
                        <h4>Circuit relays</h4>
                        {nodes.length === 0 ? (
                            <p className="dp-empty-note">
                                No live circuit to report.
                            </p>
                        ) : (
                            <div className="dp-relay-list">
                                {nodes.map((relay, index) => (
                                    <div key={`${relay.circuit_id}-${index}`} className="dp-relay-item">
                                        <span className={`dp-relay-position dp-relay-${relay.position}`}>
                                            {relay.position}
                                        </span>
                                        <span className="dp-relay-nickname">{relay.nickname || 'unknown'}</span>
                                        <span className="dp-relay-fingerprint">{relay.fingerprint || ''}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                        {/* Stated explicitly because "no exit node" is a real
                            property of onion-service circuits, and the relay
                            positions above are what demonstrate it. */}
                        <p className="dp-empty-note">
                            Onion-service circuits end at a rendezvous point inside Tor — there is
                            no exit node.
                        </p>
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
                        <h4>Routing Hops</h4>

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
                        <h4>Bridge Nodes</h4>

                        <div className="dp-setting-row checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.use_bridge_nodes}
                                    onChange={(e) => handleChange('use_bridge_nodes', e.target.checked)}
                                />
                                Use Bridge Nodes (simulated demo)
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

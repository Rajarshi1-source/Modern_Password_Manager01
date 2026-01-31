/**
 * DuressEventLog.jsx
 * 
 * Component for viewing duress event history and evidence packages.
 * Provides filtering, details view, and evidence export capabilities.
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as duressService from '../../services/duressCodeService';
import './DuressEventLog.css';

const DuressEventLog = () => {
    const { getAccessToken } = useAuth();
    const authToken = getAccessToken();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [events, setEvents] = useState([]);

    // Filter state
    const [filters, setFilters] = useState({
        threatLevel: 'all',
        dateRange: '30',  // days
        eventType: 'all'
    });

    // Detail view state
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [evidencePackage, setEvidencePackage] = useState(null);
    const [loadingEvidence, setLoadingEvidence] = useState(false);

    useEffect(() => {
        loadEvents();
    }, [filters]);

    const loadEvents = async () => {
        try {
            setLoading(true);
            const options = {
                limit: 50
            };

            if (filters.threatLevel !== 'all') {
                options.threatLevel = filters.threatLevel;
            }
            if (filters.dateRange !== 'all') {
                const startDate = new Date();
                startDate.setDate(startDate.getDate() - parseInt(filters.dateRange));
                options.startDate = startDate.toISOString();
            }

            const result = await duressService.getEvents(authToken, options);
            setEvents(result.events || []);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const viewEventDetails = async (event) => {
        setSelectedEvent(event);
        setEvidencePackage(null);

        if (event.evidence_package_id) {
            try {
                setLoadingEvidence(true);
                const result = await duressService.getEvidencePackage(authToken, event.evidence_package_id);
                setEvidencePackage(result.evidence);
            } catch (err) {
                console.error('Failed to load evidence package:', err);
            } finally {
                setLoadingEvidence(false);
            }
        }
    };

    const exportEvidence = async () => {
        if (!selectedEvent?.evidence_package_id) return;

        try {
            setLoadingEvidence(true);
            const result = await duressService.exportEvidencePackage(
                authToken,
                selectedEvent.evidence_package_id,
                'authenticated_user'  // This would come from current user
            );

            // In a real implementation, this would download the exported file
            console.log('Evidence exported:', result);
            alert('Evidence package exported successfully');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoadingEvidence(false);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    const formatTimeAgo = (dateString) => {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    };

    // Get filtered events based on event type
    const getFilteredEvents = () => {
        if (filters.eventType === 'all') return events;
        return events.filter(e => e.event_type === filters.eventType);
    };

    return (
        <div className="duress-event-log">
            {/* Header */}
            <div className="log-header">
                <div className="header-info">
                    <h2>🚨 Duress Event Log</h2>
                    <p>History of duress activations and collected evidence</p>
                </div>

                <button
                    className="refresh-btn"
                    onClick={loadEvents}
                    disabled={loading}
                >
                    🔄 Refresh
                </button>
            </div>

            {/* Error Display */}
            {error && (
                <div className="log-error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Filters */}
            <div className="log-filters">
                <div className="filter-group">
                    <label>Threat Level</label>
                    <select
                        value={filters.threatLevel}
                        onChange={(e) => setFilters({ ...filters, threatLevel: e.target.value })}
                    >
                        <option value="all">All Levels</option>
                        <option value="low">🟢 Low</option>
                        <option value="medium">🟡 Medium</option>
                        <option value="high">🟠 High</option>
                        <option value="critical">🔴 Critical</option>
                    </select>
                </div>

                <div className="filter-group">
                    <label>Time Range</label>
                    <select
                        value={filters.dateRange}
                        onChange={(e) => setFilters({ ...filters, dateRange: e.target.value })}
                    >
                        <option value="7">Last 7 days</option>
                        <option value="30">Last 30 days</option>
                        <option value="90">Last 90 days</option>
                        <option value="365">Last year</option>
                        <option value="all">All time</option>
                    </select>
                </div>

                <div className="filter-group">
                    <label>Event Type</label>
                    <select
                        value={filters.eventType}
                        onChange={(e) => setFilters({ ...filters, eventType: e.target.value })}
                    >
                        <option value="all">All Types</option>
                        <option value="activation">🚨 Real Activation</option>
                        <option value="test">🧪 Test</option>
                    </select>
                </div>
            </div>

            {/* Stats Summary */}
            <div className="log-stats">
                <div className="stat">
                    <span className="stat-value">{events.length}</span>
                    <span className="stat-label">Total Events</span>
                </div>
                <div className="stat">
                    <span className="stat-value">
                        {events.filter(e => e.event_type === 'activation').length}
                    </span>
                    <span className="stat-label">Real Activations</span>
                </div>
                <div className="stat">
                    <span className="stat-value">
                        {events.filter(e => e.evidence_package_id).length}
                    </span>
                    <span className="stat-label">With Evidence</span>
                </div>
                <div className="stat">
                    <span className="stat-value">
                        {events.filter(e => e.silent_alarm_sent).length}
                    </span>
                    <span className="stat-label">Alarms Sent</span>
                </div>
            </div>

            {/* Events Table */}
            <div className="events-container">
                {loading && events.length === 0 ? (
                    <div className="loading-state">
                        <div className="spinner" />
                        <span>Loading events...</span>
                    </div>
                ) : getFilteredEvents().length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">📋</span>
                        <h3>No Events Found</h3>
                        <p>No duress events match your current filters</p>
                    </div>
                ) : (
                    <table className="events-table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Threat</th>
                                <th>Time</th>
                                <th>IP Address</th>
                                <th>Evidence</th>
                                <th>Alarm</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {getFilteredEvents().map(event => {
                                const levelInfo = duressService.formatThreatLevel(event.threat_level);
                                return (
                                    <tr
                                        key={event.id}
                                        className={`event-row ${event.event_type}`}
                                        onClick={() => viewEventDetails(event)}
                                    >
                                        <td>
                                            <span className={`type-badge ${event.event_type}`}>
                                                {event.event_type === 'test' ? '🧪 Test' : '🚨 Alert'}
                                            </span>
                                        </td>
                                        <td>
                                            <span
                                                className="threat-badge"
                                                style={{ backgroundColor: levelInfo.color }}
                                            >
                                                {levelInfo.label}
                                            </span>
                                        </td>
                                        <td>
                                            <div className="time-cell">
                                                <span className="time-relative">
                                                    {formatTimeAgo(event.timestamp)}
                                                </span>
                                                <span className="time-full">
                                                    {formatDate(event.timestamp)}
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            <code className="ip-address">{event.ip_address}</code>
                                        </td>
                                        <td>
                                            {event.evidence_package_id ? (
                                                <span className="evidence-yes">📦 Available</span>
                                            ) : (
                                                <span className="evidence-no">—</span>
                                            )}
                                        </td>
                                        <td>
                                            {event.silent_alarm_sent ? (
                                                <span className="alarm-sent">✓ Sent</span>
                                            ) : (
                                                <span className="alarm-no">—</span>
                                            )}
                                        </td>
                                        <td>
                                            <button className="details-btn">
                                                Details →
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Event Detail Modal */}
            {selectedEvent && (
                <div className="modal-overlay" onClick={() => setSelectedEvent(null)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <div className="modal-title">
                                <span className={`type-icon ${selectedEvent.event_type}`}>
                                    {selectedEvent.event_type === 'test' ? '🧪' : '🚨'}
                                </span>
                                <h3>Event Details</h3>
                            </div>
                            <button
                                className="close-btn"
                                onClick={() => setSelectedEvent(null)}
                            >
                                ×
                            </button>
                        </div>

                        <div className="modal-body">
                            {/* Event Info */}
                            <section className="detail-section">
                                <h4>Event Information</h4>
                                <div className="detail-grid">
                                    <div className="detail-item">
                                        <span className="detail-label">Type</span>
                                        <span className={`detail-value type-${selectedEvent.event_type}`}>
                                            {selectedEvent.event_type === 'test' ? 'Test Activation' : 'Real Activation'}
                                        </span>
                                    </div>
                                    <div className="detail-item">
                                        <span className="detail-label">Threat Level</span>
                                        <span
                                            className="detail-value"
                                            style={{ color: duressService.formatThreatLevel(selectedEvent.threat_level).color }}
                                        >
                                            {duressService.formatThreatLevel(selectedEvent.threat_level).label}
                                        </span>
                                    </div>
                                    <div className="detail-item">
                                        <span className="detail-label">Timestamp</span>
                                        <span className="detail-value">
                                            {formatDate(selectedEvent.timestamp)}
                                        </span>
                                    </div>
                                    <div className="detail-item">
                                        <span className="detail-label">IP Address</span>
                                        <code className="detail-value">{selectedEvent.ip_address}</code>
                                    </div>
                                </div>
                            </section>

                            {/* Device Info */}
                            {selectedEvent.device_fingerprint && (
                                <section className="detail-section">
                                    <h4>Device Information</h4>
                                    <div className="detail-grid">
                                        <div className="detail-item">
                                            <span className="detail-label">Browser</span>
                                            <span className="detail-value">
                                                {selectedEvent.device_fingerprint.browser || 'Unknown'}
                                            </span>
                                        </div>
                                        <div className="detail-item">
                                            <span className="detail-label">OS</span>
                                            <span className="detail-value">
                                                {selectedEvent.device_fingerprint.os || 'Unknown'}
                                            </span>
                                        </div>
                                        <div className="detail-item">
                                            <span className="detail-label">Device Type</span>
                                            <span className="detail-value">
                                                {selectedEvent.device_fingerprint.device_type || 'Unknown'}
                                            </span>
                                        </div>
                                        <div className="detail-item">
                                            <span className="detail-label">Screen</span>
                                            <span className="detail-value">
                                                {selectedEvent.device_fingerprint.screen || 'Unknown'}
                                            </span>
                                        </div>
                                    </div>
                                </section>
                            )}

                            {/* Behavioral Data */}
                            {selectedEvent.behavioral_data && (
                                <section className="detail-section">
                                    <h4>Behavioral Indicators</h4>
                                    <div className="behavioral-indicators">
                                        <div className="indicator">
                                            <span className="indicator-label">Typing Speed</span>
                                            <div className="indicator-bar">
                                                <div
                                                    className="indicator-fill"
                                                    style={{
                                                        width: `${selectedEvent.behavioral_data.typing_speed_percentile || 50}%`
                                                    }}
                                                />
                                            </div>
                                            <span className="indicator-value">
                                                {selectedEvent.behavioral_data.typing_speed || 'Normal'}
                                            </span>
                                        </div>
                                        <div className="indicator">
                                            <span className="indicator-label">Stress Level</span>
                                            <div className="indicator-bar stress">
                                                <div
                                                    className="indicator-fill"
                                                    style={{
                                                        width: `${selectedEvent.behavioral_data.stress_score || 0}%`
                                                    }}
                                                />
                                            </div>
                                            <span className="indicator-value">
                                                {selectedEvent.behavioral_data.stress_level || 'Unknown'}
                                            </span>
                                        </div>
                                    </div>
                                </section>
                            )}

                            {/* Evidence Package */}
                            {selectedEvent.evidence_package_id && (
                                <section className="detail-section evidence-section">
                                    <h4>📦 Evidence Package</h4>

                                    {loadingEvidence ? (
                                        <div className="loading-evidence">
                                            <div className="spinner" />
                                            <span>Loading evidence...</span>
                                        </div>
                                    ) : evidencePackage ? (
                                        <>
                                            <div className="evidence-summary">
                                                <div className="evidence-item">
                                                    <span className="evidence-icon">🖼️</span>
                                                    <span>Screenshot captured</span>
                                                </div>
                                                <div className="evidence-item">
                                                    <span className="evidence-icon">📍</span>
                                                    <span>
                                                        Location: {evidencePackage.geo_location?.city || 'Unknown'}
                                                    </span>
                                                </div>
                                                <div className="evidence-item">
                                                    <span className="evidence-icon">🔒</span>
                                                    <span>Encrypted & timestamped</span>
                                                </div>
                                            </div>

                                            <button
                                                className="export-btn"
                                                onClick={exportEvidence}
                                                disabled={loadingEvidence}
                                            >
                                                📥 Export Evidence Package
                                            </button>
                                        </>
                                    ) : (
                                        <p className="no-evidence">
                                            Evidence package unavailable
                                        </p>
                                    )}
                                </section>
                            )}

                            {/* Alarm Status */}
                            <section className="detail-section">
                                <h4>Silent Alarm Status</h4>
                                {selectedEvent.silent_alarm_sent ? (
                                    <div className="alarm-status sent">
                                        <span className="status-icon">✅</span>
                                        <div className="status-info">
                                            <span className="status-text">Alarm Successfully Sent</span>
                                            <span className="status-meta">
                                                Notified at {formatDate(selectedEvent.alarm_sent_at || selectedEvent.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="alarm-status not-sent">
                                        <span className="status-icon">ℹ️</span>
                                        <div className="status-info">
                                            <span className="status-text">No Alarm Sent</span>
                                            <span className="status-meta">
                                                {selectedEvent.event_type === 'test'
                                                    ? 'Test mode - alarms disabled'
                                                    : 'Silent alarms not configured for this threat level'}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </section>
                        </div>

                        <div className="modal-footer">
                            <button
                                className="close-modal-btn"
                                onClick={() => setSelectedEvent(null)}
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DuressEventLog;

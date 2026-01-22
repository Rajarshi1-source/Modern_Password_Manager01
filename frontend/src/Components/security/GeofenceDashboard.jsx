/**
 * GeofenceDashboard Component
 * 
 * Main dashboard for geofencing and impossible travel detection features.
 * Integrates location capture, trusted zones, and travel event management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import GeolocationCapture from './GeolocationCapture';
import TrustedZonesManager from './TrustedZonesManager';
import ImpossibleTravelAlert from './ImpossibleTravelAlert';
import TravelItineraryManager from './TravelItineraryManager';
import * as geofenceService from '../../services/geofenceService';
import './GeofenceDashboard.css';

const GeofenceDashboard = ({ authToken }) => {
    const [activeTab, setActiveTab] = useState('overview');
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        zonesCount: 0,
        activeEvents: 0,
        lastLocation: null,
        upcomingTravel: 0
    });
    const [recentEvents, setRecentEvents] = useState([]);
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [error, setError] = useState(null);

    // Fetch dashboard data
    const fetchDashboardData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const [zonesData, eventsData, itinerariesData] = await Promise.all([
                geofenceService.getZones(authToken),
                geofenceService.getTravelEvents(authToken, { resolved: false, limit: 5 }),
                geofenceService.getItineraries(authToken, { upcoming: true })
            ]);

            setStats({
                zonesCount: zonesData.zones?.length || 0,
                activeEvents: eventsData.count || 0,
                lastLocation: eventsData.events?.[0]?.destination_location || null,
                upcomingTravel: itinerariesData.itineraries?.length || 0
            });

            setRecentEvents(eventsData.events || []);
        } catch (err) {
            console.error('Dashboard fetch error:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken]);

    useEffect(() => {
        fetchDashboardData();
    }, [fetchDashboardData]);

    // Handle location capture
    const handleLocationCaptured = (data) => {
        if (data.analysis && !data.analysis.is_plausible) {
            // Refresh events if suspicious travel detected
            fetchDashboardData();
        }
    };

    // Handle event resolution
    const handleEventResolved = () => {
        setSelectedEvent(null);
        fetchDashboardData();
    };

    const renderOverview = () => (
        <div className="geofence-overview">
            {/* Stats Cards */}
            <div className="stats-grid">
                <div className="stat-card zones">
                    <div className="stat-icon">🛡️</div>
                    <div className="stat-content">
                        <span className="stat-value">{stats.zonesCount}</span>
                        <span className="stat-label">Trusted Zones</span>
                    </div>
                </div>

                <div className={`stat-card events ${stats.activeEvents > 0 ? 'warning' : ''}`}>
                    <div className="stat-icon">⚠️</div>
                    <div className="stat-content">
                        <span className="stat-value">{stats.activeEvents}</span>
                        <span className="stat-label">Active Alerts</span>
                    </div>
                </div>

                <div className="stat-card travel">
                    <div className="stat-icon">✈️</div>
                    <div className="stat-content">
                        <span className="stat-value">{stats.upcomingTravel}</span>
                        <span className="stat-label">Upcoming Trips</span>
                    </div>
                </div>

                <div className="stat-card location">
                    <div className="stat-icon">📍</div>
                    <div className="stat-content">
                        <span className="stat-value">
                            {stats.lastLocation ? 'Active' : 'None'}
                        </span>
                        <span className="stat-label">Last Location</span>
                    </div>
                </div>
            </div>

            {/* Location Capture */}
            <div className="section-card">
                <h3>📍 Current Location</h3>
                <GeolocationCapture
                    authToken={authToken}
                    onLocationCaptured={handleLocationCaptured}
                    showStatus={true}
                    autoCapture={false}
                />
            </div>

            {/* Recent Alerts */}
            {recentEvents.length > 0 && (
                <div className="section-card alerts">
                    <h3>🚨 Recent Travel Alerts</h3>
                    <div className="alerts-list">
                        {recentEvents.map(event => (
                            <div
                                key={event.id}
                                className={`alert-item ${event.severity}`}
                                onClick={() => setSelectedEvent(event)}
                            >
                                <div className="alert-icon">
                                    {geofenceService.formatTravelMode(event.inferred_travel_mode).icon}
                                </div>
                                <div className="alert-content">
                                    <span className="alert-title">
                                        {event.inferred_travel_mode === 'supersonic'
                                            ? 'Impossible Travel Detected'
                                            : 'Unusual Travel Pattern'}
                                    </span>
                                    <span className="alert-meta">
                                        {event.distance_km?.toFixed(0)} km •
                                        {Math.round(event.required_speed_kmh)} km/h required
                                    </span>
                                </div>
                                <div
                                    className="alert-severity"
                                    style={{
                                        backgroundColor: geofenceService.formatSeverity(event.severity).color
                                    }}
                                >
                                    {geofenceService.formatSeverity(event.severity).label}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Quick Actions */}
            <div className="quick-actions">
                <button
                    className="action-btn primary"
                    onClick={() => setActiveTab('zones')}
                >
                    🏠 Manage Zones
                </button>
                <button
                    className="action-btn secondary"
                    onClick={() => setActiveTab('travel')}
                >
                    ✈️ Add Travel Plans
                </button>
            </div>
        </div>
    );

    if (loading) {
        return (
            <div className="geofence-dashboard loading">
                <div className="spinner"></div>
                <p>Loading geofence data...</p>
            </div>
        );
    }

    return (
        <div className="geofence-dashboard">
            {/* Header */}
            <div className="dashboard-header">
                <div className="header-content">
                    <h2>🌍 Geofencing & Travel Security</h2>
                    <p>Physics-based location security with impossible travel detection</p>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="tab-nav">
                <button
                    className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    Overview
                </button>
                <button
                    className={`tab-btn ${activeTab === 'zones' ? 'active' : ''}`}
                    onClick={() => setActiveTab('zones')}
                >
                    Trusted Zones
                </button>
                <button
                    className={`tab-btn ${activeTab === 'travel' ? 'active' : ''}`}
                    onClick={() => setActiveTab('travel')}
                >
                    Travel Plans
                </button>
                <button
                    className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
                    onClick={() => setActiveTab('history')}
                >
                    History
                </button>
            </div>

            {/* Error Display */}
            {error && (
                <div className="error-banner">
                    {error}
                    <button onClick={fetchDashboardData}>Retry</button>
                </div>
            )}

            {/* Tab Content */}
            <div className="tab-content">
                {activeTab === 'overview' && renderOverview()}

                {activeTab === 'zones' && (
                    <TrustedZonesManager
                        authToken={authToken}
                        onZoneChange={fetchDashboardData}
                    />
                )}

                {activeTab === 'travel' && (
                    <TravelItineraryManager
                        authToken={authToken}
                        onItineraryChange={fetchDashboardData}
                    />
                )}

                {activeTab === 'history' && (
                    <div className="history-section">
                        <h3>📊 Location History</h3>
                        <p className="hint">
                            Your location history helps detect impossible travel patterns.
                            Data is automatically deleted after 90 days.
                        </p>
                        {/* Location history visualization could be added here */}
                    </div>
                )}
            </div>

            {/* Travel Event Modal */}
            {selectedEvent && (
                <div className="modal-overlay" onClick={() => setSelectedEvent(null)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <ImpossibleTravelAlert
                            event={selectedEvent}
                            authToken={authToken}
                            onResolve={handleEventResolved}
                            onDismiss={() => setSelectedEvent(null)}
                        />
                    </div>
                </div>
            )}
        </div>
    );
};

export default GeofenceDashboard;

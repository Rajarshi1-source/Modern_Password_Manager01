/**
 * TrustedZonesManager Component
 * 
 * Allows users to manage their trusted location zones (geofences).
 * Includes map visualization and zone CRUD operations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './TrustedZonesManager.css';

const TrustedZonesManager = ({
    authToken,
    onZoneChange,
    baseUrl = '/api/security'
}) => {
    const [zones, setZones] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [editingZone, setEditingZone] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        latitude: '',
        longitude: '',
        radius_meters: 500,
        is_always_trusted: true,
        require_mfa_outside: true
    });

    // Fetch zones
    const fetchZones = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${baseUrl}/geofence/zones/`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });

            if (!response.ok) throw new Error('Failed to fetch zones');

            const data = await response.json();
            setZones(data.zones || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken, baseUrl]);

    useEffect(() => {
        fetchZones();
    }, [fetchZones]);

    // Get current location for new zone
    const useCurrentLocation = () => {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported');
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                setFormData(prev => ({
                    ...prev,
                    latitude: position.coords.latitude.toFixed(7),
                    longitude: position.coords.longitude.toFixed(7)
                }));
            },
            (err) => {
                console.error('Location error:', err);
                alert('Could not get current location');
            },
            { enableHighAccuracy: true }
        );
    };

    // Create zone
    const handleCreate = async () => {
        if (!formData.name || !formData.latitude || !formData.longitude) {
            alert('Please fill in all required fields');
            return;
        }

        try {
            const response = await fetch(`${baseUrl}/geofence/zones/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    ...formData,
                    latitude: parseFloat(formData.latitude),
                    longitude: parseFloat(formData.longitude)
                })
            });

            if (!response.ok) throw new Error('Failed to create zone');

            const newZone = await response.json();
            setZones(prev => [...prev, newZone]);
            resetForm();
            onZoneChange?.('created', newZone);
        } catch (err) {
            console.error('Create failed:', err);
            alert('Failed to create zone');
        }
    };

    // Update zone
    const handleUpdate = async () => {
        if (!editingZone) return;

        try {
            const response = await fetch(`${baseUrl}/geofence/zones/${editingZone.id}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    ...formData,
                    latitude: parseFloat(formData.latitude),
                    longitude: parseFloat(formData.longitude)
                })
            });

            if (!response.ok) throw new Error('Failed to update zone');

            const updatedZone = await response.json();
            setZones(prev => prev.map(z => z.id === updatedZone.id ? updatedZone : z));
            resetForm();
            onZoneChange?.('updated', updatedZone);
        } catch (err) {
            console.error('Update failed:', err);
            alert('Failed to update zone');
        }
    };

    // Delete zone
    const handleDelete = async (zoneId) => {
        if (!window.confirm('Delete this trusted zone?')) return;

        try {
            const response = await fetch(`${baseUrl}/geofence/zones/${zoneId}/`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });

            if (!response.ok) throw new Error('Failed to delete zone');

            setZones(prev => prev.filter(z => z.id !== zoneId));
            onZoneChange?.('deleted', { id: zoneId });
        } catch (err) {
            console.error('Delete failed:', err);
            alert('Failed to delete zone');
        }
    };

    // Edit zone
    const startEdit = (zone) => {
        setEditingZone(zone);
        setFormData({
            name: zone.name,
            latitude: zone.latitude,
            longitude: zone.longitude,
            radius_meters: zone.radius_meters,
            is_always_trusted: zone.is_always_trusted,
            require_mfa_outside: zone.require_mfa_outside
        });
        setShowForm(true);
    };

    // Reset form
    const resetForm = () => {
        setShowForm(false);
        setEditingZone(null);
        setFormData({
            name: '',
            latitude: '',
            longitude: '',
            radius_meters: 500,
            is_always_trusted: true,
            require_mfa_outside: true
        });
    };

    const getZoneIcon = (name) => {
        const lower = name.toLowerCase();
        if (lower.includes('home')) return '🏠';
        if (lower.includes('office') || lower.includes('work')) return '🏢';
        if (lower.includes('gym')) return '🏋️';
        if (lower.includes('school') || lower.includes('university')) return '🎓';
        return '📍';
    };

    if (loading) {
        return (
            <div className="trusted-zones-manager loading">
                <div className="spinner"></div>
                <p>Loading trusted zones...</p>
            </div>
        );
    }

    return (
        <div className="trusted-zones-manager">
            <div className="zones-header">
                <div className="header-content">
                    <h2>🛡️ Trusted Zones</h2>
                    <p>Define locations where MFA is not required</p>
                </div>
                <button
                    className="add-zone-btn"
                    onClick={() => setShowForm(true)}
                >
                    + Add Zone
                </button>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                    <button onClick={fetchZones}>Retry</button>
                </div>
            )}

            {showForm && (
                <div className="zone-form-overlay">
                    <div className="zone-form">
                        <h3>{editingZone ? 'Edit Zone' : 'Add Trusted Zone'}</h3>

                        <div className="form-group">
                            <label>Zone Name</label>
                            <input
                                type="text"
                                placeholder="e.g., Home, Office"
                                value={formData.name}
                                onChange={e => setFormData({ ...formData, name: e.target.value })}
                            />
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Latitude</label>
                                <input
                                    type="number"
                                    step="0.0000001"
                                    placeholder="28.6139"
                                    value={formData.latitude}
                                    onChange={e => setFormData({ ...formData, latitude: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label>Longitude</label>
                                <input
                                    type="number"
                                    step="0.0000001"
                                    placeholder="77.2090"
                                    value={formData.longitude}
                                    onChange={e => setFormData({ ...formData, longitude: e.target.value })}
                                />
                            </div>
                        </div>

                        <button
                            className="location-btn"
                            type="button"
                            onClick={useCurrentLocation}
                        >
                            📍 Use Current Location
                        </button>

                        <div className="form-group">
                            <label>Radius: {formData.radius_meters}m</label>
                            <input
                                type="range"
                                min="50"
                                max="5000"
                                step="50"
                                value={formData.radius_meters}
                                onChange={e => setFormData({ ...formData, radius_meters: parseInt(e.target.value) })}
                            />
                            <div className="range-labels">
                                <span>50m</span>
                                <span>5km</span>
                            </div>
                        </div>

                        <div className="form-group checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.is_always_trusted}
                                    onChange={e => setFormData({ ...formData, is_always_trusted: e.target.checked })}
                                />
                                Skip MFA in this zone
                            </label>
                        </div>

                        <div className="form-group checkbox">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={formData.require_mfa_outside}
                                    onChange={e => setFormData({ ...formData, require_mfa_outside: e.target.checked })}
                                />
                                Require MFA outside all zones
                            </label>
                        </div>

                        <div className="form-actions">
                            <button className="btn cancel" onClick={resetForm}>Cancel</button>
                            <button
                                className="btn save"
                                onClick={editingZone ? handleUpdate : handleCreate}
                            >
                                {editingZone ? 'Update Zone' : 'Create Zone'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="zones-list">
                {zones.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">📍</span>
                        <p>No trusted zones defined</p>
                        <p className="hint">Add your home or office to skip MFA when logging in</p>
                    </div>
                ) : (
                    zones.map(zone => (
                        <div key={zone.id} className={`zone-card ${!zone.is_active ? 'inactive' : ''}`}>
                            <div className="zone-icon">{getZoneIcon(zone.name)}</div>
                            <div className="zone-info">
                                <h4>{zone.name}</h4>
                                <p className="zone-coords">
                                    {parseFloat(zone.latitude).toFixed(4)}, {parseFloat(zone.longitude).toFixed(4)}
                                </p>
                                <div className="zone-meta">
                                    <span className="radius-badge">{zone.radius_meters}m</span>
                                    {zone.is_always_trusted && (
                                        <span className="trust-badge">🔓 No MFA</span>
                                    )}
                                </div>
                            </div>
                            <div className="zone-actions">
                                <button className="edit-btn" onClick={() => startEdit(zone)}>✏️</button>
                                <button className="delete-btn" onClick={() => handleDelete(zone.id)}>🗑️</button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default TrustedZonesManager;

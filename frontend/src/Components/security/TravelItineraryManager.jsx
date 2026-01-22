/**
 * TravelItineraryManager Component
 * 
 * Allows users to manage their travel itineraries for impossible travel verification.
 * Supports adding travel plans and verifying bookings via airline APIs.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as geofenceService from '../../services/geofenceService';
import './TravelItineraryManager.css';

const TravelItineraryManager = ({ authToken, onItineraryChange }) => {
    const [itineraries, setItineraries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [verifying, setVerifying] = useState(null);
    const [formData, setFormData] = useState({
        departure_city: '',
        arrival_city: '',
        departure_time: '',
        arrival_time: '',
        airline_code: '',
        flight_number: '',
        booking_reference: '',
        notes: ''
    });

    // Fetch itineraries
    const fetchItineraries = useCallback(async () => {
        setLoading(true);
        try {
            const data = await geofenceService.getItineraries(authToken);
            setItineraries(data.itineraries || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken]);

    useEffect(() => {
        fetchItineraries();
    }, [fetchItineraries]);

    // Handle form submission
    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!formData.departure_city || !formData.arrival_city ||
            !formData.departure_time || !formData.arrival_time) {
            alert('Please fill in all required fields');
            return;
        }

        try {
            await geofenceService.addItinerary(authToken, formData);
            resetForm();
            fetchItineraries();
            onItineraryChange?.('created');
        } catch (err) {
            alert(`Failed to add itinerary: ${err.message}`);
        }
    };

    // Handle verification
    const handleVerify = async (itinerary) => {
        if (!itinerary.booking_reference) {
            alert('No booking reference available for verification');
            return;
        }

        setVerifying(itinerary.id);
        try {
            const result = await geofenceService.verifyTravel(authToken, {
                reference: itinerary.booking_reference,
                lastName: prompt('Enter your last name for booking verification:'),
                itineraryId: itinerary.id
            });

            if (result.verified) {
                alert('✅ Travel verified successfully!');
                fetchItineraries();
            } else {
                alert(`❌ Verification failed: ${result.message || 'Unknown error'}`);
            }
        } catch (err) {
            alert(`Verification error: ${err.message}`);
        } finally {
            setVerifying(null);
        }
    };

    // Handle delete
    const handleDelete = async (itineraryId) => {
        if (!window.confirm('Delete this travel itinerary?')) return;

        try {
            await geofenceService.deleteItinerary(authToken, itineraryId);
            setItineraries(prev => prev.filter(i => i.id !== itineraryId));
            onItineraryChange?.('deleted');
        } catch (err) {
            alert(`Failed to delete: ${err.message}`);
        }
    };

    const resetForm = () => {
        setShowForm(false);
        setFormData({
            departure_city: '',
            arrival_city: '',
            departure_time: '',
            arrival_time: '',
            airline_code: '',
            flight_number: '',
            booking_reference: '',
            notes: ''
        });
    };

    const formatDateTime = (dateStr) => {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getStatusBadge = (status) => {
        const badges = {
            pending: { color: '#eab308', label: 'Pending' },
            verified: { color: '#22c55e', label: 'Verified' },
            failed: { color: '#ef4444', label: 'Failed' },
            expired: { color: '#6b7280', label: 'Expired' }
        };
        return badges[status] || badges.pending;
    };

    if (loading) {
        return (
            <div className="travel-itinerary-manager loading">
                <div className="spinner"></div>
                <p>Loading itineraries...</p>
            </div>
        );
    }

    return (
        <div className="travel-itinerary-manager">
            <div className="manager-header">
                <div className="header-content">
                    <h2>✈️ Travel Itineraries</h2>
                    <p>Pre-register travel to avoid false security alerts</p>
                </div>
                <button className="add-btn" onClick={() => setShowForm(true)}>
                    + Add Trip
                </button>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                    <button onClick={fetchItineraries}>Retry</button>
                </div>
            )}

            {/* Add Form */}
            {showForm && (
                <div className="form-overlay">
                    <form className="itinerary-form" onSubmit={handleSubmit}>
                        <h3>Add Travel Itinerary</h3>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Departure City *</label>
                                <input
                                    type="text"
                                    placeholder="e.g., New Delhi"
                                    value={formData.departure_city}
                                    onChange={e => setFormData({ ...formData, departure_city: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Arrival City *</label>
                                <input
                                    type="text"
                                    placeholder="e.g., Mumbai"
                                    value={formData.arrival_city}
                                    onChange={e => setFormData({ ...formData, arrival_city: e.target.value })}
                                    required
                                />
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Departure Time *</label>
                                <input
                                    type="datetime-local"
                                    value={formData.departure_time}
                                    onChange={e => setFormData({ ...formData, departure_time: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Arrival Time *</label>
                                <input
                                    type="datetime-local"
                                    value={formData.arrival_time}
                                    onChange={e => setFormData({ ...formData, arrival_time: e.target.value })}
                                    required
                                />
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group small">
                                <label>Airline Code</label>
                                <input
                                    type="text"
                                    placeholder="AI"
                                    maxLength="3"
                                    value={formData.airline_code}
                                    onChange={e => setFormData({ ...formData, airline_code: e.target.value.toUpperCase() })}
                                />
                            </div>
                            <div className="form-group">
                                <label>Flight Number</label>
                                <input
                                    type="text"
                                    placeholder="101"
                                    value={formData.flight_number}
                                    onChange={e => setFormData({ ...formData, flight_number: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label>Booking Reference (PNR)</label>
                                <input
                                    type="text"
                                    placeholder="ABC123"
                                    value={formData.booking_reference}
                                    onChange={e => setFormData({ ...formData, booking_reference: e.target.value.toUpperCase() })}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label>Notes</label>
                            <textarea
                                placeholder="Any additional details..."
                                value={formData.notes}
                                onChange={e => setFormData({ ...formData, notes: e.target.value })}
                            />
                        </div>

                        <div className="form-info">
                            <span className="info-icon">ℹ️</span>
                            <span>Providing a booking reference allows automatic verification via airline APIs</span>
                        </div>

                        <div className="form-actions">
                            <button type="button" className="btn cancel" onClick={resetForm}>
                                Cancel
                            </button>
                            <button type="submit" className="btn save">
                                Add Itinerary
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Itineraries List */}
            <div className="itineraries-list">
                {itineraries.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">🗓️</span>
                        <p>No travel itineraries</p>
                        <p className="hint">
                            Add your upcoming trips to prevent false impossible travel alerts
                        </p>
                    </div>
                ) : (
                    itineraries.map(itinerary => (
                        <div key={itinerary.id} className="itinerary-card">
                            <div className="itinerary-route">
                                <div className="city departure">
                                    <span className="city-name">{itinerary.departure_city}</span>
                                    <span className="time">{formatDateTime(itinerary.departure_time)}</span>
                                </div>
                                <div className="route-line">
                                    <div className="plane-icon">✈️</div>
                                    {itinerary.airline_code && itinerary.flight_number && (
                                        <span className="flight-number">
                                            {itinerary.airline_code}{itinerary.flight_number}
                                        </span>
                                    )}
                                </div>
                                <div className="city arrival">
                                    <span className="city-name">{itinerary.arrival_city}</span>
                                    <span className="time">{formatDateTime(itinerary.arrival_time)}</span>
                                </div>
                            </div>

                            <div className="itinerary-meta">
                                <span
                                    className="status-badge"
                                    style={{ backgroundColor: getStatusBadge(itinerary.verification_status).color }}
                                >
                                    {getStatusBadge(itinerary.verification_status).label}
                                </span>

                                {itinerary.booking_reference && (
                                    <span className="booking-ref">
                                        PNR: {itinerary.booking_reference}
                                    </span>
                                )}
                            </div>

                            <div className="itinerary-actions">
                                {itinerary.verification_status === 'pending' && itinerary.booking_reference && (
                                    <button
                                        className="verify-btn"
                                        onClick={() => handleVerify(itinerary)}
                                        disabled={verifying === itinerary.id}
                                    >
                                        {verifying === itinerary.id ? 'Verifying...' : '✓ Verify'}
                                    </button>
                                )}
                                <button
                                    className="delete-btn"
                                    onClick={() => handleDelete(itinerary.id)}
                                >
                                    🗑️
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default TravelItineraryManager;

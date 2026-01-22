/**
 * ImpossibleTravelAlert Component
 * 
 * Displays alerts when impossible travel is detected.
 * Allows users to verify legitimate travel or report unauthorized access.
 */

import React, { useState } from 'react';
import './ImpossibleTravelAlert.css';

const ImpossibleTravelAlert = ({
    event,
    authToken,
    onResolve,
    onDismiss,
    baseUrl = '/api/security'
}) => {
    const [isResolving, setIsResolving] = useState(false);
    const [showVerifyForm, setShowVerifyForm] = useState(false);
    const [bookingRef, setBookingRef] = useState('');
    const [lastName, setLastName] = useState('');

    const formatSpeed = (speed) => {
        if (speed >= 1000) {
            return `${(speed / 1000).toFixed(1)}k km/h`;
        }
        return `${Math.round(speed)} km/h`;
    };

    const formatTime = (seconds) => {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        const hours = Math.floor(seconds / 3600);
        const mins = Math.round((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    };

    const getSeverityColor = (severity) => {
        const colors = {
            low: '#00e676',
            medium: '#ffc107',
            high: '#ff9800',
            critical: '#f44336'
        };
        return colors[severity] || '#fff';
    };

    const handleConfirmLegitimate = async () => {
        setIsResolving(true);
        try {
            const response = await fetch(`${baseUrl}/geofence/travel/resolve/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    event_id: event.id,
                    is_legitimate: true,
                    resolution_notes: 'User confirmed as legitimate travel'
                })
            });

            if (!response.ok) throw new Error('Failed to resolve event');

            onResolve?.({ success: true, legitimate: true });
        } catch (err) {
            console.error('Failed to resolve:', err);
        } finally {
            setIsResolving(false);
        }
    };

    const handleReportUnauthorized = async () => {
        setIsResolving(true);
        try {
            const response = await fetch(`${baseUrl}/geofence/travel/resolve/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    event_id: event.id,
                    is_legitimate: false,
                    resolution_notes: 'User reported as unauthorized access'
                })
            });

            if (!response.ok) throw new Error('Failed to resolve event');

            onResolve?.({ success: true, legitimate: false, requiresAction: true });
        } catch (err) {
            console.error('Failed to resolve:', err);
        } finally {
            setIsResolving(false);
        }
    };

    const handleVerifyBooking = async () => {
        if (!bookingRef || !lastName) return;

        setIsResolving(true);
        try {
            const response = await fetch(`${baseUrl}/geofence/travel/verify/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    booking_reference: bookingRef,
                    last_name: lastName
                })
            });

            const data = await response.json();

            if (data.is_valid) {
                // Auto-resolve the event
                await handleConfirmLegitimate();
            } else {
                alert('Booking verification failed: ' + (data.error_message || 'Invalid booking'));
            }
        } catch (err) {
            console.error('Verification failed:', err);
        } finally {
            setIsResolving(false);
        }
    };

    return (
        <div className={`impossible-travel-alert ${event.severity}`}>
            <div className="alert-header">
                <div className="alert-icon">
                    {event.severity === 'critical' ? '🚨' : '⚠️'}
                </div>
                <div className="alert-title">
                    {event.is_cloned_session ? 'Cloned Session Detected' : 'Impossible Travel Detected'}
                </div>
                <button className="dismiss-btn" onClick={onDismiss}>×</button>
            </div>

            <div className="alert-body">
                <div className="travel-summary">
                    <div className="location-pair">
                        <div className="location from">
                            <span className="label">From</span>
                            <span className="city">{event.source_city || 'Unknown'}</span>
                            <span className="time">
                                {new Date(event.source_timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                        <div className="arrow">→</div>
                        <div className="location to">
                            <span className="label">To</span>
                            <span className="city">{event.destination_city || 'Unknown'}</span>
                            <span className="time">
                                {new Date(event.destination_timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                    </div>

                    <div className="stats">
                        <div className="stat">
                            <span className="stat-value">{Math.round(event.distance_km)} km</span>
                            <span className="stat-label">Distance</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{formatTime(event.time_difference_seconds)}</span>
                            <span className="stat-label">Time</span>
                        </div>
                        <div className="stat">
                            <span
                                className="stat-value"
                                style={{ color: getSeverityColor(event.severity) }}
                            >
                                {formatSpeed(event.required_speed_kmh)}
                            </span>
                            <span className="stat-label">Required Speed</span>
                        </div>
                    </div>
                </div>

                <div className="alert-message">
                    {event.severity === 'critical' ? (
                        <p>
                            ⚠️ This travel speed exceeds the speed of sound and is physically impossible.
                            This may indicate your account has been compromised.
                        </p>
                    ) : event.severity === 'high' ? (
                        <p>
                            This travel speed exceeds commercial flight capability.
                            Please verify if this was legitimate travel.
                        </p>
                    ) : (
                        <p>
                            This travel pattern requires verification.
                            Was this you?
                        </p>
                    )}
                </div>

                {showVerifyForm ? (
                    <div className="verify-form">
                        <h4>Verify with Booking Reference</h4>
                        <input
                            type="text"
                            placeholder="Booking Reference (PNR)"
                            value={bookingRef}
                            onChange={(e) => setBookingRef(e.target.value.toUpperCase())}
                            maxLength={6}
                        />
                        <input
                            type="text"
                            placeholder="Last Name"
                            value={lastName}
                            onChange={(e) => setLastName(e.target.value)}
                        />
                        <div className="form-actions">
                            <button
                                className="btn secondary"
                                onClick={() => setShowVerifyForm(false)}
                            >
                                Cancel
                            </button>
                            <button
                                className="btn primary"
                                onClick={handleVerifyBooking}
                                disabled={isResolving || !bookingRef || !lastName}
                            >
                                {isResolving ? 'Verifying...' : 'Verify'}
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="alert-actions">
                        <button
                            className="btn danger"
                            onClick={handleReportUnauthorized}
                            disabled={isResolving}
                        >
                            🚫 Not Me - Secure Account
                        </button>
                        <button
                            className="btn secondary"
                            onClick={() => setShowVerifyForm(true)}
                            disabled={isResolving}
                        >
                            ✈️ Verify Flight
                        </button>
                        <button
                            className="btn success"
                            onClick={handleConfirmLegitimate}
                            disabled={isResolving}
                        >
                            ✓ This Was Me
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ImpossibleTravelAlert;

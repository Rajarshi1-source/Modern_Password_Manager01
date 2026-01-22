/**
 * GeolocationCapture Component
 * 
 * Captures GPS coordinates from the browser and sends to the backend.
 * Used for impossible travel detection.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './GeolocationCapture.css';

const GeolocationCapture = ({
    authToken,
    onLocationCaptured,
    onError,
    autoCapture = true,
    showStatus = true,
    baseUrl = '/api/security'
}) => {
    const [status, setStatus] = useState('idle'); // idle, requesting, capturing, success, error
    const [location, setLocation] = useState(null);
    const [error, setError] = useState(null);
    const [analysis, setAnalysis] = useState(null);
    const [permissionGranted, setPermissionGranted] = useState(null);

    // Check permission status
    useEffect(() => {
        if ('permissions' in navigator) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                setPermissionGranted(result.state === 'granted');

                result.onchange = () => {
                    setPermissionGranted(result.state === 'granted');
                };
            });
        }
    }, []);

    // Auto-capture on mount
    useEffect(() => {
        if (autoCapture && permissionGranted) {
            captureLocation();
        }
    }, [autoCapture, permissionGranted]);

    const captureLocation = useCallback(async () => {
        if (!navigator.geolocation) {
            const err = new Error('Geolocation is not supported by your browser');
            setError(err.message);
            setStatus('error');
            onError?.(err);
            return;
        }

        setStatus('requesting');
        setError(null);

        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 30000
        };

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                setStatus('capturing');

                const coords = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy_meters: position.coords.accuracy,
                    altitude: position.coords.altitude,
                    source: 'gps'
                };

                setLocation(coords);

                // Send to backend
                try {
                    const response = await fetch(`${baseUrl}/geofence/location/record/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${authToken}`
                        },
                        body: JSON.stringify(coords)
                    });

                    if (!response.ok) {
                        throw new Error('Failed to record location');
                    }

                    const data = await response.json();
                    setAnalysis(data.analysis);
                    setStatus('success');
                    onLocationCaptured?.(data);

                    // Check if action is required
                    if (data.action_required && data.action_required !== 'allowed') {
                        onError?.({
                            type: 'travel_alert',
                            action: data.action_required,
                            analysis: data.analysis,
                            eventId: data.travel_event_id
                        });
                    }

                } catch (err) {
                    console.error('Location recording failed:', err);
                    setError(err.message);
                    setStatus('error');
                    onError?.(err);
                }
            },
            (err) => {
                console.error('Geolocation error:', err);
                setError(err.message);
                setStatus('error');
                onError?.(err);
            },
            options
        );
    }, [authToken, baseUrl, onLocationCaptured, onError]);

    const requestPermission = useCallback(async () => {
        setStatus('requesting');
        captureLocation();
    }, [captureLocation]);

    if (!showStatus) {
        return null;
    }

    return (
        <div className="geolocation-capture">
            <div className="geolocation-header">
                <span className="geolocation-icon">📍</span>
                <span className="geolocation-title">Location Security</span>
            </div>

            {status === 'idle' && permissionGranted === false && (
                <div className="geolocation-permission">
                    <p>Enable location for enhanced security</p>
                    <button
                        className="geolocation-btn primary"
                        onClick={requestPermission}
                    >
                        Enable Location
                    </button>
                </div>
            )}

            {status === 'requesting' && (
                <div className="geolocation-loading">
                    <div className="spinner"></div>
                    <p>Requesting location access...</p>
                </div>
            )}

            {status === 'capturing' && (
                <div className="geolocation-loading">
                    <div className="spinner"></div>
                    <p>Analyzing travel pattern...</p>
                </div>
            )}

            {status === 'success' && location && (
                <div className="geolocation-success">
                    <div className="location-info">
                        <span className="success-icon">✓</span>
                        <span>Location verified</span>
                    </div>

                    {analysis && (
                        <div className={`analysis-badge ${analysis.severity}`}>
                            {analysis.is_plausible ? (
                                <span>Normal travel pattern</span>
                            ) : (
                                <span>⚠ Unusual travel detected</span>
                            )}
                        </div>
                    )}
                </div>
            )}

            {status === 'error' && (
                <div className="geolocation-error">
                    <span className="error-icon">⚠</span>
                    <p>{error || 'Location capture failed'}</p>
                    <button
                        className="geolocation-btn secondary"
                        onClick={captureLocation}
                    >
                        Retry
                    </button>
                </div>
            )}
        </div>
    );
};

export default GeolocationCapture;

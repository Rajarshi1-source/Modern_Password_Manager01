/**
 * Collect Fragments Component
 * =============================
 * 
 * AR/GPS-guided fragment collection interface.
 * Guides user to dead drop location and collects fragments when nearby.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './CollectFragments.css';

const API_BASE = '/api/mesh';

const CollectFragments = ({ deadDropId, onSuccess, onCancel }) => {
    const [step, setStep] = useState('location'); // location, scanning, collecting, success, error
    const [userLocation, setUserLocation] = useState(null);
    const [deadDrop, setDeadDrop] = useState(null);
    const [distance, setDistance] = useState(null);
    const [bleNodes, setBleNodes] = useState([]);
    const [progress, setProgress] = useState(0);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [isScanning, setIsScanning] = useState(false);

    // Fetch dead drop details
    useEffect(() => {
        const fetchDeadDrop = async () => {
            try {
                const response = await fetch(`${API_BASE}/deaddrops/${deadDropId}/`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    }
                });
                const data = await response.json();
                setDeadDrop(data);
            } catch (error) {
                setError('Failed to load dead drop details');
            }
        };
        fetchDeadDrop();
    }, [deadDropId]);

    // Watch user location
    useEffect(() => {
        if (!navigator.geolocation) {
            setError('Geolocation not supported');
            return;
        }

        const watchId = navigator.geolocation.watchPosition(
            (position) => {
                const loc = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy
                };
                setUserLocation(loc);

                // Calculate distance to dead drop
                if (deadDrop) {
                    const dist = calculateDistance(
                        loc.lat, loc.lng,
                        parseFloat(deadDrop.latitude),
                        parseFloat(deadDrop.longitude)
                    );
                    setDistance(dist);
                }
            },
            (error) => {
                console.error('Geolocation error:', error);
                setError('Failed to get location');
            },
            { enableHighAccuracy: true, maximumAge: 5000 }
        );

        return () => navigator.geolocation.clearWatch(watchId);
    }, [deadDrop]);

    // Calculate haversine distance
    const calculateDistance = (lat1, lon1, lat2, lon2) => {
        const R = 6371000; // Earth radius in meters
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    };

    // Simulate BLE scanning (in real app, use Web Bluetooth API)
    const startBLEScan = useCallback(async () => {
        setStep('scanning');
        setIsScanning(true);
        setBleNodes([]);

        // Simulate finding nodes
        const mockNodes = [
            { id: 'node-1', name: 'MeshNode-A', rssi: -55 },
            { id: 'node-2', name: 'MeshNode-B', rssi: -68 },
            { id: 'node-3', name: 'MeshNode-C', rssi: -72 },
        ];

        for (let i = 0; i < mockNodes.length; i++) {
            await new Promise(r => setTimeout(r, 800));
            setBleNodes(prev => [...prev, mockNodes[i]]);
        }

        setIsScanning(false);
        setStep('collecting');
    }, []);

    // Collect fragments
    const collectFragments = async () => {
        setProgress(0);

        try {
            // Build location proof
            const locationData = {
                latitude: userLocation.lat.toFixed(6),
                longitude: userLocation.lng.toFixed(6),
                accuracy_meters: userLocation.accuracy,
                ble_nodes: bleNodes.map(n => ({ id: n.id, rssi: n.rssi }))
            };

            // Simulate progress
            const interval = setInterval(() => {
                setProgress(p => Math.min(p + 10, 90));
            }, 300);

            // Make API call
            const response = await fetch(`${API_BASE}/deaddrops/${deadDropId}/collect/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ location: locationData })
            });

            clearInterval(interval);

            const data = await response.json();

            if (response.ok && data.secret) {
                setProgress(100);
                setResult(data);
                setStep('success');
                if (onSuccess) onSuccess(data);
            } else {
                setError(data.error || 'Collection failed');
                setStep('error');
            }
        } catch (error) {
            setError(error.message);
            setStep('error');
        }
    };

    // Check if in range
    const inRange = distance !== null && deadDrop && distance <= deadDrop.radius_meters;

    return (
        <div className="collect-fragments">
            {/* Header */}
            <div className="collect-header">
                <button className="back-btn" onClick={onCancel}>← Back</button>
                <h2>📥 Collect Fragments</h2>
            </div>

            {/* Location Step */}
            {step === 'location' && deadDrop && (
                <motion.div
                    className="collect-step"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                >
                    <div className="location-compass">
                        <div className="compass-ring">
                            <motion.div
                                className="compass-pointer"
                                animate={{ rotate: 360 }}
                                transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                            />
                        </div>
                        <div className="distance-display">
                            {distance !== null ? (
                                <>
                                    <span className="distance-value">
                                        {distance > 1000
                                            ? `${(distance / 1000).toFixed(1)}km`
                                            : `${Math.round(distance)}m`}
                                    </span>
                                    <span className="distance-label">to target</span>
                                </>
                            ) : (
                                <span className="distance-label">Locating...</span>
                            )}
                        </div>
                    </div>

                    {deadDrop.location_hint && (
                        <div className="location-hint-card">
                            <span className="hint-icon">💡</span>
                            <p>{deadDrop.location_hint}</p>
                        </div>
                    )}

                    <div className={`range-status ${inRange ? 'in-range' : 'out-of-range'}`}>
                        {inRange ? (
                            <>
                                <span className="range-icon">✓</span>
                                <span>You are within collection range</span>
                            </>
                        ) : (
                            <>
                                <span className="range-icon">↗</span>
                                <span>Move closer to the target location</span>
                            </>
                        )}
                    </div>

                    <button
                        className="action-btn primary"
                        onClick={startBLEScan}
                        disabled={!inRange}
                    >
                        {inRange ? '📶 Scan for Mesh Nodes' : 'Get Closer to Collect'}
                    </button>
                </motion.div>
            )}

            {/* Scanning Step */}
            {step === 'scanning' && (
                <motion.div
                    className="collect-step"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                >
                    <div className="scanning-animation">
                        <div className="radar">
                            <div className="radar-sweep" />
                            {bleNodes.map((node, i) => (
                                <motion.div
                                    key={node.id}
                                    className="radar-dot"
                                    initial={{ scale: 0, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    style={{
                                        left: `${30 + i * 20}%`,
                                        top: `${40 + (i % 2) * 20}%`
                                    }}
                                />
                            ))}
                        </div>
                    </div>

                    <h3>Scanning for Mesh Nodes...</h3>

                    <div className="nodes-found">
                        {bleNodes.map(node => (
                            <motion.div
                                key={node.id}
                                className="node-item"
                                initial={{ x: -20, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                            >
                                <span className="node-icon">📶</span>
                                <span className="node-name">{node.name}</span>
                                <span className="node-rssi">{node.rssi}dBm</span>
                            </motion.div>
                        ))}
                    </div>

                    {isScanning && (
                        <p className="scanning-text">
                            Detecting nearby mesh nodes...
                        </p>
                    )}
                </motion.div>
            )}

            {/* Collecting Step */}
            {step === 'collecting' && (
                <motion.div
                    className="collect-step"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                >
                    <div className="collection-status">
                        <div className="collection-circle">
                            <svg viewBox="0 0 100 100">
                                <circle
                                    cx="50" cy="50" r="45"
                                    fill="none"
                                    stroke="rgba(255,255,255,0.1)"
                                    strokeWidth="8"
                                />
                                <motion.circle
                                    cx="50" cy="50" r="45"
                                    fill="none"
                                    stroke="#00e676"
                                    strokeWidth="8"
                                    strokeLinecap="round"
                                    strokeDasharray={283}
                                    strokeDashoffset={283 - (283 * progress / 100)}
                                    initial={{ strokeDashoffset: 283 }}
                                    animate={{ strokeDashoffset: 283 - (283 * progress / 100) }}
                                />
                            </svg>
                            <span className="progress-percent">{progress}%</span>
                        </div>
                    </div>

                    <h3>Ready to Collect</h3>
                    <p className="collect-info">
                        Found {bleNodes.length} mesh nodes.
                        Need {deadDrop?.required_fragments || 3} fragments to reconstruct.
                    </p>

                    <button
                        className="action-btn primary large"
                        onClick={collectFragments}
                        disabled={progress > 0 && progress < 100}
                    >
                        {progress > 0 ? 'Collecting...' : '🔓 Collect & Reconstruct'}
                    </button>
                </motion.div>
            )}

            {/* Success Step */}
            {step === 'success' && result && (
                <motion.div
                    className="collect-step success"
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                >
                    <div className="success-icon">🎉</div>
                    <h3>Secret Recovered!</h3>
                    <p>Successfully collected {result.fragments_collected} fragments</p>

                    <div className="secret-reveal">
                        <label>Your Secret:</label>
                        <div className="secret-box">
                            {result.secret}
                        </div>
                        <button
                            className="copy-btn"
                            onClick={() => navigator.clipboard.writeText(result.secret)}
                        >
                            📋 Copy to Clipboard
                        </button>
                    </div>

                    <button className="action-btn secondary" onClick={onCancel}>
                        Done
                    </button>
                </motion.div>
            )}

            {/* Error Step */}
            {step === 'error' && (
                <motion.div
                    className="collect-step error"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                >
                    <div className="error-icon">❌</div>
                    <h3>Collection Failed</h3>
                    <p className="error-message">{error}</p>

                    <button
                        className="action-btn secondary"
                        onClick={() => setStep('location')}
                    >
                        Try Again
                    </button>
                </motion.div>
            )}

            {/* Error display */}
            {error && step !== 'error' && (
                <div className="inline-error">{error}</div>
            )}
        </div>
    );
};

export default CollectFragments;

/**
 * Location Proof Component
 * ==========================
 * 
 * Location verification flow for dead drop collection.
 * Multi-factor: GPS + BLE + optional NFC/WiFi
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './LocationProof.css';

const LocationProof = ({
    targetLocation,
    radiusMeters = 50,
    requireBLE = true,
    requireNFC = false,
    onVerified,
    onFailed
}) => {
    const [step, setStep] = useState('gps'); // gps, ble, nfc, verified, failed
    const [gpsStatus, setGpsStatus] = useState({ verified: false, distance: null, accuracy: null });
    const [bleStatus, setBleStatus] = useState({ verified: false, nodesFound: 0, nodes: [] });
    const [nfcStatus, setNfcStatus] = useState({ verified: false });
    const [confidence, setConfidence] = useState(0);
    const [error, setError] = useState(null);

    // Calculate distance between two points (Haversine)
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

    // GPS verification
    const verifyGPS = useCallback(() => {
        if (!navigator.geolocation) {
            setError('Geolocation not supported');
            setStep('failed');
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const distance = calculateDistance(
                    position.coords.latitude,
                    position.coords.longitude,
                    targetLocation.lat,
                    targetLocation.lng
                );

                const verified = distance <= (radiusMeters + position.coords.accuracy);

                setGpsStatus({
                    verified,
                    distance: Math.round(distance),
                    accuracy: Math.round(position.coords.accuracy),
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                });

                if (verified) {
                    setConfidence(prev => prev + 40);
                    if (requireBLE) {
                        setStep('ble');
                    } else if (requireNFC) {
                        setStep('nfc');
                    } else {
                        setStep('verified');
                        onVerified?.({ gps: gpsStatus, ble: bleStatus, nfc: nfcStatus });
                    }
                } else {
                    setError(`Too far from location (${Math.round(distance)}m away)`);
                    setStep('failed');
                    onFailed?.('GPS verification failed');
                }
            },
            (error) => {
                setError(`GPS error: ${error.message}`);
                setStep('failed');
                onFailed?.(error.message);
            },
            { enableHighAccuracy: true, timeout: 15000 }
        );
    }, [targetLocation, radiusMeters, requireBLE, requireNFC, onVerified, onFailed]);

    // BLE scanning simulation
    const scanBLE = useCallback(async () => {
        // Simulate BLE scanning (use Web Bluetooth API in production)
        const mockNodes = [
            { id: 'node-1', name: 'MeshNode-Alpha', rssi: -55 },
            { id: 'node-2', name: 'MeshNode-Beta', rssi: -68 },
            { id: 'node-3', name: 'MeshNode-Gamma', rssi: -72 },
        ];

        for (let i = 0; i < mockNodes.length; i++) {
            await new Promise(r => setTimeout(r, 600));
            setBleStatus(prev => ({
                ...prev,
                nodesFound: i + 1,
                nodes: [...prev.nodes, mockNodes[i]]
            }));
        }

        setBleStatus(prev => ({ ...prev, verified: true }));
        setConfidence(prev => prev + 40);

        if (requireNFC) {
            setStep('nfc');
        } else {
            setStep('verified');
            onVerified?.({ gps: gpsStatus, ble: { verified: true, nodes: mockNodes }, nfc: nfcStatus });
        }
    }, [requireNFC, gpsStatus, nfcStatus, onVerified]);

    // NFC tap simulation
    const handleNFCTap = useCallback(async () => {
        // Simulate NFC tap
        await new Promise(r => setTimeout(r, 1000));

        setNfcStatus({ verified: true });
        setConfidence(prev => prev + 20);
        setStep('verified');
        onVerified?.({ gps: gpsStatus, ble: bleStatus, nfc: { verified: true } });
    }, [gpsStatus, bleStatus, onVerified]);

    // Start verification on mount
    useEffect(() => {
        if (step === 'gps') {
            verifyGPS();
        } else if (step === 'ble') {
            scanBLE();
        }
    }, [step, verifyGPS, scanBLE]);

    return (
        <div className="location-proof">
            <div className="proof-header">
                <h2>📍 Location Verification</h2>
                <p>Proving you are at the dead drop location</p>
            </div>

            {/* Progress indicator */}
            <div className="proof-progress">
                <div className="progress-steps">
                    <div className={`step-item ${step === 'gps' ? 'active' : gpsStatus.verified ? 'done' : ''}`}>
                        <span className="step-icon">📍</span>
                        <span className="step-label">GPS</span>
                    </div>
                    {requireBLE && (
                        <div className={`step-item ${step === 'ble' ? 'active' : bleStatus.verified ? 'done' : ''}`}>
                            <span className="step-icon">📶</span>
                            <span className="step-label">BLE</span>
                        </div>
                    )}
                    {requireNFC && (
                        <div className={`step-item ${step === 'nfc' ? 'active' : nfcStatus.verified ? 'done' : ''}`}>
                            <span className="step-icon">📱</span>
                            <span className="step-label">NFC</span>
                        </div>
                    )}
                </div>
                <div className="confidence-bar">
                    <motion.div
                        className="confidence-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${confidence}%` }}
                    />
                </div>
                <span className="confidence-text">{confidence}% confident</span>
            </div>

            {/* Step content */}
            <AnimatePresence mode="wait">
                {step === 'gps' && (
                    <motion.div
                        key="gps"
                        className="step-content"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                    >
                        <div className="verification-animation gps">
                            <div className="pulse-ring" />
                            <div className="pulse-ring delay-1" />
                            <div className="center-dot" />
                        </div>
                        <h3>Verifying GPS Location...</h3>
                        <p>Checking if you're within {radiusMeters}m of the target</p>
                    </motion.div>
                )}

                {step === 'ble' && (
                    <motion.div
                        key="ble"
                        className="step-content"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                    >
                        <div className="verification-animation ble">
                            <div className="radar-sweep" />
                            {bleStatus.nodes.map((node, i) => (
                                <motion.div
                                    key={node.id}
                                    className="node-dot"
                                    initial={{ scale: 0 }}
                                    animate={{ scale: 1 }}
                                    style={{
                                        left: `${30 + i * 20}%`,
                                        top: `${40 + (i % 2) * 20}%`
                                    }}
                                />
                            ))}
                        </div>
                        <h3>Scanning for Mesh Nodes...</h3>
                        <p>Found {bleStatus.nodesFound} node{bleStatus.nodesFound !== 1 ? 's' : ''}</p>

                        <div className="nodes-list">
                            {bleStatus.nodes.map(node => (
                                <div key={node.id} className="node-item">
                                    <span className="node-name">{node.name}</span>
                                    <span className="node-rssi">{node.rssi}dBm</span>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {step === 'nfc' && (
                    <motion.div
                        key="nfc"
                        className="step-content"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                    >
                        <div className="verification-animation nfc">
                            <div className="nfc-icon">📱</div>
                            <div className="nfc-waves" />
                        </div>
                        <h3>Tap NFC Tag</h3>
                        <p>Hold your device near the NFC beacon at the location</p>

                        <button className="nfc-tap-btn" onClick={handleNFCTap}>
                            Simulate NFC Tap
                        </button>
                    </motion.div>
                )}

                {step === 'verified' && (
                    <motion.div
                        key="verified"
                        className="step-content success"
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                    >
                        <div className="success-icon">✓</div>
                        <h3>Location Verified!</h3>
                        <p>You are confirmed at the dead drop location</p>

                        <div className="verification-summary">
                            <div className="summary-item">
                                <span className="label">GPS</span>
                                <span className="value success">✓ {gpsStatus.distance}m</span>
                            </div>
                            {requireBLE && (
                                <div className="summary-item">
                                    <span className="label">BLE Nodes</span>
                                    <span className="value success">✓ {bleStatus.nodesFound}</span>
                                </div>
                            )}
                            {requireNFC && (
                                <div className="summary-item">
                                    <span className="label">NFC</span>
                                    <span className="value success">✓ Verified</span>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}

                {step === 'failed' && (
                    <motion.div
                        key="failed"
                        className="step-content failed"
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                    >
                        <div className="error-icon">✗</div>
                        <h3>Verification Failed</h3>
                        <p>{error}</p>

                        <button className="retry-btn" onClick={() => {
                            setStep('gps');
                            setError(null);
                            setConfidence(0);
                            setGpsStatus({ verified: false, distance: null });
                            setBleStatus({ verified: false, nodesFound: 0, nodes: [] });
                        }}>
                            Try Again
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default LocationProof;

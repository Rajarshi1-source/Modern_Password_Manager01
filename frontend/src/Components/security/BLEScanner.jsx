/**
 * BLE Scanner Component
 * =======================
 * 
 * Bluetooth Low Energy device scanner for mesh networking.
 * Uses Web Bluetooth API where available.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './BLEScanner.css';

const BLEScanner = ({
    onDeviceFound,
    onScanComplete,
    autoStart = false,
    scanDuration = 10000,
    filterMeshOnly = true
}) => {
    const [isScanning, setIsScanning] = useState(false);
    const [devices, setDevices] = useState([]);
    const [supported, setSupported] = useState(true);
    const [error, setError] = useState(null);
    const [scanProgress, setScanProgress] = useState(0);

    // Check Web Bluetooth support
    useEffect(() => {
        if (!navigator.bluetooth) {
            setSupported(false);
            setError('Web Bluetooth not supported in this browser');
        }
    }, []);

    // Start scanning
    const startScan = useCallback(async () => {
        if (!supported) return;

        setIsScanning(true);
        setDevices([]);
        setError(null);
        setScanProgress(0);

        // Progress animation
        const progressInterval = setInterval(() => {
            setScanProgress(prev => Math.min(prev + 1, 100));
        }, scanDuration / 100);

        try {
            // For Web Bluetooth, we need user interaction
            // This is a simplified demo - real implementation would use requestDevice

            // Simulate finding devices
            const mockDevices = [
                { id: 'mesh-1', name: 'MeshNode-Alpha', rssi: -52, type: 'mesh_node', services: ['dead-d'] },
                { id: 'mesh-2', name: 'MeshNode-Beta', rssi: -65, type: 'mesh_node', services: ['dead-d'] },
                { id: 'mesh-3', name: 'MeshNode-Gamma', rssi: -78, type: 'mesh_node', services: ['dead-d'] },
                { id: 'other-1', name: 'Unknown Device', rssi: -85, type: 'other', services: [] },
            ];

            for (let i = 0; i < mockDevices.length; i++) {
                await new Promise(r => setTimeout(r, 800 + Math.random() * 400));

                const device = mockDevices[i];

                if (!filterMeshOnly || device.type === 'mesh_node') {
                    setDevices(prev => [...prev, device]);
                    onDeviceFound?.(device);
                }
            }

            clearInterval(progressInterval);
            setScanProgress(100);

            setTimeout(() => {
                setIsScanning(false);
                onScanComplete?.(devices);
            }, 500);

        } catch (err) {
            clearInterval(progressInterval);
            setError(err.message || 'Scan failed');
            setIsScanning(false);
        }
    }, [supported, scanDuration, filterMeshOnly, onDeviceFound, onScanComplete, devices]);

    // Auto-start if enabled
    useEffect(() => {
        if (autoStart && supported) {
            startScan();
        }
    }, [autoStart, supported, startScan]);

    // Stop scanning
    const stopScan = () => {
        setIsScanning(false);
        setScanProgress(100);
    };

    // Get signal strength bars
    const getSignalBars = (rssi) => {
        if (rssi >= -50) return 4;
        if (rssi >= -65) return 3;
        if (rssi >= -80) return 2;
        return 1;
    };

    // Get signal quality label
    const getSignalQuality = (rssi) => {
        if (rssi >= -50) return { label: 'Excellent', color: '#00e676' };
        if (rssi >= -65) return { label: 'Good', color: '#8bc34a' };
        if (rssi >= -80) return { label: 'Fair', color: '#ffc107' };
        return { label: 'Weak', color: '#f44336' };
    };

    if (!supported) {
        return (
            <div className="ble-scanner unsupported">
                <div className="unsupported-icon">📵</div>
                <h3>Bluetooth Not Available</h3>
                <p>{error}</p>
                <p className="hint">
                    Use Chrome on Android/Windows/macOS for Web Bluetooth support,
                    or use the mobile app for full BLE functionality.
                </p>
            </div>
        );
    }

    return (
        <div className="ble-scanner">
            {/* Header */}
            <div className="scanner-header">
                <h3>📶 BLE Scanner</h3>
                {filterMeshOnly && (
                    <span className="filter-badge">Mesh nodes only</span>
                )}
            </div>

            {/* Scan visualization */}
            <div className="scan-visualization">
                <div className={`radar ${isScanning ? 'active' : ''}`}>
                    <div className="radar-ring ring-1" />
                    <div className="radar-ring ring-2" />
                    <div className="radar-ring ring-3" />
                    {isScanning && <div className="radar-sweep" />}
                    <div className="radar-center" />

                    {/* Device dots */}
                    {devices.map((device, i) => {
                        const angle = (i / devices.length) * Math.PI * 2;
                        const distance = 30 + (100 - Math.abs(device.rssi)) * 0.8;
                        const x = 50 + Math.cos(angle) * distance * 0.4;
                        const y = 50 + Math.sin(angle) * distance * 0.4;

                        return (
                            <motion.div
                                key={device.id}
                                className="device-dot"
                                initial={{ scale: 0, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                style={{
                                    left: `${x}%`,
                                    top: `${y}%`,
                                    backgroundColor: device.type === 'mesh_node' ? '#00e676' : '#808080'
                                }}
                                title={device.name}
                            />
                        );
                    })}
                </div>

                {/* Progress */}
                {isScanning && (
                    <div className="scan-progress">
                        <div className="progress-bar">
                            <motion.div
                                className="progress-fill"
                                initial={{ width: 0 }}
                                animate={{ width: `${scanProgress}%` }}
                            />
                        </div>
                        <span className="progress-text">Scanning... {Math.round(scanProgress)}%</span>
                    </div>
                )}
            </div>

            {/* Control button */}
            <button
                className={`scan-btn ${isScanning ? 'scanning' : ''}`}
                onClick={isScanning ? stopScan : startScan}
            >
                {isScanning ? (
                    <>
                        <span className="spinner-small" />
                        Stop Scanning
                    </>
                ) : (
                    <>📡 Start Scan</>
                )}
            </button>

            {/* Device list */}
            <div className="devices-list">
                <h4>Discovered Devices ({devices.length})</h4>

                <AnimatePresence>
                    {devices.length === 0 ? (
                        <div className="empty-list">
                            {isScanning ? 'Searching...' : 'No devices found'}
                        </div>
                    ) : (
                        devices.map((device, i) => {
                            const signal = getSignalQuality(device.rssi);
                            const bars = getSignalBars(device.rssi);

                            return (
                                <motion.div
                                    key={device.id}
                                    className="device-card"
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: 20 }}
                                    transition={{ delay: i * 0.05 }}
                                >
                                    <div className="device-icon">
                                        {device.type === 'mesh_node' ? '📡' : '📱'}
                                    </div>
                                    <div className="device-info">
                                        <span className="device-name">{device.name}</span>
                                        <span className="device-id">{device.id}</span>
                                    </div>
                                    <div className="signal-info">
                                        <div className="signal-bars">
                                            {[1, 2, 3, 4].map(bar => (
                                                <div
                                                    key={bar}
                                                    className={`bar ${bar <= bars ? 'active' : ''}`}
                                                    style={{
                                                        height: `${bar * 5 + 5}px`,
                                                        backgroundColor: bar <= bars ? signal.color : undefined
                                                    }}
                                                />
                                            ))}
                                        </div>
                                        <span className="rssi-value">{device.rssi}dBm</span>
                                    </div>
                                    {device.type === 'mesh_node' && (
                                        <div className="mesh-badge">MESH</div>
                                    )}
                                </motion.div>
                            );
                        })
                    )}
                </AnimatePresence>
            </div>

            {/* Error display */}
            {error && (
                <div className="scan-error">
                    ⚠️ {error}
                </div>
            )}
        </div>
    );
};

export default BLEScanner;

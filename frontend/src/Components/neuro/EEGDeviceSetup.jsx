/**
 * EEG Device Setup Component
 * 
 * Component for pairing and managing EEG headset devices.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import React, { useState } from 'react';
import neuroFeedbackService from '../../services/neuroFeedbackService';
import './EEGDeviceSetup.css';

const DEVICE_TYPES = [
    { value: 'muse_2', label: 'Muse 2', icon: '🎧' },
    { value: 'muse_s', label: 'Muse S', icon: '🎧' },
    { value: 'neurosky', label: 'NeuroSky MindWave', icon: '🧠' },
    { value: 'openbci', label: 'OpenBCI', icon: '⚡' },
    { value: 'emotiv', label: 'Emotiv Insight', icon: '💫' },
    { value: 'other', label: 'Other Device', icon: '📟' },
];

const EEGDeviceSetup = ({ devices, onDevicesChange, onBack }) => {
    const [showAddDevice, setShowAddDevice] = useState(false);
    const [scanning, setScanning] = useState(false);
    const [calibrating, setCalibratingId] = useState(null);
    const [error, setError] = useState(null);

    // New device form
    const [newDevice, setNewDevice] = useState({
        deviceId: '',
        deviceType: 'muse_2',
        deviceName: '',
    });

    const handleScan = async () => {
        setScanning(true);
        setError(null);

        // Simulate Bluetooth scan
        setTimeout(() => {
            setScanning(false);
            setNewDevice(prev => ({
                ...prev,
                deviceId: `BT-${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
            }));
        }, 2000);
    };

    const handleRegister = async (e) => {
        e.preventDefault();

        if (!newDevice.deviceName || !newDevice.deviceId) {
            setError('Please provide device name and scan for device');
            return;
        }

        try {
            await neuroFeedbackService.registerDevice(
                newDevice.deviceId,
                newDevice.deviceType,
                newDevice.deviceName
            );

            setShowAddDevice(false);
            setNewDevice({ deviceId: '', deviceType: 'muse_2', deviceName: '' });
            onDevicesChange();
        } catch (err) {
            setError('Failed to register device');
        }
    };

    const handleCalibrate = async (deviceId) => {
        setCalibratingId(deviceId);

        try {
            await neuroFeedbackService.calibrateDevice(deviceId);
            // Calibration happens via WebSocket in real use
            setTimeout(() => {
                setCalibratingId(null);
                onDevicesChange();
            }, 3000);
        } catch (err) {
            setError('Calibration failed');
            setCalibratingId(null);
        }
    };

    const handleRemove = async (deviceId) => {
        if (!window.confirm('Remove this device?')) return;

        try {
            await neuroFeedbackService.removeDevice(deviceId);
            onDevicesChange();
        } catch (err) {
            setError('Failed to remove device');
        }
    };

    return (
        <div className="eeg-device-setup">
            <div className="setup-header">
                <button className="btn-back" onClick={onBack}>
                    ← Back to Dashboard
                </button>
                <h2>EEG Device Management</h2>
            </div>

            {error && (
                <div className="error-message">
                    <span>{error}</span>
                    <button onClick={() => setError(null)}>✕</button>
                </div>
            )}

            {/* Device List */}
            <div className="devices-section">
                <div className="section-header">
                    <h3>Paired Devices</h3>
                    <button
                        className="btn-add"
                        onClick={() => setShowAddDevice(true)}
                    >
                        + Add Device
                    </button>
                </div>

                {devices.length === 0 ? (
                    <div className="empty-devices">
                        <span className="empty-icon">🎧</span>
                        <p>No EEG devices paired yet</p>
                        <p className="hint">Pair an EEG headset to start brain training</p>
                    </div>
                ) : (
                    <div className="device-cards">
                        {devices.map(device => (
                            <div key={device.id} className={`device-card status-${device.status}`}>
                                <div className="device-icon">
                                    {DEVICE_TYPES.find(t => t.value === device.device_type)?.icon || '🧠'}
                                </div>

                                <div className="device-info">
                                    <h4>{device.device_name}</h4>
                                    <span className="device-type">{device.device_type_display}</span>
                                    <div className="device-meta">
                                        <span className={`status-badge ${device.status}`}>
                                            {device.status}
                                        </span>
                                        {device.is_calibrated && (
                                            <span className="calibrated-badge">✓ Calibrated</span>
                                        )}
                                    </div>
                                </div>

                                <div className="device-actions">
                                    <button
                                        className="btn-calibrate"
                                        onClick={() => handleCalibrate(device.id)}
                                        disabled={calibrating === device.id}
                                    >
                                        {calibrating === device.id ? (
                                            <span className="spinner">⟳</span>
                                        ) : (
                                            'Calibrate'
                                        )}
                                    </button>
                                    <button
                                        className="btn-remove"
                                        onClick={() => handleRemove(device.id)}
                                    >
                                        Remove
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add Device Modal */}
            {showAddDevice && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h3>Add New EEG Device</h3>

                        <form onSubmit={handleRegister}>
                            <div className="form-group">
                                <label>Device Type</label>
                                <select
                                    value={newDevice.deviceType}
                                    onChange={(e) => setNewDevice(prev => ({
                                        ...prev,
                                        deviceType: e.target.value
                                    }))}
                                >
                                    {DEVICE_TYPES.map(type => (
                                        <option key={type.value} value={type.value}>
                                            {type.icon} {type.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Device Name</label>
                                <input
                                    type="text"
                                    placeholder="e.g., My Muse Headband"
                                    value={newDevice.deviceName}
                                    onChange={(e) => setNewDevice(prev => ({
                                        ...prev,
                                        deviceName: e.target.value
                                    }))}
                                />
                            </div>

                            <div className="form-group">
                                <label>Device ID</label>
                                <div className="scan-group">
                                    <input
                                        type="text"
                                        placeholder="Scan to detect..."
                                        value={newDevice.deviceId}
                                        readOnly
                                    />
                                    <button
                                        type="button"
                                        className="btn-scan"
                                        onClick={handleScan}
                                        disabled={scanning}
                                    >
                                        {scanning ? 'Scanning...' : '🔍 Scan'}
                                    </button>
                                </div>
                            </div>

                            <div className="modal-actions">
                                <button
                                    type="button"
                                    className="btn-cancel"
                                    onClick={() => setShowAddDevice(false)}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn-primary"
                                    disabled={!newDevice.deviceName || !newDevice.deviceId}
                                >
                                    Pair Device
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Supported Devices Info */}
            <div className="supported-devices">
                <h3>Supported Devices</h3>
                <div className="device-support-grid">
                    {DEVICE_TYPES.slice(0, -1).map(type => (
                        <div key={type.value} className="supported-device">
                            <span className="device-icon">{type.icon}</span>
                            <span className="device-name">{type.label}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default EEGDeviceSetup;

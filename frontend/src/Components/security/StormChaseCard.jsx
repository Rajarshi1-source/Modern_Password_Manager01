/**
 * Storm Chase Card Component
 * ==========================
 * 
 * Displays Storm Chase Mode status and active storm alerts.
 * Shows hurricane/storm conditions for maximum entropy harvesting!
 * 
 * "During hurricanes, buoys have MAXIMUM entropy!" 🌀
 * 
 * @author Password Manager Team
 * @created 2026-01-30
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import './StormChaseCard.css';

const API_URL = import.meta.env.VITE_API_URL || '';
const API_BASE = `${API_URL}/api/security/ocean`;

// Severity badge colors
const severityColors = {
    none: '#6b7280',
    storm: '#f59e0b',
    severe: '#ef4444',
    extreme: '#dc2626',
};

const severityEmoji = {
    none: '🌊',
    storm: '⚠️',
    severe: '🌊',
    extreme: '🌀',
};

const StormChaseCard = ({ onStormStatusChange }) => {
    const [stormStatus, setStormStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isScanning, setIsScanning] = useState(false);

    // Fetch storm status
    const fetchStormStatus = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE}/storms/status/`);
            setStormStatus(response.data);
            setError(null);

            // Notify parent of storm status change
            if (onStormStatusChange) {
                onStormStatusChange(response.data);
            }
        } catch (err) {
            console.error('Failed to fetch storm status:', err);
            setError('Failed to load storm data');
        } finally {
            setLoading(false);
        }
    }, [onStormStatusChange]);

    // Manual storm scan
    const scanForStorms = async () => {
        setIsScanning(true);
        try {
            await axios.post(`${API_BASE}/storms/scan/`);
            await fetchStormStatus();
        } catch (err) {
            console.error('Storm scan failed:', err);
            setError('Storm scan failed');
        } finally {
            setIsScanning(false);
        }
    };

    // Initial fetch and polling
    useEffect(() => {
        fetchStormStatus();
        const interval = setInterval(fetchStormStatus, 60000); // Poll every minute
        return () => clearInterval(interval);
    }, [fetchStormStatus]);

    if (loading) {
        return (
            <div className="storm-chase-card storm-chase-loading">
                <div className="storm-loading-spinner">
                    <span className="storm-icon-spinning">🌀</span>
                </div>
                <p>Scanning for storms...</p>
            </div>
        );
    }

    const isActive = stormStatus?.is_active;
    const severity = stormStatus?.most_severe || 'none';
    const stormAlerts = stormStatus?.storm_alerts || [];

    return (
        <motion.div
            className={`storm-chase-card ${isActive ? 'storm-active' : ''} storm-severity-${severity}`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
        >
            {/* Header */}
            <div className="storm-chase-header">
                <div className="storm-title-section">
                    <motion.span
                        className={`storm-icon ${isActive ? 'storm-icon-spinning' : ''}`}
                        animate={isActive ? { rotate: 360 } : {}}
                        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                    >
                        {severityEmoji[severity]}
                    </motion.span>
                    <div>
                        <h3 className="storm-chase-title">Storm Chase Mode</h3>
                        <p className="storm-chase-subtitle">
                            {isActive
                                ? "🔥 MAXIMUM ENTROPY AVAILABLE!"
                                : "Monitoring for storm conditions"}
                        </p>
                    </div>
                </div>

                <button
                    className={`storm-scan-btn ${isScanning ? 'scanning' : ''}`}
                    onClick={scanForStorms}
                    disabled={isScanning}
                >
                    {isScanning ? '🔄' : '📡'} {isScanning ? 'Scanning...' : 'Scan'}
                </button>
            </div>

            {/* Status Indicator */}
            <div className={`storm-status-indicator ${isActive ? 'active' : 'inactive'}`}>
                <div className="status-dot"></div>
                <span className="status-text">
                    {isActive
                        ? `${stormAlerts.length} Active Storm${stormAlerts.length !== 1 ? 's' : ''} Detected`
                        : 'No Active Storms'}
                </span>
                {isActive && (
                    <span className="entropy-bonus-badge">
                        +{((stormStatus?.max_entropy_bonus || 0) * 100).toFixed(0)}% Entropy
                    </span>
                )}
            </div>

            {/* Message */}
            {stormStatus?.message && (
                <motion.p
                    className="storm-message"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    key={stormStatus.message}
                >
                    {stormStatus.message}
                </motion.p>
            )}

            {/* Active Storm Alerts */}
            <AnimatePresence>
                {isActive && stormAlerts.length > 0 && (
                    <motion.div
                        className="storm-alerts-section"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                    >
                        <h4 className="alerts-title">⚡ Active Storm Alerts</h4>
                        <div className="storm-alerts-list">
                            {stormAlerts.slice(0, 5).map((alert, idx) => (
                                <motion.div
                                    key={alert.buoy_id}
                                    className={`storm-alert-item severity-${alert.severity}`}
                                    initial={{ x: -20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    transition={{ delay: idx * 0.1 }}
                                >
                                    <div className="alert-buoy-info">
                                        <span className="alert-severity-icon">
                                            {severityEmoji[alert.severity]}
                                        </span>
                                        <div>
                                            <span className="alert-buoy-name">{alert.buoy_name}</span>
                                            <span className="alert-region">{alert.region}</span>
                                        </div>
                                    </div>

                                    <div className="alert-conditions">
                                        {alert.wave_height_m && (
                                            <span className="condition-badge wave">
                                                🌊 {alert.wave_height_m.toFixed(1)}m
                                            </span>
                                        )}
                                        {alert.wind_speed_mps && (
                                            <span className="condition-badge wind">
                                                💨 {alert.wind_speed_mps.toFixed(1)}m/s
                                            </span>
                                        )}
                                        {alert.pressure_hpa && (
                                            <span className="condition-badge pressure">
                                                📊 {alert.pressure_hpa.toFixed(0)}hPa
                                            </span>
                                        )}
                                    </div>

                                    <div className="alert-bonus">
                                        <span
                                            className="severity-badge"
                                            style={{ backgroundColor: severityColors[alert.severity] }}
                                        >
                                            {alert.severity_label}
                                        </span>
                                        <span className="bonus-text">
                                            +{(alert.entropy_bonus * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </motion.div>
                            ))}
                        </div>

                        {stormAlerts.length > 5 && (
                            <p className="more-alerts-text">
                                +{stormAlerts.length - 5} more storm alert(s)
                            </p>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Regions Affected */}
            {isActive && stormStatus?.regions_affected?.length > 0 && (
                <div className="regions-affected">
                    <span className="regions-label">Regions:</span>
                    {stormStatus.regions_affected.map(region => (
                        <span key={region} className="region-tag">
                            📍 {region}
                        </span>
                    ))}
                </div>
            )}

            {/* Last Scan Time */}
            {stormStatus?.last_scan && (
                <p className="last-scan-time">
                    Last scan: {new Date(stormStatus.last_scan).toLocaleTimeString()}
                </p>
            )}

            {/* Error message */}
            {error && (
                <div className="storm-error">
                    ⚠️ {error}
                </div>
            )}
        </motion.div>
    );
};

export default StormChaseCard;

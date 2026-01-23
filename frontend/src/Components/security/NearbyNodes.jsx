/**
 * Nearby Nodes Component
 * =======================
 * 
 * Lists and manages nearby mesh nodes.
 * Shows node status, trust scores, and fragment capacity.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './NearbyNodes.css';

const API_BASE = '/api/mesh';

const NearbyNodes = ({ onNodeSelect, radiusKm = 10 }) => {
    const [nodes, setNodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [scanning, setScanning] = useState(false);
    const [userLocation, setUserLocation] = useState(null);
    const [filter, setFilter] = useState('all'); // all, online, available

    // Get user location
    useEffect(() => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setUserLocation({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    });
                },
                (error) => console.error('Geolocation error:', error)
            );
        }
    }, []);

    // Fetch nearby nodes
    const fetchNodes = useCallback(async () => {
        if (!userLocation) return;

        setScanning(true);
        try {
            const response = await fetch(
                `${API_BASE}/nodes/nearby/?lat=${userLocation.lat}&lon=${userLocation.lng}&radius=${radiusKm}`,
                {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    }
                }
            );
            const data = await response.json();
            setNodes(data.nodes || []);
        } catch (error) {
            console.error('Failed to fetch nodes:', error);
        } finally {
            setLoading(false);
            setScanning(false);
        }
    }, [userLocation, radiusKm]);

    useEffect(() => {
        fetchNodes();
    }, [fetchNodes]);

    // Filter nodes
    const filteredNodes = nodes.filter(node => {
        if (filter === 'online') return node.is_online;
        if (filter === 'available') return node.is_online && node.is_available_for_storage;
        return true;
    });

    // Get signal strength indicator
    const getSignalStrength = (rssi) => {
        if (rssi >= -50) return { bars: 4, label: 'Excellent' };
        if (rssi >= -65) return { bars: 3, label: 'Good' };
        if (rssi >= -80) return { bars: 2, label: 'Fair' };
        return { bars: 1, label: 'Weak' };
    };

    // Get trust color
    const getTrustColor = (score) => {
        if (score >= 0.8) return '#00e676';
        if (score >= 0.5) return '#ffc107';
        return '#f44336';
    };

    if (loading) {
        return (
            <div className="nearby-nodes loading">
                <div className="spinner" />
                <p>Finding nearby nodes...</p>
            </div>
        );
    }

    return (
        <div className="nearby-nodes">
            {/* Header */}
            <div className="nodes-header">
                <h3>📡 Nearby Mesh Nodes</h3>
                <button
                    className="refresh-btn"
                    onClick={fetchNodes}
                    disabled={scanning}
                >
                    {scanning ? '...' : '🔄'}
                </button>
            </div>

            {/* Stats */}
            <div className="nodes-stats">
                <div className="stat">
                    <span className="stat-value">{nodes.length}</span>
                    <span className="stat-label">Total</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{nodes.filter(n => n.is_online).length}</span>
                    <span className="stat-label">Online</span>
                </div>
                <div className="stat">
                    <span className="stat-value">
                        {nodes.filter(n => n.is_online && n.is_available_for_storage).length}
                    </span>
                    <span className="stat-label">Available</span>
                </div>
            </div>

            {/* Filter */}
            <div className="nodes-filter">
                {['all', 'online', 'available'].map(f => (
                    <button
                        key={f}
                        className={`filter-btn ${filter === f ? 'active' : ''}`}
                        onClick={() => setFilter(f)}
                    >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
            </div>

            {/* Nodes List */}
            <div className="nodes-list">
                <AnimatePresence>
                    {filteredNodes.length === 0 ? (
                        <div className="empty-state">
                            <span className="empty-icon">📭</span>
                            <p>No nodes found</p>
                        </div>
                    ) : (
                        filteredNodes.map((node, index) => {
                            const signal = getSignalStrength(node.rssi || -70);
                            return (
                                <motion.div
                                    key={node.id}
                                    className={`node-card ${node.is_online ? 'online' : 'offline'}`}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -20 }}
                                    transition={{ delay: index * 0.05 }}
                                    onClick={() => onNodeSelect?.(node)}
                                >
                                    <div className="node-main">
                                        <div className="node-status">
                                            <span className={`status-dot ${node.is_online ? 'online' : 'offline'}`} />
                                        </div>
                                        <div className="node-info">
                                            <span className="node-name">{node.device_name}</span>
                                            <span className="node-type">{node.device_type}</span>
                                        </div>
                                        <div className="signal-bars">
                                            {[1, 2, 3, 4].map(bar => (
                                                <div
                                                    key={bar}
                                                    className={`bar ${bar <= signal.bars ? 'active' : ''}`}
                                                    style={{ height: `${bar * 4 + 4}px` }}
                                                />
                                            ))}
                                        </div>
                                    </div>

                                    <div className="node-details">
                                        <div className="detail-item">
                                            <span className="detail-label">Trust</span>
                                            <span
                                                className="detail-value trust"
                                                style={{ color: getTrustColor(node.trust_score) }}
                                            >
                                                {Math.round(node.trust_score * 100)}%
                                            </span>
                                        </div>
                                        <div className="detail-item">
                                            <span className="detail-label">Capacity</span>
                                            <span className="detail-value">
                                                {node.current_fragment_count}/{node.max_fragments}
                                            </span>
                                        </div>
                                        <div className="detail-item">
                                            <span className="detail-label">Last Seen</span>
                                            <span className="detail-value">
                                                {new Date(node.last_seen).toLocaleTimeString()}
                                            </span>
                                        </div>
                                    </div>

                                    {node.is_available_for_storage && (
                                        <div className="available-badge">
                                            ✓ Available for storage
                                        </div>
                                    )}
                                </motion.div>
                            );
                        })
                    )}
                </AnimatePresence>
            </div>

            {/* My Nodes Section */}
            <div className="my-nodes-section">
                <h4>🖥️ Register as Node</h4>
                <p>Turn this device into a mesh node to help others share passwords securely.</p>
                <button className="register-btn">
                    + Register This Device
                </button>
            </div>
        </div>
    );
};

export default NearbyNodes;

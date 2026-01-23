/**
 * Fragment Distribution Component
 * =================================
 * 
 * Visualizes the distribution status of fragments across mesh nodes.
 * Shows which nodes have which fragments and their availability.
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import './FragmentDistribution.css';

const API_BASE = '/api/mesh';

const FragmentDistribution = ({ deadDropId, onRefresh }) => {
    const [status, setStatus] = useState(null);
    const [fragments, setFragments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [redistributing, setRedistributing] = useState(false);

    // Fetch distribution status
    useEffect(() => {
        if (!deadDropId) return;

        const fetchStatus = async () => {
            try {
                const response = await fetch(`${API_BASE}/deaddrops/${deadDropId}/`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    }
                });
                const data = await response.json();
                setStatus(data.distribution_status);
                setFragments(data.fragments || []);
            } catch (error) {
                console.error('Failed to fetch distribution status:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 30000); // Refresh every 30s
        return () => clearInterval(interval);
    }, [deadDropId]);

    // Handle redistribution
    const handleRedistribute = async () => {
        setRedistributing(true);
        try {
            const response = await fetch(`${API_BASE}/deaddrops/${deadDropId}/distribute/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            const data = await response.json();

            if (data.status) {
                setStatus(data.status);
            }

            if (onRefresh) onRefresh();
        } catch (error) {
            console.error('Failed to redistribute:', error);
        } finally {
            setRedistributing(false);
        }
    };

    if (loading) {
        return (
            <div className="fragment-distribution loading">
                <div className="spinner" />
                <p>Loading distribution status...</p>
            </div>
        );
    }

    if (!status) {
        return (
            <div className="fragment-distribution empty">
                <p>No distribution data available</p>
            </div>
        );
    }

    const healthColor = status.health === 'good' ? '#00e676' : '#ffc107';
    const availablePercent = (status.available / status.total_fragments) * 100;

    return (
        <div className="fragment-distribution">
            {/* Header */}
            <div className="distrib-header">
                <h3>📡 Fragment Distribution</h3>
                <div
                    className="health-indicator"
                    style={{ backgroundColor: `${healthColor}20`, borderColor: `${healthColor}50` }}
                >
                    <span
                        className="health-dot"
                        style={{ backgroundColor: healthColor }}
                    />
                    <span style={{ color: healthColor }}>{status.health.toUpperCase()}</span>
                </div>
            </div>

            {/* Progress bar */}
            <div className="distrib-progress">
                <div className="progress-bar">
                    <motion.div
                        className="progress-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${availablePercent}%` }}
                        transition={{ duration: 0.5 }}
                        style={{ backgroundColor: healthColor }}
                    />
                </div>
                <span className="progress-text">
                    {status.available}/{status.total_fragments} available
                </span>
            </div>

            {/* Stats grid */}
            <div className="distrib-stats">
                <div className="stat-card">
                    <span className="stat-icon">📦</span>
                    <div className="stat-content">
                        <span className="stat-value">{status.distributed}</span>
                        <span className="stat-label">Distributed</span>
                    </div>
                </div>
                <div className="stat-card">
                    <span className="stat-icon">✅</span>
                    <div className="stat-content">
                        <span className="stat-value">{status.available}</span>
                        <span className="stat-label">Available</span>
                    </div>
                </div>
                <div className="stat-card">
                    <span className="stat-icon">📥</span>
                    <div className="stat-content">
                        <span className="stat-value">{status.collected}</span>
                        <span className="stat-label">Collected</span>
                    </div>
                </div>
                <div className="stat-card">
                    <span className="stat-icon">🖥️</span>
                    <div className="stat-content">
                        <span className="stat-value">{status.nodes_online}/{status.nodes_used}</span>
                        <span className="stat-label">Nodes Online</span>
                    </div>
                </div>
            </div>

            {/* Threshold info */}
            <div className="threshold-info">
                <span className="threshold-icon">🔐</span>
                <span>
                    Need <strong>{status.required_fragments}</strong> of{' '}
                    <strong>{status.total_fragments}</strong> fragments to reconstruct
                </span>
            </div>

            {/* Fragment grid */}
            <div className="fragments-grid">
                {fragments.map((fragment, i) => (
                    <motion.div
                        key={i}
                        className={`fragment-tile ${fragment.is_available ? 'available' : ''} ${fragment.is_collected ? 'collected' : ''}`}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: i * 0.05 }}
                    >
                        <span className="fragment-index">{fragment.index}</span>
                        <span className="fragment-status">
                            {fragment.is_collected ? '✓' : fragment.is_available ? '●' : '○'}
                        </span>
                        {fragment.node_name && (
                            <span className="fragment-node">{fragment.node_name}</span>
                        )}
                    </motion.div>
                ))}
            </div>

            {/* Actions */}
            {status.health === 'degraded' && (
                <button
                    className="redistribute-btn"
                    onClick={handleRedistribute}
                    disabled={redistributing}
                >
                    {redistributing ? (
                        <>
                            <span className="spinner-small" />
                            Redistributing...
                        </>
                    ) : (
                        <>🔄 Redistribute Fragments</>
                    )}
                </button>
            )}
        </div>
    );
};

export default FragmentDistribution;

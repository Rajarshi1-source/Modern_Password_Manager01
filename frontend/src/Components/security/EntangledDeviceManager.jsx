/**
 * EntangledDeviceManager.jsx
 * 
 * Main dashboard for managing quantum entangled device pairs.
 * Features:
 * - List paired devices with sync status
 * - Visual entropy health indicator
 * - One-click instant revocation
 * - Pairing initiation
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Shield,
    Link,
    Unlink,
    RefreshCw,
    AlertTriangle,
    CheckCircle,
    Clock,
    Zap,
    Activity,
    Plus,
    ChevronRight,
    Lock,
    Unlock
} from 'lucide-react';
import DevicePairingFlow from './DevicePairingFlow';
import EntropyHealthCard from './EntropyHealthCard';
import InstantRevokeModal from './InstantRevokeModal';
import './EntangledDeviceManager.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const EntangledDeviceManager = () => {
    const [pairs, setPairs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showPairingFlow, setShowPairingFlow] = useState(false);
    const [selectedPair, setSelectedPair] = useState(null);
    const [showRevokeModal, setShowRevokeModal] = useState(false);
    const [maxPairs, setMaxPairs] = useState(5);

    // Fetch user's entangled pairs
    const fetchPairs = useCallback(async () => {
        try {
            setLoading(true);
            const response = await fetch(`${API_BASE_URL}/api/security/entanglement/pairs/`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) throw new Error('Failed to fetch pairs');

            const data = await response.json();
            setPairs(data.pairs || []);
            setMaxPairs(data.max_allowed || 5);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPairs();
    }, [fetchPairs]);

    // Rotate keys for a pair
    const handleRotateKeys = async (pairId, deviceId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/security/entanglement/rotate/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    pair_id: pairId,
                    device_id: deviceId,
                }),
            });

            if (!response.ok) throw new Error('Failed to rotate keys');

            fetchPairs();
        } catch (err) {
            setError(err.message);
        }
    };

    // Open revocation modal
    const handleRevokeClick = (pair) => {
        setSelectedPair(pair);
        setShowRevokeModal(true);
    };

    // Handle successful revocation
    const handleRevocationComplete = () => {
        setShowRevokeModal(false);
        setSelectedPair(null);
        fetchPairs();
    };

    // Handle successful pairing
    const handlePairingComplete = () => {
        setShowPairingFlow(false);
        fetchPairs();
    };

    // Get status badge
    const getStatusBadge = (status) => {
        const statusConfig = {
            active: { color: 'green', icon: CheckCircle, label: 'Active' },
            pending: { color: 'yellow', icon: Clock, label: 'Pending' },
            suspended: { color: 'orange', icon: AlertTriangle, label: 'Suspended' },
            revoked: { color: 'red', icon: Unlink, label: 'Revoked' },
        };

        const config = statusConfig[status] || statusConfig.pending;
        const Icon = config.icon;

        return (
            <span className={`status-badge status-${config.color}`}>
                <Icon size={14} />
                {config.label}
            </span>
        );
    };

    // Get entropy status color
    const getEntropyColor = (health) => {
        if (health === 'healthy') return 'green';
        if (health === 'degraded') return 'yellow';
        return 'red';
    };

    if (loading) {
        return (
            <div className="entanglement-manager loading">
                <div className="loading-spinner">
                    <Zap className="spinning" size={48} />
                    <p>Loading entangled devices...</p>
                </div>
            </div>
        );
    }

    if (showPairingFlow) {
        return (
            <DevicePairingFlow
                onComplete={handlePairingComplete}
                onCancel={() => setShowPairingFlow(false)}
            />
        );
    }

    return (
        <div className="entanglement-manager">
            {/* Header */}
            <div className="manager-header">
                <div className="header-title">
                    <Link size={32} className="header-icon" />
                    <div>
                        <h1>Quantum Entangled Devices</h1>
                        <p>Manage device pairs with synchronized cryptographic keys</p>
                    </div>
                </div>

                <button
                    className="btn-primary"
                    onClick={() => setShowPairingFlow(true)}
                    disabled={pairs.filter(p => p.status === 'active').length >= maxPairs}
                >
                    <Plus size={20} />
                    Pair New Devices
                </button>
            </div>

            {/* Error Alert */}
            {error && (
                <div className="error-alert">
                    <AlertTriangle size={20} />
                    <span>{error}</span>
                    <button onClick={() => setError(null)}>Dismiss</button>
                </div>
            )}

            {/* Stats Overview */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon blue">
                        <Link size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{pairs.filter(p => p.status === 'active').length}</span>
                        <span className="stat-label">Active Pairs</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon green">
                        <Shield size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">{maxPairs}</span>
                        <span className="stat-label">Max Allowed</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon purple">
                        <Activity size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-value">
                            {pairs.filter(p => p.entropy_health === 'healthy').length}
                        </span>
                        <span className="stat-label">Healthy</span>
                    </div>
                </div>
            </div>

            {/* Pairs List */}
            <div className="pairs-list">
                <h2>Your Entangled Pairs</h2>

                {pairs.length === 0 ? (
                    <div className="empty-state">
                        <Zap size={64} className="empty-icon" />
                        <h3>No Entangled Devices</h3>
                        <p>Pair two devices to create quantum-inspired synchronized keys</p>
                        <button
                            className="btn-primary"
                            onClick={() => setShowPairingFlow(true)}
                        >
                            <Plus size={20} />
                            Start Pairing
                        </button>
                    </div>
                ) : (
                    <div className="pairs-grid">
                        {pairs.map((pair) => (
                            <div key={pair.pair_id} className={`pair-card status-${pair.status}`}>
                                {/* Card Header */}
                                <div className="pair-header">
                                    <div className="pair-devices">
                                        <span className="device-name">{pair.device_a_name || 'Device A'}</span>
                                        <Link size={16} className="link-icon" />
                                        <span className="device-name">{pair.device_b_name || 'Device B'}</span>
                                    </div>
                                    {getStatusBadge(pair.status)}
                                </div>

                                {/* Entropy Health */}
                                <EntropyHealthCard
                                    health={pair.entropy_health}
                                    score={pair.entropy_score}
                                    generation={pair.current_generation}
                                    compact={true}
                                />

                                {/* Last Sync */}
                                <div className="pair-info">
                                    <div className="info-item">
                                        <Clock size={14} />
                                        <span>
                                            Last sync: {pair.last_sync_at
                                                ? new Date(pair.last_sync_at).toLocaleString()
                                                : 'Never'}
                                        </span>
                                    </div>
                                    <div className="info-item">
                                        <RefreshCw size={14} />
                                        <span>Generation: {pair.current_generation}</span>
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="pair-actions">
                                    {pair.status === 'active' && (
                                        <>
                                            <button
                                                className="btn-secondary"
                                                onClick={() => handleRotateKeys(pair.pair_id, pair.device_a_id)}
                                                title="Rotate Keys"
                                            >
                                                <RefreshCw size={16} />
                                                Rotate
                                            </button>
                                            <button
                                                className="btn-danger"
                                                onClick={() => handleRevokeClick(pair)}
                                                title="Revoke Pairing"
                                            >
                                                <Unlink size={16} />
                                                Revoke
                                            </button>
                                        </>
                                    )}
                                    <button
                                        className="btn-ghost"
                                        onClick={() => setSelectedPair(pair)}
                                        title="View Details"
                                    >
                                        <ChevronRight size={16} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Revoke Modal */}
            {showRevokeModal && selectedPair && (
                <InstantRevokeModal
                    pair={selectedPair}
                    onConfirm={handleRevocationComplete}
                    onCancel={() => {
                        setShowRevokeModal(false);
                        setSelectedPair(null);
                    }}
                />
            )}
        </div>
    );
};

export default EntangledDeviceManager;

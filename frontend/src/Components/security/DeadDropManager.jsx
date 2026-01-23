/**
 * Dead Drop Manager Component
 * ============================
 * 
 * Dashboard for managing mesh dead drop password sharing.
 * Lists all dead drops, shows status, and allows collection.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './DeadDropManager.css';

const API_BASE = '/api/mesh';

const DeadDropManager = () => {
    const [deadDrops, setDeadDrops] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedDrop, setSelectedDrop] = useState(null);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [filter, setFilter] = useState('all');

    // Fetch dead drops
    const fetchDeadDrops = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/deaddrops/`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            const data = await response.json();
            setDeadDrops(data.dead_drops || []);
        } catch (error) {
            console.error('Failed to fetch dead drops:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDeadDrops();
    }, [fetchDeadDrops]);

    // Filter dead drops
    const filteredDrops = deadDrops.filter(drop => {
        if (filter === 'all') return true;
        return drop.status === filter;
    });

    // Get status badge color
    const getStatusColor = (status) => {
        const colors = {
            pending: '#ffc107',
            distributed: '#17a2b8',
            active: '#28a745',
            collected: '#6c757d',
            expired: '#dc3545',
            cancelled: '#343a40'
        };
        return colors[status] || '#6c757d';
    };

    // Format time remaining
    const formatTimeRemaining = (seconds) => {
        if (seconds <= 0) return 'Expired';

        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);

        if (days > 0) return `${days}d ${hours}h`;

        const minutes = Math.floor((seconds % 3600) / 60);
        if (hours > 0) return `${hours}h ${minutes}m`;

        return `${minutes}m`;
    };

    if (loading) {
        return (
            <div className="deaddrop-manager loading">
                <div className="spinner" />
                <p>Loading dead drops...</p>
            </div>
        );
    }

    return (
        <div className="deaddrop-manager">
            {/* Header */}
            <div className="manager-header">
                <div className="header-left">
                    <h1>📡 Dead Drop Manager</h1>
                    <p>Secure offline password sharing via mesh networks</p>
                </div>
                <button
                    className="create-btn"
                    onClick={() => setShowCreateModal(true)}
                >
                    + Create Dead Drop
                </button>
            </div>

            {/* Filters */}
            <div className="filter-bar">
                {['all', 'active', 'pending', 'collected', 'expired'].map(f => (
                    <button
                        key={f}
                        className={`filter-btn ${filter === f ? 'active' : ''}`}
                        onClick={() => setFilter(f)}
                    >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
            </div>

            {/* Dead Drops List */}
            <div className="drops-grid">
                {filteredDrops.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">📭</span>
                        <h3>No Dead Drops</h3>
                        <p>Create your first dead drop to share passwords securely</p>
                    </div>
                ) : (
                    filteredDrops.map(drop => (
                        <motion.div
                            key={drop.id}
                            className="drop-card"
                            layoutId={drop.id}
                            onClick={() => setSelectedDrop(drop)}
                            whileHover={{ scale: 1.02 }}
                        >
                            <div className="card-header">
                                <span className="drop-icon">📡</span>
                                <span
                                    className="status-badge"
                                    style={{ backgroundColor: getStatusColor(drop.status) }}
                                >
                                    {drop.status.toUpperCase()}
                                </span>
                            </div>

                            <h3 className="drop-title">{drop.title}</h3>

                            <div className="drop-info">
                                <div className="info-item">
                                    <span className="label">🎯 Threshold</span>
                                    <span className="value">{drop.threshold_display}</span>
                                </div>
                                <div className="info-item">
                                    <span className="label">⏱️ Expires</span>
                                    <span className="value">
                                        {formatTimeRemaining(drop.time_remaining_seconds)}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="label">📍 Radius</span>
                                    <span className="value">{drop.radius_meters}m</span>
                                </div>
                            </div>

                            {drop.location_hint && (
                                <p className="location-hint">
                                    💡 {drop.location_hint}
                                </p>
                            )}

                            <div className="verification-badges">
                                {drop.require_ble_verification && (
                                    <span className="verify-badge ble">📶 BLE</span>
                                )}
                                {drop.require_nfc_tap && (
                                    <span className="verify-badge nfc">📱 NFC</span>
                                )}
                            </div>
                        </motion.div>
                    ))
                )}
            </div>

            {/* Create Modal */}
            <AnimatePresence>
                {showCreateModal && (
                    <CreateDeadDropModal
                        onClose={() => setShowCreateModal(false)}
                        onCreated={() => {
                            setShowCreateModal(false);
                            fetchDeadDrops();
                        }}
                    />
                )}
            </AnimatePresence>

            {/* Detail Modal */}
            <AnimatePresence>
                {selectedDrop && (
                    <DeadDropDetailModal
                        drop={selectedDrop}
                        onClose={() => setSelectedDrop(null)}
                        onUpdate={fetchDeadDrops}
                    />
                )}
            </AnimatePresence>
        </div>
    );
};

// Create Dead Drop Modal
const CreateDeadDropModal = ({ onClose, onCreated }) => {
    const [step, setStep] = useState(1);
    const [creating, setCreating] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        secret: '',
        latitude: '',
        longitude: '',
        radius_meters: 50,
        location_hint: '',
        required_fragments: 3,
        total_fragments: 5,
        expires_in_hours: 168,
        require_ble_verification: true,
        require_nfc_tap: false,
        recipient_email: ''
    });

    // Get current location
    const getCurrentLocation = () => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setFormData(prev => ({
                        ...prev,
                        latitude: position.coords.latitude.toFixed(6),
                        longitude: position.coords.longitude.toFixed(6)
                    }));
                },
                (error) => console.error('Geolocation error:', error)
            );
        }
    };

    const handleSubmit = async () => {
        setCreating(true);
        try {
            const response = await fetch(`${API_BASE}/deaddrops/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                onCreated();
            } else {
                const error = await response.json();
                alert('Failed to create dead drop: ' + JSON.stringify(error));
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            setCreating(false);
        }
    };

    return (
        <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <motion.div
                className="modal-content create-modal"
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
            >
                <div className="modal-header">
                    <h2>📡 Create Dead Drop</h2>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <div className="step-indicator">
                    {['Basic Info', 'Location', 'Security', 'Review'].map((name, i) => (
                        <div
                            key={i}
                            className={`step ${step === i + 1 ? 'active' : ''} ${step > i + 1 ? 'completed' : ''}`}
                        >
                            <span className="step-num">{i + 1}</span>
                            <span className="step-name">{name}</span>
                        </div>
                    ))}
                </div>

                <div className="modal-body">
                    {step === 1 && (
                        <div className="step-content">
                            <div className="form-group">
                                <label>Title</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="e.g., Emergency Access Codes"
                                />
                            </div>
                            <div className="form-group">
                                <label>Description (Optional)</label>
                                <textarea
                                    value={formData.description}
                                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="Brief description..."
                                />
                            </div>
                            <div className="form-group">
                                <label>Secret Data</label>
                                <textarea
                                    className="secret-input"
                                    value={formData.secret}
                                    onChange={e => setFormData({ ...formData, secret: e.target.value })}
                                    placeholder="Enter the secret password or data to share..."
                                />
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="step-content">
                            <div className="location-section">
                                <button
                                    className="location-btn"
                                    onClick={getCurrentLocation}
                                >
                                    📍 Use Current Location
                                </button>

                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Latitude</label>
                                        <input
                                            type="text"
                                            value={formData.latitude}
                                            onChange={e => setFormData({ ...formData, latitude: e.target.value })}
                                            placeholder="40.7128"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Longitude</label>
                                        <input
                                            type="text"
                                            value={formData.longitude}
                                            onChange={e => setFormData({ ...formData, longitude: e.target.value })}
                                            placeholder="-74.0060"
                                        />
                                    </div>
                                </div>

                                <div className="form-group">
                                    <label>Collection Radius (meters)</label>
                                    <input
                                        type="range"
                                        min="10"
                                        max="200"
                                        value={formData.radius_meters}
                                        onChange={e => setFormData({ ...formData, radius_meters: parseInt(e.target.value) })}
                                    />
                                    <span className="range-value">{formData.radius_meters}m</span>
                                </div>

                                <div className="form-group">
                                    <label>Location Hint</label>
                                    <input
                                        type="text"
                                        value={formData.location_hint}
                                        onChange={e => setFormData({ ...formData, location_hint: e.target.value })}
                                        placeholder="e.g., Behind the main fountain"
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="step-content">
                            <div className="threshold-section">
                                <h4>🔐 Shamir Threshold (3-of-5 recommended)</h4>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Required Fragments (k)</label>
                                        <input
                                            type="number"
                                            min="2"
                                            max="10"
                                            value={formData.required_fragments}
                                            onChange={e => setFormData({ ...formData, required_fragments: parseInt(e.target.value) })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Total Fragments (n)</label>
                                        <input
                                            type="number"
                                            min="2"
                                            max="20"
                                            value={formData.total_fragments}
                                            onChange={e => setFormData({ ...formData, total_fragments: parseInt(e.target.value) })}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="verification-section">
                                <h4>✓ Verification Requirements</h4>
                                <label className="checkbox-label">
                                    <input
                                        type="checkbox"
                                        checked={formData.require_ble_verification}
                                        onChange={e => setFormData({ ...formData, require_ble_verification: e.target.checked })}
                                    />
                                    <span>Require BLE beacon detection</span>
                                </label>
                                <label className="checkbox-label">
                                    <input
                                        type="checkbox"
                                        checked={formData.require_nfc_tap}
                                        onChange={e => setFormData({ ...formData, require_nfc_tap: e.target.checked })}
                                    />
                                    <span>Require NFC tap (optional)</span>
                                </label>
                            </div>

                            <div className="form-group">
                                <label>Expiration (hours)</label>
                                <select
                                    value={formData.expires_in_hours}
                                    onChange={e => setFormData({ ...formData, expires_in_hours: parseInt(e.target.value) })}
                                >
                                    <option value="24">24 hours</option>
                                    <option value="72">3 days</option>
                                    <option value="168">1 week</option>
                                    <option value="720">30 days</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Recipient Email (optional)</label>
                                <input
                                    type="email"
                                    value={formData.recipient_email}
                                    onChange={e => setFormData({ ...formData, recipient_email: e.target.value })}
                                    placeholder="recipient@example.com"
                                />
                            </div>
                        </div>
                    )}

                    {step === 4 && (
                        <div className="step-content review-content">
                            <h4>📋 Review Your Dead Drop</h4>
                            <div className="review-grid">
                                <div className="review-item">
                                    <span className="review-label">Title</span>
                                    <span className="review-value">{formData.title}</span>
                                </div>
                                <div className="review-item">
                                    <span className="review-label">Location</span>
                                    <span className="review-value">
                                        {formData.latitude}, {formData.longitude}
                                    </span>
                                </div>
                                <div className="review-item">
                                    <span className="review-label">Threshold</span>
                                    <span className="review-value">
                                        {formData.required_fragments}-of-{formData.total_fragments}
                                    </span>
                                </div>
                                <div className="review-item">
                                    <span className="review-label">Expires In</span>
                                    <span className="review-value">{formData.expires_in_hours} hours</span>
                                </div>
                                <div className="review-item">
                                    <span className="review-label">BLE Required</span>
                                    <span className="review-value">
                                        {formData.require_ble_verification ? 'Yes' : 'No'}
                                    </span>
                                </div>
                                <div className="review-item">
                                    <span className="review-label">NFC Required</span>
                                    <span className="review-value">
                                        {formData.require_nfc_tap ? 'Yes' : 'No'}
                                    </span>
                                </div>
                            </div>

                            <div className="warning-box">
                                ⚠️ The secret will be split into fragments and distributed to mesh nodes.
                                Make sure you've set the correct location!
                            </div>
                        </div>
                    )}
                </div>

                <div className="modal-footer">
                    {step > 1 && (
                        <button className="btn secondary" onClick={() => setStep(s => s - 1)}>
                            Back
                        </button>
                    )}

                    {step < 4 ? (
                        <button
                            className="btn primary"
                            onClick={() => setStep(s => s + 1)}
                            disabled={step === 1 && (!formData.title || !formData.secret)}
                        >
                            Next
                        </button>
                    ) : (
                        <button
                            className="btn primary"
                            onClick={handleSubmit}
                            disabled={creating}
                        >
                            {creating ? 'Creating...' : '🚀 Create Dead Drop'}
                        </button>
                    )}
                </div>
            </motion.div>
        </motion.div>
    );
};

// Dead Drop Detail Modal
const DeadDropDetailModal = ({ drop, onClose, onUpdate }) => {
    const [distribStatus, setDistribStatus] = useState(null);
    const [cancelling, setCancelling] = useState(false);

    useEffect(() => {
        // Fetch distribution status
        fetch(`${API_BASE}/deaddrops/${drop.id}/`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        })
            .then(r => r.json())
            .then(data => setDistribStatus(data.distribution_status))
            .catch(console.error);
    }, [drop.id]);

    const handleCancel = async () => {
        if (!window.confirm('Are you sure you want to cancel this dead drop?')) return;

        setCancelling(true);
        try {
            await fetch(`${API_BASE}/deaddrops/${drop.id}/cancel/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            onUpdate();
            onClose();
        } catch (error) {
            alert('Failed to cancel: ' + error.message);
        } finally {
            setCancelling(false);
        }
    };

    return (
        <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
        >
            <motion.div
                className="modal-content detail-modal"
                initial={{ y: 50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 50, opacity: 0 }}
                onClick={e => e.stopPropagation()}
            >
                <div className="modal-header">
                    <h2>📡 {drop.title}</h2>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <div className="modal-body">
                    <div className="detail-section">
                        <h4>Status</h4>
                        <span
                            className="status-badge large"
                            style={{ backgroundColor: drop.status === 'active' ? '#28a745' : '#6c757d' }}
                        >
                            {drop.status.toUpperCase()}
                        </span>
                    </div>

                    {distribStatus && (
                        <div className="detail-section">
                            <h4>Distribution Status</h4>
                            <div className="distrib-grid">
                                <div className="distrib-item">
                                    <span className="num">{distribStatus.distributed}</span>
                                    <span className="label">Distributed</span>
                                </div>
                                <div className="distrib-item">
                                    <span className="num">{distribStatus.available}</span>
                                    <span className="label">Available</span>
                                </div>
                                <div className="distrib-item">
                                    <span className="num">{distribStatus.nodes_online}</span>
                                    <span className="label">Nodes Online</span>
                                </div>
                            </div>
                            <div className={`health-badge ${distribStatus.health}`}>
                                {distribStatus.health === 'good' ? '✓ Healthy' : '⚠️ Degraded'}
                            </div>
                        </div>
                    )}

                    <div className="detail-section">
                        <h4>Location</h4>
                        <p>{drop.latitude}, {drop.longitude}</p>
                        {drop.location_hint && <p className="hint">💡 {drop.location_hint}</p>}
                    </div>

                    <div className="detail-section">
                        <h4>Security</h4>
                        <p>Threshold: {drop.threshold_display}</p>
                        <p>Radius: {drop.radius_meters}m</p>
                    </div>
                </div>

                {drop.status === 'active' && (
                    <div className="modal-footer">
                        <button
                            className="btn danger"
                            onClick={handleCancel}
                            disabled={cancelling}
                        >
                            {cancelling ? 'Cancelling...' : '❌ Cancel Dead Drop'}
                        </button>
                    </div>
                )}
            </motion.div>
        </motion.div>
    );
};

export default DeadDropManager;

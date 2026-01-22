/**
 * TimeLockManager Component
 * 
 * Main dashboard for managing time-lock capsules.
 * Shows locked secrets, countdowns, and actions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './TimeLockManager.css';

const TimeLockManager = ({
    authToken,
    onCapsuleClick,
    baseUrl = '/api/security'
}) => {
    const [capsules, setCapsules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('all');
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [stats, setStats] = useState({ locked: 0, unlocked: 0 });

    // Fetch capsules
    const fetchCapsules = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${baseUrl}/timelock/capsules/`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Failed to fetch capsules');

            const data = await response.json();
            setCapsules(data.capsules || []);
            setStats({
                locked: data.locked_count || 0,
                unlocked: data.unlocked_count || 0
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken, baseUrl]);

    useEffect(() => {
        fetchCapsules();
    }, [fetchCapsules]);

    // Update countdowns every second
    useEffect(() => {
        const interval = setInterval(() => {
            setCapsules(prev => prev.map(capsule => ({
                ...capsule,
                time_remaining_seconds: Math.max(0, capsule.time_remaining_seconds - 1)
            })));
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const formatTime = (seconds) => {
        if (seconds <= 0) return 'Ready';

        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${mins}m`;
        if (mins > 0) return `${mins}m ${secs}s`;
        return `${secs}s`;
    };

    const getStatusColor = (status) => {
        const colors = {
            locked: '#ff6b6b',
            solving: '#ffa500',
            unlocked: '#00e676',
            expired: '#808080',
            cancelled: '#444'
        };
        return colors[status] || '#fff';
    };

    const getTypeIcon = (type) => {
        const icons = {
            general: '🔐',
            will: '📜',
            escrow: '🤝',
            time_capsule: '⏳',
            emergency: '🚨'
        };
        return icons[type] || '🔒';
    };

    const filteredCapsules = capsules.filter(c => {
        if (activeTab === 'all') return true;
        if (activeTab === 'locked') return c.status === 'locked';
        if (activeTab === 'unlocked') return c.status === 'unlocked';
        if (activeTab === 'wills') return c.capsule_type === 'will';
        if (activeTab === 'escrows') return c.capsule_type === 'escrow';
        return true;
    });

    const handleUnlock = async (capsuleId) => {
        try {
            const response = await fetch(`${baseUrl}/timelock/capsules/${capsuleId}/unlock/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                }
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to unlock');
            }

            fetchCapsules();
        } catch (err) {
            alert(err.message);
        }
    };

    const handleCancel = async (capsuleId) => {
        if (!window.confirm('Cancel this capsule? This cannot be undone.')) return;

        try {
            const response = await fetch(`${baseUrl}/timelock/capsules/${capsuleId}/cancel/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Failed to cancel');

            fetchCapsules();
        } catch (err) {
            alert(err.message);
        }
    };

    if (loading) {
        return (
            <div className="timelock-manager loading">
                <div className="spinner"></div>
                <p>Loading time-lock capsules...</p>
            </div>
        );
    }

    return (
        <div className="timelock-manager">
            <div className="manager-header">
                <div className="header-content">
                    <h2>🔐 Time-Lock Vault</h2>
                    <p>Secrets locked in time</p>
                </div>
                <button
                    className="create-btn"
                    onClick={() => setShowCreateModal(true)}
                >
                    + Create Capsule
                </button>
            </div>

            <div className="stats-bar">
                <div className="stat">
                    <span className="value">{stats.locked}</span>
                    <span className="label">Locked</span>
                </div>
                <div className="stat">
                    <span className="value">{stats.unlocked}</span>
                    <span className="label">Unlocked</span>
                </div>
                <div className="stat">
                    <span className="value">{capsules.length}</span>
                    <span className="label">Total</span>
                </div>
            </div>

            <div className="tabs">
                {['all', 'locked', 'unlocked', 'wills', 'escrows'].map(tab => (
                    <button
                        key={tab}
                        className={`tab ${activeTab === tab ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab)}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}
            </div>

            {error && (
                <div className="error-message">
                    {error}
                    <button onClick={fetchCapsules}>Retry</button>
                </div>
            )}

            <div className="capsules-grid">
                {filteredCapsules.length === 0 ? (
                    <div className="empty-state">
                        <span className="icon">🔐</span>
                        <p>No capsules found</p>
                        <button onClick={() => setShowCreateModal(true)}>
                            Create your first capsule
                        </button>
                    </div>
                ) : (
                    filteredCapsules.map(capsule => (
                        <div
                            key={capsule.id}
                            className={`capsule-card ${capsule.status}`}
                            onClick={() => onCapsuleClick?.(capsule)}
                        >
                            <div className="card-header">
                                <span className="type-icon">{getTypeIcon(capsule.capsule_type)}</span>
                                <span
                                    className="status-badge"
                                    style={{ backgroundColor: getStatusColor(capsule.status) }}
                                >
                                    {capsule.status}
                                </span>
                            </div>

                            <h3 className="title">{capsule.title}</h3>
                            {capsule.description && (
                                <p className="description">{capsule.description}</p>
                            )}

                            {capsule.status === 'locked' && (
                                <div className="countdown">
                                    <div className="time-display">
                                        {formatTime(capsule.time_remaining_seconds)}
                                    </div>
                                    <div className="progress-bar">
                                        <div
                                            className="progress"
                                            style={{
                                                width: `${Math.max(0, (1 - capsule.time_remaining_seconds / capsule.delay_seconds) * 100)}%`
                                            }}
                                        />
                                    </div>
                                </div>
                            )}

                            {capsule.beneficiary_count > 0 && (
                                <div className="beneficiaries-badge">
                                    👥 {capsule.beneficiary_count} beneficiaries
                                </div>
                            )}

                            <div className="card-actions">
                                {capsule.is_ready_to_unlock && capsule.status === 'locked' && (
                                    <button
                                        className="btn unlock"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleUnlock(capsule.id);
                                        }}
                                    >
                                        🔓 Unlock
                                    </button>
                                )}
                                {capsule.status === 'locked' && !capsule.is_ready_to_unlock && (
                                    <button
                                        className="btn cancel"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleCancel(capsule.id);
                                        }}
                                    >
                                        ❌ Cancel
                                    </button>
                                )}
                                {capsule.status === 'unlocked' && (
                                    <button className="btn view">
                                        👁️ View Secret
                                    </button>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {showCreateModal && (
                <CreateCapsuleModal
                    authToken={authToken}
                    baseUrl={baseUrl}
                    onClose={() => setShowCreateModal(false)}
                    onCreated={() => {
                        setShowCreateModal(false);
                        fetchCapsules();
                    }}
                />
            )}
        </div>
    );
};

// Create Capsule Modal
const CreateCapsuleModal = ({ authToken, baseUrl, onClose, onCreated }) => {
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        secret_data: '',
        delay_seconds: 3600,
        mode: 'server',
        capsule_type: 'general'
    });
    const [creating, setCreating] = useState(false);

    const delayPresets = [
        { label: '1 hour', value: 3600 },
        { label: '24 hours', value: 86400 },
        { label: '7 days', value: 604800 },
        { label: '30 days', value: 2592000 },
        { label: '1 year', value: 31536000 }
    ];

    const handleSubmit = async (e) => {
        e.preventDefault();
        setCreating(true);

        try {
            const response = await fetch(`${baseUrl}/timelock/capsules/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) throw new Error('Failed to create capsule');

            onCreated();
        } catch (err) {
            alert(err.message);
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <h3>🔐 Create Time-Lock Capsule</h3>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Title</label>
                        <input
                            type="text"
                            value={formData.title}
                            onChange={e => setFormData({ ...formData, title: e.target.value })}
                            placeholder="e.g., Bitcoin Wallet Keys"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Secret</label>
                        <textarea
                            value={formData.secret_data}
                            onChange={e => setFormData({ ...formData, secret_data: e.target.value })}
                            placeholder="Enter the secret to lock..."
                            rows={4}
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Unlock Delay</label>
                        <div className="delay-presets">
                            {delayPresets.map(preset => (
                                <button
                                    key={preset.value}
                                    type="button"
                                    className={`preset ${formData.delay_seconds === preset.value ? 'active' : ''}`}
                                    onClick={() => setFormData({ ...formData, delay_seconds: preset.value })}
                                >
                                    {preset.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Type</label>
                        <select
                            value={formData.capsule_type}
                            onChange={e => setFormData({ ...formData, capsule_type: e.target.value })}
                        >
                            <option value="general">General</option>
                            <option value="time_capsule">Time Capsule</option>
                            <option value="emergency">Emergency Access</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Mode</label>
                        <select
                            value={formData.mode}
                            onChange={e => setFormData({ ...formData, mode: e.target.value })}
                        >
                            <option value="server">Server-Enforced (Recommended)</option>
                            <option value="client">Client-Side Puzzle</option>
                            <option value="hybrid">Hybrid</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Description (Optional)</label>
                        <textarea
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            placeholder="Additional notes..."
                            rows={2}
                        />
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn cancel" onClick={onClose}>
                            Cancel
                        </button>
                        <button type="submit" className="btn create" disabled={creating}>
                            {creating ? 'Creating...' : '🔐 Lock Secret'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default TimeLockManager;

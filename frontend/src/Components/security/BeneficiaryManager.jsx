/**
 * BeneficiaryManager Component
 * 
 * Manages beneficiaries for time-lock capsules.
 * Supports CRUD operations and verification status.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './BeneficiaryManager.css';

const BeneficiaryManager = ({
    authToken,
    capsuleId = null,  // If provided, filter to specific capsule
    baseUrl = '/api/security'
}) => {
    const [beneficiaries, setBeneficiaries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [selectedCapsule, setSelectedCapsule] = useState(capsuleId);

    const fetchBeneficiaries = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${baseUrl}/timelock/beneficiaries/`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Failed to fetch beneficiaries');

            const data = await response.json();
            let bens = data.beneficiaries || [];

            if (capsuleId) {
                bens = bens.filter(b => b.capsule_id === capsuleId);
            }

            setBeneficiaries(bens);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken, baseUrl, capsuleId]);

    useEffect(() => {
        fetchBeneficiaries();
    }, [fetchBeneficiaries]);

    const handleRemove = async (beneficiaryId) => {
        if (!window.confirm('Remove this beneficiary?')) return;

        try {
            const response = await fetch(`${baseUrl}/timelock/beneficiaries/${beneficiaryId}/`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Failed to remove beneficiary');

            fetchBeneficiaries();
        } catch (err) {
            alert(err.message);
        }
    };

    const handleResendVerification = async (beneficiaryId) => {
        alert('Verification email would be resent (feature pending)');
    };

    const getAccessIcon = (level) => {
        const icons = { full: '🔓', view: '👁️', download: '📥' };
        return icons[level] || '❓';
    };

    if (loading) {
        return (
            <div className="beneficiary-manager loading">
                <div className="spinner"></div>
                <p>Loading beneficiaries...</p>
            </div>
        );
    }

    return (
        <div className="beneficiary-manager">
            <div className="manager-header">
                <div>
                    <h2>👥 Beneficiaries</h2>
                    <p>People who can access your time-locked secrets</p>
                </div>
                <button
                    className="add-btn"
                    onClick={() => setShowAddModal(true)}
                >
                    + Add Beneficiary
                </button>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                    <button onClick={fetchBeneficiaries}>Retry</button>
                </div>
            )}

            {beneficiaries.length === 0 ? (
                <div className="empty-state">
                    <span className="icon">👥</span>
                    <p>No beneficiaries added yet</p>
                    <span className="hint">
                        Add beneficiaries to share your time-locked secrets
                    </span>
                </div>
            ) : (
                <div className="beneficiaries-list">
                    {beneficiaries.map(ben => (
                        <div key={ben.id} className="beneficiary-card">
                            <div className="ben-avatar">
                                {ben.name.charAt(0).toUpperCase()}
                            </div>

                            <div className="ben-info">
                                <h4 className="ben-name">{ben.name}</h4>
                                <span className="ben-email">{ben.email}</span>
                                {ben.relationship && (
                                    <span className="ben-relationship">{ben.relationship}</span>
                                )}
                            </div>

                            <div className="ben-status">
                                <div className={`verification-badge ${ben.verified ? 'verified' : 'pending'}`}>
                                    {ben.verified ? '✓ Verified' : '○ Pending'}
                                </div>
                                <div className="access-badge">
                                    {getAccessIcon(ben.access_level)} {ben.access_level}
                                </div>
                            </div>

                            <div className="ben-meta">
                                {ben.notified_at && (
                                    <span className="notified">
                                        📧 Notified {new Date(ben.notified_at).toLocaleDateString()}
                                    </span>
                                )}
                                {ben.accessed_at && (
                                    <span className="accessed">
                                        👁️ Accessed {new Date(ben.accessed_at).toLocaleDateString()}
                                    </span>
                                )}
                            </div>

                            <div className="ben-actions">
                                {!ben.verified && (
                                    <button
                                        className="action-btn resend"
                                        onClick={() => handleResendVerification(ben.id)}
                                        title="Resend verification email"
                                    >
                                        📧
                                    </button>
                                )}
                                <button
                                    className="action-btn remove"
                                    onClick={() => handleRemove(ben.id)}
                                    title="Remove beneficiary"
                                >
                                    🗑️
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {showAddModal && (
                <AddBeneficiaryModal
                    authToken={authToken}
                    baseUrl={baseUrl}
                    capsuleId={selectedCapsule}
                    onClose={() => setShowAddModal(false)}
                    onAdded={() => {
                        setShowAddModal(false);
                        fetchBeneficiaries();
                    }}
                />
            )}
        </div>
    );
};

// Add Beneficiary Modal
const AddBeneficiaryModal = ({ authToken, baseUrl, capsuleId, onClose, onAdded }) => {
    const [formData, setFormData] = useState({
        capsule_id: capsuleId || '',
        name: '',
        email: '',
        relationship: '',
        access_level: 'view',
        requires_verification: true
    });
    const [capsules, setCapsules] = useState([]);
    const [adding, setAdding] = useState(false);

    useEffect(() => {
        if (!capsuleId) {
            fetchCapsules();
        }
    }, [capsuleId]);

    const fetchCapsules = async () => {
        try {
            const response = await fetch(`${baseUrl}/timelock/capsules/`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (response.ok) {
                const data = await response.json();
                setCapsules(data.capsules || []);
            }
        } catch (err) {
            console.error('Failed to fetch capsules:', err);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setAdding(true);

        try {
            const response = await fetch(`${baseUrl}/timelock/beneficiaries/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) throw new Error('Failed to add beneficiary');

            onAdded();
        } catch (err) {
            alert(err.message);
        } finally {
            setAdding(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <h3>👥 Add Beneficiary</h3>

                <form onSubmit={handleSubmit}>
                    {!capsuleId && (
                        <div className="form-group">
                            <label>Capsule</label>
                            <select
                                value={formData.capsule_id}
                                onChange={e => setFormData({ ...formData, capsule_id: e.target.value })}
                                required
                            >
                                <option value="">Select capsule...</option>
                                {capsules.map(cap => (
                                    <option key={cap.id} value={cap.id}>
                                        {cap.title}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="form-group">
                        <label>Name</label>
                        <input
                            type="text"
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Full name"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Email</label>
                        <input
                            type="email"
                            value={formData.email}
                            onChange={e => setFormData({ ...formData, email: e.target.value })}
                            placeholder="email@example.com"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Relationship</label>
                        <input
                            type="text"
                            value={formData.relationship}
                            onChange={e => setFormData({ ...formData, relationship: e.target.value })}
                            placeholder="e.g., Spouse, Lawyer, Partner"
                        />
                    </div>

                    <div className="form-group">
                        <label>Access Level</label>
                        <select
                            value={formData.access_level}
                            onChange={e => setFormData({ ...formData, access_level: e.target.value })}
                        >
                            <option value="view">View Only</option>
                            <option value="full">Full Access</option>
                            <option value="download">Download Only</option>
                        </select>
                    </div>

                    <div className="form-group checkbox">
                        <label>
                            <input
                                type="checkbox"
                                checked={formData.requires_verification}
                                onChange={e => setFormData({ ...formData, requires_verification: e.target.checked })}
                            />
                            <span>Require email verification</span>
                        </label>
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn cancel" onClick={onClose}>
                            Cancel
                        </button>
                        <button type="submit" className="btn add" disabled={adding}>
                            {adding ? 'Adding...' : '👥 Add Beneficiary'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default BeneficiaryManager;

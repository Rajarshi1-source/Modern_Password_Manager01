/**
 * TrustedAuthorityManager.jsx
 * 
 * Component for managing trusted authorities (silent alarm recipients).
 * Allows adding, editing, verifying, and removing authority contacts.
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as duressService from '../../services/duressCodeService';
import './TrustedAuthorityManager.css';

const TrustedAuthorityManager = () => {
    const { getAccessToken } = useAuth();
    const authToken = getAccessToken();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [authorities, setAuthorities] = useState([]);

    // Form state
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        type: 'security_team',
        contactMethod: 'email',
        contactValue: '',
        threatLevels: ['high', 'critical'],
        notes: ''
    });

    // Verification state
    const [verifyingId, setVerifyingId] = useState(null);
    const [verificationCode, setVerificationCode] = useState('');

    useEffect(() => {
        loadAuthorities();
    }, []);

    const loadAuthorities = async () => {
        try {
            setLoading(true);
            const result = await duressService.getAuthorities(authToken);
            setAuthorities(result.authorities || []);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const resetForm = () => {
        setFormData({
            name: '',
            type: 'security_team',
            contactMethod: 'email',
            contactValue: '',
            threatLevels: ['high', 'critical'],
            notes: ''
        });
        setEditingId(null);
        setShowForm(false);
    };

    const handleSubmit = async () => {
        if (!formData.name || !formData.contactValue) {
            setError('Name and contact details are required');
            return;
        }

        try {
            setLoading(true);

            const authorityData = {
                name: formData.name,
                type: formData.type,
                contactMethod: formData.contactMethod,
                contactDetails: {
                    value: formData.contactValue,
                    notes: formData.notes
                },
                threatLevels: formData.threatLevels
            };

            if (editingId) {
                await duressService.updateAuthority(authToken, editingId, authorityData);
            } else {
                await duressService.addAuthority(authToken, authorityData);
            }

            await loadAuthorities();
            resetForm();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = (authority) => {
        setFormData({
            name: authority.name || '',
            type: authority.authority_type,
            contactMethod: authority.contact_method,
            contactValue: authority.contact_details?.value || '',
            threatLevels: authority.threat_levels || ['high', 'critical'],
            notes: authority.contact_details?.notes || ''
        });
        setEditingId(authority.id);
        setShowForm(true);
    };

    const handleDelete = async (authorityId) => {
        if (!window.confirm('Are you sure you want to remove this contact?')) {
            return;
        }

        try {
            setLoading(true);
            await duressService.deleteAuthority(authToken, authorityId);
            setAuthorities(authorities.filter(a => a.id !== authorityId));
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleThreatLevelToggle = (level) => {
        if (formData.threatLevels.includes(level)) {
            setFormData({
                ...formData,
                threatLevels: formData.threatLevels.filter(l => l !== level)
            });
        } else {
            setFormData({
                ...formData,
                threatLevels: [...formData.threatLevels, level]
            });
        }
    };

    const startVerification = (authorityId) => {
        setVerifyingId(authorityId);
        setVerificationCode('');
        // In a real implementation, this would send a verification code
    };

    const getContactPlaceholder = () => {
        switch (formData.contactMethod) {
            case 'email': return 'email@example.com';
            case 'sms': return '+1 (555) 123-4567';
            case 'phone': return '+1 (555) 123-4567';
            case 'webhook': return 'https://your-endpoint.com/alert';
            case 'signal': return '+1 (555) 123-4567';
            default: return 'Enter contact details';
        }
    };

    if (loading && authorities.length === 0) {
        return (
            <div className="authority-manager-loading">
                <div className="spinner" />
                <span>Loading trusted authorities...</span>
            </div>
        );
    }

    return (
        <div className="trusted-authority-manager">
            {/* Header */}
            <div className="manager-header">
                <div className="header-info">
                    <h2>📞 Trusted Authorities</h2>
                    <p>Contacts who receive silent alarms during duress events</p>
                </div>

                <button
                    className="add-btn"
                    onClick={() => setShowForm(!showForm)}
                >
                    {showForm ? '× Cancel' : '+ Add Contact'}
                </button>
            </div>

            {/* Error Display */}
            {error && (
                <div className="manager-error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Add/Edit Form */}
            {showForm && (
                <div className="authority-form">
                    <h3>{editingId ? 'Edit Contact' : 'Add New Contact'}</h3>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Contact Name *</label>
                            <input
                                type="text"
                                placeholder="e.g., John Smith (Lawyer)"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            />
                        </div>

                        <div className="form-group">
                            <label>Authority Type</label>
                            <select
                                value={formData.type}
                                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                            >
                                <option value="law_enforcement">🚔 Law Enforcement</option>
                                <option value="legal_counsel">⚖️ Legal Counsel</option>
                                <option value="security_team">🛡️ Security Team</option>
                                <option value="family">👨‍👩‍👧 Family Member</option>
                                <option value="custom">📋 Custom</option>
                            </select>
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Contact Method</label>
                            <select
                                value={formData.contactMethod}
                                onChange={(e) => setFormData({ ...formData, contactMethod: e.target.value })}
                            >
                                <option value="email">📧 Email</option>
                                <option value="sms">📱 SMS</option>
                                <option value="phone">📞 Phone Call</option>
                                <option value="webhook">🔗 Webhook</option>
                                <option value="signal">💬 Signal</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label>Contact Details *</label>
                            <input
                                type="text"
                                placeholder={getContactPlaceholder()}
                                value={formData.contactValue}
                                onChange={(e) => setFormData({ ...formData, contactValue: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Trigger on Threat Levels</label>
                        <div className="threat-level-selector">
                            {['low', 'medium', 'high', 'critical'].map(level => {
                                const info = duressService.formatThreatLevel(level);
                                const isSelected = formData.threatLevels.includes(level);
                                return (
                                    <button
                                        key={level}
                                        type="button"
                                        className={`level-btn ${isSelected ? 'active' : ''}`}
                                        style={{
                                            '--level-color': info.color,
                                            borderColor: isSelected ? info.color : 'transparent'
                                        }}
                                        onClick={() => handleThreatLevelToggle(level)}
                                    >
                                        {info.icon} {info.label}
                                    </button>
                                );
                            })}
                        </div>
                        <p className="form-hint">
                            This contact will be notified when any of the selected threat levels are triggered
                        </p>
                    </div>

                    <div className="form-group">
                        <label>Notes (Optional)</label>
                        <textarea
                            placeholder="Additional instructions or context..."
                            value={formData.notes}
                            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                        />
                    </div>

                    <div className="form-actions">
                        <button className="cancel-btn" onClick={resetForm}>
                            Cancel
                        </button>
                        <button
                            className="save-btn"
                            onClick={handleSubmit}
                            disabled={loading || !formData.name || !formData.contactValue}
                        >
                            {loading ? 'Saving...' : (editingId ? 'Update Contact' : 'Add Contact')}
                        </button>
                    </div>
                </div>
            )}

            {/* Authority List */}
            <div className="authorities-list">
                {authorities.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">📭</span>
                        <h3>No Trusted Authorities</h3>
                        <p>Add contacts who should be notified during duress events</p>
                    </div>
                ) : (
                    authorities.map(authority => {
                        const typeInfo = duressService.formatAuthorityType(authority.authority_type);
                        const methodInfo = duressService.formatContactMethod(authority.contact_method);

                        return (
                            <div key={authority.id} className="authority-card">
                                <div className="authority-header">
                                    <span className="authority-type-icon">{typeInfo.icon}</span>
                                    <div className="authority-title">
                                        <span className="authority-name">{authority.name || 'Unnamed'}</span>
                                        <span className="authority-type">{typeInfo.label}</span>
                                    </div>
                                    <div className="authority-status">
                                        {authority.is_verified ? (
                                            <span className="verified-badge">✓ Verified</span>
                                        ) : (
                                            <span className="unverified-badge">⚠️ Unverified</span>
                                        )}
                                    </div>
                                </div>

                                <div className="authority-body">
                                    <div className="contact-info">
                                        <span className="contact-method">
                                            {methodInfo.icon} {methodInfo.label}
                                        </span>
                                        <span className="contact-value">
                                            {authority.contact_details?.value || 'No contact set'}
                                        </span>
                                    </div>

                                    <div className="trigger-levels">
                                        <span className="levels-label">Triggers on:</span>
                                        <div className="levels-badges">
                                            {(authority.threat_levels || []).map(level => {
                                                const info = duressService.formatThreatLevel(level);
                                                return (
                                                    <span
                                                        key={level}
                                                        className="level-badge"
                                                        style={{ backgroundColor: info.color }}
                                                    >
                                                        {info.label}
                                                    </span>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {authority.contact_details?.notes && (
                                        <div className="authority-notes">
                                            <span className="notes-label">Notes:</span>
                                            <span className="notes-text">{authority.contact_details.notes}</span>
                                        </div>
                                    )}
                                </div>

                                <div className="authority-actions">
                                    {!authority.is_verified && (
                                        <button
                                            className="verify-btn"
                                            onClick={() => startVerification(authority.id)}
                                        >
                                            ✓ Verify
                                        </button>
                                    )}
                                    <button
                                        className="edit-btn"
                                        onClick={() => handleEdit(authority)}
                                    >
                                        ✏️ Edit
                                    </button>
                                    <button
                                        className="delete-btn"
                                        onClick={() => handleDelete(authority.id)}
                                    >
                                        🗑️ Remove
                                    </button>
                                </div>

                                {/* Verification Modal */}
                                {verifyingId === authority.id && (
                                    <div className="verification-overlay">
                                        <div className="verification-modal">
                                            <h4>Verify Contact</h4>
                                            <p>
                                                A verification code has been sent to this contact.
                                                Enter the code below to confirm:
                                            </p>
                                            <input
                                                type="text"
                                                placeholder="Enter verification code"
                                                value={verificationCode}
                                                onChange={(e) => setVerificationCode(e.target.value)}
                                            />
                                            <div className="verification-actions">
                                                <button onClick={() => setVerifyingId(null)}>
                                                    Cancel
                                                </button>
                                                <button className="confirm-btn">
                                                    Confirm
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>

            {/* Info Box */}
            <div className="info-box">
                <span className="info-icon">ℹ️</span>
                <div className="info-content">
                    <strong>How Silent Alarms Work</strong>
                    <p>
                        When a duress code is activated, selected contacts will be notified silently
                        without alerting the attacker. Messages include your location, device info,
                        and timestamp. Verify contacts to ensure they receive alerts correctly.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default TrustedAuthorityManager;

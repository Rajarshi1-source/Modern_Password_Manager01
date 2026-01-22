/**
 * EscrowDashboard Component
 * 
 * Dashboard for managing escrow agreements.
 * Shows owned escrows, party escrows, and approval status.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './EscrowDashboard.css';

const EscrowDashboard = ({
    authToken,
    onEscrowClick,
    baseUrl = '/api/security'
}) => {
    const [ownedEscrows, setOwnedEscrows] = useState([]);
    const [partyEscrows, setPartyEscrows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showCreateModal, setShowCreateModal] = useState(false);

    const fetchEscrows = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${baseUrl}/timelock/escrows/`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Failed to fetch escrows');

            const data = await response.json();
            setOwnedEscrows(data.owned_escrows || []);
            setPartyEscrows(data.party_escrows || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken, baseUrl]);

    useEffect(() => {
        fetchEscrows();
    }, [fetchEscrows]);

    const handleApprove = async (escrowId) => {
        try {
            const response = await fetch(`${baseUrl}/timelock/escrows/${escrowId}/approve/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Approval failed');

            const data = await response.json();
            if (data.released) {
                alert('Escrow has been released!');
            }
            fetchEscrows();
        } catch (err) {
            alert(err.message);
        }
    };

    const getConditionIcon = (condition) => {
        const icons = {
            date: '📅',
            all_approve: '👥',
            any_approve: '👤',
            majority: '⚖️',
            date_or_approve: '🔄'
        };
        return icons[condition] || '📋';
    };

    const renderEscrowCard = (escrow, isOwned = true) => (
        <div
            key={escrow.id}
            className={`escrow-card ${escrow.is_released ? 'released' : ''} ${escrow.is_disputed ? 'disputed' : ''}`}
            onClick={() => onEscrowClick?.(escrow)}
        >
            <div className="card-header">
                <span className="condition-icon">{getConditionIcon(escrow.release_condition)}</span>
                <div className="status-badges">
                    {escrow.is_released && <span className="badge released">Released</span>}
                    {escrow.is_disputed && <span className="badge disputed">Disputed</span>}
                    {!escrow.is_released && !escrow.is_disputed && (
                        <span className="badge pending">Pending</span>
                    )}
                </div>
            </div>

            <h3 className="title">{escrow.title}</h3>
            {escrow.description && (
                <p className="description">{escrow.description}</p>
            )}

            <div className="approval-status">
                <div className="approval-bar">
                    <div
                        className="approval-progress"
                        style={{ width: `${(escrow.approval_count / escrow.total_parties) * 100}%` }}
                    />
                </div>
                <span className="approval-text">
                    {escrow.approval_count} / {escrow.total_parties} approved
                </span>
            </div>

            <div className="parties-list">
                <h4>Parties</h4>
                {escrow.parties?.map((party, idx) => (
                    <div key={idx} className="party-item">
                        <span className="party-name">{party.username}</span>
                        <span className={`approved-badge ${escrow.approved_by?.includes(party.id) ? 'yes' : 'no'}`}>
                            {escrow.approved_by?.includes(party.id) ? '✓' : '○'}
                        </span>
                    </div>
                ))}
            </div>

            {escrow.can_release && !escrow.is_released && (
                <div className="release-ready">
                    🔓 Ready to release
                </div>
            )}

            {!isOwned && !escrow.is_released && (
                <button
                    className="approve-btn"
                    onClick={(e) => {
                        e.stopPropagation();
                        handleApprove(escrow.id);
                    }}
                >
                    ✓ Approve Release
                </button>
            )}
        </div>
    );

    if (loading) {
        return (
            <div className="escrow-dashboard loading">
                <div className="spinner"></div>
                <p>Loading escrow agreements...</p>
            </div>
        );
    }

    return (
        <div className="escrow-dashboard">
            <div className="dashboard-header">
                <div>
                    <h2>🤝 Escrow Agreements</h2>
                    <p>Multi-party secret releases</p>
                </div>
                <button
                    className="create-btn"
                    onClick={() => setShowCreateModal(true)}
                >
                    + Create Escrow
                </button>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                    <button onClick={fetchEscrows}>Retry</button>
                </div>
            )}

            <div className="escrow-sections">
                <section className="escrow-section">
                    <h3>📤 Your Escrows</h3>
                    {ownedEscrows.length === 0 ? (
                        <div className="empty-state">
                            <p>No escrows created yet</p>
                        </div>
                    ) : (
                        <div className="escrows-grid">
                            {ownedEscrows.map(e => renderEscrowCard(e, true))}
                        </div>
                    )}
                </section>

                <section className="escrow-section">
                    <h3>📥 Escrows as Party</h3>
                    {partyEscrows.length === 0 ? (
                        <div className="empty-state">
                            <p>No pending approvals</p>
                        </div>
                    ) : (
                        <div className="escrows-grid">
                            {partyEscrows.map(e => renderEscrowCard(e, false))}
                        </div>
                    )}
                </section>
            </div>

            {showCreateModal && (
                <CreateEscrowModal
                    authToken={authToken}
                    baseUrl={baseUrl}
                    onClose={() => setShowCreateModal(false)}
                    onCreated={() => {
                        setShowCreateModal(false);
                        fetchEscrows();
                    }}
                />
            )}
        </div>
    );
};

// Create Escrow Modal
const CreateEscrowModal = ({ authToken, baseUrl, onClose, onCreated }) => {
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        secret_data: '',
        release_condition: 'all_approve',
        unlock_date: '',
        party_emails: ['']
    });
    const [creating, setCreating] = useState(false);

    const addPartyEmail = () => {
        setFormData(prev => ({
            ...prev,
            party_emails: [...prev.party_emails, '']
        }));
    };

    const updatePartyEmail = (index, value) => {
        const emails = [...formData.party_emails];
        emails[index] = value;
        setFormData(prev => ({ ...prev, party_emails: emails }));
    };

    const removePartyEmail = (index) => {
        setFormData(prev => ({
            ...prev,
            party_emails: prev.party_emails.filter((_, i) => i !== index)
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setCreating(true);

        try {
            const response = await fetch(`${baseUrl}/timelock/escrows/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    ...formData,
                    party_emails: formData.party_emails.filter(e => e.trim())
                })
            });

            if (!response.ok) throw new Error('Failed to create escrow');

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
                <h3>🤝 Create Escrow Agreement</h3>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Title</label>
                        <input
                            type="text"
                            value={formData.title}
                            onChange={e => setFormData({ ...formData, title: e.target.value })}
                            placeholder="e.g., Business Partnership Agreement"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Secret Content</label>
                        <textarea
                            value={formData.secret_data}
                            onChange={e => setFormData({ ...formData, secret_data: e.target.value })}
                            placeholder="Secret to be released..."
                            rows={4}
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Release Condition</label>
                        <select
                            value={formData.release_condition}
                            onChange={e => setFormData({ ...formData, release_condition: e.target.value })}
                        >
                            <option value="all_approve">All Parties Approve</option>
                            <option value="any_approve">Any Party Approves</option>
                            <option value="majority">Majority Approves</option>
                            <option value="date">On Specific Date</option>
                            <option value="date_or_approve">Date OR All Approve</option>
                        </select>
                    </div>

                    {(formData.release_condition === 'date' || formData.release_condition === 'date_or_approve') && (
                        <div className="form-group">
                            <label>Unlock Date</label>
                            <input
                                type="datetime-local"
                                value={formData.unlock_date}
                                onChange={e => setFormData({ ...formData, unlock_date: e.target.value })}
                            />
                        </div>
                    )}

                    <div className="form-group">
                        <label>Party Emails</label>
                        {formData.party_emails.map((email, idx) => (
                            <div key={idx} className="email-row">
                                <input
                                    type="email"
                                    value={email}
                                    onChange={e => updatePartyEmail(idx, e.target.value)}
                                    placeholder="party@example.com"
                                />
                                {formData.party_emails.length > 1 && (
                                    <button
                                        type="button"
                                        className="remove-btn"
                                        onClick={() => removePartyEmail(idx)}
                                    >
                                        ×
                                    </button>
                                )}
                            </div>
                        ))}
                        <button type="button" className="add-email-btn" onClick={addPartyEmail}>
                            + Add Party
                        </button>
                    </div>

                    <div className="form-group">
                        <label>Description (Optional)</label>
                        <textarea
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            placeholder="Terms and conditions..."
                            rows={2}
                        />
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn cancel" onClick={onClose}>
                            Cancel
                        </button>
                        <button type="submit" className="btn create" disabled={creating}>
                            {creating ? 'Creating...' : '🤝 Create Escrow'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default EscrowDashboard;

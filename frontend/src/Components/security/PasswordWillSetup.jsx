/**
 * PasswordWillSetup Component
 * 
 * Setup wizard for creating password wills (digital inheritance).
 * Implements dead man's switch pattern with beneficiary management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './PasswordWillSetup.css';

const PasswordWillSetup = ({
    authToken,
    onComplete,
    onCancel,
    baseUrl = '/api/security'
}) => {
    const [step, setStep] = useState(1);
    const [wills, setWills] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const [formData, setFormData] = useState({
        title: '',
        description: '',
        secret_data: '',
        trigger_type: 'inactivity',
        inactivity_days: 30,
        target_date: '',
        check_in_reminder_days: 7,
        beneficiaries: [],
        notes: ''
    });

    const [newBeneficiary, setNewBeneficiary] = useState({
        name: '',
        email: '',
        relationship: '',
        access_level: 'full'
    });

    // Fetch existing wills
    const fetchWills = useCallback(async () => {
        try {
            const response = await fetch(`${baseUrl}/timelock/wills/`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (response.ok) {
                const data = await response.json();
                setWills(data.wills || []);
            }
        } catch (err) {
            console.error('Failed to fetch wills:', err);
        }
    }, [authToken, baseUrl]);

    useEffect(() => {
        fetchWills();
    }, [fetchWills]);

    const addBeneficiary = () => {
        if (!newBeneficiary.name || !newBeneficiary.email) {
            alert('Please enter name and email');
            return;
        }

        setFormData(prev => ({
            ...prev,
            beneficiaries: [...prev.beneficiaries, { ...newBeneficiary }]
        }));

        setNewBeneficiary({
            name: '',
            email: '',
            relationship: '',
            access_level: 'full'
        });
    };

    const removeBeneficiary = (index) => {
        setFormData(prev => ({
            ...prev,
            beneficiaries: prev.beneficiaries.filter((_, i) => i !== index)
        }));
    };

    const handleSubmit = async () => {
        if (formData.beneficiaries.length === 0) {
            alert('Please add at least one beneficiary');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${baseUrl}/timelock/wills/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to create will');
            }

            onComplete?.();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCheckIn = async (willId) => {
        try {
            const response = await fetch(`${baseUrl}/timelock/wills/${willId}/checkin/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) throw new Error('Check-in failed');

            fetchWills();
        } catch (err) {
            alert(err.message);
        }
    };

    const nextStep = () => setStep(prev => Math.min(prev + 1, 4));
    const prevStep = () => setStep(prev => Math.max(prev - 1, 1));

    return (
        <div className="password-will-setup">
            <div className="setup-header">
                <h2>📜 Password Will</h2>
                <p>Digital inheritance for your passwords</p>
            </div>

            {/* Existing wills */}
            {wills.length > 0 && (
                <div className="existing-wills">
                    <h3>Your Active Wills</h3>
                    {wills.map(will => (
                        <div key={will.id} className={`will-card ${will.is_triggered ? 'triggered' : ''}`}>
                            <div className="will-info">
                                <h4>{will.capsule_title}</h4>
                                <p>
                                    {will.trigger_type === 'inactivity'
                                        ? `${will.days_until_trigger} days until trigger`
                                        : `Triggers on ${new Date(will.target_date).toLocaleDateString()}`}
                                </p>
                                <span className="last-checkin">
                                    Last check-in: {new Date(will.last_check_in).toLocaleDateString()}
                                </span>
                            </div>
                            <button
                                className="checkin-btn"
                                onClick={() => handleCheckIn(will.id)}
                                disabled={will.is_triggered}
                            >
                                ✓ Check In
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Setup wizard */}
            <div className="setup-wizard">
                <div className="progress-steps">
                    {[1, 2, 3, 4].map(s => (
                        <div
                            key={s}
                            className={`step ${step >= s ? 'active' : ''} ${step === s ? 'current' : ''}`}
                        >
                            {s}
                        </div>
                    ))}
                </div>

                {step === 1 && (
                    <div className="step-content">
                        <h3>📝 Will Details</h3>
                        <div className="form-group">
                            <label>Will Title</label>
                            <input
                                type="text"
                                value={formData.title}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="e.g., Digital Estate Will"
                            />
                        </div>
                        <div className="form-group">
                            <label>Description</label>
                            <textarea
                                value={formData.description}
                                onChange={e => setFormData({ ...formData, description: e.target.value })}
                                placeholder="Instructions for your beneficiaries..."
                                rows={3}
                            />
                        </div>
                    </div>
                )}

                {step === 2 && (
                    <div className="step-content">
                        <h3>🔐 Secrets to Pass On</h3>
                        <div className="form-group">
                            <label>Passwords & Secrets</label>
                            <textarea
                                value={formData.secret_data}
                                onChange={e => setFormData({ ...formData, secret_data: e.target.value })}
                                placeholder="Enter all passwords and accounts to pass on..."
                                rows={8}
                            />
                            <p className="hint">This will be encrypted and only released to beneficiaries</p>
                        </div>
                        <div className="form-group">
                            <label>Personal Message to Beneficiaries</label>
                            <textarea
                                value={formData.notes}
                                onChange={e => setFormData({ ...formData, notes: e.target.value })}
                                placeholder="A message to your loved ones..."
                                rows={3}
                            />
                        </div>
                    </div>
                )}

                {step === 3 && (
                    <div className="step-content">
                        <h3>⏰ Trigger Settings</h3>

                        <div className="trigger-options">
                            <label className={`trigger-option ${formData.trigger_type === 'inactivity' ? 'active' : ''}`}>
                                <input
                                    type="radio"
                                    name="trigger_type"
                                    value="inactivity"
                                    checked={formData.trigger_type === 'inactivity'}
                                    onChange={e => setFormData({ ...formData, trigger_type: e.target.value })}
                                />
                                <div className="option-content">
                                    <span className="icon">🔄</span>
                                    <span className="title">Inactivity Trigger</span>
                                    <span className="desc">Release if you don't check in</span>
                                </div>
                            </label>

                            <label className={`trigger-option ${formData.trigger_type === 'date' ? 'active' : ''}`}>
                                <input
                                    type="radio"
                                    name="trigger_type"
                                    value="date"
                                    checked={formData.trigger_type === 'date'}
                                    onChange={e => setFormData({ ...formData, trigger_type: e.target.value })}
                                />
                                <div className="option-content">
                                    <span className="icon">📅</span>
                                    <span className="title">Specific Date</span>
                                    <span className="desc">Release on a set date</span>
                                </div>
                            </label>
                        </div>

                        {formData.trigger_type === 'inactivity' && (
                            <div className="trigger-settings">
                                <div className="form-group">
                                    <label>Inactivity Period: {formData.inactivity_days} days</label>
                                    <input
                                        type="range"
                                        min="7"
                                        max="365"
                                        value={formData.inactivity_days}
                                        onChange={e => setFormData({ ...formData, inactivity_days: parseInt(e.target.value) })}
                                    />
                                    <div className="range-labels">
                                        <span>7 days</span>
                                        <span>1 year</span>
                                    </div>
                                </div>
                                <div className="form-group">
                                    <label>Reminder: {formData.check_in_reminder_days} days before deadline</label>
                                    <input
                                        type="range"
                                        min="1"
                                        max="30"
                                        value={formData.check_in_reminder_days}
                                        onChange={e => setFormData({ ...formData, check_in_reminder_days: parseInt(e.target.value) })}
                                    />
                                </div>
                            </div>
                        )}

                        {formData.trigger_type === 'date' && (
                            <div className="form-group">
                                <label>Release Date</label>
                                <input
                                    type="datetime-local"
                                    value={formData.target_date}
                                    onChange={e => setFormData({ ...formData, target_date: e.target.value })}
                                />
                            </div>
                        )}
                    </div>
                )}

                {step === 4 && (
                    <div className="step-content">
                        <h3>👥 Beneficiaries</h3>

                        <div className="beneficiaries-list">
                            {formData.beneficiaries.map((ben, index) => (
                                <div key={index} className="beneficiary-item">
                                    <div className="ben-info">
                                        <span className="name">{ben.name}</span>
                                        <span className="email">{ben.email}</span>
                                        {ben.relationship && <span className="rel">{ben.relationship}</span>}
                                    </div>
                                    <button
                                        className="remove-btn"
                                        onClick={() => removeBeneficiary(index)}
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>

                        <div className="add-beneficiary">
                            <h4>Add Beneficiary</h4>
                            <div className="form-row">
                                <input
                                    type="text"
                                    placeholder="Full Name"
                                    value={newBeneficiary.name}
                                    onChange={e => setNewBeneficiary({ ...newBeneficiary, name: e.target.value })}
                                />
                                <input
                                    type="email"
                                    placeholder="Email"
                                    value={newBeneficiary.email}
                                    onChange={e => setNewBeneficiary({ ...newBeneficiary, email: e.target.value })}
                                />
                            </div>
                            <div className="form-row">
                                <input
                                    type="text"
                                    placeholder="Relationship (e.g., Spouse)"
                                    value={newBeneficiary.relationship}
                                    onChange={e => setNewBeneficiary({ ...newBeneficiary, relationship: e.target.value })}
                                />
                                <select
                                    value={newBeneficiary.access_level}
                                    onChange={e => setNewBeneficiary({ ...newBeneficiary, access_level: e.target.value })}
                                >
                                    <option value="full">Full Access</option>
                                    <option value="view">View Only</option>
                                </select>
                            </div>
                            <button className="add-btn" onClick={addBeneficiary}>
                                + Add Beneficiary
                            </button>
                        </div>
                    </div>
                )}

                {error && <div className="error-message">{error}</div>}

                <div className="wizard-actions">
                    {step > 1 && (
                        <button className="btn secondary" onClick={prevStep}>
                            ← Back
                        </button>
                    )}
                    {step < 4 ? (
                        <button className="btn primary" onClick={nextStep}>
                            Next →
                        </button>
                    ) : (
                        <button
                            className="btn primary"
                            onClick={handleSubmit}
                            disabled={loading}
                        >
                            {loading ? 'Creating...' : '📜 Create Password Will'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default PasswordWillSetup;

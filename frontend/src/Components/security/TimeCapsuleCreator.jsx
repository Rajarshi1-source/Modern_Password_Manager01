/**
 * TimeCapsuleCreator Component
 * 
 * Create time capsules with future unlock dates.
 * Supports message attachments and beneficiary notifications.
 */

import React, { useState } from 'react';
import './TimeCapsuleCreator.css';

const TimeCapsuleCreator = ({
    authToken,
    onComplete,
    onCancel,
    baseUrl = '/api/security'
}) => {
    const [step, setStep] = useState(1);
    const [creating, setCreating] = useState(false);

    const [formData, setFormData] = useState({
        title: '',
        description: '',
        secret_data: '',
        unlock_date: '',
        mode: 'server',
        notify_on_unlock: true,
        beneficiaries: []
    });

    const [newBeneficiary, setNewBeneficiary] = useState({
        name: '',
        email: ''
    });

    // Preset unlock dates
    const datePresets = [
        { label: '1 Month', days: 30 },
        { label: '6 Months', days: 180 },
        { label: '1 Year', days: 365 },
        { label: '5 Years', days: 1825 },
        { label: '10 Years', days: 3650 },
        { label: 'Custom', days: null }
    ];

    const [selectedPreset, setSelectedPreset] = useState(null);

    const applyDatePreset = (preset) => {
        setSelectedPreset(preset.label);
        if (preset.days) {
            const date = new Date();
            date.setDate(date.getDate() + preset.days);
            setFormData(prev => ({
                ...prev,
                unlock_date: date.toISOString().slice(0, 16)
            }));
        }
    };

    const addBeneficiary = () => {
        if (!newBeneficiary.name || !newBeneficiary.email) return;

        setFormData(prev => ({
            ...prev,
            beneficiaries: [...prev.beneficiaries, { ...newBeneficiary }]
        }));
        setNewBeneficiary({ name: '', email: '' });
    };

    const removeBeneficiary = (index) => {
        setFormData(prev => ({
            ...prev,
            beneficiaries: prev.beneficiaries.filter((_, i) => i !== index)
        }));
    };

    const handleSubmit = async () => {
        if (!formData.unlock_date) {
            alert('Please select an unlock date');
            return;
        }

        setCreating(true);

        try {
            const unlockDate = new Date(formData.unlock_date);
            const delaySeconds = Math.floor((unlockDate - new Date()) / 1000);

            const response = await fetch(`${baseUrl}/timelock/capsules/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    title: formData.title,
                    description: formData.description,
                    secret_data: formData.secret_data,
                    delay_seconds: delaySeconds,
                    mode: formData.mode,
                    capsule_type: 'time_capsule',
                    beneficiaries: formData.beneficiaries
                })
            });

            if (!response.ok) throw new Error('Failed to create time capsule');

            onComplete?.();
        } catch (err) {
            alert(err.message);
        } finally {
            setCreating(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getTimeUntil = () => {
        if (!formData.unlock_date) return null;
        const now = new Date();
        const unlock = new Date(formData.unlock_date);
        const diff = unlock - now;

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const years = Math.floor(days / 365);
        const months = Math.floor((days % 365) / 30);
        const remainingDays = days % 30;

        if (years > 0) return `${years} years, ${months} months`;
        if (months > 0) return `${months} months, ${remainingDays} days`;
        return `${days} days`;
    };

    return (
        <div className="time-capsule-creator">
            <div className="creator-header">
                <h2>⏳ Create Time Capsule</h2>
                <p>Lock a message for the future</p>
            </div>

            <div className="progress-indicator">
                {[1, 2, 3].map(s => (
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
                    <h3>📝 Capsule Contents</h3>

                    <div className="form-group">
                        <label>Title</label>
                        <input
                            type="text"
                            value={formData.title}
                            onChange={e => setFormData({ ...formData, title: e.target.value })}
                            placeholder="e.g., Message to Future Self"
                        />
                    </div>

                    <div className="form-group">
                        <label>Your Message / Secret</label>
                        <textarea
                            value={formData.secret_data}
                            onChange={e => setFormData({ ...formData, secret_data: e.target.value })}
                            placeholder="Write your message to the future..."
                            rows={8}
                        />
                        <div className="char-count">
                            {formData.secret_data.length} characters
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Description (Optional)</label>
                        <textarea
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            placeholder="What is this capsule about?"
                            rows={2}
                        />
                    </div>
                </div>
            )}

            {step === 2 && (
                <div className="step-content">
                    <h3>📅 Unlock Date</h3>

                    <div className="date-presets">
                        {datePresets.map(preset => (
                            <button
                                key={preset.label}
                                className={`preset ${selectedPreset === preset.label ? 'active' : ''}`}
                                onClick={() => applyDatePreset(preset)}
                            >
                                {preset.label}
                            </button>
                        ))}
                    </div>

                    <div className="form-group">
                        <label>Custom Date & Time</label>
                        <input
                            type="datetime-local"
                            value={formData.unlock_date}
                            onChange={e => {
                                setFormData({ ...formData, unlock_date: e.target.value });
                                setSelectedPreset('Custom');
                            }}
                            min={new Date().toISOString().slice(0, 16)}
                        />
                    </div>

                    {formData.unlock_date && (
                        <div className="unlock-preview">
                            <div className="preview-icon">⏰</div>
                            <div className="preview-info">
                                <div className="preview-date">{formatDate(formData.unlock_date)}</div>
                                <div className="preview-countdown">Opens in {getTimeUntil()}</div>
                            </div>
                        </div>
                    )}

                    <div className="form-group">
                        <label>Security Mode</label>
                        <select
                            value={formData.mode}
                            onChange={e => setFormData({ ...formData, mode: e.target.value })}
                        >
                            <option value="server">Server-Enforced (Recommended)</option>
                            <option value="client">Client-Side VDF</option>
                            <option value="hybrid">Hybrid</option>
                        </select>
                    </div>
                </div>
            )}

            {step === 3 && (
                <div className="step-content">
                    <h3>👥 Notify Recipients (Optional)</h3>
                    <p className="step-description">
                        Add people to notify when the capsule unlocks
                    </p>

                    <div className="beneficiaries-list">
                        {formData.beneficiaries.map((ben, idx) => (
                            <div key={idx} className="beneficiary-item">
                                <span className="ben-name">{ben.name}</span>
                                <span className="ben-email">{ben.email}</span>
                                <button
                                    className="remove-btn"
                                    onClick={() => removeBeneficiary(idx)}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="add-beneficiary">
                        <input
                            type="text"
                            placeholder="Name"
                            value={newBeneficiary.name}
                            onChange={e => setNewBeneficiary({ ...newBeneficiary, name: e.target.value })}
                        />
                        <input
                            type="email"
                            placeholder="Email"
                            value={newBeneficiary.email}
                            onChange={e => setNewBeneficiary({ ...newBeneficiary, email: e.target.value })}
                        />
                        <button className="add-btn" onClick={addBeneficiary}>+</button>
                    </div>

                    <div className="summary-section">
                        <h4>📋 Summary</h4>
                        <div className="summary-item">
                            <span>Title:</span> {formData.title || 'Untitled'}
                        </div>
                        <div className="summary-item">
                            <span>Opens:</span> {formatDate(formData.unlock_date)}
                        </div>
                        <div className="summary-item">
                            <span>Recipients:</span> {formData.beneficiaries.length} people
                        </div>
                    </div>
                </div>
            )}

            <div className="creator-actions">
                {step > 1 && (
                    <button className="btn secondary" onClick={() => setStep(s => s - 1)}>
                        ← Back
                    </button>
                )}
                {step < 3 ? (
                    <button className="btn primary" onClick={() => setStep(s => s + 1)}>
                        Next →
                    </button>
                ) : (
                    <button
                        className="btn primary"
                        onClick={handleSubmit}
                        disabled={creating}
                    >
                        {creating ? 'Creating...' : '⏳ Create Time Capsule'}
                    </button>
                )}
            </div>
        </div>
    );
};

export default TimeCapsuleCreator;

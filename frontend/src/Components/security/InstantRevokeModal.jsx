/**
 * InstantRevokeModal.jsx
 * 
 * Emergency revocation modal for compromised devices.
 * Features:
 * - Confirm device selection
 * - Show impact warning
 * - Execute instant revoke
 * - Success/failure feedback
 */

import React, { useState } from 'react';
import {
    AlertTriangle,
    Unlink,
    Loader,
    ShieldOff,
    CheckCircle,
    XCircle,
    AlertOctagon
} from 'lucide-react';
import './InstantRevokeModal.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const InstantRevokeModal = ({ pair, onConfirm, onCancel }) => {
    const [step, setStep] = useState('confirm'); // confirm, processing, success, error
    const [selectedCompromised, setSelectedCompromised] = useState(null);
    const [reason, setReason] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleRevoke = async () => {
        try {
            setLoading(true);
            setStep('processing');
            setError(null);

            const response = await fetch(`${API_BASE_URL}/api/security/entanglement/revoke/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    pair_id: pair.pair_id,
                    compromised_device_id: selectedCompromised,
                    reason: reason || 'Manual revocation via UI',
                }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Revocation failed');
            }

            setStep('success');
        } catch (err) {
            setError(err.message);
            setStep('error');
        } finally {
            setLoading(false);
        }
    };

    const renderContent = () => {
        switch (step) {
            case 'confirm':
                return (
                    <>
                        <div className="modal-icon warning">
                            <AlertTriangle size={48} />
                        </div>

                        <h2>Revoke Device Pairing?</h2>

                        <p className="modal-description">
                            This will immediately invalidate the cryptographic connection between these devices.
                            This action cannot be undone.
                        </p>

                        <div className="affected-devices">
                            <h4>Affected Devices:</h4>
                            <div className="device-list">
                                <div
                                    className={`device-item ${selectedCompromised === pair.device_a_id ? 'compromised' : ''}`}
                                    onClick={() => setSelectedCompromised(
                                        selectedCompromised === pair.device_a_id ? null : pair.device_a_id
                                    )}
                                >
                                    <span className="device-name">{pair.device_a_name || 'Device A'}</span>
                                    {selectedCompromised === pair.device_a_id && (
                                        <span className="compromised-badge">
                                            <AlertOctagon size={14} />
                                            Compromised
                                        </span>
                                    )}
                                </div>
                                <div
                                    className={`device-item ${selectedCompromised === pair.device_b_id ? 'compromised' : ''}`}
                                    onClick={() => setSelectedCompromised(
                                        selectedCompromised === pair.device_b_id ? null : pair.device_b_id
                                    )}
                                >
                                    <span className="device-name">{pair.device_b_name || 'Device B'}</span>
                                    {selectedCompromised === pair.device_b_id && (
                                        <span className="compromised-badge">
                                            <AlertOctagon size={14} />
                                            Compromised
                                        </span>
                                    )}
                                </div>
                            </div>
                            <p className="hint">
                                Click on a device if it's compromised (optional)
                            </p>
                        </div>

                        <div className="reason-input">
                            <label>Reason for revocation (optional):</label>
                            <textarea
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="e.g., Device lost, suspected breach, etc."
                                rows={2}
                            />
                        </div>

                        <div className="warning-box">
                            <AlertTriangle size={20} />
                            <div>
                                <strong>Warning:</strong>
                                <p>
                                    After revocation, both devices will need to be re-paired to establish
                                    a new entangled connection. Any active encrypted sessions will be terminated.
                                </p>
                            </div>
                        </div>
                    </>
                );

            case 'processing':
                return (
                    <div className="processing-state">
                        <div className="modal-icon processing">
                            <ShieldOff size={48} className="pulse" />
                        </div>
                        <h2>Revoking Entanglement...</h2>
                        <p>Invalidating cryptographic keys and clearing shared entropy pool</p>
                        <div className="progress-bar">
                            <div className="progress-fill animate" />
                        </div>
                    </div>
                );

            case 'success':
                return (
                    <div className="success-state">
                        <div className="modal-icon success">
                            <CheckCircle size={48} />
                        </div>
                        <h2>Entanglement Revoked</h2>
                        <p>The device pairing has been successfully terminated.</p>

                        <div className="success-details">
                            <div className="detail-row">
                                <span className="label">Status:</span>
                                <span className="value">Revoked</span>
                            </div>
                            <div className="detail-row">
                                <span className="label">Revoked at:</span>
                                <span className="value">{new Date().toLocaleString()}</span>
                            </div>
                            {selectedCompromised && (
                                <div className="detail-row">
                                    <span className="label">Compromised device:</span>
                                    <span className="value warning">Marked for review</span>
                                </div>
                            )}
                        </div>

                        <div className="info-box">
                            <p>
                                The randomness pool has been securely deleted.
                                To reconnect these devices, initiate a new pairing process.
                            </p>
                        </div>
                    </div>
                );

            case 'error':
                return (
                    <div className="error-state">
                        <div className="modal-icon error">
                            <XCircle size={48} />
                        </div>
                        <h2>Revocation Failed</h2>
                        <p className="error-message">{error}</p>

                        <div className="error-actions">
                            <button className="btn-secondary" onClick={() => setStep('confirm')}>
                                Try Again
                            </button>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="revoke-modal" onClick={(e) => e.stopPropagation()}>
                {/* Close button */}
                <button className="modal-close" onClick={onCancel}>×</button>

                {/* Content */}
                <div className="modal-content">
                    {renderContent()}
                </div>

                {/* Actions */}
                <div className="modal-actions">
                    {step === 'confirm' && (
                        <>
                            <button className="btn-secondary" onClick={onCancel}>
                                Cancel
                            </button>
                            <button
                                className="btn-danger"
                                onClick={handleRevoke}
                                disabled={loading}
                            >
                                {loading ? <Loader className="spinning" size={20} /> : <Unlink size={20} />}
                                Revoke Now
                            </button>
                        </>
                    )}

                    {step === 'success' && (
                        <button className="btn-primary" onClick={onConfirm}>
                            <CheckCircle size={20} />
                            Done
                        </button>
                    )}

                    {step === 'error' && (
                        <button className="btn-secondary" onClick={onCancel}>
                            Close
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default InstantRevokeModal;

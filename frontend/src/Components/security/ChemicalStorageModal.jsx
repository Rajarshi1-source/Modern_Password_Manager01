/**
 * Chemical Storage Modal
 * ======================
 * 
 * Main UI component for chemical password storage feature.
 * Provides tabbed interface for:
 * - DNA Encoding
 * - Time-Lock capsules
 * - Physical storage (lab synthesis)
 * - Certificates
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import chemicalStorageService from '../../services/chemicalStorageService';
import DNASequenceVisualizer from './DNASequenceVisualizer';
import TimeLockCountdown from './TimeLockCountdown';

const TABS = [
    { id: 'encode', label: '🧬 Encode', icon: '🧬' },
    { id: 'timelock', label: '⏰ Time-Lock', icon: '⏰' },
    { id: 'storage', label: '🏭 Physical', icon: '🏭' },
    { id: 'certificates', label: '📜 Certs', icon: '📜' },
];

const ChemicalStorageModal = ({
    isOpen,
    onClose,
    initialPassword = '',
    onPasswordGenerated,
}) => {
    const [activeTab, setActiveTab] = useState('encode');
    const [password, setPassword] = useState(initialPassword);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [subscription, setSubscription] = useState(null);

    // Encode tab state
    const [dnaSequence, setDnaSequence] = useState(null);
    const [validation, setValidation] = useState(null);

    // Time-lock tab state
    const [timeLockHours, setTimeLockHours] = useState(72);
    const [beneficiaryEmail, setBeneficiaryEmail] = useState('');
    const [capsuleCreated, setCapsuleCreated] = useState(null);

    // Storage tab state
    const [synthesisOrder, setSynthesisOrder] = useState(null);
    const [providers, setProviders] = useState([]);
    const [selectedProvider, setSelectedProvider] = useState('mock');

    // Certificates tab state
    const [certificates, setCertificates] = useState([]);

    // Load subscription on mount
    useEffect(() => {
        if (isOpen) {
            loadSubscription();
            loadProviders();
            loadCertificates();
        }
    }, [isOpen]);

    const loadSubscription = async () => {
        const result = await chemicalStorageService.getSubscription();
        if (result.success) {
            setSubscription(result.subscription);
        }
    };

    const loadProviders = async () => {
        const result = await chemicalStorageService.getProviders();
        if (result.success) {
            setProviders(result.providers);
        }
    };

    const loadCertificates = async () => {
        const result = await chemicalStorageService.listCertificates();
        if (result.success) {
            setCertificates(result.certificates);
        }
    };

    // Encode password to DNA
    const handleEncode = async () => {
        if (!password) {
            setError('Please enter a password');
            return;
        }

        setLoading(true);
        setError(null);

        const result = await chemicalStorageService.encodePassword(password);

        if (result.success) {
            setDnaSequence(result.dna_sequence);
            setValidation(result.validation);
        } else {
            setError(result.error);
        }

        setLoading(false);
    };

    // Create time-lock capsule
    const handleCreateTimeLock = async () => {
        if (!password) {
            setError('Please enter a password');
            return;
        }

        setLoading(true);
        setError(null);

        const result = await chemicalStorageService.createTimeLock(password, timeLockHours, {
            beneficiaryEmail: beneficiaryEmail || undefined,
        });

        if (result.success) {
            setCapsuleCreated(result);
        } else {
            setError(result.error);
        }

        setLoading(false);
    };

    // Order synthesis
    const handleOrderSynthesis = async () => {
        if (!dnaSequence) {
            setError('Please encode password first');
            return;
        }

        setLoading(true);
        setError(null);

        const result = await chemicalStorageService.orderSynthesis(
            dnaSequence.sequence,
            selectedProvider
        );

        if (result.success) {
            setSynthesisOrder(result);
            loadCertificates(); // Refresh certificates
        } else {
            setError(result.error);
        }

        setLoading(false);
    };

    if (!isOpen) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <motion.div
                className="modal-content"
                onClick={e => e.stopPropagation()}
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
            >
                {/* Header */}
                <div className="modal-header">
                    <div className="header-title">
                        <span className="header-icon">🧪</span>
                        <div>
                            <h2>Chemical Password Storage</h2>
                            <span className="tier-badge">{subscription?.tier || 'Free'}</span>
                        </div>
                    </div>
                    <button className="close-btn" onClick={onClose}>✕</button>
                </div>

                {/* Tabs */}
                <div className="tabs">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            <span className="tab-icon">{tab.icon}</span>
                            <span className="tab-label">{tab.label}</span>
                        </button>
                    ))}
                </div>

                {/* Error Display */}
                <AnimatePresence>
                    {error && (
                        <motion.div
                            className="error-banner"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                        >
                            ⚠️ {error}
                            <button onClick={() => setError(null)}>✕</button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Tab Content */}
                <div className="tab-content">
                    {/* ENCODE TAB */}
                    {activeTab === 'encode' && (
                        <div className="tab-panel encode-panel">
                            <div className="input-group">
                                <label>Password to encode</label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    placeholder="Enter password..."
                                />
                            </div>

                            <button
                                className="btn-primary"
                                onClick={handleEncode}
                                disabled={loading || !password}
                            >
                                {loading ? 'Encoding...' : '🧬 Encode to DNA'}
                            </button>

                            {dnaSequence && (
                                <div className="result-section">
                                    <DNASequenceVisualizer
                                        sequence={dnaSequence.sequence}
                                        gcContent={dnaSequence.gc_content}
                                        checksum={dnaSequence.checksum}
                                    />

                                    {validation && !validation.is_valid && (
                                        <div className="validation-warnings">
                                            {validation.errors.map((err, i) => (
                                                <div key={i} className="warning-item error">⛔ {err}</div>
                                            ))}
                                            {validation.warnings.map((warn, i) => (
                                                <div key={i} className="warning-item">⚠️ {warn}</div>
                                            ))}
                                        </div>
                                    )}

                                    <div className="cost-estimate">
                                        <h4>Estimated Synthesis Cost</h4>
                                        <span className="cost-value">
                                            ${chemicalStorageService.estimateCost(dnaSequence.sequence_length || dnaSequence.sequence.length).totalUsd}
                                        </span>
                                        <span className="cost-note">via {selectedProvider}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* TIME-LOCK TAB */}
                    {activeTab === 'timelock' && (
                        <div className="tab-panel timelock-panel">
                            {!capsuleCreated ? (
                                <>
                                    <div className="input-group">
                                        <label>Password to lock</label>
                                        <input
                                            type="password"
                                            value={password}
                                            onChange={e => setPassword(e.target.value)}
                                            placeholder="Enter password..."
                                        />
                                    </div>

                                    <div className="input-group">
                                        <label>Delay (hours)</label>
                                        <input
                                            type="number"
                                            value={timeLockHours}
                                            onChange={e => setTimeLockHours(parseInt(e.target.value) || 1)}
                                            min={1}
                                            max={8760}
                                        />
                                        <span className="input-hint">
                                            = {Math.floor(timeLockHours / 24)} days {timeLockHours % 24} hours
                                        </span>
                                    </div>

                                    <div className="input-group">
                                        <label>Beneficiary Email (optional)</label>
                                        <input
                                            type="email"
                                            value={beneficiaryEmail}
                                            onChange={e => setBeneficiaryEmail(e.target.value)}
                                            placeholder="family@example.com"
                                        />
                                        <span className="input-hint">
                                            This person will be notified when the capsule unlocks
                                        </span>
                                    </div>

                                    <button
                                        className="btn-primary"
                                        onClick={handleCreateTimeLock}
                                        disabled={loading || !password}
                                    >
                                        {loading ? 'Creating...' : '🔒 Create Time-Lock Capsule'}
                                    </button>
                                </>
                            ) : (
                                <div className="capsule-created">
                                    <div className="success-message">
                                        <span className="success-icon">✅</span>
                                        <h3>Capsule Created!</h3>
                                        <p>Your password is now time-locked</p>
                                    </div>

                                    <TimeLockCountdown
                                        unlockAt={capsuleCreated.unlock_at}
                                        capsuleId={capsuleCreated.capsule_id}
                                        beneficiaryEmail={beneficiaryEmail}
                                    />

                                    <button
                                        className="btn-secondary"
                                        onClick={() => setCapsuleCreated(null)}
                                    >
                                        Create Another
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* PHYSICAL STORAGE TAB */}
                    {activeTab === 'storage' && (
                        <div className="tab-panel storage-panel">
                            <div className="enterprise-notice">
                                {subscription?.tier === 'enterprise' ? (
                                    <span className="enterprise-badge">✨ Enterprise Enabled</span>
                                ) : (
                                    <span className="demo-badge">Demo Mode (Mock Synthesis)</span>
                                )}
                            </div>

                            <div className="input-group">
                                <label>Lab Provider</label>
                                <select
                                    value={selectedProvider}
                                    onChange={e => setSelectedProvider(e.target.value)}
                                >
                                    {providers.map(p => (
                                        <option key={p.id} value={p.id}>
                                            {p.name} - ${p.pricing?.synthesis?.per_bp_usd || '0.07'}/bp
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {!dnaSequence ? (
                                <div className="info-box">
                                    <p>First, encode your password in the Encode tab to generate a DNA sequence.</p>
                                    <button
                                        className="btn-secondary"
                                        onClick={() => setActiveTab('encode')}
                                    >
                                        Go to Encode
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <div className="sequence-preview">
                                        <span className="preview-label">Sequence Preview</span>
                                        <code>{dnaSequence.sequence.slice(0, 50)}...</code>
                                        <span className="preview-length">{dnaSequence.sequence.length} bp</span>
                                    </div>

                                    <div className="cost-summary">
                                        <div className="cost-row">
                                            <span>Synthesis</span>
                                            <span>${chemicalStorageService.estimateCost(dnaSequence.sequence.length, selectedProvider).synthesisUsd}</span>
                                        </div>
                                        <div className="cost-row">
                                            <span>Handling & Shipping</span>
                                            <span>$55.00</span>
                                        </div>
                                        <div className="cost-row total">
                                            <span>Total</span>
                                            <span>${chemicalStorageService.estimateCost(dnaSequence.sequence.length, selectedProvider).totalUsd}</span>
                                        </div>
                                    </div>

                                    <button
                                        className="btn-primary"
                                        onClick={handleOrderSynthesis}
                                        disabled={loading}
                                    >
                                        {loading ? 'Processing...' : '🏭 Order Synthesis'}
                                    </button>
                                </>
                            )}

                            {synthesisOrder && (
                                <div className="order-result">
                                    <h4>✅ Order Submitted</h4>
                                    <div className="order-details">
                                        <span>Order ID: {synthesisOrder.order_id}</span>
                                        <span>Status: {synthesisOrder.status}</span>
                                        <span>Est. Completion: {new Date(synthesisOrder.estimated_completion).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* CERTIFICATES TAB */}
                    {activeTab === 'certificates' && (
                        <div className="tab-panel certificates-panel">
                            <h3>Your Chemical Storage Certificates</h3>

                            {certificates.length === 0 ? (
                                <div className="empty-state">
                                    <span className="empty-icon">📜</span>
                                    <p>No certificates yet</p>
                                    <p className="empty-hint">Certificates are generated when you store passwords chemically</p>
                                </div>
                            ) : (
                                <div className="certificates-list">
                                    {certificates.map(cert => (
                                        <div key={cert.certificate_id} className="certificate-card">
                                            <div className="cert-header">
                                                <span className="cert-id">#{cert.certificate_id.slice(0, 8)}</span>
                                                <span className="cert-date">{new Date(cert.created_at).toLocaleDateString()}</span>
                                            </div>
                                            <div className="cert-details">
                                                <span>Method: {cert.encoding_method}</span>
                                                <span>ECC: {cert.error_correction}</span>
                                                {cert.synthesis_provider && (
                                                    <span>Provider: {cert.synthesis_provider}</span>
                                                )}
                                            </div>
                                            {cert.time_lock && (
                                                <span className="time-lock-badge">⏰ Time-Locked</span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <style jsx>{`
          .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
          }

          .modal-content {
            background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 16px;
            width: 90%;
            max-width: 700px;
            max-height: 85vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
          }

          .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
          }

          .header-title {
            display: flex;
            align-items: center;
            gap: 12px;
          }

          .header-icon {
            font-size: 32px;
          }

          h2 {
            margin: 0;
            color: #fff;
            font-size: 20px;
          }

          .tier-badge {
            font-size: 11px;
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            padding: 2px 8px;
            border-radius: 10px;
            text-transform: uppercase;
          }

          .close-btn {
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
          }

          .tabs {
            display: flex;
            padding: 0 24px;
            gap: 4px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
          }

          .tab {
            background: transparent;
            border: none;
            color: #9ca3af;
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
          }

          .tab:hover {
            color: #fff;
          }

          .tab.active {
            color: #fff;
            border-bottom-color: #6366f1;
          }

          .error-banner {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.4);
            margin: 12px 24px;
            padding: 12px;
            border-radius: 8px;
            color: #fca5a5;
            display: flex;
            justify-content: space-between;
            align-items: center;
          }

          .tab-content {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
          }

          .tab-panel {
            display: flex;
            flex-direction: column;
            gap: 16px;
          }

          .input-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
          }

          .input-group label {
            font-size: 12px;
            color: #9ca3af;
            text-transform: uppercase;
          }

          .input-group input,
          .input-group select {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 12px;
            border-radius: 8px;
            font-size: 14px;
          }

          .input-hint {
            font-size: 11px;
            color: #6b7280;
          }

          .btn-primary {
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            border: none;
            color: #fff;
            padding: 14px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
          }

          .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .btn-secondary {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
          }

          .result-section {
            margin-top: 16px;
          }

          .cost-estimate {
            background: rgba(99, 102, 241, 0.1);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            margin-top: 16px;
          }

          .cost-value {
            font-size: 28px;
            font-weight: 700;
            color: #fff;
            display: block;
          }

          .cost-note {
            font-size: 12px;
            color: #9ca3af;
          }

          .empty-state {
            text-align: center;
            padding: 40px;
            color: #6b7280;
          }

          .empty-icon {
            font-size: 48px;
            opacity: 0.5;
          }

          .certificates-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
          }

          .certificate-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 12px;
          }

          .cert-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
          }

          .cert-id {
            font-family: monospace;
            color: #8b5cf6;
          }

          .cert-date {
            font-size: 12px;
            color: #6b7280;
          }

          .cert-details {
            font-size: 12px;
            color: #9ca3af;
            display: flex;
            gap: 16px;
          }

          .time-lock-badge {
            display: inline-block;
            margin-top: 8px;
            font-size: 11px;
            background: rgba(234, 179, 8, 0.2);
            color: #eab308;
            padding: 2px 8px;
            border-radius: 4px;
          }
        `}</style>
            </motion.div>
        </div>
    );
};

export default ChemicalStorageModal;

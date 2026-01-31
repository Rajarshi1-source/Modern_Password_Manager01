/**
 * DuressCodeSetup.jsx
 * 
 * Main setup wizard for Military-Grade Duress Codes.
 * Guides users through enabling duress protection, creating codes,
 * configuring trusted authorities, reviewing decoy vault, and testing.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as duressService from '../../services/duressCodeService';
import './DuressCodeSetup.css';

// Step components
const STEPS = [
    { id: 'intro', title: 'Introduction', icon: '🎖️' },
    { id: 'enable', title: 'Enable Protection', icon: '🛡️' },
    { id: 'codes', title: 'Create Codes', icon: '🔐' },
    { id: 'authorities', title: 'Trusted Authorities', icon: '📞' },
    { id: 'decoy', title: 'Review Decoy', icon: '🎭' },
    { id: 'test', title: 'Test Code', icon: '✅' }
];

const DuressCodeSetup = ({ onComplete, onCancel }) => {
    const { getAccessToken } = useAuth();
    const authToken = getAccessToken();
    const [currentStep, setCurrentStep] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Configuration state
    const [config, setConfig] = useState({
        is_enabled: false,
        silent_alarm_enabled: false,
        evidence_preservation_enabled: true,
        legal_compliance_mode: false
    });

    // Duress codes state
    const [codes, setCodes] = useState([]);
    const [newCode, setNewCode] = useState({
        code: '',
        threatLevel: 'medium',
        codeHint: ''
    });

    // Trusted authorities state
    const [authorities, setAuthorities] = useState([]);
    const [newAuthority, setNewAuthority] = useState({
        type: 'security_team',
        contactMethod: 'email',
        contactDetails: {},
        threatLevels: ['high', 'critical'],
        name: ''
    });

    // Decoy vault state
    const [decoyVault, setDecoyVault] = useState(null);

    // Test state
    const [testCode, setTestCode] = useState('');
    const [testResult, setTestResult] = useState(null);

    // Load existing data
    useEffect(() => {
        loadExistingData();
    }, []);

    const loadExistingData = async () => {
        try {
            setLoading(true);
            const [configData, codesData, authoritiesData] = await Promise.all([
                duressService.getConfig(authToken),
                duressService.getCodes(authToken),
                duressService.getAuthorities(authToken)
            ]);

            if (configData.config) {
                setConfig(configData.config);
            }
            if (codesData.codes) {
                setCodes(codesData.codes);
            }
            if (authoritiesData.authorities) {
                setAuthorities(authoritiesData.authorities);
            }
        } catch (err) {
            console.error('Error loading data:', err);
        } finally {
            setLoading(false);
        }
    };

    // Step navigation
    const nextStep = () => {
        if (currentStep < STEPS.length - 1) {
            setCurrentStep(currentStep + 1);
            setError(null);
        }
    };

    const prevStep = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
            setError(null);
        }
    };

    // Save configuration
    const saveConfig = async (configUpdates) => {
        try {
            setLoading(true);
            const result = await duressService.updateConfig(authToken, configUpdates);
            setConfig(result.config);
            return true;
        } catch (err) {
            setError(err.message);
            return false;
        } finally {
            setLoading(false);
        }
    };

    // Add duress code
    const addCode = async () => {
        if (!newCode.code || newCode.code.length < 6) {
            setError('Duress code must be at least 6 characters');
            return;
        }

        try {
            setLoading(true);
            const result = await duressService.createCode(authToken, newCode);
            setCodes([...codes, result.duress_code]);
            setNewCode({ code: '', threatLevel: 'medium', codeHint: '' });
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Delete duress code
    const removeCode = async (codeId) => {
        try {
            setLoading(true);
            await duressService.deleteCode(authToken, codeId);
            setCodes(codes.filter(c => c.id !== codeId));
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Add trusted authority
    const addAuthorityHandler = async () => {
        if (!newAuthority.name) {
            setError('Authority name is required');
            return;
        }

        try {
            setLoading(true);
            const result = await duressService.addAuthority(authToken, newAuthority);
            setAuthorities([...authorities, result.authority]);
            setNewAuthority({
                type: 'security_team',
                contactMethod: 'email',
                contactDetails: {},
                threatLevels: ['high', 'critical'],
                name: ''
            });
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Remove authority
    const removeAuthority = async (authorityId) => {
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

    // Load decoy vault
    const loadDecoyVault = async (threatLevel = 'medium') => {
        try {
            setLoading(true);
            const result = await duressService.getDecoyVault(authToken, threatLevel);
            setDecoyVault(result.decoy_vault);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Regenerate decoy vault
    const regenerateDecoy = async () => {
        try {
            setLoading(true);
            const result = await duressService.regenerateDecoyVault(authToken, 'medium');
            setDecoyVault(result.decoy_vault);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Test duress code activation
    const testDuressCode = async () => {
        if (!testCode) {
            setError('Please enter a duress code to test');
            return;
        }

        try {
            setLoading(true);
            const result = await duressService.testActivation(authToken, testCode);
            setTestResult(result);
            setError(null);
        } catch (err) {
            setError(err.message);
            setTestResult(null);
        } finally {
            setLoading(false);
        }
    };

    // Complete setup
    const completeSetup = async () => {
        await saveConfig({ ...config, is_enabled: true });
        onComplete?.();
    };

    // Render step content
    const renderStep = () => {
        const step = STEPS[currentStep];

        switch (step.id) {
            case 'intro':
                return <IntroStep onContinue={nextStep} />;
            case 'enable':
                return (
                    <EnableStep
                        config={config}
                        onConfigChange={setConfig}
                        onSave={saveConfig}
                        loading={loading}
                    />
                );
            case 'codes':
                return (
                    <CodesStep
                        codes={codes}
                        newCode={newCode}
                        onNewCodeChange={setNewCode}
                        onAddCode={addCode}
                        onRemoveCode={removeCode}
                        loading={loading}
                    />
                );
            case 'authorities':
                return (
                    <AuthoritiesStep
                        authorities={authorities}
                        newAuthority={newAuthority}
                        onNewAuthorityChange={setNewAuthority}
                        onAddAuthority={addAuthorityHandler}
                        onRemoveAuthority={removeAuthority}
                        loading={loading}
                    />
                );
            case 'decoy':
                return (
                    <DecoyStep
                        decoyVault={decoyVault}
                        onLoadDecoy={loadDecoyVault}
                        onRegenerate={regenerateDecoy}
                        loading={loading}
                    />
                );
            case 'test':
                return (
                    <TestStep
                        testCode={testCode}
                        onTestCodeChange={setTestCode}
                        testResult={testResult}
                        onTest={testDuressCode}
                        onComplete={completeSetup}
                        loading={loading}
                    />
                );
            default:
                return null;
        }
    };

    return (
        <div className="duress-setup-wizard">
            {/* Progress Indicator */}
            <div className="setup-progress">
                {STEPS.map((step, index) => (
                    <div
                        key={step.id}
                        className={`progress-step ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'completed' : ''}`}
                        onClick={() => index < currentStep && setCurrentStep(index)}
                    >
                        <span className="step-icon">{step.icon}</span>
                        <span className="step-title">{step.title}</span>
                        <div className="step-connector" />
                    </div>
                ))}
            </div>

            {/* Error Display */}
            {error && (
                <div className="setup-error">
                    <span className="error-icon">⚠️</span>
                    <span className="error-message">{error}</span>
                    <button className="dismiss-btn" onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Step Content */}
            <div className="setup-content">
                {renderStep()}
            </div>

            {/* Navigation */}
            <div className="setup-navigation">
                <button
                    className="nav-btn cancel-btn"
                    onClick={onCancel}
                    disabled={loading}
                >
                    Cancel
                </button>

                <div className="nav-spacer" />

                {currentStep > 0 && (
                    <button
                        className="nav-btn back-btn"
                        onClick={prevStep}
                        disabled={loading}
                    >
                        ← Back
                    </button>
                )}

                {currentStep < STEPS.length - 1 && (
                    <button
                        className="nav-btn next-btn"
                        onClick={nextStep}
                        disabled={loading}
                    >
                        Next →
                    </button>
                )}
            </div>
        </div>
    );
};

// =============================================================================
// Step Components
// =============================================================================

const IntroStep = ({ onContinue }) => (
    <div className="step-intro">
        <div className="intro-header">
            <span className="intro-icon">🎖️</span>
            <h2>Military-Grade Duress Protection</h2>
        </div>

        <div className="intro-description">
            <p>
                Duress codes provide sophisticated protection against coerced access scenarios.
                If someone forces you to unlock your vault, enter a duress code instead of
                your real password to trigger protective measures.
            </p>
        </div>

        <div className="feature-grid">
            <div className="feature-card">
                <span className="feature-icon">🎭</span>
                <h3>Decoy Vault</h3>
                <p>Show convincing fake credentials while your real data stays hidden</p>
            </div>

            <div className="feature-card">
                <span className="feature-icon">📞</span>
                <h3>Silent Alarms</h3>
                <p>Automatically notify trusted contacts without alerting the attacker</p>
            </div>

            <div className="feature-card">
                <span className="feature-icon">📦</span>
                <h3>Evidence Preservation</h3>
                <p>Capture forensic data including IP, location, and device info</p>
            </div>

            <div className="feature-card">
                <span className="feature-icon">🔒</span>
                <h3>Multiple Threat Levels</h3>
                <p>Different codes for different threat scenarios</p>
            </div>
        </div>

        <div className="intro-warning">
            <span className="warning-icon">⚠️</span>
            <p>
                <strong>Important:</strong> Make sure your duress codes are memorable but
                distinct from your real password. Practice using them regularly.
            </p>
        </div>

        <button className="primary-btn start-btn" onClick={onContinue}>
            Begin Setup →
        </button>
    </div>
);

const EnableStep = ({ config, onConfigChange, onSave, loading }) => {
    const handleToggle = (field) => {
        onConfigChange({ ...config, [field]: !config[field] });
    };

    return (
        <div className="step-enable">
            <h2>Configure Protection Settings</h2>
            <p className="step-description">
                Choose which protection features to enable for your account.
            </p>

            <div className="settings-list">
                <div className="setting-item">
                    <div className="setting-info">
                        <h3>🛡️ Enable Duress Protection</h3>
                        <p>Activate duress code system for your account</p>
                    </div>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={config.is_enabled}
                            onChange={() => handleToggle('is_enabled')}
                        />
                        <span className="toggle-slider" />
                    </label>
                </div>

                <div className="setting-item">
                    <div className="setting-info">
                        <h3>📞 Silent Alarms</h3>
                        <p>Send notifications to trusted authorities when duress is detected</p>
                    </div>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={config.silent_alarm_enabled}
                            onChange={() => handleToggle('silent_alarm_enabled')}
                        />
                        <span className="toggle-slider" />
                    </label>
                </div>

                <div className="setting-item">
                    <div className="setting-info">
                        <h3>📦 Evidence Preservation</h3>
                        <p>Automatically collect forensic evidence during duress events</p>
                    </div>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={config.evidence_preservation_enabled}
                            onChange={() => handleToggle('evidence_preservation_enabled')}
                        />
                        <span className="toggle-slider" />
                    </label>
                </div>

                <div className="setting-item enterprise-only">
                    <div className="setting-info">
                        <h3>⚖️ Legal Compliance Mode</h3>
                        <p>RFC 3161 timestamping and chain of custody for legal admissibility</p>
                        <span className="enterprise-badge">Enterprise</span>
                    </div>
                    <label className="toggle-switch">
                        <input
                            type="checkbox"
                            checked={config.legal_compliance_mode}
                            onChange={() => handleToggle('legal_compliance_mode')}
                            disabled
                        />
                        <span className="toggle-slider" />
                    </label>
                </div>
            </div>

            <button
                className="primary-btn save-btn"
                onClick={() => onSave(config)}
                disabled={loading}
            >
                {loading ? 'Saving...' : 'Save Settings'}
            </button>
        </div>
    );
};

const CodesStep = ({ codes, newCode, onNewCodeChange, onAddCode, onRemoveCode, loading }) => {
    const codeStrength = duressService.calculateCodeStrength(newCode.code);
    const threatLevelInfo = duressService.formatThreatLevel(newCode.threatLevel);

    return (
        <div className="step-codes">
            <h2>Create Duress Codes</h2>
            <p className="step-description">
                Create codes for different threat levels. You can enter these instead of
                your real password when under duress.
            </p>

            {/* Existing Codes */}
            {codes.length > 0 && (
                <div className="existing-codes">
                    <h3>Your Duress Codes</h3>
                    <div className="codes-list">
                        {codes.map(code => {
                            const levelInfo = duressService.formatThreatLevel(code.threat_level);
                            return (
                                <div key={code.id} className="code-item">
                                    <span className="code-icon">{levelInfo.icon}</span>
                                    <div className="code-info">
                                        <span className="code-level" style={{ color: levelInfo.color }}>
                                            {levelInfo.label} Threat
                                        </span>
                                        <span className="code-hint">
                                            {code.code_hint || 'No hint set'}
                                        </span>
                                    </div>
                                    <span className="code-activations">
                                        {code.activation_count || 0} activations
                                    </span>
                                    <button
                                        className="remove-btn"
                                        onClick={() => onRemoveCode(code.id)}
                                        disabled={loading}
                                    >
                                        ×
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Add New Code */}
            <div className="add-code-form">
                <h3>Add New Code</h3>

                <div className="form-group">
                    <label>Duress Code</label>
                    <input
                        type="password"
                        className="code-input"
                        placeholder="Enter your duress code"
                        value={newCode.code}
                        onChange={(e) => onNewCodeChange({ ...newCode, code: e.target.value })}
                    />
                    <div className="strength-meter">
                        <div
                            className="strength-bar"
                            style={{
                                width: `${codeStrength.score}%`,
                                backgroundColor: codeStrength.score >= 80 ? '#22c55e' :
                                    codeStrength.score >= 60 ? '#eab308' : '#ef4444'
                            }}
                        />
                        <span className="strength-label">{codeStrength.label}</span>
                    </div>
                </div>

                <div className="form-group">
                    <label>Threat Level</label>
                    <select
                        className="level-select"
                        value={newCode.threatLevel}
                        onChange={(e) => onNewCodeChange({ ...newCode, threatLevel: e.target.value })}
                    >
                        <option value="low">🟢 Low - Show Limited Decoy</option>
                        <option value="medium">🟡 Medium - Full Decoy + Evidence</option>
                        <option value="high">🟠 High - Decoy + Alert Authorities</option>
                        <option value="critical">🔴 Critical - Full Response</option>
                    </select>
                    <p className="level-description">{threatLevelInfo.description}</p>
                </div>

                <div className="form-group">
                    <label>Code Hint (for your memory)</label>
                    <input
                        type="text"
                        className="hint-input"
                        placeholder="Optional hint to remember this code"
                        value={newCode.codeHint}
                        onChange={(e) => onNewCodeChange({ ...newCode, codeHint: e.target.value })}
                    />
                </div>

                <button
                    className="primary-btn add-btn"
                    onClick={onAddCode}
                    disabled={loading || !newCode.code || newCode.code.length < 6}
                >
                    {loading ? 'Adding...' : 'Add Code'}
                </button>
            </div>
        </div>
    );
};

const AuthoritiesStep = ({ authorities, newAuthority, onNewAuthorityChange, onAddAuthority, onRemoveAuthority, loading }) => {
    return (
        <div className="step-authorities">
            <h2>Trusted Authorities</h2>
            <p className="step-description">
                Configure contacts who will be silently notified when a duress code is used.
            </p>

            {/* Existing Authorities */}
            {authorities.length > 0 && (
                <div className="existing-authorities">
                    <h3>Configured Contacts</h3>
                    <div className="authorities-list">
                        {authorities.map(auth => {
                            const typeInfo = duressService.formatAuthorityType(auth.authority_type);
                            const methodInfo = duressService.formatContactMethod(auth.contact_method);
                            return (
                                <div key={auth.id} className="authority-item">
                                    <span className="auth-icon">{typeInfo.icon}</span>
                                    <div className="auth-info">
                                        <span className="auth-name">{auth.name || typeInfo.label}</span>
                                        <span className="auth-method">{methodInfo.icon} {methodInfo.label}</span>
                                    </div>
                                    <div className="auth-levels">
                                        {(auth.threat_levels || []).map(level => (
                                            <span
                                                key={level}
                                                className="level-badge"
                                                style={{ backgroundColor: duressService.formatThreatLevel(level).color }}
                                            >
                                                {level}
                                            </span>
                                        ))}
                                    </div>
                                    <button
                                        className="remove-btn"
                                        onClick={() => onRemoveAuthority(auth.id)}
                                        disabled={loading}
                                    >
                                        ×
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Add New Authority */}
            <div className="add-authority-form">
                <h3>Add Contact</h3>

                <div className="form-row">
                    <div className="form-group">
                        <label>Contact Name</label>
                        <input
                            type="text"
                            placeholder="e.g., John Smith (Lawyer)"
                            value={newAuthority.name}
                            onChange={(e) => onNewAuthorityChange({ ...newAuthority, name: e.target.value })}
                        />
                    </div>

                    <div className="form-group">
                        <label>Authority Type</label>
                        <select
                            value={newAuthority.type}
                            onChange={(e) => onNewAuthorityChange({ ...newAuthority, type: e.target.value })}
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
                            value={newAuthority.contactMethod}
                            onChange={(e) => onNewAuthorityChange({ ...newAuthority, contactMethod: e.target.value })}
                        >
                            <option value="email">📧 Email</option>
                            <option value="sms">📱 SMS</option>
                            <option value="phone">📞 Phone Call</option>
                            <option value="webhook">🔗 Webhook</option>
                            <option value="signal">💬 Signal</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>
                            {newAuthority.contactMethod === 'email' ? 'Email Address' :
                                newAuthority.contactMethod === 'sms' ? 'Phone Number' :
                                    newAuthority.contactMethod === 'phone' ? 'Phone Number' :
                                        newAuthority.contactMethod === 'webhook' ? 'Webhook URL' :
                                            'Contact Details'}
                        </label>
                        <input
                            type="text"
                            placeholder={
                                newAuthority.contactMethod === 'email' ? 'lawyer@example.com' :
                                    newAuthority.contactMethod === 'sms' ? '+1234567890' :
                                        newAuthority.contactMethod === 'phone' ? '+1234567890' :
                                            newAuthority.contactMethod === 'webhook' ? 'https://...' :
                                                'Enter details'
                            }
                            value={newAuthority.contactDetails.value || ''}
                            onChange={(e) => onNewAuthorityChange({
                                ...newAuthority,
                                contactDetails: { ...newAuthority.contactDetails, value: e.target.value }
                            })}
                        />
                    </div>
                </div>

                <div className="form-group">
                    <label>Trigger on Threat Levels</label>
                    <div className="level-checkboxes">
                        {['low', 'medium', 'high', 'critical'].map(level => {
                            const levelInfo = duressService.formatThreatLevel(level);
                            return (
                                <label key={level} className="level-checkbox">
                                    <input
                                        type="checkbox"
                                        checked={newAuthority.threatLevels.includes(level)}
                                        onChange={(e) => {
                                            const newLevels = e.target.checked
                                                ? [...newAuthority.threatLevels, level]
                                                : newAuthority.threatLevels.filter(l => l !== level);
                                            onNewAuthorityChange({ ...newAuthority, threatLevels: newLevels });
                                        }}
                                    />
                                    <span style={{ color: levelInfo.color }}>
                                        {levelInfo.icon} {levelInfo.label}
                                    </span>
                                </label>
                            );
                        })}
                    </div>
                </div>

                <button
                    className="primary-btn add-btn"
                    onClick={onAddAuthority}
                    disabled={loading || !newAuthority.name}
                >
                    {loading ? 'Adding...' : 'Add Contact'}
                </button>
            </div>
        </div>
    );
};

const DecoyStep = ({ decoyVault, onLoadDecoy, onRegenerate, loading }) => {
    useEffect(() => {
        if (!decoyVault) {
            onLoadDecoy('medium');
        }
    }, []);

    return (
        <div className="step-decoy">
            <h2>Review Decoy Vault</h2>
            <p className="step-description">
                This is what attackers will see when you enter a duress code.
                The data is realistic-looking but completely fake.
            </p>

            {loading && !decoyVault && (
                <div className="loading-state">
                    <div className="spinner" />
                    <span>Loading decoy vault...</span>
                </div>
            )}

            {decoyVault && (
                <>
                    <div className="decoy-stats">
                        <div className="stat">
                            <span className="stat-value">{decoyVault.items?.length || 0}</span>
                            <span className="stat-label">Fake Credentials</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{decoyVault.folders?.length || 0}</span>
                            <span className="stat-label">Folders</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{Math.round((decoyVault.realism_score || 0) * 100)}%</span>
                            <span className="stat-label">Realism Score</span>
                        </div>
                    </div>

                    <div className="decoy-preview">
                        <h3>Sample Entries</h3>
                        <div className="preview-list">
                            {(decoyVault.items || []).slice(0, 5).map((item, index) => (
                                <div key={index} className="preview-item">
                                    <span className="item-icon">
                                        {item.type === 'login' ? '🔑' :
                                            item.type === 'card' ? '💳' :
                                                item.type === 'identity' ? '🪪' : '📝'}
                                    </span>
                                    <div className="item-info">
                                        <span className="item-name">{item.name || item.service_name}</span>
                                        <span className="item-meta">
                                            {item.username || item.email || 'No username'}
                                        </span>
                                    </div>
                                    <span className="fake-badge">FAKE</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <button
                        className="secondary-btn regenerate-btn"
                        onClick={onRegenerate}
                        disabled={loading}
                    >
                        {loading ? 'Regenerating...' : '🔄 Regenerate Decoy Data'}
                    </button>
                </>
            )}
        </div>
    );
};

const TestStep = ({ testCode, onTestCodeChange, testResult, onTest, onComplete, loading }) => {
    return (
        <div className="step-test">
            <h2>Test Your Duress Code</h2>
            <p className="step-description">
                Test your duress code in safe mode. This will NOT send real alerts
                or affect your actual vault.
            </p>

            <div className="test-form">
                <div className="form-group">
                    <label>Enter a Duress Code to Test</label>
                    <input
                        type="password"
                        className="test-input"
                        placeholder="Enter your duress code"
                        value={testCode}
                        onChange={(e) => onTestCodeChange(e.target.value)}
                    />
                </div>

                <button
                    className="secondary-btn test-btn"
                    onClick={onTest}
                    disabled={loading || !testCode}
                >
                    {loading ? 'Testing...' : '🧪 Test Activation'}
                </button>
            </div>

            {testResult && (
                <div className={`test-result ${testResult.success ? 'success' : 'failure'}`}>
                    {testResult.success ? (
                        <>
                            <span className="result-icon">✅</span>
                            <h3>Duress Code Recognized!</h3>
                            <p>Threat Level: <strong>{duressService.formatThreatLevel(testResult.threat_level).label}</strong></p>
                            <p>Actions that would trigger:</p>
                            <ul>
                                <li>✓ Show decoy vault</li>
                                {testResult.evidence_would_be_collected && <li>✓ Collect evidence</li>}
                                {testResult.alarms_would_be_sent && <li>✓ Send silent alarms</li>}
                            </ul>
                        </>
                    ) : (
                        <>
                            <span className="result-icon">❌</span>
                            <h3>Code Not Recognized</h3>
                            <p>The entered code does not match any configured duress codes.</p>
                        </>
                    )}
                </div>
            )}

            <div className="complete-setup">
                <button
                    className="primary-btn complete-btn"
                    onClick={onComplete}
                    disabled={loading}
                >
                    Complete Setup ✓
                </button>
            </div>
        </div>
    );
};

export default DuressCodeSetup;

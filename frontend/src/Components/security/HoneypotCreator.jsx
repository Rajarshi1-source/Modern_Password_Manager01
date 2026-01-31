/**
 * Honeypot Creator Component
 * 
 * Modal form for creating new honeypot email addresses.
 * Supports single creation and bulk creation wizard.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
 */

import React, { useState, useEffect } from 'react';
import {
    FiX,
    FiPlus,
    FiMail,
    FiInfo,
    FiCheckCircle,
    FiAlertCircle,
    FiLoader
} from 'react-icons/fi';
import honeypotService from '../../services/honeypotService';
import './HoneypotDashboard.css';

const HoneypotCreator = ({ onClose, onCreated, vaultItems = [] }) => {
    const [mode, setMode] = useState('single'); // 'single' or 'bulk'
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    // Single creation form
    const [serviceName, setServiceName] = useState('');
    const [serviceDomain, setServiceDomain] = useState('');
    const [notes, setNotes] = useState('');
    const [tags, setTags] = useState('');
    const [vaultItemId, setVaultItemId] = useState('');

    // Bulk creation
    const [bulkServices, setBulkServices] = useState([
        { service_name: '', service_domain: '' }
    ]);
    const [bulkResults, setBulkResults] = useState(null);

    const handleSingleSubmit = async (e) => {
        e.preventDefault();

        if (!serviceName.trim()) {
            setError('Service name is required');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const result = await honeypotService.createHoneypot({
                service_name: serviceName.trim(),
                service_domain: serviceDomain.trim(),
                notes: notes.trim(),
                tags: tags.split(',').map(t => t.trim()).filter(Boolean),
                vault_item_id: vaultItemId || null
            });

            setSuccess(`Honeypot created: ${result.honeypot.honeypot_address}`);

            setTimeout(() => {
                onCreated(result.honeypot);
            }, 1500);

        } catch (err) {
            setError(err.response?.data?.error || 'Failed to create honeypot');
        } finally {
            setLoading(false);
        }
    };

    const handleBulkSubmit = async (e) => {
        e.preventDefault();

        const validServices = bulkServices.filter(s => s.service_name.trim());

        if (validServices.length === 0) {
            setError('Add at least one service');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const result = await honeypotService.bulkCreateHoneypots(validServices);
            setBulkResults(result);

            if (result.created_count > 0) {
                setTimeout(() => {
                    onCreated();
                }, 2000);
            }

        } catch (err) {
            setError(err.response?.data?.error || 'Bulk creation failed');
        } finally {
            setLoading(false);
        }
    };

    const addBulkRow = () => {
        setBulkServices([...bulkServices, { service_name: '', service_domain: '' }]);
    };

    const updateBulkRow = (index, field, value) => {
        const updated = [...bulkServices];
        updated[index][field] = value;
        setBulkServices(updated);
    };

    const removeBulkRow = (index) => {
        if (bulkServices.length > 1) {
            setBulkServices(bulkServices.filter((_, i) => i !== index));
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content honeypot-creator" onClick={(e) => e.stopPropagation()}>
                <header className="modal-header">
                    <h2>
                        <FiMail /> Create Honeypot Email
                    </h2>
                    <button className="close-btn" onClick={onClose}>
                        <FiX />
                    </button>
                </header>

                {/* Mode Tabs */}
                <div className="creator-tabs">
                    <button
                        className={`tab ${mode === 'single' ? 'active' : ''}`}
                        onClick={() => setMode('single')}
                    >
                        Single Honeypot
                    </button>
                    <button
                        className={`tab ${mode === 'bulk' ? 'active' : ''}`}
                        onClick={() => setMode('bulk')}
                    >
                        Bulk Create
                    </button>
                </div>

                {/* Info Banner */}
                <div className="info-banner">
                    <FiInfo />
                    <p>
                        Honeypot emails detect data breaches. Use a unique honeypot for each
                        service—if it receives spam, that service was likely breached.
                    </p>
                </div>

                {/* Error/Success Messages */}
                {error && (
                    <div className="message error">
                        <FiAlertCircle />
                        {error}
                    </div>
                )}

                {success && (
                    <div className="message success">
                        <FiCheckCircle />
                        {success}
                    </div>
                )}

                {/* Single Creation Form */}
                {mode === 'single' && !success && (
                    <form onSubmit={handleSingleSubmit} className="creator-form">
                        <div className="form-group">
                            <label htmlFor="serviceName">Service Name *</label>
                            <input
                                type="text"
                                id="serviceName"
                                value={serviceName}
                                onChange={(e) => setServiceName(e.target.value)}
                                placeholder="e.g., Netflix, Amazon, LinkedIn"
                                disabled={loading}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="serviceDomain">Service Domain</label>
                            <input
                                type="text"
                                id="serviceDomain"
                                value={serviceDomain}
                                onChange={(e) => setServiceDomain(e.target.value)}
                                placeholder="e.g., netflix.com"
                                disabled={loading}
                            />
                        </div>

                        {vaultItems.length > 0 && (
                            <div className="form-group">
                                <label htmlFor="vaultItem">Link to Vault Item</label>
                                <select
                                    id="vaultItem"
                                    value={vaultItemId}
                                    onChange={(e) => setVaultItemId(e.target.value)}
                                    disabled={loading}
                                >
                                    <option value="">-- No link --</option>
                                    {vaultItems.map(item => (
                                        <option key={item.id} value={item.id}>
                                            {item.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <div className="form-group">
                            <label htmlFor="notes">Notes</label>
                            <textarea
                                id="notes"
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Optional notes about this honeypot"
                                rows={2}
                                disabled={loading}
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="tags">Tags (comma-separated)</label>
                            <input
                                type="text"
                                id="tags"
                                value={tags}
                                onChange={(e) => setTags(e.target.value)}
                                placeholder="e.g., streaming, shopping"
                                disabled={loading}
                            />
                        </div>

                        <div className="form-actions">
                            <button type="button" className="btn btn-secondary" onClick={onClose}>
                                Cancel
                            </button>
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? (
                                    <>
                                        <FiLoader className="spin" /> Creating...
                                    </>
                                ) : (
                                    <>
                                        <FiPlus /> Create Honeypot
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                )}

                {/* Bulk Creation Form */}
                {mode === 'bulk' && !bulkResults && (
                    <form onSubmit={handleBulkSubmit} className="creator-form bulk-form">
                        <div className="bulk-list">
                            {bulkServices.map((service, index) => (
                                <div key={index} className="bulk-row">
                                    <input
                                        type="text"
                                        value={service.service_name}
                                        onChange={(e) => updateBulkRow(index, 'service_name', e.target.value)}
                                        placeholder="Service name"
                                        disabled={loading}
                                    />
                                    <input
                                        type="text"
                                        value={service.service_domain}
                                        onChange={(e) => updateBulkRow(index, 'service_domain', e.target.value)}
                                        placeholder="Domain (optional)"
                                        disabled={loading}
                                    />
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-ghost danger"
                                        onClick={() => removeBulkRow(index)}
                                        disabled={loading || bulkServices.length === 1}
                                    >
                                        <FiX />
                                    </button>
                                </div>
                            ))}
                        </div>

                        <button
                            type="button"
                            className="btn btn-sm btn-secondary add-row-btn"
                            onClick={addBulkRow}
                            disabled={loading}
                        >
                            <FiPlus /> Add Another Service
                        </button>

                        <div className="form-actions">
                            <button type="button" className="btn btn-secondary" onClick={onClose}>
                                Cancel
                            </button>
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? (
                                    <>
                                        <FiLoader className="spin" /> Creating...
                                    </>
                                ) : (
                                    <>
                                        <FiPlus /> Create {bulkServices.filter(s => s.service_name.trim()).length} Honeypots
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                )}

                {/* Bulk Results */}
                {bulkResults && (
                    <div className="bulk-results">
                        <h3>Bulk Creation Results</h3>

                        {bulkResults.created_count > 0 && (
                            <div className="results-section success">
                                <h4><FiCheckCircle /> Created ({bulkResults.created_count})</h4>
                                <ul>
                                    {bulkResults.results.created.map((item, i) => (
                                        <li key={i}>
                                            <strong>{item.service_name}</strong>: {item.honeypot_address}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {bulkResults.failed_count > 0 && (
                            <div className="results-section error">
                                <h4><FiAlertCircle /> Failed ({bulkResults.failed_count})</h4>
                                <ul>
                                    {bulkResults.results.failed.map((item, i) => (
                                        <li key={i}>
                                            <strong>{item.service_name}</strong>: {item.error}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        <div className="form-actions">
                            <button className="btn btn-primary" onClick={onClose}>
                                Done
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default HoneypotCreator;

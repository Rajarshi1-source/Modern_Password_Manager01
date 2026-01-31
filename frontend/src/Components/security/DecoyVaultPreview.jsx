/**
 * DecoyVaultPreview.jsx
 * 
 * Preview component for decoy vault appearance.
 * Shows side-by-side comparison and realism score.
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as duressService from '../../services/duressCodeService';
import './DecoyVaultPreview.css';

const DecoyVaultPreview = ({ threatLevel = 'medium', onClose }) => {
    const { getAccessToken } = useAuth();
    const authToken = getAccessToken();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [decoyVault, setDecoyVault] = useState(null);
    const [selectedThreatLevel, setSelectedThreatLevel] = useState(threatLevel);
    const [viewMode, setViewMode] = useState('grid'); // grid | list
    const [selectedCategory, setSelectedCategory] = useState('all');

    useEffect(() => {
        loadDecoyVault();
    }, [selectedThreatLevel]);

    const loadDecoyVault = async () => {
        try {
            setLoading(true);
            const result = await duressService.getDecoyVault(authToken, selectedThreatLevel);
            setDecoyVault(result.decoy_vault);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const regenerateDecoy = async () => {
        try {
            setLoading(true);
            const result = await duressService.regenerateDecoyVault(authToken, selectedThreatLevel);
            setDecoyVault(result.decoy_vault);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Get unique categories from items
    const getCategories = () => {
        if (!decoyVault?.items) return [];
        const cats = new Set(decoyVault.items.map(item => item.type || 'other'));
        return ['all', ...Array.from(cats)];
    };

    // Filter items by category
    const getFilteredItems = () => {
        if (!decoyVault?.items) return [];
        if (selectedCategory === 'all') return decoyVault.items;
        return decoyVault.items.filter(item => item.type === selectedCategory);
    };

    // Get icon for item type
    const getItemIcon = (type) => {
        const icons = {
            login: '🔑',
            card: '💳',
            identity: '🪪',
            note: '📝',
            other: '📄'
        };
        return icons[type] || icons.other;
    };

    // Get category label
    const getCategoryLabel = (type) => {
        const labels = {
            login: 'Logins',
            card: 'Cards',
            identity: 'Identities',
            note: 'Secure Notes',
            all: 'All Items',
            other: 'Other'
        };
        return labels[type] || type;
    };

    // Calculate realism metrics
    const getRealismMetrics = () => {
        if (!decoyVault) return [];

        const metrics = [
            {
                label: 'Overall Score',
                value: Math.round((decoyVault.realism_score || 0) * 100),
                max: 100,
                icon: '🎯'
            },
            {
                label: 'Credential Count',
                value: decoyVault.items?.length || 0,
                max: 50,
                icon: '🔐'
            },
            {
                label: 'Folder Structure',
                value: decoyVault.folders?.length || 0,
                max: 10,
                icon: '📁'
            }
        ];

        return metrics;
    };

    if (loading && !decoyVault) {
        return (
            <div className="decoy-preview-loading">
                <div className="spinner" />
                <span>Loading decoy vault...</span>
            </div>
        );
    }

    return (
        <div className="decoy-vault-preview">
            {/* Header */}
            <div className="preview-header">
                <div className="header-info">
                    <h2>🎭 Decoy Vault Preview</h2>
                    <p>This is what attackers will see during a duress event</p>
                </div>

                {onClose && (
                    <button className="close-btn" onClick={onClose}>×</button>
                )}
            </div>

            {/* Error Display */}
            {error && (
                <div className="preview-error">
                    ⚠️ {error}
                </div>
            )}

            {/* Controls */}
            <div className="preview-controls">
                <div className="threat-selector">
                    <label>Threat Level:</label>
                    <div className="level-buttons">
                        {['low', 'medium', 'high', 'critical'].map(level => {
                            const info = duressService.formatThreatLevel(level);
                            return (
                                <button
                                    key={level}
                                    className={`level-btn ${selectedThreatLevel === level ? 'active' : ''}`}
                                    style={{
                                        '--level-color': info.color,
                                        borderColor: selectedThreatLevel === level ? info.color : 'transparent'
                                    }}
                                    onClick={() => setSelectedThreatLevel(level)}
                                >
                                    {info.icon} {info.label}
                                </button>
                            );
                        })}
                    </div>
                </div>

                <div className="view-controls">
                    <button
                        className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`}
                        onClick={() => setViewMode('grid')}
                    >
                        ▦
                    </button>
                    <button
                        className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
                        onClick={() => setViewMode('list')}
                    >
                        ≡
                    </button>
                </div>
            </div>

            {/* Realism Score */}
            <div className="realism-section">
                <h3>Realism Analysis</h3>
                <div className="realism-metrics">
                    {getRealismMetrics().map((metric, index) => (
                        <div key={index} className="metric-card">
                            <span className="metric-icon">{metric.icon}</span>
                            <div className="metric-bar">
                                <div
                                    className="metric-fill"
                                    style={{
                                        width: `${Math.min(100, (metric.value / metric.max) * 100)}%`
                                    }}
                                />
                            </div>
                            <div className="metric-info">
                                <span className="metric-value">{metric.value}</span>
                                <span className="metric-label">{metric.label}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Category Filter */}
            <div className="category-filter">
                {getCategories().map(cat => (
                    <button
                        key={cat}
                        className={`category-btn ${selectedCategory === cat ? 'active' : ''}`}
                        onClick={() => setSelectedCategory(cat)}
                    >
                        {getItemIcon(cat)} {getCategoryLabel(cat)}
                        <span className="count">
                            {cat === 'all'
                                ? decoyVault?.items?.length
                                : decoyVault?.items?.filter(i => i.type === cat).length}
                        </span>
                    </button>
                ))}
            </div>

            {/* Items Preview */}
            <div className={`items-preview ${viewMode}`}>
                {getFilteredItems().map((item, index) => (
                    <div key={index} className="preview-item">
                        <div className="item-icon-wrapper">
                            <span className="item-icon">{getItemIcon(item.type)}</span>
                            <span className="fake-indicator">FAKE</span>
                        </div>

                        <div className="item-details">
                            <span className="item-name">
                                {item.name || item.service_name || 'Unnamed'}
                            </span>
                            <span className="item-username">
                                {item.username || item.email || 'No username'}
                            </span>
                            {item.url && (
                                <span className="item-url">{item.url}</span>
                            )}
                        </div>

                        <div className="item-meta">
                            {item.folder && (
                                <span className="item-folder">📁 {item.folder}</span>
                            )}
                            <span className="item-date">
                                {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recently'}
                            </span>
                        </div>
                    </div>
                ))}

                {getFilteredItems().length === 0 && (
                    <div className="no-items">
                        <span>No items in this category</span>
                    </div>
                )}
            </div>

            {/* Folders Preview */}
            {decoyVault?.folders && decoyVault.folders.length > 0 && (
                <div className="folders-section">
                    <h3>📁 Folder Structure</h3>
                    <div className="folders-grid">
                        {decoyVault.folders.map((folder, index) => (
                            <div key={index} className="folder-item">
                                <span className="folder-icon">
                                    {folder.icon || '📁'}
                                </span>
                                <span className="folder-name">{folder.name}</span>
                                <span className="folder-count">
                                    {folder.item_count || 0} items
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Actions */}
            <div className="preview-actions">
                <button
                    className="regenerate-btn"
                    onClick={regenerateDecoy}
                    disabled={loading}
                >
                    {loading ? 'Regenerating...' : '🔄 Regenerate Decoy Data'}
                </button>

                <p className="regenerate-hint">
                    Regenerating will create new fake entries while maintaining realistic patterns
                </p>
            </div>

            {/* Warning */}
            <div className="preview-warning">
                <span className="warning-icon">⚠️</span>
                <div className="warning-content">
                    <strong>Security Notice</strong>
                    <p>
                        This preview shows fake credentials that will be displayed during duress mode.
                        Real credentials are never shown to attackers.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default DecoyVaultPreview;

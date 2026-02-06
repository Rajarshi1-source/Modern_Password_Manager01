/**
 * Predictive Intent Dashboard
 * 
 * Displays AI-powered password predictions with:
 * - Current predictions with confidence bars
 * - Usage pattern heatmap
 * - Prediction accuracy stats
 * - Quick settings toggle
 * 
 * @author Password Manager Team
 * @created 2026-02-06
 */

import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import predictiveIntentService from '../../services/predictiveIntentService';
import './PredictiveIntentDashboard.css';

const PredictiveIntentDashboard = () => {
    const [predictions, setPredictions] = useState([]);
    const [statistics, setStatistics] = useState(null);
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadDashboardData();
    }, []);

    const loadDashboardData = async () => {
        try {
            setLoading(true);
            setError(null);

            const [settingsData, statsData, predictionsData] = await Promise.all([
                predictiveIntentService.getSettings(),
                predictiveIntentService.getStatistics(),
                predictiveIntentService.getPredictions(),
            ]);

            setSettings(settingsData);
            setStatistics(statsData);
            setPredictions(predictionsData);
        } catch (err) {
            console.error('Failed to load dashboard data:', err);
            setError('Failed to load predictive intent data');
        } finally {
            setLoading(false);
        }
    };

    const toggleEnabled = async () => {
        try {
            const newSettings = await predictiveIntentService.updateSettings({
                is_enabled: !settings.is_enabled,
            });
            setSettings(newSettings);
            toast.success(newSettings.is_enabled ? 'Predictions enabled' : 'Predictions disabled');
        } catch (err) {
            toast.error('Failed to update settings');
        }
    };

    const handleUsePrediction = async (prediction) => {
        try {
            await predictiveIntentService.markPredictionUsed(prediction.id);
            toast.success('Prediction marked as used');
            await loadDashboardData();
        } catch (err) {
            toast.error('Failed to record usage');
        }
    };

    const handleDismissPrediction = async (prediction) => {
        try {
            await predictiveIntentService.markPredictionDismissed(prediction.id);
            setPredictions(prev => prev.filter(p => p.id !== prediction.id));
            toast.success('Prediction dismissed');
        } catch (err) {
            toast.error('Failed to dismiss prediction');
        }
    };

    const getConfidenceClass = (confidence) => {
        if (confidence >= 0.85) return 'confidence-high';
        if (confidence >= 0.7) return 'confidence-medium';
        return 'confidence-low';
    };

    const getReasonIcon = (reason) => {
        switch (reason) {
            case 'time_pattern': return '🕐';
            case 'sequence_pattern': return '📋';
            case 'domain_correlation': return '🌐';
            case 'frequency': return '📊';
            case 'combined': return '🔮';
            default: return '💡';
        }
    };

    const getReasonLabel = (reason) => {
        switch (reason) {
            case 'time_pattern': return 'Time Pattern';
            case 'sequence_pattern': return 'Sequence Pattern';
            case 'domain_correlation': return 'Domain Match';
            case 'frequency': return 'Frequently Used';
            case 'combined': return 'Multiple Signals';
            default: return 'Predicted';
        }
    };

    if (loading) {
        return (
            <div className="predictive-intent-dashboard loading">
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <p>Loading predictions...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="predictive-intent-dashboard error">
                <div className="error-message">
                    <span className="error-icon">⚠️</span>
                    <p>{error}</p>
                    <button onClick={loadDashboardData}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <div className="predictive-intent-dashboard">
            {/* Header */}
            <div className="dashboard-header">
                <div className="header-title">
                    <span className="header-icon">🔮</span>
                    <h1>Predictive Intent</h1>
                </div>
                <div className="header-toggle">
                    <span className="toggle-label">
                        {settings?.is_enabled ? 'Active' : 'Inactive'}
                    </span>
                    <button
                        className={`toggle-button ${settings?.is_enabled ? 'active' : ''}`}
                        onClick={toggleEnabled}
                    >
                        <span className="toggle-slider"></span>
                    </button>
                </div>
            </div>

            {/* Stats Overview */}
            {statistics && (
                <div className="stats-grid">
                    <div className="stat-card">
                        <div className="stat-value">{statistics.accuracy}%</div>
                        <div className="stat-label">Accuracy</div>
                        <div className="stat-trend">
                            {statistics.recent_accuracy > statistics.accuracy ? '↑' : '↓'}
                            {Math.abs(statistics.recent_accuracy - statistics.accuracy).toFixed(1)}% this week
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{statistics.predictions_used}</div>
                        <div className="stat-label">Used</div>
                        <div className="stat-sublabel">of {statistics.total_predictions} predictions</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{statistics.pattern_count}</div>
                        <div className="stat-label">Patterns</div>
                        <div className="stat-sublabel">learned from your usage</div>
                    </div>
                </div>
            )}

            {/* Current Predictions */}
            <div className="predictions-section">
                <h2>Current Predictions</h2>
                {predictions.length > 0 ? (
                    <div className="predictions-list">
                        {predictions.map((prediction, index) => (
                            <div key={prediction.id} className="prediction-card">
                                <div className="prediction-rank">#{index + 1}</div>
                                <div className="prediction-content">
                                    <div className="prediction-header">
                                        <span className="prediction-reason-icon">
                                            {getReasonIcon(prediction.reason)}
                                        </span>
                                        <span className="prediction-type">{prediction.vault_item_type}</span>
                                        <span className="prediction-reason">
                                            {getReasonLabel(prediction.reason)}
                                        </span>
                                    </div>

                                    <div className="prediction-domain">
                                        {prediction.trigger_domain || 'Any domain'}
                                    </div>

                                    <div className="confidence-bar-container">
                                        <div
                                            className={`confidence-bar ${getConfidenceClass(prediction.confidence)}`}
                                            style={{ width: `${prediction.confidence * 100}%` }}
                                        ></div>
                                        <span className="confidence-value">
                                            {(prediction.confidence * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </div>

                                <div className="prediction-actions">
                                    <button
                                        className="action-btn use"
                                        onClick={() => handleUsePrediction(prediction)}
                                        title="Mark as used"
                                    >
                                        ✓
                                    </button>
                                    <button
                                        className="action-btn dismiss"
                                        onClick={() => handleDismissPrediction(prediction)}
                                        title="Dismiss"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="no-predictions">
                        <span className="empty-icon">🔍</span>
                        <p>No predictions yet</p>
                        <span className="empty-hint">
                            Use your vault to help the AI learn your patterns
                        </span>
                    </div>
                )}
            </div>

            {/* Usage Heatmap */}
            {statistics?.top_domains?.length > 0 && (
                <div className="heatmap-section">
                    <h2>Top Accessed Domains</h2>
                    <div className="domain-list">
                        {statistics.top_domains.slice(0, 5).map((domain, index) => (
                            <div key={index} className="domain-item">
                                <span className="domain-name">{domain.domain}</span>
                                <div className="domain-bar-container">
                                    <div
                                        className="domain-bar"
                                        style={{
                                            width: `${(domain.count / statistics.top_domains[0].count) * 100}%`
                                        }}
                                    ></div>
                                </div>
                                <span className="domain-count">{domain.count}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Quick Actions */}
            <div className="quick-actions">
                <button onClick={loadDashboardData} className="action-btn refresh">
                    🔄 Refresh
                </button>
                <a href="/settings/security/predictive-intent" className="action-btn settings">
                    ⚙️ Settings
                </a>
            </div>
        </div>
    );
};

export default PredictiveIntentDashboard;

/**
 * EntropyHealthCard.jsx
 * 
 * Visual indicator of entanglement health based on entropy analysis.
 * Features:
 * - Entropy gauge (0-8 bits/byte)
 * - Anomaly alerts
 * - Last sync timestamp
 * - Quick actions (rotate, check)
 */

import React from 'react';
import {
    Activity,
    AlertTriangle,
    CheckCircle,
    XCircle,
    TrendingUp,
    RefreshCw,
    Shield
} from 'lucide-react';
import './EntropyHealthCard.css';

const EntropyHealthCard = ({
    health = 'healthy',
    score = 8.0,
    generation = 0,
    lastSync = null,
    compact = false,
    onRotate = null,
    onCheck = null
}) => {
    // Calculate percentage (8 bits/byte is max)
    const percentage = Math.min((score / 8.0) * 100, 100);

    // Get health configuration
    const getHealthConfig = () => {
        if (health === 'critical' || score < 7.0) {
            return {
                color: 'red',
                icon: XCircle,
                label: 'Critical',
                message: 'Entropy critically low - immediate action required',
                gradient: 'linear-gradient(90deg, #ef4444, #dc2626)',
            };
        }
        if (health === 'degraded' || score < 7.5) {
            return {
                color: 'yellow',
                icon: AlertTriangle,
                label: 'Degraded',
                message: 'Entropy degraded - consider key rotation',
                gradient: 'linear-gradient(90deg, #f59e0b, #d97706)',
            };
        }
        return {
            color: 'green',
            icon: CheckCircle,
            label: 'Healthy',
            message: 'Entropy optimal - no issues detected',
            gradient: 'linear-gradient(90deg, #10b981, #059669)',
        };
    };

    const config = getHealthConfig();
    const Icon = config.icon;

    // Compact view for list items
    if (compact) {
        return (
            <div className={`entropy-card compact health-${config.color}`}>
                <div className="entropy-bar-container">
                    <div
                        className="entropy-bar"
                        style={{
                            width: `${percentage}%`,
                            background: config.gradient,
                        }}
                    />
                </div>
                <div className="entropy-info">
                    <Icon size={14} />
                    <span className="entropy-value">{score.toFixed(2)} bits/byte</span>
                    <span className={`entropy-badge ${config.color}`}>{config.label}</span>
                </div>
            </div>
        );
    }

    // Full view
    return (
        <div className={`entropy-card full health-${config.color}`}>
            {/* Header */}
            <div className="entropy-header">
                <div className="header-title">
                    <Activity size={24} />
                    <h3>Entropy Health</h3>
                </div>
                <div className={`health-badge ${config.color}`}>
                    <Icon size={16} />
                    {config.label}
                </div>
            </div>

            {/* Gauge */}
            <div className="entropy-gauge">
                <svg viewBox="0 0 200 120" className="gauge-svg">
                    {/* Background arc */}
                    <path
                        d="M 20 100 A 80 80 0 0 1 180 100"
                        fill="none"
                        stroke="var(--gauge-bg)"
                        strokeWidth="20"
                        strokeLinecap="round"
                    />
                    {/* Value arc */}
                    <path
                        d="M 20 100 A 80 80 0 0 1 180 100"
                        fill="none"
                        stroke={`url(#gauge-gradient-${config.color})`}
                        strokeWidth="20"
                        strokeLinecap="round"
                        strokeDasharray={`${percentage * 2.51} 251`}
                        className="gauge-value"
                    />
                    {/* Gradient definitions */}
                    <defs>
                        <linearGradient id="gauge-gradient-green" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#10b981" />
                            <stop offset="100%" stopColor="#059669" />
                        </linearGradient>
                        <linearGradient id="gauge-gradient-yellow" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#f59e0b" />
                            <stop offset="100%" stopColor="#d97706" />
                        </linearGradient>
                        <linearGradient id="gauge-gradient-red" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#ef4444" />
                            <stop offset="100%" stopColor="#dc2626" />
                        </linearGradient>
                    </defs>
                </svg>

                <div className="gauge-center">
                    <span className="gauge-value-text">{score.toFixed(2)}</span>
                    <span className="gauge-unit">bits/byte</span>
                </div>

                {/* Scale markers */}
                <div className="gauge-markers">
                    <span className="marker-start">0</span>
                    <span className="marker-warning">7.0</span>
                    <span className="marker-end">8.0</span>
                </div>
            </div>

            {/* Message */}
            <div className={`entropy-message ${config.color}`}>
                <Icon size={16} />
                <span>{config.message}</span>
            </div>

            {/* Stats */}
            <div className="entropy-stats">
                <div className="stat-item">
                    <TrendingUp size={16} />
                    <span className="stat-label">Generation</span>
                    <span className="stat-value">{generation}</span>
                </div>
                <div className="stat-item">
                    <Shield size={16} />
                    <span className="stat-label">Pool Quality</span>
                    <span className="stat-value">{percentage.toFixed(0)}%</span>
                </div>
            </div>

            {/* Actions */}
            {(onRotate || onCheck) && (
                <div className="entropy-actions">
                    {onCheck && (
                        <button className="btn-secondary" onClick={onCheck}>
                            <Activity size={16} />
                            Check Now
                        </button>
                    )}
                    {onRotate && (
                        <button className="btn-primary" onClick={onRotate}>
                            <RefreshCw size={16} />
                            Rotate Keys
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default EntropyHealthCard;

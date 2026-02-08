/**
 * CredentialRiskCard.jsx
 * ======================
 * 
 * Individual credential risk visualization with risk score meter,
 * predicted compromise date, contributing threat factors, and rotate action.
 */

import React from 'react';
import './CredentialRiskCard.css';

const CredentialRiskCard = ({
    credential,
    onRotate,
    onAcknowledge,
    onViewDetails
}) => {
    const getRiskColor = (level) => {
        switch (level) {
            case 'critical': return '#ef4444';
            case 'high': return '#f97316';
            case 'medium': return '#eab308';
            case 'low': return '#22c55e';
            default: return '#6b7280';
        }
    };

    const getRiskLabel = (level) => {
        switch (level) {
            case 'critical': return 'CRITICAL';
            case 'high': return 'HIGH RISK';
            case 'medium': return 'MEDIUM';
            case 'low': return 'LOW';
            default: return 'MINIMAL';
        }
    };

    const getDaysUntil = () => {
        if (!credential.predicted_compromise_date) return null;
        const now = new Date();
        const target = new Date(credential.predicted_compromise_date);
        const diffTime = target - now;
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'Unknown';
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    const riskColor = getRiskColor(credential.risk_level);
    const riskScore = credential.risk_score || 0;
    const daysUntil = getDaysUntil();

    return (
        <div
            className="credential-risk-card"
            style={{ '--risk-color': riskColor }}
        >
            <div className="card-header">
                <div className="credential-icon">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 1C8.676 1 6 3.676 6 7v2H4v14h16V9h-2V7c0-3.324-2.676-6-6-6zm0 2c2.276 0 4 1.724 4 4v2H8V7c0-2.276 1.724-4 4-4zm0 10a2 2 0 0 1 2 2c0 .738-.405 1.376-1 1.723V18a1 1 0 0 1-2 0v-1.277c-.595-.347-1-.985-1-1.723a2 2 0 0 1 2-2z" />
                    </svg>
                </div>
                <div className="credential-info">
                    <h4 className="credential-domain">{credential.credential_domain}</h4>
                    <span className="credential-age">
                        {credential.age_days ? `${credential.age_days} days old` : 'Age unknown'}
                    </span>
                </div>
                <div className={`risk-badge ${credential.risk_level}`}>
                    {getRiskLabel(credential.risk_level)}
                </div>
            </div>

            <div className="risk-meter-container">
                <div className="risk-meter">
                    <div
                        className="risk-meter-fill"
                        style={{
                            width: `${riskScore * 100}%`,
                            background: riskColor
                        }}
                    />
                </div>
                <span className="risk-score">{Math.round(riskScore * 100)}%</span>
            </div>

            <div className="card-body">
                {daysUntil !== null && (
                    <div className="prediction-info">
                        <div className="prediction-icon">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
                            </svg>
                        </div>
                        <div className="prediction-text">
                            {daysUntil > 0 ? (
                                <>
                                    <span className="days-count">{daysUntil}</span>
                                    <span className="days-label">days until predicted compromise</span>
                                </>
                            ) : (
                                <span className="urgent">Immediate action required</span>
                            )}
                        </div>
                    </div>
                )}

                {credential.threat_factors?.length > 0 && (
                    <div className="threat-factors">
                        <span className="factors-label">Contributing Factors:</span>
                        <ul className="factors-list">
                            {credential.threat_factors.slice(0, 3).map((factor, idx) => (
                                <li key={idx}>{factor}</li>
                            ))}
                        </ul>
                    </div>
                )}

                <div className="action-info">
                    <span className="action-label">Recommended:</span>
                    <span className="action-value">
                        {credential.recommended_action?.replace(/_/g, ' ') || 'Monitor'}
                    </span>
                </div>
            </div>

            <div className="card-footer">
                {onViewDetails && (
                    <button
                        className="btn-secondary"
                        onClick={() => onViewDetails(credential)}
                    >
                        Details
                    </button>
                )}
                {!credential.user_acknowledged && onAcknowledge && (
                    <button
                        className="btn-acknowledge"
                        onClick={() => onAcknowledge(credential.credential_id)}
                    >
                        Acknowledge
                    </button>
                )}
                {['rotate_immediately', 'rotate_soon'].includes(credential.recommended_action) && onRotate && (
                    <button
                        className="btn-rotate"
                        onClick={() => onRotate(credential.credential_id)}
                    >
                        Rotate Now
                    </button>
                )}
            </div>
        </div>
    );
};

export default CredentialRiskCard;

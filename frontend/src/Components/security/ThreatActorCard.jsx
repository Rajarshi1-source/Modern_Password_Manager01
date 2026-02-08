/**
 * ThreatActorCard.jsx
 * ===================
 * 
 * Displays threat actor information targeting user's industry/patterns.
 */

import React from 'react';
import './ThreatActorCard.css';

const ThreatActorCard = ({ threat, onViewDetails }) => {
    const getThreatColor = (level) => {
        switch (level) {
            case 'critical': return 'var(--risk-critical)';
            case 'high': return 'var(--risk-high)';
            case 'medium': return 'var(--risk-medium)';
            default: return 'var(--risk-low)';
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'Unknown';
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    return (
        <div
            className="threat-actor-card"
            style={{ '--threat-color': getThreatColor(threat.threat_level) }}
        >
            <div className="threat-header">
                <div className="threat-icon">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                    </svg>
                </div>
                <div className="threat-info">
                    <h4 className="threat-name">{threat.name}</h4>
                    <span className="threat-type">{threat.actor_type}</span>
                </div>
                <div className={`threat-badge ${threat.threat_level}`}>
                    {threat.threat_level?.toUpperCase()}
                </div>
            </div>

            <div className="threat-body">
                {threat.description && (
                    <p className="threat-description">{threat.description}</p>
                )}

                <div className="threat-stats">
                    <div className="stat">
                        <span className="stat-label">Target Industries</span>
                        <span className="stat-value">
                            {threat.target_industries?.length || 0}
                        </span>
                    </div>
                    <div className="stat">
                        <span className="stat-label">Attack Techniques</span>
                        <span className="stat-value">
                            {threat.attack_techniques?.length || 0}
                        </span>
                    </div>
                    <div className="stat">
                        <span className="stat-label">Last Active</span>
                        <span className="stat-value">
                            {formatDate(threat.last_active)}
                        </span>
                    </div>
                </div>

                {threat.target_industries?.length > 0 && (
                    <div className="threat-tags">
                        {threat.target_industries.slice(0, 3).map((industry, idx) => (
                            <span key={idx} className="tag">{industry}</span>
                        ))}
                        {threat.target_industries.length > 3 && (
                            <span className="tag more">+{threat.target_industries.length - 3}</span>
                        )}
                    </div>
                )}
            </div>

            <div className="threat-footer">
                {threat.is_currently_active && (
                    <div className="active-indicator">
                        <span className="pulse"></span>
                        Active Now
                    </div>
                )}
                {onViewDetails && (
                    <button
                        className="btn-details"
                        onClick={() => onViewDetails(threat)}
                    >
                        View Details
                    </button>
                )}
            </div>
        </div>
    );
};

export default ThreatActorCard;

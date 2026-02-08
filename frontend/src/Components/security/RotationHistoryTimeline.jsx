/**
 * RotationHistoryTimeline.jsx
 * ============================
 * 
 * Visual timeline of password rotations (forced and voluntary).
 */

import React from 'react';
import './RotationHistoryTimeline.css';

const RotationHistoryTimeline = ({ rotations = [], loading = false }) => {
    const getTypeColor = (type) => {
        switch (type) {
            case 'forced': return '#ef4444';
            case 'proactive': return '#f97316';
            case 'scheduled': return '#6366f1';
            case 'voluntary': return '#22c55e';
            default: return '#6b7280';
        }
    };

    const getOutcomeIcon = (outcome) => {
        switch (outcome) {
            case 'success':
                return (
                    <svg viewBox="0 0 24 24" fill="currentColor" className="icon success">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                    </svg>
                );
            case 'failed':
                return (
                    <svg viewBox="0 0 24 24" fill="currentColor" className="icon failed">
                        <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z" />
                    </svg>
                );
            case 'pending':
                return (
                    <svg viewBox="0 0 24 24" fill="currentColor" className="icon pending">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
                    </svg>
                );
            default:
                return (
                    <svg viewBox="0 0 24 24" fill="currentColor" className="icon">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                    </svg>
                );
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const formatDuration = (startDate, endDate) => {
        if (!startDate || !endDate) return null;
        const start = new Date(startDate);
        const end = new Date(endDate);
        const diffMs = end - start;
        const diffSecs = Math.floor(diffMs / 1000);

        if (diffSecs < 60) return `${diffSecs}s`;
        if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m`;
        return `${Math.floor(diffSecs / 3600)}h ${Math.floor((diffSecs % 3600) / 60)}m`;
    };

    if (loading) {
        return (
            <div className="rotation-timeline loading">
                <div className="loading-skeleton"></div>
                <div className="loading-skeleton"></div>
                <div className="loading-skeleton"></div>
            </div>
        );
    }

    if (!rotations.length) {
        return (
            <div className="rotation-timeline empty">
                <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" />
                    </svg>
                    <p>No rotation history yet</p>
                </div>
            </div>
        );
    }

    return (
        <div className="rotation-timeline">
            <div className="timeline-header">
                <h3>Rotation History</h3>
                <span className="count">{rotations.length} events</span>
            </div>

            <div className="timeline-container">
                {rotations.map((rotation, index) => (
                    <div
                        key={rotation.event_id || index}
                        className={`timeline-item ${rotation.outcome}`}
                        style={{ '--type-color': getTypeColor(rotation.rotation_type) }}
                    >
                        <div className="timeline-marker">
                            <div className="marker-dot"></div>
                            {index < rotations.length - 1 && <div className="marker-line"></div>}
                        </div>

                        <div className="timeline-content">
                            <div className="timeline-header-row">
                                <span className="credential-name">
                                    {rotation.credential_domain || 'Unknown Credential'}
                                </span>
                                {getOutcomeIcon(rotation.outcome)}
                            </div>

                            <div className="timeline-details">
                                <span className={`type-badge ${rotation.rotation_type}`}>
                                    {rotation.rotation_type}
                                </span>
                                <span className="timestamp">
                                    {formatDate(rotation.initiated_at)}
                                </span>
                                {rotation.completed_at && (
                                    <span className="duration">
                                        {formatDuration(rotation.initiated_at, rotation.completed_at)}
                                    </span>
                                )}
                            </div>

                            {rotation.trigger_reason && (
                                <p className="trigger-reason">{rotation.trigger_reason}</p>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default RotationHistoryTimeline;

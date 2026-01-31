/**
 * Breach Timeline Component
 * 
 * Displays detailed timeline of a breach event with key milestones.
 * Shows detection, notification, public disclosure, and resolution.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
 */

import React, { useState, useEffect } from 'react';
import {
    FiX,
    FiClock,
    FiAlertTriangle,
    FiCheck,
    FiRefreshCw,
    FiEye,
    FiBell,
    FiShield,
    FiLoader
} from 'react-icons/fi';
import honeypotService from '../../services/honeypotService';
import './HoneypotDashboard.css';

const BreachTimeline = ({ breachId, onClose }) => {
    const [loading, setLoading] = useState(true);
    const [breach, setBreach] = useState(null);
    const [error, setError] = useState(null);
    const [rotating, setRotating] = useState(false);

    useEffect(() => {
        loadBreach();
    }, [breachId]);

    const loadBreach = async () => {
        try {
            setError(null);
            const data = await honeypotService.getBreachTimeline(breachId);
            setBreach(data);
        } catch (err) {
            setError('Failed to load breach details');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleRotateCredentials = async () => {
        setRotating(true);
        try {
            await honeypotService.initiateRotation(breachId);
            await loadBreach();
        } catch (err) {
            setError('Failed to initiate credential rotation');
        } finally {
            setRotating(false);
        }
    };

    const getEventIcon = (event) => {
        switch (event) {
            case 'first_activity':
                return <FiEye className="event-icon activity" />;
            case 'detected':
                return <FiAlertTriangle className="event-icon detected" />;
            case 'notified':
                return <FiBell className="event-icon notified" />;
            case 'acknowledged':
                return <FiCheck className="event-icon acknowledged" />;
            case 'public_disclosure':
                return <FiShield className="event-icon disclosure" />;
            case 'resolved':
                return <FiCheck className="event-icon resolved" />;
            default:
                return <FiClock className="event-icon" />;
        }
    };

    const getSeverityClass = (severity) => {
        return `severity-${severity}`;
    };

    if (loading) {
        return (
            <div className="modal-overlay" onClick={onClose}>
                <div className="modal-content timeline-modal loading" onClick={(e) => e.stopPropagation()}>
                    <FiLoader className="spin" size={32} />
                    <p>Loading breach details...</p>
                </div>
            </div>
        );
    }

    if (!breach) {
        return (
            <div className="modal-overlay" onClick={onClose}>
                <div className="modal-content timeline-modal" onClick={(e) => e.stopPropagation()}>
                    <header className="modal-header">
                        <h2>Breach Not Found</h2>
                        <button className="close-btn" onClick={onClose}>
                            <FiX />
                        </button>
                    </header>
                    <p>The requested breach could not be found.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div
                className={`modal-content timeline-modal ${getSeverityClass(breach.severity)}`}
                onClick={(e) => e.stopPropagation()}
            >
                <header className="modal-header">
                    <h2>
                        <FiClock /> Breach Timeline
                    </h2>
                    <button className="close-btn" onClick={onClose}>
                        <FiX />
                    </button>
                </header>

                {/* Breach Summary */}
                <div className="breach-summary">
                    <div className="summary-header">
                        <h3>{breach.service_name}</h3>
                        <span className={`severity-badge ${breach.severity}`}>
                            {breach.severity.toUpperCase()}
                        </span>
                    </div>

                    <div className="summary-stats">
                        <div className="stat">
                            <span className="label">Status</span>
                            <span className="value">{breach.status}</span>
                        </div>
                        <div className="stat">
                            <span className="label">Confidence</span>
                            <span className="value">{(breach.confidence_score * 100).toFixed(0)}%</span>
                        </div>
                        {breach.days_before_public !== null && (
                            <div className="stat highlight">
                                <span className="label">Early Detection</span>
                                <span className="value">{breach.days_before_public} days</span>
                            </div>
                        )}
                        <div className="stat">
                            <span className="label">Credentials Rotated</span>
                            <span className="value">
                                {breach.credentials_rotated ? (
                                    <FiCheck className="success" />
                                ) : (
                                    <span className="pending">Pending</span>
                                )}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="message error">
                        <FiAlertTriangle />
                        {error}
                    </div>
                )}

                {/* Timeline */}
                <div className="timeline-container">
                    <h4>Event Timeline</h4>
                    <div className="timeline">
                        {breach.timeline.map((event, index) => (
                            <div
                                key={index}
                                className={`timeline-event ${event.event}`}
                            >
                                <div className="event-dot">
                                    {getEventIcon(event.event)}
                                </div>
                                <div className="event-content">
                                    <span className="event-label">{event.label}</span>
                                    <span className="event-time">
                                        {new Date(event.timestamp).toLocaleString()}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Early Detection Highlight */}
                {breach.days_before_public !== null && (
                    <div className="early-detection-banner">
                        <FiShield size={24} />
                        <div>
                            <strong>🎯 Early Detection!</strong>
                            <p>
                                This breach was detected <strong>{breach.days_before_public} days</strong> before
                                the public disclosure. You had time to protect your account before the attacker
                                could exploit your credentials.
                            </p>
                        </div>
                    </div>
                )}

                {/* Actions */}
                <div className="timeline-actions">
                    {!breach.credentials_rotated && (
                        <button
                            className="btn btn-primary"
                            onClick={handleRotateCredentials}
                            disabled={rotating}
                        >
                            {rotating ? (
                                <>
                                    <FiLoader className="spin" /> Rotating...
                                </>
                            ) : (
                                <>
                                    <FiRefreshCw /> Rotate Credentials
                                </>
                            )}
                        </button>
                    )}
                    <button className="btn btn-secondary" onClick={onClose}>
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

export default BreachTimeline;

/**
 * Time Machine View
 * ==================
 * Reconstruct and visualize account security state at any point in history.
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Rewind, Clock, Shield, Key, AlertTriangle,
    Calendar, Search, ChevronRight,
} from 'lucide-react';
import archaeologyService from '../../services/archaeologyService';

function getStrengthColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
}

export default function TimeMachineView() {
    const [selectedDate, setSelectedDate] = useState('');
    const [snapshot, setSnapshot] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleTravel = async () => {
        if (!selectedDate) return;
        setLoading(true);
        setError(null);
        setSnapshot(null);
        try {
            const timestamp = new Date(selectedDate).toISOString();
            const data = await archaeologyService.getTimeMachineSnapshot(timestamp);
            setSnapshot(data);
        } catch (err) {
            console.error('Time machine error:', err);
            setError(err.message || 'Failed to load snapshot');
        } finally {
            setLoading(false);
        }
    };

    // Quick presets
    const setPresetDate = (daysAgo) => {
        const d = new Date();
        d.setDate(d.getDate() - daysAgo);
        setSelectedDate(d.toISOString().slice(0, 16));
    };

    return (
        <div>
            <motion.div
                className="arch-time-machine"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <h3 className="arch-chart-card-title" style={{ marginBottom: 16 }}>
                    <Rewind size={20} />
                    Time Machine
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', marginBottom: 20 }}>
                    Select a date to see what your account security looked like at that point in time.
                </p>

                <div className="arch-time-machine-controls">
                    <div className="arch-form-group" style={{ flex: 1, minWidth: 200 }}>
                        <label className="arch-form-label">
                            <Calendar size={14} style={{ marginRight: 6, display: 'inline' }} />
                            Travel To
                        </label>
                        <input
                            type="datetime-local"
                            className="arch-form-input"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            max={new Date().toISOString().slice(0, 16)}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button className="arch-tab" onClick={() => setPresetDate(7)}>1 week ago</button>
                        <button className="arch-tab" onClick={() => setPresetDate(30)}>1 month ago</button>
                        <button className="arch-tab" onClick={() => setPresetDate(90)}>3 months ago</button>
                        <button className="arch-tab" onClick={() => setPresetDate(180)}>6 months ago</button>
                        <button className="arch-tab" onClick={() => setPresetDate(365)}>1 year ago</button>
                    </div>

                    <button
                        className="arch-btn-primary"
                        onClick={handleTravel}
                        disabled={!selectedDate || loading}
                    >
                        {loading ? (
                            <><div className="arch-loading-spinner" style={{ width: 16, height: 16 }} /> Traveling...</>
                        ) : (
                            <><Rewind size={16} /> Travel Back</>
                        )}
                    </button>
                </div>

                {error && (
                    <div style={{ color: '#ef4444', fontSize: 14, padding: '12px 0' }}>
                        ⚠️ {error}
                    </div>
                )}
            </motion.div>

            {/* Snapshot Results */}
            <AnimatePresence>
                {snapshot && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{ duration: 0.5 }}
                        style={{ marginTop: 24 }}
                    >
                        {/* Header */}
                        <div className="arch-stat-card" style={{
                            marginBottom: 20,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 16,
                            flexWrap: 'wrap',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div className="arch-stat-icon purple" style={{ width: 48, height: 48 }}>
                                    <Clock size={24} />
                                </div>
                                <div>
                                    <div style={{ fontSize: 14, color: '#94a3b8' }}>Account state at</div>
                                    <div style={{ fontSize: 18, fontWeight: 700 }}>
                                        {new Date(snapshot.point_in_time).toLocaleString('en-US', {
                                            month: 'long', day: 'numeric', year: 'numeric',
                                            hour: '2-digit', minute: '2-digit',
                                        })}
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 24 }}>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 28, fontWeight: 700, color: getStrengthColor(snapshot.overall_score) }}>
                                        {snapshot.overall_score}
                                    </div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Overall Score</div>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 28, fontWeight: 700 }}>{snapshot.total_credentials}</div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Credentials</div>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 28, fontWeight: 700, color: '#ef4444' }}>
                                        {snapshot.unresolved_events}
                                    </div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Unresolved</div>
                                </div>
                            </div>
                        </div>

                        {/* Credential States */}
                        <div className="arch-time-machine-snapshot">
                            {snapshot.credentials && snapshot.credentials.length > 0 ? (
                                snapshot.credentials.map((cred, i) => (
                                    <motion.div
                                        key={cred.credential_domain}
                                        className="arch-snapshot-card"
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: i * 0.05, duration: 0.3 }}
                                    >
                                        <div className="arch-snapshot-card-title">
                                            <Key size={14} />
                                            {cred.credential_domain}
                                        </div>
                                        <div className="arch-snapshot-detail">
                                            <span className="arch-snapshot-detail-label">Strength</span>
                                            <span
                                                className="arch-snapshot-detail-value"
                                                style={{ color: getStrengthColor(cred.strength_score) }}
                                            >
                                                {cred.strength_score}/100
                                            </span>
                                        </div>
                                        <div className="arch-snapshot-detail">
                                            <span className="arch-snapshot-detail-label">Password Age</span>
                                            <span className="arch-snapshot-detail-value">
                                                {cred.password_age_days} days
                                            </span>
                                        </div>
                                        <div className="arch-snapshot-detail">
                                            <span className="arch-snapshot-detail-label">Total Changes</span>
                                            <span className="arch-snapshot-detail-value">
                                                {cred.total_changes}
                                            </span>
                                        </div>
                                        <div className="arch-snapshot-detail">
                                            <span className="arch-snapshot-detail-label">Entropy</span>
                                            <span className="arch-snapshot-detail-value">
                                                {cred.entropy_bits?.toFixed(1)} bits
                                            </span>
                                        </div>
                                        {cred.breach_exposure > 0 && (
                                            <div className="arch-snapshot-detail">
                                                <span className="arch-snapshot-detail-label">
                                                    <AlertTriangle size={12} style={{ marginRight: 4 }} />
                                                    Breaches
                                                </span>
                                                <span className="arch-snapshot-detail-value" style={{ color: '#ef4444' }}>
                                                    {cred.breach_exposure}
                                                </span>
                                            </div>
                                        )}
                                    </motion.div>
                                ))
                            ) : (
                                <div className="arch-empty" style={{ gridColumn: '1 / -1' }}>
                                    <div className="arch-empty-icon">🕰️</div>
                                    <div className="arch-empty-text">No credentials tracked at this time</div>
                                </div>
                            )}
                        </div>

                        {/* Summary Stats */}
                        <div className="arch-stat-card" style={{ marginTop: 16, padding: 16 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-around', textAlign: 'center', flexWrap: 'wrap', gap: 16 }}>
                                <div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Total Events</div>
                                    <div style={{ fontSize: 20, fontWeight: 700 }}>{snapshot.total_security_events}</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Breaches</div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{snapshot.total_breaches}</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 12, color: '#64748b' }}>Unresolved</div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: '#f59e0b' }}>{snapshot.unresolved_events}</div>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {!snapshot && !loading && (
                <div className="arch-empty" style={{ marginTop: 40 }}>
                    <div className="arch-empty-icon">⏰</div>
                    <div className="arch-empty-text">Select a date to travel back in time</div>
                    <div className="arch-empty-sub">
                        See exactly what your security posture looked like at any moment.
                    </div>
                </div>
            )}
        </div>
    );
}

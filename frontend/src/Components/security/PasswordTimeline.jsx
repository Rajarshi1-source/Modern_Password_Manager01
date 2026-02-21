/**
 * Password Archaeology & Time Travel — Main Dashboard
 * =====================================================
 * Interactive timeline of password evolution, security events,
 * strength charts, what-if simulations, and gamification.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Clock, Shield, TrendingUp, GitBranch, Award, Rewind,
    Key, AlertTriangle, ShieldCheck, Lock, Unlock, Smartphone,
    Eye, Zap, RefreshCw, ChevronDown, ChevronUp, Link2,
    Star, Target, Calendar, Activity, BarChart3,
} from 'lucide-react';
import archaeologyService from '../../services/archaeologyService';
import StrengthEvolutionChart from './StrengthEvolutionChart';
import WhatIfSimulator from './WhatIfSimulator';
import SecurityScoreTimeline from './SecurityScoreTimeline';
import TimeMachineView from './TimeMachineView';
import './PasswordTimeline.css';

// ===================================================================
// Constants & Helpers
// ===================================================================

const TABS = [
    { id: 'timeline', label: 'Timeline', icon: Clock },
    { id: 'strength', label: 'Strength Evolution', icon: TrendingUp },
    { id: 'whatif', label: 'What-If Simulator', icon: GitBranch },
    { id: 'achievements', label: 'Achievements', icon: Award },
    { id: 'timemachine', label: 'Time Machine', icon: Rewind },
];

const EVENT_ICONS = {
    password_change: Key,
    breach_detected: AlertTriangle,
    suspicious_login: Eye,
    account_locked: Lock,
    account_unlocked: Unlock,
    mfa_enabled: ShieldCheck,
    mfa_disabled: Shield,
    device_added: Smartphone,
    password_reuse: RefreshCw,
    weak_password: AlertTriangle,
    phishing_attempt: AlertTriangle,
    impossible_travel: Zap,
};

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    });
}

function formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit',
    });
}

function getStrengthColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
}

function getScoreGrade(score) {
    if (score >= 90) return 'A+';
    if (score >= 80) return 'A';
    if (score >= 70) return 'B';
    if (score >= 60) return 'C';
    if (score >= 50) return 'D';
    return 'F';
}

// ===================================================================
// Score Ring Component
// ===================================================================

function ScoreRing({ score, size = 56 }) {
    const r = (size - 8) / 2;
    const circ = 2 * Math.PI * r;
    const offset = circ - (score / 100) * circ;
    const color = getStrengthColor(score);

    return (
        <div className="arch-score-ring" style={{ width: size, height: size }}>
            <svg width={size} height={size}>
                <circle
                    className="arch-score-ring-track"
                    cx={size / 2} cy={size / 2} r={r}
                />
                <circle
                    className="arch-score-ring-fill"
                    cx={size / 2} cy={size / 2} r={r}
                    stroke={color}
                    strokeDasharray={circ}
                    strokeDashoffset={offset}
                />
            </svg>
            <span className="arch-score-value" style={{ color }}>
                {score}
            </span>
        </div>
    );
}

// ===================================================================
// Timeline Item Component
// ===================================================================

function TimelineItem({ event, index }) {
    const [expanded, setExpanded] = useState(false);
    const isPasswordChange = event.type === 'password_change';
    const Icon = isPasswordChange
        ? Key
        : (EVENT_ICONS[event.event_type] || Shield);

    const dotClass = isPasswordChange
        ? 'password-change'
        : event.severity === 'critical' ? 'critical' : 'security-event';

    return (
        <motion.div
            className="arch-timeline-item"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05, duration: 0.3 }}
        >
            <div className={`arch-timeline-dot ${dotClass}`} />
            <div
                className="arch-timeline-card"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="arch-timeline-card-header">
                    <div className="arch-timeline-card-title">
                        <Icon size={16} />
                        {isPasswordChange ? (
                            <span>
                                Password changed: <strong>{event.credential_domain || 'Unknown'}</strong>
                            </span>
                        ) : (
                            <span>{event.title || event.event_type_display}</span>
                        )}
                    </div>
                    <div className="arch-timeline-timestamp">
                        {formatDate(event.timestamp)} · {formatTime(event.timestamp)}
                        {expanded ? <ChevronUp size={14} style={{ marginLeft: 4 }} /> : <ChevronDown size={14} style={{ marginLeft: 4 }} />}
                    </div>
                </div>

                {isPasswordChange && (
                    <>
                        <div className="arch-timeline-card-body">
                            <span style={{ marginRight: 12 }}>
                                Trigger: <strong>{event.trigger_display}</strong>
                            </span>
                        </div>
                        <div className="arch-timeline-strength-bar">
                            <span className="arch-timeline-strength-label">Before</span>
                            <div className="arch-timeline-strength-track">
                                <div
                                    className="arch-timeline-strength-fill"
                                    style={{
                                        width: `${event.strength_before}%`,
                                        background: getStrengthColor(event.strength_before),
                                    }}
                                />
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 600, color: getStrengthColor(event.strength_before) }}>
                                {event.strength_before}
                            </span>
                        </div>
                        <div className="arch-timeline-strength-bar">
                            <span className="arch-timeline-strength-label">After</span>
                            <div className="arch-timeline-strength-track">
                                <div
                                    className="arch-timeline-strength-fill"
                                    style={{
                                        width: `${event.strength_after}%`,
                                        background: getStrengthColor(event.strength_after),
                                    }}
                                />
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 600, color: getStrengthColor(event.strength_after) }}>
                                {event.strength_after}
                            </span>
                        </div>
                        {event.has_blockchain_proof && (
                            <div className="arch-timeline-blockchain-badge">
                                <Link2 size={12} /> Blockchain Verified
                            </div>
                        )}
                    </>
                )}

                {!isPasswordChange && (
                    <>
                        <div className="arch-timeline-card-body">
                            {event.description}
                        </div>
                        <div style={{ marginTop: 8 }}>
                            <span className={`arch-severity-badge ${event.severity}`}>
                                {event.severity}
                            </span>
                            {event.resolved && (
                                <span
                                    className="arch-severity-badge"
                                    style={{
                                        background: 'rgba(16,185,129,0.15)',
                                        color: '#34d399',
                                        marginLeft: 8,
                                    }}
                                >
                                    Resolved
                                </span>
                            )}
                        </div>
                    </>
                )}

                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            style={{ overflow: 'hidden', marginTop: 12 }}
                        >
                            <div style={{
                                padding: '12px 16px',
                                background: 'rgba(255,255,255,0.02)',
                                borderRadius: 8,
                                fontSize: 13,
                                color: '#94a3b8',
                            }}>
                                {isPasswordChange ? (
                                    <>
                                        <div>Entropy: {event.entropy_before?.toFixed(1)} → {event.entropy_after?.toFixed(1)} bits</div>
                                        {event.change_notes && <div style={{ marginTop: 6 }}>Notes: {event.change_notes}</div>}
                                        {event.commitment_hash && (
                                            <div style={{ marginTop: 6, fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all' }}>
                                                Commitment: {event.commitment_hash}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        {event.risk_score_impact !== 0 && (
                                            <div>Risk Impact: <strong style={{ color: event.risk_score_impact < 0 ? '#ef4444' : '#10b981' }}>
                                                {event.risk_score_impact > 0 ? '+' : ''}{event.risk_score_impact}
                                            </strong></div>
                                        )}
                                        {event.resolved_at && <div>Resolved: {formatDate(event.resolved_at)}</div>}
                                        {event.metadata && Object.keys(event.metadata).length > 0 && (
                                            <div style={{ marginTop: 6 }}>
                                                {Object.entries(event.metadata).map(([k, v]) => (
                                                    <span key={k} style={{ marginRight: 12 }}>
                                                        {k}: <strong>{String(v)}</strong>
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}

// ===================================================================
// Main Component
// ===================================================================

export default function PasswordTimeline() {
    const [activeTab, setActiveTab] = useState('timeline');
    const [dashboard, setDashboard] = useState(null);
    const [timeline, setTimeline] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch dashboard + timeline data
    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [dashData, timelineData] = await Promise.all([
                archaeologyService.getDashboard(),
                archaeologyService.getTimeline({ limit: 50 }),
            ]);
            setDashboard(dashData);
            setTimeline(timelineData.timeline || []);
        } catch (err) {
            console.error('Failed to load archaeology data:', err);
            setError(err.message || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return (
        <div className="arch-container">
            {/* Header */}
            <header className="arch-header">
                <div className="arch-header-content">
                    <div className="arch-title-group">
                        <div className="arch-title-icon">
                            <Clock size={24} />
                        </div>
                        <div>
                            <h1 className="arch-title">Password Archaeology</h1>
                            <p className="arch-subtitle">Time Travel · Security History · Insights</p>
                        </div>
                    </div>

                    {dashboard && (
                        <motion.div
                            className="arch-score-badge"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.5 }}
                        >
                            <ScoreRing score={dashboard.overall_score || 0} />
                            <div>
                                <div style={{ fontSize: 20, fontWeight: 700 }}>
                                    {getScoreGrade(dashboard.overall_score || 0)}
                                </div>
                                <div className="arch-score-label">Security Grade</div>
                            </div>
                        </motion.div>
                    )}
                </div>
            </header>

            {/* Stats Grid */}
            {dashboard && (
                <motion.div
                    className="arch-stats-grid"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 }}
                >
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon purple"><Key size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.total_changes || 0}</div>
                        <div className="arch-stat-label">Password Changes</div>
                    </div>
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon blue"><Shield size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.total_credentials || 0}</div>
                        <div className="arch-stat-label">Credentials Tracked</div>
                    </div>
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon green"><TrendingUp size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.avg_strength?.toFixed(0) || '—'}</div>
                        <div className="arch-stat-label">Avg Strength</div>
                    </div>
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon orange"><Calendar size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.avg_password_age_days?.toFixed(0) || 0}</div>
                        <div className="arch-stat-label">Avg Age (Days)</div>
                    </div>
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon red"><AlertTriangle size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.total_breaches || 0}</div>
                        <div className="arch-stat-label">Breaches Detected</div>
                    </div>
                    <div className="arch-stat-card">
                        <div className="arch-stat-header">
                            <div className="arch-stat-icon purple"><Award size={18} /></div>
                        </div>
                        <div className="arch-stat-value">{dashboard.achievements?.total_points || 0}</div>
                        <div className="arch-stat-label">Achievement Points</div>
                    </div>
                </motion.div>
            )}

            {/* Tab Navigation */}
            <nav className="arch-tabs">
                {TABS.map((tab) => {
                    const Icon = tab.icon;
                    return (
                        <button
                            key={tab.id}
                            className={`arch-tab ${activeTab === tab.id ? 'active' : ''}`}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            <Icon size={16} className="arch-tab-icon" />
                            {tab.label}
                        </button>
                    );
                })}
            </nav>

            {/* Tab Content */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                >
                    {loading && (
                        <div className="arch-loading">
                            <div className="arch-loading-spinner" />
                            Loading archaeology data...
                        </div>
                    )}

                    {error && (
                        <div className="arch-empty">
                            <div className="arch-empty-icon">⚠️</div>
                            <div className="arch-empty-text">Error loading data</div>
                            <div className="arch-empty-sub">{error}</div>
                            <button className="arch-btn-primary" style={{ marginTop: 16 }} onClick={fetchData}>
                                <RefreshCw size={16} /> Retry
                            </button>
                        </div>
                    )}

                    {!loading && !error && activeTab === 'timeline' && (
                        <div>
                            {timeline.length === 0 ? (
                                <div className="arch-empty">
                                    <div className="arch-empty-icon">🕰️</div>
                                    <div className="arch-empty-text">No history yet</div>
                                    <div className="arch-empty-sub">
                                        Password changes and security events will appear here as they happen.
                                    </div>
                                </div>
                            ) : (
                                <div className="arch-timeline">
                                    {timeline.map((event, i) => (
                                        <TimelineItem key={event.id} event={event} index={i} />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {!loading && !error && activeTab === 'strength' && (
                        <StrengthEvolutionChart />
                    )}

                    {!loading && !error && activeTab === 'whatif' && (
                        <WhatIfSimulator />
                    )}

                    {!loading && !error && activeTab === 'achievements' && (
                        <SecurityScoreTimeline />
                    )}

                    {!loading && !error && activeTab === 'timemachine' && (
                        <TimeMachineView />
                    )}
                </motion.div>
            </AnimatePresence>
        </div>
    );
}

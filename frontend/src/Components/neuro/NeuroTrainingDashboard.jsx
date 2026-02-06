/**
 * Neuro Training Dashboard
 * 
 * Main dashboard for EEG-based password memory training.
 * Shows training programs, progress, and device status.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import React, { useState, useEffect } from 'react';
import neuroFeedbackService from '../../services/neuroFeedbackService';
import EEGDeviceSetup from './EEGDeviceSetup';
import PasswordTrainer from './PasswordTrainer';
import BrainwaveVisualizer from './BrainwaveVisualizer';
import './NeuroTrainingDashboard.css';

const NeuroTrainingDashboard = () => {
    const [view, setView] = useState('overview'); // overview, devices, training, progress
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Data state
    const [programs, setPrograms] = useState([]);
    const [dueReviews, setDueReviews] = useState([]);
    const [statistics, setStatistics] = useState(null);
    const [devices, setDevices] = useState([]);
    const [activeSession, setActiveSession] = useState(null);

    // Load initial data
    useEffect(() => {
        loadDashboardData();
    }, []);

    const loadDashboardData = async () => {
        setLoading(true);
        try {
            const [programsRes, dueRes, statsRes, devicesRes] = await Promise.all([
                neuroFeedbackService.getPrograms(),
                neuroFeedbackService.getDueReviews(),
                neuroFeedbackService.getStatistics(),
                neuroFeedbackService.getDevices(),
            ]);

            setPrograms(programsRes.programs || []);
            setDueReviews(dueRes.programs || []);
            setStatistics(statsRes.statistics || null);
            setDevices(devicesRes.devices || []);
        } catch (err) {
            setError('Failed to load dashboard data');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleStartTraining = async (program) => {
        try {
            const result = await neuroFeedbackService.startSession(program.program_id);
            setActiveSession({
                ...result,
                program,
            });
            setView('training');
        } catch (err) {
            setError('Failed to start training session');
        }
    };

    const handleEndTraining = () => {
        setActiveSession(null);
        setView('overview');
        loadDashboardData();
    };

    const renderOverview = () => (
        <div className="neuro-overview">
            {/* Stats Cards */}
            <div className="neuro-stats-grid">
                <div className="stat-card stat-primary">
                    <div className="stat-icon">🧠</div>
                    <div className="stat-content">
                        <div className="stat-value">{statistics?.active_programs || 0}</div>
                        <div className="stat-label">Active Programs</div>
                    </div>
                </div>

                <div className="stat-card stat-success">
                    <div className="stat-icon">✅</div>
                    <div className="stat-content">
                        <div className="stat-value">{statistics?.passwords_memorized || 0}</div>
                        <div className="stat-label">Passwords Memorized</div>
                    </div>
                </div>

                <div className="stat-card stat-info">
                    <div className="stat-icon">⏱️</div>
                    <div className="stat-content">
                        <div className="stat-value">{statistics?.total_training_time_hours || 0}h</div>
                        <div className="stat-label">Training Time</div>
                    </div>
                </div>

                <div className="stat-card stat-warning">
                    <div className="stat-icon">📊</div>
                    <div className="stat-content">
                        <div className="stat-value">{Math.round((statistics?.average_memory_strength || 0) * 100)}%</div>
                        <div className="stat-label">Avg Memory Strength</div>
                    </div>
                </div>
            </div>

            {/* Due Reviews Alert */}
            {dueReviews.length > 0 && (
                <div className="due-reviews-alert">
                    <h3>📅 Reviews Due</h3>
                    <p>{dueReviews.length} password(s) need practice to maintain memory strength</p>
                    <div className="due-reviews-list">
                        {dueReviews.slice(0, 3).map(program => (
                            <div key={program.program_id} className="due-review-item">
                                <span className="vault-name">Password #{program.program_id?.substring(0, 8)}</span>
                                <span className="strength">{Math.round(program.average_strength * 100)}% strength</span>
                                <button
                                    className="btn-train"
                                    onClick={() => handleStartTraining(program)}
                                >
                                    Practice Now
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Active Programs */}
            <div className="programs-section">
                <div className="section-header">
                    <h3>Active Training Programs</h3>
                    <button
                        className="btn-secondary"
                        onClick={() => setView('devices')}
                    >
                        Manage Devices
                    </button>
                </div>

                {programs.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">🎓</span>
                        <p>No active training programs</p>
                        <p className="empty-hint">Start training a password from your vault to begin</p>
                    </div>
                ) : (
                    <div className="programs-grid">
                        {programs.map(program => (
                            <div key={program.program_id} className="program-card">
                                <div className="program-header">
                                    <span className="program-status">{program.status}</span>
                                    <span className="chunk-progress">
                                        {program.chunks_mastered}/{program.total_chunks} chunks
                                    </span>
                                </div>

                                <div className="progress-bar">
                                    <div
                                        className="progress-fill"
                                        style={{ width: `${program.completion_percentage}%` }}
                                    />
                                </div>

                                <div className="program-stats">
                                    <span>Strength: {Math.round(program.average_strength * 100)}%</span>
                                    <span>{program.total_sessions} sessions</span>
                                </div>

                                <div className="program-actions">
                                    <button
                                        className="btn-primary"
                                        onClick={() => handleStartTraining(program)}
                                    >
                                        Continue Training
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Device Status */}
            <div className="device-status-section">
                <h3>EEG Device Status</h3>
                {devices.length === 0 ? (
                    <div className="device-prompt">
                        <p>No EEG devices paired</p>
                        <button
                            className="btn-primary"
                            onClick={() => setView('devices')}
                        >
                            Pair Device
                        </button>
                    </div>
                ) : (
                    <div className="device-list">
                        {devices.map(device => (
                            <div key={device.id} className={`device-item status-${device.status}`}>
                                <span className="device-name">{device.device_name}</span>
                                <span className="device-type">{device.device_type_display}</span>
                                <span className={`device-status ${device.status}`}>
                                    {device.status}
                                </span>
                                {device.battery_level && (
                                    <span className="battery">🔋 {device.battery_level}%</span>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );

    if (loading) {
        return (
            <div className="neuro-dashboard loading">
                <div className="loading-spinner">
                    <div className="brain-pulse">🧠</div>
                    <p>Loading Neuro-Feedback Dashboard...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="neuro-dashboard">
            {/* Header */}
            <header className="neuro-header">
                <div className="header-content">
                    <h1>🧠 Neuro-Feedback Training</h1>
                    <p className="subtitle">Train your brain to memorize passwords using EEG neurofeedback</p>
                </div>

                <nav className="neuro-nav">
                    <button
                        className={`nav-btn ${view === 'overview' ? 'active' : ''}`}
                        onClick={() => setView('overview')}
                    >
                        Overview
                    </button>
                    <button
                        className={`nav-btn ${view === 'devices' ? 'active' : ''}`}
                        onClick={() => setView('devices')}
                    >
                        Devices
                    </button>
                    <button
                        className={`nav-btn ${view === 'progress' ? 'active' : ''}`}
                        onClick={() => setView('progress')}
                    >
                        Progress
                    </button>
                </nav>
            </header>

            {/* Error Display */}
            {error && (
                <div className="error-banner">
                    <span>{error}</span>
                    <button onClick={() => setError(null)}>✕</button>
                </div>
            )}

            {/* Main Content */}
            <main className="neuro-content">
                {view === 'overview' && renderOverview()}

                {view === 'devices' && (
                    <EEGDeviceSetup
                        devices={devices}
                        onDevicesChange={loadDashboardData}
                        onBack={() => setView('overview')}
                    />
                )}

                {view === 'training' && activeSession && (
                    <PasswordTrainer
                        session={activeSession}
                        onEnd={handleEndTraining}
                    />
                )}

                {view === 'progress' && (
                    <BrainwaveVisualizer
                        programs={programs}
                        statistics={statistics}
                    />
                )}
            </main>
        </div>
    );
};

export default NeuroTrainingDashboard;

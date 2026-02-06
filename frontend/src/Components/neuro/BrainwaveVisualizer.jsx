/**
 * Brainwave Visualizer Component
 * 
 * Displays memory strength and training progress with
 * visualizations inspired by brain activity patterns.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import React from 'react';
import './BrainwaveVisualizer.css';

const BrainwaveVisualizer = ({ programs, statistics }) => {
    // Calculate overall metrics
    const totalChunks = programs.reduce((sum, p) => sum + p.total_chunks, 0);
    const masteredChunks = programs.reduce((sum, p) => sum + p.chunks_mastered, 0);
    const overallProgress = totalChunks > 0 ? (masteredChunks / totalChunks) * 100 : 0;

    return (
        <div className="brainwave-visualizer">
            <header className="viz-header">
                <h2>Memory Progress</h2>
                <p>Track your password memorization journey</p>
            </header>

            {/* Overall Progress Ring */}
            <div className="progress-ring-container">
                <div className="progress-ring">
                    <svg viewBox="0 0 100 100">
                        {/* Background ring */}
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke="rgba(255, 255, 255, 0.1)"
                            strokeWidth="8"
                        />
                        {/* Progress ring */}
                        <circle
                            cx="50"
                            cy="50"
                            r="45"
                            fill="none"
                            stroke="url(#progressGradient)"
                            strokeWidth="8"
                            strokeLinecap="round"
                            strokeDasharray={`${overallProgress * 2.83} 283`}
                            transform="rotate(-90 50 50)"
                        />
                        <defs>
                            <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" stopColor="#6366f1" />
                                <stop offset="100%" stopColor="#a78bfa" />
                            </linearGradient>
                        </defs>
                    </svg>
                    <div className="ring-content">
                        <span className="ring-value">{Math.round(overallProgress)}%</span>
                        <span className="ring-label">Overall</span>
                    </div>
                </div>

                <div className="ring-stats">
                    <div className="ring-stat">
                        <span className="stat-value">{masteredChunks}</span>
                        <span className="stat-label">Chunks Mastered</span>
                    </div>
                    <div className="ring-stat">
                        <span className="stat-value">{totalChunks - masteredChunks}</span>
                        <span className="stat-label">In Progress</span>
                    </div>
                    <div className="ring-stat">
                        <span className="stat-value">{statistics?.total_sessions || 0}</span>
                        <span className="stat-label">Total Sessions</span>
                    </div>
                </div>
            </div>

            {/* Program Breakdown */}
            {programs.length > 0 && (
                <div className="programs-breakdown">
                    <h3>Password Training Progress</h3>

                    <div className="program-bars">
                        {programs.map(program => (
                            <div key={program.program_id} className="program-bar-item">
                                <div className="bar-header">
                                    <span className="program-name">
                                        Password #{program.program_id?.substring(0, 8)}
                                    </span>
                                    <span className="program-percent">
                                        {Math.round(program.completion_percentage)}%
                                    </span>
                                </div>

                                <div className="strength-bar">
                                    <div
                                        className="strength-fill"
                                        style={{ width: `${program.completion_percentage}%` }}
                                    />
                                    <div
                                        className="strength-marker"
                                        style={{ left: `${program.average_strength * 100}%` }}
                                    />
                                </div>

                                <div className="bar-details">
                                    <span>{program.chunks_mastered}/{program.total_chunks} chunks</span>
                                    <span>Strength: {Math.round(program.average_strength * 100)}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Memory Strength Legend */}
            <div className="strength-legend">
                <h4>Memory Strength Guide</h4>
                <div className="legend-items">
                    <div className="legend-item">
                        <div className="legend-color" style={{ background: '#22c55e' }} />
                        <span>90-100% Mastered</span>
                    </div>
                    <div className="legend-item">
                        <div className="legend-color" style={{ background: '#eab308' }} />
                        <span>50-89% Learning</span>
                    </div>
                    <div className="legend-item">
                        <div className="legend-color" style={{ background: '#ef4444' }} />
                        <span>0-49% Needs Practice</span>
                    </div>
                </div>
            </div>

            {/* Brain State Waves (Decorative) */}
            <div className="brain-waves">
                <div className="wave wave-alpha">
                    <span className="wave-label">Alpha Waves</span>
                    <div className="wave-line" />
                </div>
                <div className="wave wave-theta">
                    <span className="wave-label">Theta Waves</span>
                    <div className="wave-line" />
                </div>
                <div className="wave wave-gamma">
                    <span className="wave-label">Gamma Waves</span>
                    <div className="wave-line" />
                </div>
            </div>
        </div>
    );
};

export default BrainwaveVisualizer;

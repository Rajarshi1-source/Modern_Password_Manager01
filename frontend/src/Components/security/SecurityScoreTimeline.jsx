/**
 * Security Score Timeline & Achievements
 * ========================================
 * Gamification view showing security score over time,
 * achievement badges, and streak indicators.
 */

import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale, LinearScale, PointElement,
    LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { motion } from 'framer-motion';
import {
    Award, Star, Shield, ShieldCheck, Trophy, Crown,
    Zap, RotateCw, Key, GitBranch, Flame,
} from 'lucide-react';
import archaeologyService from '../../services/archaeologyService';

ChartJS.register(
    CategoryScale, LinearScale, PointElement,
    LineElement, Title, Tooltip, Legend, Filler,
);

const ICON_MAP = {
    'key-round': Key,
    'rotate-cw': RotateCw,
    'trophy': Trophy,
    'shield-check': ShieldCheck,
    'shield': Shield,
    'shield-off': Shield,
    'crown': Crown,
    'zap': Zap,
    'git-branch': GitBranch,
    'star': Star,
};

function getIcon(name) {
    return ICON_MAP[name] || Award;
}

export default function SecurityScoreTimeline() {
    const [achievements, setAchievements] = useState([]);
    const [scoreData, setScoreData] = useState(null);
    const [totalPoints, setTotalPoints] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                const [achData, scoreResult] = await Promise.all([
                    archaeologyService.getAchievements(),
                    archaeologyService.getSecurityScore(),
                ]);
                setAchievements(achData.achievements || []);
                setTotalPoints(achData.total_points || 0);
                setScoreData(scoreResult);
            } catch (err) {
                console.error('Score/Achievement error:', err);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const handleAcknowledge = async (id) => {
        try {
            await archaeologyService.acknowledgeAchievement(id);
            setAchievements(prev =>
                prev.map(a => a.id === id ? { ...a, acknowledged: true } : a)
            );
        } catch (err) {
            console.error('Acknowledge error:', err);
        }
    };

    if (loading) {
        return (
            <div className="arch-loading">
                <div className="arch-loading-spinner" />
                Loading achievements...
            </div>
        );
    }

    // Score chart data
    const scores = scoreData?.scores || [];
    const chartData = scores.length > 0 ? {
        labels: scores.map(s => {
            const d = new Date(s.date);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }),
        datasets: [
            {
                label: 'Security Score',
                data: scores.map(s => s.avg_score),
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 5,
                pointBackgroundColor: '#10b981',
            },
        ],
    } : null;

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(17, 24, 39, 0.95)',
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(16, 185, 129, 0.3)',
                borderWidth: 1,
                cornerRadius: 8,
                padding: 12,
            },
        },
        scales: {
            x: {
                grid: { color: 'rgba(255,255,255,0.04)' },
                ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 45 },
            },
            y: {
                grid: { color: 'rgba(255,255,255,0.04)' },
                ticks: { color: '#64748b', font: { size: 11 } },
                min: 0,
                max: 100,
            },
        },
    };

    return (
        <div>
            {/* Total Points Banner */}
            <motion.div
                className="arch-stat-card"
                style={{
                    marginBottom: 24,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 20,
                    padding: '20px 28px',
                }}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4 }}
            >
                <div className="arch-stat-icon gold" style={{ width: 56, height: 56 }}>
                    <Trophy size={28} />
                </div>
                <div>
                    <div className="arch-stat-value" style={{ fontSize: 32 }}>
                        {totalPoints}
                    </div>
                    <div className="arch-stat-label">Total Achievement Points</div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Flame size={18} style={{ color: '#f59e0b' }} />
                    <span style={{ fontSize: 14, color: '#f59e0b', fontWeight: 600 }}>
                        {achievements.length} badges earned
                    </span>
                </div>
            </motion.div>

            {/* Score Chart */}
            {chartData && (
                <motion.div
                    className="arch-chart-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 }}
                >
                    <div className="arch-chart-card-header">
                        <h3 className="arch-chart-card-title">
                            <Shield size={20} />
                            Security Score Over Time
                        </h3>
                    </div>
                    <div className="arch-chart-container">
                        <Line data={chartData} options={chartOptions} />
                    </div>
                </motion.div>
            )}

            {/* Achievements Grid */}
            <h3 className="arch-chart-card-title" style={{ marginBottom: 16 }}>
                <Award size={20} />
                Achievements
            </h3>

            {achievements.length === 0 ? (
                <div className="arch-empty">
                    <div className="arch-empty-icon">🏆</div>
                    <div className="arch-empty-text">No achievements yet</div>
                    <div className="arch-empty-sub">
                        Keep improving your security to earn badges!
                    </div>
                </div>
            ) : (
                <div className="arch-achievements-grid">
                    {achievements.map((ach, i) => {
                        const Icon = getIcon(ach.icon_name);
                        return (
                            <motion.div
                                key={ach.id}
                                className={`arch-achievement-card ${!ach.acknowledged ? 'unacknowledged' : ''}`}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05, duration: 0.3 }}
                                onClick={() => !ach.acknowledged && handleAcknowledge(ach.id)}
                                style={{ cursor: ach.acknowledged ? 'default' : 'pointer' }}
                            >
                                <div className={`arch-achievement-icon ${ach.badge_tier}`}>
                                    <Icon size={22} />
                                </div>
                                <div className="arch-achievement-info">
                                    <div className="arch-achievement-title">{ach.title}</div>
                                    <div className="arch-achievement-desc">{ach.description}</div>
                                    <div className="arch-achievement-meta">
                                        <span className="arch-achievement-points">
                                            <Star size={12} /> {ach.score_points} pts
                                        </span>
                                        <span>
                                            {new Date(ach.earned_at).toLocaleDateString('en-US', {
                                                month: 'short', day: 'numeric', year: 'numeric',
                                            })}
                                        </span>
                                        {!ach.acknowledged && (
                                            <span style={{ color: '#6366f1', fontWeight: 600 }}>
                                                ✨ New!
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

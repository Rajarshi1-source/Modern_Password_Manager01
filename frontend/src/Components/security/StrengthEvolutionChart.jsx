/**
 * Strength Evolution Chart
 * =========================
 * Chart.js line chart showing password strength over time.
 */

import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale, LinearScale, PointElement,
    LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { motion } from 'framer-motion';
import { TrendingUp, RefreshCw } from 'lucide-react';
import archaeologyService from '../../services/archaeologyService';

ChartJS.register(
    CategoryScale, LinearScale, PointElement,
    LineElement, Title, Tooltip, Legend, Filler,
);

export default function StrengthEvolutionChart() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        (async () => {
            try {
                const result = await archaeologyService.getOverallStrength();
                setData(result.data_points || []);
            } catch (err) {
                console.error('Strength evolution error:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    if (loading) {
        return (
            <div className="arch-loading">
                <div className="arch-loading-spinner" />
                Loading strength data...
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="arch-empty">
                <div className="arch-empty-icon">📊</div>
                <div className="arch-empty-text">{error || 'No strength data available'}</div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="arch-empty">
                <div className="arch-empty-icon">📈</div>
                <div className="arch-empty-text">No strength snapshots yet</div>
                <div className="arch-empty-sub">
                    Strength data will appear here once passwords are tracked.
                </div>
            </div>
        );
    }

    const labels = data.map(d => {
        const date = new Date(d.timestamp);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const chartData = {
        labels,
        datasets: [
            {
                label: 'Strength Score',
                data: data.map(d => d.strength_score),
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: '#6366f1',
                pointBorderColor: '#0a0e1a',
                pointBorderWidth: 2,
            },
            {
                label: 'Entropy (bits)',
                data: data.map(d => d.entropy_bits),
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.05)',
                fill: true,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 5,
                borderDash: [5, 5],
                pointBackgroundColor: '#8b5cf6',
            },
        ],
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    color: '#94a3b8',
                    font: { size: 12, family: 'Inter, sans-serif' },
                    boxWidth: 12,
                    padding: 20,
                },
            },
            tooltip: {
                backgroundColor: 'rgba(17, 24, 39, 0.95)',
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(99, 102, 241, 0.3)',
                borderWidth: 1,
                cornerRadius: 8,
                padding: 12,
                bodyFont: { family: 'Inter, sans-serif' },
                callbacks: {
                    afterBody(context) {
                        const idx = context[0].dataIndex;
                        const point = data[idx];
                        const lines = [];
                        if (point.credential_domain) {
                            lines.push(`Domain: ${point.credential_domain}`);
                        }
                        if (point.breach_exposure_count > 0) {
                            lines.push(`⚠️ Breach exposures: ${point.breach_exposure_count}`);
                        }
                        if (point.is_reused) {
                            lines.push('🔄 Password is reused');
                        }
                        return lines;
                    },
                },
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
        <motion.div
            className="arch-chart-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
        >
            <div className="arch-chart-card-header">
                <h3 className="arch-chart-card-title">
                    <TrendingUp size={20} />
                    Strength Evolution
                </h3>
            </div>
            <div className="arch-chart-container">
                <Line data={chartData} options={chartOptions} />
            </div>
        </motion.div>
    );
}

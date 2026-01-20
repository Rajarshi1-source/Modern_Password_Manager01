/**
 * EntropyHistoryChart.jsx
 * 
 * Interactive chart showing historical entropy measurements for an entangled pair.
 * Displays entropy trends with warning/critical thresholds.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import './EntropyHistoryChart.css';

// Register Chart.js components
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
);

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Threshold constants
const ENTROPY_HEALTHY = 7.5;
const ENTROPY_WARNING = 7.0;

function EntropyHistoryChart({ pairId, authToken, onError }) {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [days, setDays] = useState(7);
    const [error, setError] = useState(null);

    const fetchEntropyHistory = useCallback(async () => {
        if (!pairId || !authToken) return;

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/security/entanglement/entropy-history/${pairId}/?days=${days}&limit=100`,
                {
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json',
                    },
                }
            );

            if (!response.ok) {
                throw new Error('Failed to fetch entropy history');
            }

            const result = await response.json();
            setData(result);
        } catch (err) {
            setError(err.message);
            if (onError) onError(err);
        } finally {
            setLoading(false);
        }
    }, [pairId, authToken, days, onError]);

    useEffect(() => {
        fetchEntropyHistory();
    }, [fetchEntropyHistory]);

    // Prepare chart data
    const chartData = data ? {
        labels: data.measurements
            .slice()
            .reverse()
            .map(m => new Date(m.measured_at).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            })),
        datasets: [
            {
                label: 'Entropy (bits/byte)',
                data: data.measurements.slice().reverse().map(m => m.entropy_value),
                borderColor: 'rgba(99, 102, 241, 1)',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: data.measurements.slice().reverse().map(m => {
                    if (m.is_critical) return '#ef4444';
                    if (m.is_warning) return '#f59e0b';
                    return '#10b981';
                }),
            },
            {
                label: 'Healthy Threshold',
                data: Array(data.measurements.length).fill(ENTROPY_HEALTHY),
                borderColor: 'rgba(16, 185, 129, 0.5)',
                borderDash: [5, 5],
                pointRadius: 0,
                fill: false,
            },
            {
                label: 'Warning Threshold',
                data: Array(data.measurements.length).fill(ENTROPY_WARNING),
                borderColor: 'rgba(245, 158, 11, 0.5)',
                borderDash: [5, 5],
                pointRadius: 0,
                fill: false,
            },
        ],
    } : null;

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 15,
                },
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                padding: 12,
                displayColors: false,
                callbacks: {
                    label: function (context) {
                        const value = context.raw;
                        const status = value >= ENTROPY_HEALTHY ? '🟢 Healthy' :
                            value >= ENTROPY_WARNING ? '🟡 Warning' : '🔴 Critical';
                        return `Entropy: ${value.toFixed(4)} bits/byte (${status})`;
                    }
                }
            },
        },
        scales: {
            y: {
                min: 6.5,
                max: 8.0,
                title: {
                    display: true,
                    text: 'Entropy (bits/byte)',
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)',
                },
            },
            x: {
                title: {
                    display: true,
                    text: 'Time',
                },
                grid: {
                    display: false,
                },
                ticks: {
                    maxRotation: 45,
                    minRotation: 45,
                },
            },
        },
        interaction: {
            mode: 'index',
            intersect: false,
        },
    };

    if (loading) {
        return (
            <div className="entropy-chart-container entropy-chart-loading">
                <div className="entropy-chart-spinner"></div>
                <span>Loading entropy history...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="entropy-chart-container entropy-chart-error">
                <span className="error-icon">⚠️</span>
                <span>Error: {error}</span>
                <button onClick={fetchEntropyHistory} className="retry-btn">
                    Try Again
                </button>
            </div>
        );
    }

    if (!data || data.measurements.length === 0) {
        return (
            <div className="entropy-chart-container entropy-chart-empty">
                <span className="empty-icon">📊</span>
                <span>No entropy measurements recorded yet</span>
            </div>
        );
    }

    return (
        <div className="entropy-chart-container">
            <div className="entropy-chart-header">
                <h3 className="entropy-chart-title">Entropy History</h3>
                <div className="entropy-chart-controls">
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="days-select"
                    >
                        <option value={1}>Last 24 hours</option>
                        <option value={7}>Last 7 days</option>
                        <option value={30}>Last 30 days</option>
                    </select>
                    <button onClick={fetchEntropyHistory} className="refresh-btn">
                        🔄 Refresh
                    </button>
                </div>
            </div>

            <div className="entropy-chart-stats">
                <div className="stat-card">
                    <span className="stat-value">{data.average_entropy?.toFixed(4) || '—'}</span>
                    <span className="stat-label">Avg Entropy</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value">{data.total_count || 0}</span>
                    <span className="stat-label">Measurements</span>
                </div>
                <div className="stat-card stat-warning">
                    <span className="stat-value">{data.warning_count || 0}</span>
                    <span className="stat-label">Warnings</span>
                </div>
                <div className="stat-card stat-critical">
                    <span className="stat-value">{data.critical_count || 0}</span>
                    <span className="stat-label">Critical</span>
                </div>
            </div>

            <div className="entropy-chart-wrapper">
                <Line data={chartData} options={chartOptions} />
            </div>
        </div>
    );
}

EntropyHistoryChart.propTypes = {
    pairId: PropTypes.string.isRequired,
    authToken: PropTypes.string.isRequired,
    onError: PropTypes.func,
};

export default EntropyHistoryChart;

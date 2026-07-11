/**
 * Recovery Metrics Dashboard (Phase 2B.2)
 * 
 * Admin dashboard for monitoring behavioral recovery system performance.
 * Displays KPIs, A/B test results, blockchain stats, and trends.
 */

import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import './RecoveryMetricsDashboard.css';
import MetricCard from './MetricCard';
import ABTestResults from './ABTestResults';
import BlockchainStats from './BlockchainStats';
import TrendsChart from './TrendsChart';
import FeedbackSummary from './FeedbackSummary';
import { authHeader } from '../../../utils/authHeader';

const RecoveryMetricsDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState(30); // Default: 30 days
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/api/behavioral-recovery/metrics/dashboard/`,
        {
          params: { time_range_days: timeRange },
          headers: {
            ...authHeader()
          }
        }
      );

      setMetrics(response.data.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching metrics:', err);
      setError(err.response?.data?.message || 'Failed to fetch metrics');
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchMetrics();

    // Auto-refresh every 5 minutes if enabled
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchMetrics, autoRefresh]);

  const handleTimeRangeChange = (days) => {
    setTimeRange(days);
  };

  const handleRefresh = () => {
    fetchMetrics();
  };

  const exportMetrics = () => {
    if (!metrics) return;
    
    const dataStr = JSON.stringify(metrics, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `recovery-metrics-${new Date().toISOString()}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  if (loading && !metrics) {
    return (
      <div className="metrics-dashboard loading">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading metrics...</p>
        </div>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="metrics-dashboard error">
        <div className="error-message">
          <h2>⚠️ Error Loading Metrics</h2>
          <p>{error}</p>
          <button onClick={fetchMetrics} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="metrics-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div className="header-content">
          <h1>Behavioral Recovery Metrics Dashboard</h1>
          <p className="subtitle">Phase 2B.2 Evaluation Framework</p>
        </div>
        
        <div className="header-controls">
          {/* Time Range Selector */}
          <div className="time-range-selector">
            <label>Time Range:</label>
            <button
              className={timeRange === 7 ? 'active' : ''}
              onClick={() => handleTimeRangeChange(7)}
            >
              7 Days
            </button>
            <button
              className={timeRange === 30 ? 'active' : ''}
              onClick={() => handleTimeRangeChange(30)}
            >
              30 Days
            </button>
            <button
              className={timeRange === 90 ? 'active' : ''}
              onClick={() => handleTimeRangeChange(90)}
            >
              90 Days
            </button>
          </div>
          
          {/* Controls */}
          <button onClick={handleRefresh} className="refresh-button" title="Refresh">
            🔄 Refresh
          </button>
          <button onClick={exportMetrics} className="export-button" title="Export">
            📥 Export
          </button>
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {metrics && (
        <>
          {/* Critical Security Metrics */}
          <section className="metrics-section critical">
            <h2>🔒 Critical Security Metrics</h2>
            <div className="metric-cards critical-metrics">
              <MetricCard
                title="False Positive Rate"
                value={`${metrics.metrics.false_positive_rate}%`}
                target="0.0%"
                status={metrics.metrics.false_positive_rate === 0 ? 'success' : 'danger'}
                critical={true}
                description="Unauthorized recoveries (MUST be 0%)"
                icon="🚨"
              />
              
              <MetricCard
                title="Blockchain Verification"
                value={`${metrics.metrics.blockchain_verification_rate}%`}
                target="100%"
                status={metrics.metrics.blockchain_verification_rate >= 100 ? 'success' : 'warning'}
                description="Commitments anchored to blockchain"
                icon="⛓️"
              />
            </div>
          </section>

          {/* User Experience Metrics */}
          <section className="metrics-section">
            <h2>👤 User Experience Metrics</h2>
            <div className="metric-cards">
              <MetricCard
                title="Recovery Success Rate"
                value={`${metrics.metrics.recovery_success_rate}%`}
                target="≥95%"
                status={metrics.metrics.recovery_success_rate >= 95 ? 'success' : 'warning'}
                description="Successful recovery completions"
                icon="✅"
              />
              
              <MetricCard
                title="Average Recovery Time"
                value={`${metrics.metrics.average_recovery_time} hrs`}
                target="<24 hrs"
                status={metrics.metrics.average_recovery_time < 24 ? 'success' : 'warning'}
                description="Time to complete recovery"
                icon="⏱️"
              />
              
              <MetricCard
                title="User Satisfaction"
                value={metrics.metrics.user_satisfaction ? `${metrics.metrics.user_satisfaction}/10` : 'N/A'}
                target="≥7.0"
                status={
                  metrics.metrics.user_satisfaction
                    ? (metrics.metrics.user_satisfaction >= 7 ? 'success' : 'warning')
                    : 'neutral'
                }
                description="Average satisfaction score"
                icon="😊"
              />
              
              <MetricCard
                title="Abandonment Rate"
                value={`${metrics.metrics.user_abandonment_rate}%`}
                target="<10%"
                status={metrics.metrics.user_abandonment_rate < 10 ? 'success' : 'warning'}
                description="Users who gave up"
                icon="🚪"
              />
            </div>
          </section>

          {/* Business Metrics */}
          <section className="metrics-section">
            <h2>💼 Business Metrics</h2>
            <div className="metric-cards">
              <MetricCard
                title="NPS Score"
                value={metrics.metrics.nps_score !== null ? metrics.metrics.nps_score : 'N/A'}
                target="≥40"
                status={
                  metrics.metrics.nps_score !== null
                    ? (metrics.metrics.nps_score >= 40 ? 'success' : 'warning')
                    : 'neutral'
                }
                description="Net Promoter Score"
                icon="📊"
              />
              
              <MetricCard
                title="Cost per Recovery"
                value={`$${metrics.metrics.cost_metrics?.cost_per_recovery?.toFixed(4) || '0'}`}
                target="<$0.01"
                status="info"
                description="Operational cost"
                icon="💰"
              />
              
              <MetricCard
                title="Model Accuracy"
                value={metrics.metrics.model_accuracy ? `${metrics.metrics.model_accuracy}%` : 'N/A'}
                target="≥85%"
                status={
                  metrics.metrics.model_accuracy
                    ? (metrics.metrics.model_accuracy >= 85 ? 'success' : 'warning')
                    : 'neutral'
                }
                description="ML model performance"
                icon="🧠"
              />
            </div>
          </section>

          {/* Blockchain Statistics */}
          <section className="metrics-section">
            <h2>⛓️ Blockchain Anchoring</h2>
            <BlockchainStats
              stats={metrics.blockchain}
              costMetrics={metrics.metrics.cost_metrics}
            />
          </section>

          {/* A/B Test Results */}
          {metrics.ab_tests && Object.keys(metrics.ab_tests).length > 0 && (
            <section className="metrics-section">
              <h2>🧪 A/B Testing Results</h2>
              <ABTestResults tests={metrics.ab_tests} />
            </section>
          )}

          {/* Trends */}
          {metrics.trends && (
            <section className="metrics-section">
              <h2>📈 Trends Over Time</h2>
              <TrendsChart trends={metrics.trends} />
            </section>
          )}

          {/* User Feedback Summary */}
          <section className="metrics-section">
            <h2>💬 User Feedback</h2>
            <FeedbackSummary metrics={metrics.metrics} />
          </section>

          {/* Metadata Footer */}
          <footer className="dashboard-footer">
            <p>
              Last updated: {new Date(metrics.generated_at).toLocaleString()}
            </p>
            <p>
              Time range: {metrics.time_range_days} days
            </p>
          </footer>
        </>
      )}
    </div>
  );
};

export default RecoveryMetricsDashboard;


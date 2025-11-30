/**
 * Metric Card Component (Phase 2B.2)
 * 
 * Displays a single KPI metric with status indicator
 */

import React from 'react';
import './MetricCard.css';

const MetricCard = ({
  title,
  value,
  target,
  status = 'neutral', // 'success', 'warning', 'danger', 'info', 'neutral'
  critical = false,
  description,
  icon = '📊',
  trend = null // { direction: 'up'|'down', value: '+5%' }
}) => {
  const getStatusClass = () => {
    if (critical && status !== 'success') return 'critical-alert';
    return `status-${status}`;
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'success':
        return '✅';
      case 'warning':
        return '⚠️';
      case 'danger':
        return '🚨';
      case 'info':
        return 'ℹ️';
      default:
        return '';
    }
  };

  const getTrendIcon = () => {
    if (!trend) return null;
    return trend.direction === 'up' ? '📈' : '📉';
  };

  return (
    <div className={`metric-card ${getStatusClass()}`}>
      {critical && status !== 'success' && (
        <div className="critical-banner">CRITICAL ALERT</div>
      )}
      
      <div className="metric-header">
        <span className="metric-icon">{icon}</span>
        <h3 className="metric-title">{title}</h3>
      </div>
      
      <div className="metric-value-container">
        <div className="metric-value">{value}</div>
        {trend && (
          <div className={`metric-trend trend-${trend.direction}`}>
            {getTrendIcon()} {trend.value}
          </div>
        )}
      </div>
      
      <div className="metric-footer">
        <div className="metric-target">
          Target: <strong>{target}</strong>
        </div>
        <div className="metric-status">
          {getStatusIcon()} {status.charAt(0).toUpperCase() + status.slice(1)}
        </div>
      </div>
      
      {description && (
        <div className="metric-description">{description}</div>
      )}
    </div>
  );
};

export default MetricCard;


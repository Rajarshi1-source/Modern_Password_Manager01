/**
 * Trends Chart Component (Phase 2B.2)
 * 
 * Displays trending metrics over time
 * (Simplified version - can be enhanced with Chart.js or Recharts)
 */

import React from 'react';
import './TrendsChart.css';

const TrendsChart = ({ trends }) => {
  if (!trends || !trends.dates || trends.dates.length === 0) {
    return (
      <div className="trends-chart empty">
        <p>No trend data available.</p>
      </div>
    );
  }

  const renderSimpleChart = (data, label, color) => {
    if (!data || data.length === 0) return null;
    
    // Find min and max for scaling
    const validData = data.filter(d => d !== null && d !== undefined);
    if (validData.length === 0) return null;
    
    const min = Math.min(...validData);
    const max = Math.max(...validData);
    const range = max - min || 1;
    
    return (
      <div className="chart-container">
        <div className="chart-header">
          <h4>{label}</h4>
          <span className="chart-current-value" style={{ color }}>
            {data[data.length - 1] !== null ? data[data.length - 1].toFixed(1) : 'N/A'}
          </span>
        </div>
        <div className="chart-bars">
          {data.map((value, index) => {
            if (value === null || value === undefined) {
              return (
                <div key={index} className="chart-bar-wrapper">
                  <div className="chart-bar empty"></div>
                  <div className="chart-label">{trends.dates[index]}</div>
                </div>
              );
            }
            
            const height = ((value - min) / range) * 100;
            return (
              <div key={index} className="chart-bar-wrapper">
                <div
                  className="chart-bar"
                  style={{
                    height: `${Math.max(height, 5)}%`,
                    backgroundColor: color
                  }}
                  title={`${trends.dates[index]}: ${value.toFixed(1)}`}
                >
                  <span className="bar-value">{value.toFixed(0)}</span>
                </div>
                <div className="chart-label">{trends.dates[index]}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="trends-chart">
      {trends.success_rate && renderSimpleChart(
        trends.success_rate,
        'Recovery Success Rate (%)',
        '#4CAF50'
      )}
      
      {trends.user_satisfaction && renderSimpleChart(
        trends.user_satisfaction,
        'User Satisfaction (1-10)',
        '#2196F3'
      )}
      
      {trends.nps_score && renderSimpleChart(
        trends.nps_score,
        'NPS Score',
        '#FF9800'
      )}
      
      <div className="trends-legend">
        <p>📈 Trends show data over {trends.dates.length} time periods</p>
      </div>
    </div>
  );
};

export default TrendsChart;


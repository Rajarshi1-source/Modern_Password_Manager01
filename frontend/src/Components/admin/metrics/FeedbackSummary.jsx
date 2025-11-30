/**
 * Feedback Summary Component (Phase 2B.2)
 * 
 * Displays summary of user feedback
 */

import React from 'react';
import './FeedbackSummary.css';

const FeedbackSummary = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="feedback-summary empty">
        <p>No feedback data available.</p>
      </div>
    );
  }

  const getFeedbackBreakdown = () => {
    // Calculate NPS breakdown
    const nps = metrics.nps_score;
    if (nps === null || nps === undefined) return null;
    
    let category, emoji, color;
    if (nps >= 50) {
      category = 'Excellent';
      emoji = '🤩';
      color = '#4CAF50';
    } else if (nps >= 30) {
      category = 'Good';
      emoji = '😊';
      color = '#8BC34A';
    } else if (nps >= 10) {
      category = 'Acceptable';
      emoji = '😐';
      color = '#FFC107';
    } else if (nps >= 0) {
      category = 'Needs Improvement';
      emoji = '😕';
      color = '#FF9800';
    } else {
      category = 'Poor';
      emoji = '😞';
      color = '#F44336';
    }
    
    return { category, emoji, color, score: nps };
  };

  const npsBreakdown = getFeedbackBreakdown();

  return (
    <div className="feedback-summary">
      {npsBreakdown && (
        <div className="nps-breakdown">
          <div className="nps-score-card" style={{ borderColor: npsBreakdown.color }}>
            <div className="nps-emoji">{npsBreakdown.emoji}</div>
            <div className="nps-score" style={{ color: npsBreakdown.color }}>
              {npsBreakdown.score.toFixed(1)}
            </div>
            <div className="nps-category">{npsBreakdown.category}</div>
          </div>
        </div>
      )}

      <div className="feedback-metrics-grid">
        {metrics.user_satisfaction !== null && metrics.user_satisfaction !== undefined && (
          <div className="feedback-metric">
            <div className="metric-icon">😊</div>
            <div className="metric-info">
              <div className="metric-label">User Satisfaction</div>
              <div className="metric-value">{metrics.user_satisfaction.toFixed(1)}/10</div>
            </div>
          </div>
        )}
        
        <div className="feedback-metric">
          <div className="metric-icon">⏱️</div>
          <div className="metric-info">
            <div className="metric-label">Avg Recovery Time</div>
            <div className="metric-value">{metrics.average_recovery_time.toFixed(1)} hrs</div>
          </div>
        </div>
        
        <div className="feedback-metric">
          <div className="metric-icon">✅</div>
          <div className="metric-info">
            <div className="metric-label">Success Rate</div>
            <div className="metric-value">{metrics.recovery_success_rate.toFixed(1)}%</div>
          </div>
        </div>
        
        <div className="feedback-metric">
          <div className="metric-icon">🚪</div>
          <div className="metric-info">
            <div className="metric-label">Abandonment Rate</div>
            <div className="metric-value">{metrics.user_abandonment_rate.toFixed(1)}%</div>
          </div>
        </div>
      </div>

      <div className="feedback-actions">
        <p className="feedback-note">
          💡 Collecting user feedback helps us optimize the recovery experience.
          {npsBreakdown && npsBreakdown.score < 40 && (
            <span className="improvement-note">
              {' '}Consider running additional A/B tests to improve satisfaction.
            </span>
          )}
        </p>
      </div>
    </div>
  );
};

export default FeedbackSummary;


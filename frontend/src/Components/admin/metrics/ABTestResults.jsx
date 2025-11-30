/**
 * A/B Test Results Component (Phase 2B.2)
 * 
 * Displays results from behavioral recovery A/B testing experiments
 */

import React, { useState } from 'react';
import './ABTestResults.css';

const ABTestResults = ({ tests }) => {
  const [expandedTest, setExpandedTest] = useState(null);

  const toggleTest = (testName) => {
    setExpandedTest(expandedTest === testName ? null : testName);
  };

  const getTestDisplayName = (testName) => {
    const names = {
      'recovery_time_duration': 'Recovery Timeline Duration',
      'similarity_threshold': 'Behavioral Similarity Threshold',
      'challenge_frequency': 'Challenge Frequency'
    };
    return names[testName] || testName;
  };

  const getVariantDisplayName = (variantName) => {
    const names = {
      '3_days': '3 Days',
      '5_days': '5 Days',
      '7_days': '7 Days',
      'threshold_085': '85% Threshold',
      'threshold_087': '87% Threshold',
      'threshold_090': '90% Threshold',
      'once_daily': '1x per Day',
      'twice_daily': '2x per Day',
      'three_daily': '3x per Day'
    };
    return names[variantName] || variantName;
  };

  if (!tests || Object.keys(tests).length === 0) {
    return (
      <div className="ab-test-results empty">
        <p>No A/B test results available. Experiments may not be running yet.</p>
      </div>
    );
  }

  return (
    <div className="ab-test-results">
      {Object.entries(tests).map(([testName, testData]) => (
        <div key={testName} className="test-container">
          <div
            className="test-header"
            onClick={() => toggleTest(testName)}
          >
            <h3>{getTestDisplayName(testName)}</h3>
            <div className="test-status">
              {testData.is_active ? (
                <span className="status-badge active">🟢 Active</span>
              ) : (
                <span className="status-badge inactive">🔴 Inactive</span>
              )}
              <span className="expand-icon">
                {expandedTest === testName ? '▼' : '▶'}
              </span>
            </div>
          </div>

          {expandedTest === testName && (
            <div className="test-details">
              {testData.hypothesis && (
                <div className="test-hypothesis">
                  <strong>Hypothesis:</strong> {testData.hypothesis}
                </div>
              )}
              
              <div className="variants-grid">
                {testData.variants?.map((variant) => (
                  <div key={variant.name} className="variant-card">
                    <div className="variant-header">
                      <h4>{getVariantDisplayName(variant.name)}</h4>
                      <span className="traffic-badge">
                        {variant.traffic_percentage}% traffic
                      </span>
                    </div>
                    
                    {variant.config?.description && (
                      <p className="variant-description">
                        {variant.config.description}
                      </p>
                    )}
                    
                    <div className="variant-metrics">
                      <div className="metric-row">
                        <span className="metric-label">Total Users:</span>
                        <span className="metric-value">
                          {variant.metrics?.total_users || 0}
                        </span>
                      </div>
                      <div className="metric-row">
                        <span className="metric-label">Success Rate:</span>
                        <span className="metric-value">
                          {variant.metrics?.success_rate?.toFixed(1) || '0'}%
                        </span>
                      </div>
                      <div className="metric-row">
                        <span className="metric-label">Avg Time:</span>
                        <span className="metric-value">
                          {variant.metrics?.avg_completion_time?.toFixed(1) || '0'} hrs
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {testData.start_date && (
                <div className="test-metadata">
                  <p>Started: {new Date(testData.start_date).toLocaleDateString()}</p>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default ABTestResults;


/**
 * Session Monitor Component
 * 
 * Real-time session monitoring using ML anomaly detection
 * Provides continuous security analysis during user session
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import styled from 'styled-components';
import mlSecurityService from '../../services/mlSecurityService';
import { FaShieldAlt, FaExclamationTriangle, FaCheckCircle, FaInfoCircle } from 'react-icons/fa';

const MonitorContainer = styled.div`
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 16px;
  min-width: 300px;
  max-width: 400px;
  z-index: 1000;
  transition: all 0.3s ease;
  
  &:hover {
    box-shadow: 0 6px 30px rgba(0, 0, 0, 0.2);
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  
  h3 {
    margin: 0;
    font-size: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #333;
  }
`;

const StatusBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  background: ${props => {
    if (props.status === 'safe') return '#d4edda';
    if (props.status === 'warning') return '#fff3cd';
    if (props.status === 'danger') return '#f8d7da';
    return '#e2e3e5';
  }};
  color: ${props => {
    if (props.status === 'safe') return '#155724';
    if (props.status === 'warning') return '#856404';
    if (props.status === 'danger') return '#721c24';
    return '#383d41';
  }};
`;

const MetricsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 16px 0;
`;

const Metric = styled.div`
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 3px solid ${props => props.color || '#6c757d'};
  
  .label {
    font-size: 11px;
    text-transform: uppercase;
    color: #6c757d;
    margin-bottom: 4px;
    font-weight: 600;
  }
  
  .value {
    font-size: 20px;
    font-weight: 700;
    color: #333;
  }
`;

const AnalysisResult = styled.div`
  padding: 12px;
  background: ${props => {
    if (props.severity === 'critical' || props.severity === 'high') return '#f8d7da';
    if (props.severity === 'medium') return '#fff3cd';
    return '#d4edda';
  }};
  border-radius: 8px;
  margin-top: 12px;
  
  .title {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: ${props => {
      if (props.severity === 'critical' || props.severity === 'high') return '#721c24';
      if (props.severity === 'medium') return '#856404';
      return '#155724';
    }};
  }
  
  .details {
    font-size: 13px;
    color: #666;
    line-height: 1.5;
  }
  
  ul {
    margin: 8px 0 0 0;
    padding-left: 20px;
    font-size: 12px;
  }
`;

const Controls = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
  
  button {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    
    &.primary {
      background: #007bff;
      color: white;
      
      &:hover {
        background: #0056b3;
      }
    }
    
    &.secondary {
      background: #6c757d;
      color: white;
      
      &:hover {
        background: #545b62;
      }
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
`;

const MinimizeButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  color: #6c757d;
  padding: 4px 8px;
  
  &:hover {
    color: #333;
  }
`;

const SessionMonitor = ({ enabled = true, interval = 60000 }) => {
  const [isMinimized, setIsMinimized] = useState(false);
  const [monitoring, setMonitoring] = useState(enabled);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [threatLevel, setThreatLevel] = useState('safe');
  const [sessionMetrics, setSessionMetrics] = useState({
    anomalyScore: 0,
    sessionDuration: 0,
    activityCount: 0,
    lastCheck: null
  });
  
  const monitorIntervalRef = useRef(null);
  
  // Perform session analysis
  const analyzeSession = useCallback(async () => {
    try {
      // Collect session data
      const sessionData = mlSecurityService.collectSessionData();
      const behaviorData = mlSecurityService.collectBehaviorData();
      
      // Perform batch analysis
      const result = await mlSecurityService.batchAnalyzeSession({
        session_data: sessionData,
        behavior_data: behaviorData
      });
      
      // Update analysis results
      if (result.anomaly_detection) {
        setCurrentAnalysis(result.anomaly_detection);
        
        // Update threat level based on severity
        if (result.anomaly_detection.severity === 'critical' || result.anomaly_detection.severity === 'high') {
          setThreatLevel('danger');
        } else if (result.anomaly_detection.severity === 'medium') {
          setThreatLevel('warning');
        } else {
          setThreatLevel('safe');
        }
      }
      
      // Update metrics
      setSessionMetrics({
        anomalyScore: result.anomaly_detection?.anomaly_score || 0,
        sessionDuration: Math.floor(sessionData.session_duration / 60), // Convert to minutes
        activityCount: sessionData.vault_access_frequency || 0,
        lastCheck: new Date()
      });
      
      // Update behavior profile
      await mlSecurityService.updateBehaviorProfile(sessionData);
      
    } catch (error) {
      console.error('Session analysis error:', error);
    }
  }, []);
  
  // Start monitoring
  useEffect(() => {
    if (!monitoring) return;
    
    // Initial analysis
    analyzeSession();
    
    // Set up periodic analysis
    monitorIntervalRef.current = setInterval(() => {
      analyzeSession();
    }, interval);
    
    // Cleanup
    return () => {
      if (monitorIntervalRef.current) {
        clearInterval(monitorIntervalRef.current);
      }
    };
  }, [monitoring, interval, analyzeSession]);
  
  // Track user activity
  useEffect(() => {
    const updateActivity = () => {
      sessionStorage.setItem('last_activity', Date.now().toString());
    };
    
    // Track mouse movements, clicks, and key presses
    window.addEventListener('mousemove', updateActivity);
    window.addEventListener('click', updateActivity);
    window.addEventListener('keypress', updateActivity);
    
    return () => {
      window.removeEventListener('mousemove', updateActivity);
      window.removeEventListener('click', updateActivity);
      window.removeEventListener('keypress', updateActivity);
    };
  }, []);
  
  if (isMinimized) {
    return (
      <MonitorContainer style={{ padding: '12px', minWidth: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <StatusBadge status={threatLevel}>
            {threatLevel === 'safe' && <FaCheckCircle />}
            {threatLevel === 'warning' && <FaExclamationTriangle />}
            {threatLevel === 'danger' && <FaExclamationTriangle />}
            {threatLevel === 'safe' && 'Secure'}
            {threatLevel === 'warning' && 'Warning'}
            {threatLevel === 'danger' && 'Alert'}
          </StatusBadge>
          <MinimizeButton onClick={() => setIsMinimized(false)}>
            ↑
          </MinimizeButton>
        </div>
      </MonitorContainer>
    );
  }
  
  return (
    <MonitorContainer>
      <Header>
        <h3>
          <FaShieldAlt style={{ color: '#007bff' }} />
          Session Monitor
        </h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <StatusBadge status={threatLevel}>
            {threatLevel === 'safe' && <FaCheckCircle />}
            {threatLevel === 'warning' && <FaExclamationTriangle />}
            {threatLevel === 'danger' && <FaExclamationTriangle />}
            {threatLevel === 'safe' && 'Secure'}
            {threatLevel === 'warning' && 'Warning'}
            {threatLevel === 'danger' && 'Alert'}
          </StatusBadge>
          <MinimizeButton onClick={() => setIsMinimized(true)}>
            ↓
          </MinimizeButton>
        </div>
      </Header>
      
      <MetricsGrid>
        <Metric color={sessionMetrics.anomalyScore > 0.5 ? '#dc3545' : '#28a745'}>
          <div className="label">Anomaly Score</div>
          <div className="value">{(sessionMetrics.anomalyScore * 100).toFixed(0)}%</div>
        </Metric>
        <Metric color="#007bff">
          <div className="label">Session Time</div>
          <div className="value">{sessionMetrics.sessionDuration}m</div>
        </Metric>
      </MetricsGrid>
      
      {currentAnalysis && currentAnalysis.is_anomaly && (
        <AnalysisResult severity={currentAnalysis.severity}>
          <div className="title">
            <FaExclamationTriangle />
            Anomaly Detected
          </div>
          <div className="details">
            Severity: {currentAnalysis.severity.toUpperCase()}
            <br />
            Type: {currentAnalysis.anomaly_type || 'Multiple factors'}
            
            {currentAnalysis.contributing_factors && currentAnalysis.contributing_factors.length > 0 && (
              <ul>
                {currentAnalysis.contributing_factors.map((factor, idx) => (
                  <li key={idx}>{factor}</li>
                ))}
              </ul>
            )}
          </div>
        </AnalysisResult>
      )}
      
      {sessionMetrics.lastCheck && (
        <div style={{ fontSize: '11px', color: '#6c757d', marginTop: '12px', textAlign: 'center' }}>
          Last checked: {sessionMetrics.lastCheck.toLocaleTimeString()}
        </div>
      )}
      
      <Controls>
        <button
          className={monitoring ? 'secondary' : 'primary'}
          onClick={() => setMonitoring(!monitoring)}
        >
          {monitoring ? 'Pause' : 'Resume'}
        </button>
        <button
          className="primary"
          onClick={analyzeSession}
          disabled={!monitoring}
        >
          Analyze Now
        </button>
      </Controls>
      
      <div style={{ fontSize: '10px', color: '#6c757d', marginTop: '8px', textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
        <FaInfoCircle />
        Powered by ML Anomaly Detection
      </div>
    </MonitorContainer>
  );
};

export default SessionMonitor;


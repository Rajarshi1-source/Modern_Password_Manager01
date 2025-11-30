/**
 * Similarity Score Component
 * 
 * Displays behavioral similarity score with visual indicator
 */

import React from 'react';
import styled from 'styled-components';
import { FaCheckCircle, FaExclamationCircle, FaTimesCircle } from 'react-icons/fa';

const ScoreContainer = styled.div`
  background: ${props => 
    props.score >= 0.87 ? 'linear-gradient(135deg, #4caf50 0%, #45a049 100%)' :
    props.score >= 0.70 ? 'linear-gradient(135deg, #ff9800 0%, #f57c00 100%)' :
    'linear-gradient(135deg, #f44336 0%, #d32f2f 100%)'
  };
  color: white;
  padding: 24px;
  border-radius: 12px;
  text-align: center;
  position: relative;
  overflow: hidden;
`;

const ScoreValue = styled.div`
  font-size: 64px;
  font-weight: 700;
  margin-bottom: 8px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
`;

const ScoreLabel = styled.div`
  font-size: 16px;
  opacity: 0.95;
  margin-bottom: 16px;
`;

const ThresholdInfo = styled.div`
  font-size: 14px;
  opacity: 0.9;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  
  svg {
    font-size: 18px;
  }
`;

const ScoreBreakdown = styled.div`
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.3);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 16px;
`;

const BreakdownItem = styled.div`
  .value {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 4px;
  }
  
  .label {
    font-size: 12px;
    opacity: 0.9;
  }
`;

const SimilarityScore = ({ 
  overallScore, 
  threshold = 0.87, 
  breakdown = null 
}) => {
  const scorePercentage = (overallScore * 100).toFixed(1);
  const thresholdPercentage = (threshold * 100).toFixed(0);
  
  const passed = overallScore >= threshold;
  const close = overallScore >= (threshold - 0.10) && overallScore < threshold;
  
  const getStatusIcon = () => {
    if (passed) return <FaCheckCircle />;
    if (close) return <FaExclamationCircle />;
    return <FaTimesCircle />;
  };
  
  const getStatusText = () => {
    if (passed) return 'Threshold Met - Recovery Authorized';
    if (close) return `Close - ${((threshold - overallScore) * 100).toFixed(1)}% more needed`;
    return 'Below Threshold - Continue Challenges';
  };
  
  return (
    <ScoreContainer score={overallScore}>
      <ScoreValue>{scorePercentage}%</ScoreValue>
      <ScoreLabel>Behavioral Similarity Score</ScoreLabel>
      
      <ThresholdInfo>
        {getStatusIcon()}
        <span>{getStatusText()}</span>
      </ThresholdInfo>
      
      {breakdown && (
        <ScoreBreakdown>
          {breakdown.typing !== undefined && (
            <BreakdownItem>
              <div className="value">{(breakdown.typing * 100).toFixed(0)}%</div>
              <div className="label">Typing</div>
            </BreakdownItem>
          )}
          {breakdown.mouse !== undefined && (
            <BreakdownItem>
              <div className="value">{(breakdown.mouse * 100).toFixed(0)}%</div>
              <div className="label">Mouse</div>
            </BreakdownItem>
          )}
          {breakdown.cognitive !== undefined && (
            <BreakdownItem>
              <div className="value">{(breakdown.cognitive * 100).toFixed(0)}%</div>
              <div className="label">Cognitive</div>
            </BreakdownItem>
          )}
          {breakdown.navigation !== undefined && (
            <BreakdownItem>
              <div className="value">{(breakdown.navigation * 100).toFixed(0)}%</div>
              <div className="label">Navigation</div>
            </BreakdownItem>
          )}
        </ScoreBreakdown>
      )}
    </ScoreContainer>
  );
};

export default SimilarityScore;


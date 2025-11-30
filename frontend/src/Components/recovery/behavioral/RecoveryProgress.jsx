/**
 * Recovery Progress Component
 * 
 * Displays progress through the 5-day behavioral recovery process
 */

import React from 'react';
import styled from 'styled-components';
import { FaCheckCircle, FaClock, FaCircle } from 'react-icons/fa';

const ProgressContainer = styled.div`
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
`;

const ProgressHeader = styled.div`
  margin-bottom: 24px;
  
  h3 {
    margin: 0 0 8px 0;
    color: #333;
    font-size: 20px;
  }
  
  p {
    margin: 0;
    color: #999;
    font-size: 14px;
  }
`;

const Timeline = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 24px 0;
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 2px;
    background: #e0e0e0;
    z-index: 0;
  }
`;

const TimelineItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
  background: white;
  padding: 0 8px;
  
  .icon {
    font-size: 24px;
    color: ${props => 
      props.status === 'completed' ? '#4caf50' :
      props.status === 'in_progress' ? '#667eea' :
      '#ccc'
    };
  }
  
  .label {
    font-size: 12px;
    color: ${props => 
      props.status === 'completed' || props.status === 'in_progress' ? '#333' : '#999'
    };
    font-weight: ${props => props.status === 'in_progress' ? '600' : '400'};
    text-align: center;
  }
`;

const ProgressBarContainer = styled.div`
  margin: 24px 0;
`;

const ProgressBarTrack = styled.div`
  width: 100%;
  height: 12px;
  background: #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
`;

const ProgressBarFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  width: ${props => props.progress}%;
  transition: width 0.5s ease;
  border-radius: 6px;
`;

const ProgressText = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 14px;
  color: #666;
  
  .percentage {
    font-weight: 600;
    color: #667eea;
  }
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  margin-top: 24px;
`;

const StatCard = styled.div`
  background: #f9f9f9;
  padding: 16px;
  border-radius: 8px;
  text-align: center;
  
  .value {
    font-size: 28px;
    font-weight: 700;
    color: ${props => props.color || '#667eea'};
    margin-bottom: 4px;
  }
  
  .label {
    font-size: 13px;
    color: #999;
  }
`;

const SimilarityScore = styled.div`
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  border-radius: 12px;
  margin-top: 24px;
  text-align: center;
  
  .score {
    font-size: 48px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  
  .label {
    font-size: 14px;
    opacity: 0.9;
  }
  
  .threshold {
    font-size: 12px;
    opacity: 0.8;
    margin-top: 8px;
  }
`;

const RecoveryProgress = ({ recoveryAttempt }) => {
  if (!recoveryAttempt) return null;
  
  const progress = (recoveryAttempt.challenges_completed / recoveryAttempt.challenges_total) * 100;
  const daysCompleted = Math.floor(recoveryAttempt.challenges_completed / 4); // 4 challenges per day
  const similarityScore = recoveryAttempt.overall_similarity || 0;
  const threshold = 0.87;
  
  // Timeline days
  const days = [
    { day: 1, label: 'Day 1', status: daysCompleted >= 1 ? 'completed' : daysCompleted === 0 ? 'in_progress' : 'pending' },
    { day: 2, label: 'Day 2', status: daysCompleted >= 2 ? 'completed' : daysCompleted === 1 ? 'in_progress' : 'pending' },
    { day: 3, label: 'Day 3', status: daysCompleted >= 3 ? 'completed' : daysCompleted === 2 ? 'in_progress' : 'pending' },
    { day: 4, label: 'Day 4', status: daysCompleted >= 4 ? 'completed' : daysCompleted === 3 ? 'in_progress' : 'pending' },
    { day: 5, label: 'Day 5', status: daysCompleted >= 5 ? 'completed' : daysCompleted === 4 ? 'in_progress' : 'pending' }
  ];
  
  const getStatusIcon = (status) => {
    if (status === 'completed') return <FaCheckCircle className="icon" />;
    if (status === 'in_progress') return <FaClock className="icon" />;
    return <FaCircle className="icon" />;
  };
  
  // Calculate days remaining
  const expectedCompletionDate = new Date(recoveryAttempt.expected_completion_date);
  const daysRemaining = Math.ceil((expectedCompletionDate - new Date()) / (1000 * 60 * 60 * 24));
  
  return (
    <ProgressContainer>
      <ProgressHeader>
        <h3>Recovery Progress</h3>
        <p>Complete all challenges to reset your password</p>
      </ProgressHeader>
      
      <Timeline>
        {days.map((day, index) => (
          <TimelineItem key={index} status={day.status}>
            {getStatusIcon(day.status)}
            <span className="label">{day.label}</span>
          </TimelineItem>
        ))}
      </Timeline>
      
      <ProgressBarContainer>
        <ProgressBarTrack>
          <ProgressBarFill progress={progress} />
        </ProgressBarTrack>
        <ProgressText>
          <span>{recoveryAttempt.challenges_completed} of {recoveryAttempt.challenges_total} challenges completed</span>
          <span className="percentage">{Math.round(progress)}%</span>
        </ProgressText>
      </ProgressBarContainer>
      
      <StatsGrid>
        <StatCard>
          <div className="value">{daysCompleted}/5</div>
          <div className="label">Days Completed</div>
        </StatCard>
        <StatCard color={daysRemaining > 0 ? '#667eea' : '#f44336'}>
          <div className="value">{Math.max(0, daysRemaining)}</div>
          <div className="label">Days Remaining</div>
        </StatCard>
        <StatCard>
          <div className="value">{recoveryAttempt.challenges_completed}</div>
          <div className="label">Challenges Done</div>
        </StatCard>
      </StatsGrid>
      
      {similarityScore > 0 && (
        <SimilarityScore>
          <div className="score">{(similarityScore * 100).toFixed(1)}%</div>
          <div className="label">Behavioral Similarity Score</div>
          <div className="threshold">
            Threshold: {(threshold * 100).toFixed(0)}% 
            {similarityScore >= threshold && ' ✓ Passed'}
          </div>
        </SimilarityScore>
      )}
    </ProgressContainer>
  );
};

export default RecoveryProgress;


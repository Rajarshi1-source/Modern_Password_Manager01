/**
 * Cognitive Challenge Component
 * 
 * Presents cognitive pattern challenges during behavioral recovery
 * Tests semantic knowledge and decision-making patterns
 */

import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';
import { FaBrain, FaCheckCircle, FaArrowRight } from 'react-icons/fa';
import { CognitivePatterns } from '../../../services/behavioralCapture/CognitivePatterns';

const ChallengeContainer = styled.div`
  background: white;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
`;

const ChallengeHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  
  svg {
    font-size: 32px;
    color: #667eea;
  }
  
  h2 {
    margin: 0;
    color: #333;
    font-size: 24px;
  }
`;

const Question = styled.div`
  background: #f9f9f9;
  border-left: 4px solid #667eea;
  padding: 20px;
  margin-bottom: 24px;
  border-radius: 8px;
  
  p {
    margin: 0;
    font-size: 18px;
    color: #333;
    font-weight: 500;
  }
`;

const OptionsContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
`;

const OptionButton = styled.button`
  padding: 16px 20px;
  background: ${props => props.selected ? '#667eea' : 'white'};
  color: ${props => props.selected ? 'white' : '#333'};
  border: 2px solid ${props => props.selected ? '#667eea' : '#e0e0e0'};
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  text-align: left;
  transition: all 0.3s;
  
  &:hover {
    border-color: #667eea;
    background: ${props => props.selected ? '#667eea' : '#f5f5f5'};
  }
`;

const RangeInput = styled.input`
  width: 100%;
  height: 8px;
  border-radius: 4px;
  outline: none;
  -webkit-appearance: none;
  
  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #667eea;
    cursor: pointer;
  }
  
  &::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #667eea;
    cursor: pointer;
    border: none;
  }
`;

const RangeValue = styled.div`
  text-align: center;
  margin: 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #667eea;
`;

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 20px 0;
`;

const StatItem = styled.div`
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  
  .label {
    font-size: 11px;
    color: #999;
    margin-bottom: 4px;
  }
  
  .value {
    font-size: 18px;
    font-weight: 600;
    color: #333;
  }
`;

const Button = styled.button`
  padding: 14px 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
  transition: transform 0.2s;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const CognitiveChallenge = ({ challenge, onComplete, challengeNumber, totalChallenges }) => {
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [rangeValue, setRangeValue] = useState(50);
  const [decisionStartTime, setDecisionStartTime] = useState(null);
  const [stats, setStats] = useState({
    decisionTime: 0,
    interactions: 0
  });
  
  const cognitivePatternsRef = useRef(null);
  
  // Initialize cognitive patterns capture
  useEffect(() => {
    cognitivePatternsRef.current = new CognitivePatterns();
    cognitivePatternsRef.current.attach();
    setDecisionStartTime(Date.now());
    
    return () => {
      if (cognitivePatternsRef.current) {
        cognitivePatternsRef.current.detach();
      }
    };
  }, [challenge]);
  
  // Update decision time
  useEffect(() => {
    if (selectedAnswer !== null && decisionStartTime) {
      const decisionTime = (Date.now() - decisionStartTime) / 1000;
      setStats(prev => ({
        ...prev,
        decisionTime: decisionTime.toFixed(1)
      }));
    }
  }, [selectedAnswer, decisionStartTime]);
  
  const handleOptionClick = (option) => {
    setSelectedAnswer(option);
    setStats(prev => ({ ...prev, interactions: prev.interactions + 1 }));
  };
  
  const handleRangeChange = (e) => {
    setRangeValue(parseInt(e.target.value));
    setSelectedAnswer(e.target.value);
    setStats(prev => ({ ...prev, interactions: prev.interactions + 1 }));
  };
  
  const handleSubmit = async () => {
    if (selectedAnswer === null || !cognitivePatternsRef.current) return;
    
    // Collect behavioral data
    const behavioralData = await cognitivePatternsRef.current.getFeatures();
    
    const challengeResponse = {
      ...behavioralData,
      challenge_id: challenge.challenge_id,
      challenge_type: 'cognitive',
      completed: true,
      answer: selectedAnswer,
      decision_time: stats.decisionTime,
      interactions_count: stats.interactions,
      time_taken: Date.now() - decisionStartTime
    };
    
    // Reset
    cognitivePatternsRef.current.reset();
    setSelectedAnswer(null);
    setRangeValue(50);
    setDecisionStartTime(null);
    
    if (onComplete) {
      onComplete(challengeResponse);
    }
  };
  
  const questionData = challenge?.challenge_data || {};
  const questionType = questionData.question_type || 'multiple_choice';
  
  return (
    <ChallengeContainer>
      <ChallengeHeader>
        <FaBrain />
        <div>
          <h2>Cognitive Challenge {challengeNumber}/{totalChallenges}</h2>
          <p style={{ margin: 0, color: '#999', fontSize: '14px' }}>
            Answer the question based on your typical usage patterns
          </p>
        </div>
      </ChallengeHeader>
      
      <Question>
        <p>{questionData.question || 'Loading question...'}</p>
      </Question>
      
      {questionType === 'multiple_choice' && questionData.options && (
        <OptionsContainer>
          {questionData.options.map((option, index) => (
            <OptionButton
              key={index}
              selected={selectedAnswer === option}
              onClick={() => handleOptionClick(option)}
            >
              {option}
            </OptionButton>
          ))}
        </OptionsContainer>
      )}
      
      {questionType === 'range' && (
        <div style={{ margin: '24px 0' }}>
          <RangeValue>{rangeValue}</RangeValue>
          <RangeInput
            type="range"
            min={questionData.min || 0}
            max={questionData.max || 100}
            value={rangeValue}
            onChange={handleRangeChange}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '14px', color: '#999' }}>
            <span>{questionData.min || 0}</span>
            <span>{questionData.max || 100}</span>
          </div>
        </div>
      )}
      
      <Stats>
        <StatItem>
          <div className="label">Decision Time</div>
          <div className="value">{stats.decisionTime}s</div>
        </StatItem>
        <StatItem>
          <div className="label">Interactions</div>
          <div className="value">{stats.interactions}</div>
        </StatItem>
      </Stats>
      
      <Button onClick={handleSubmit} disabled={selectedAnswer === null}>
        {selectedAnswer !== null ? (
          <>
            Submit Answer
            <FaArrowRight />
          </>
        ) : (
          'Select an answer to continue'
        )}
      </Button>
    </ChallengeContainer>
  );
};

export default CognitiveChallenge;


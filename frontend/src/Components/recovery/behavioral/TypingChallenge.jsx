/**
 * Typing Challenge Component
 * 
 * Presents typing dynamics challenges during behavioral recovery
 * Captures real-time keystroke biometrics while user types
 */

import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';
import { FaKeyboard, FaCheckCircle, FaArrowRight } from 'react-icons/fa';
import { KeystrokeDynamics } from '../../../services/behavioralCapture/KeystrokeDynamics';

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

const Instruction = styled.p`
  color: #666;
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 24px;
`;

const SentenceDisplay = styled.div`
  background: #f5f5f5;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  font-size: 18px;
  font-family: 'Courier New', monospace;
  line-height: 1.8;
  color: #333;
  text-align: center;
`;

const TypingInput = styled.textarea`
  width: 100%;
  min-height: 120px;
  padding: 16px;
  border: 2px solid ${props => props.isCorrect === true ? '#4caf50' : props.isCorrect === false ? '#f44336' : '#e0e0e0'};
  border-radius: 8px;
  font-size: 16px;
  font-family: 'Courier New', monospace;
  resize: vertical;
  transition: border-color 0.3s;
  
  &:focus {
    outline: none;
    border-color: #667eea;
  }
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  margin: 20px 0;
  overflow: hidden;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  width: ${props => props.progress}%;
  transition: width 0.3s;
`;

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin: 20px 0;
`;

const StatItem = styled.div`
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  
  .label {
    font-size: 12px;
    color: #999;
    margin-bottom: 4px;
  }
  
  .value {
    font-size: 20px;
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

const TypingChallenge = ({ challenge, onComplete, challengeNumber, totalChallenges }) => {
  const [typedText, setTypedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [stats, setStats] = useState({
    wpm: 0,
    accuracy: 0,
    keystrokes: 0,
    errors: 0
  });
  
  const keystrokeDynamicsRef = useRef(null);
  const startTimeRef = useRef(null);
  
  // Initialize keystroke dynamics capture
  useEffect(() => {
    keystrokeDynamicsRef.current = new KeystrokeDynamics();
    keystrokeDynamicsRef.current.attach();
    startTimeRef.current = Date.now();
    
    return () => {
      if (keystrokeDynamicsRef.current) {
        keystrokeDynamicsRef.current.detach();
      }
    };
  }, [challenge]);
  
  // Update stats as user types
  useEffect(() => {
    if (!startTimeRef.current || !challenge) return;
    
    const elapsedMinutes = (Date.now() - startTimeRef.current) / 60000;
    const wordsTyped = typedText.trim().split(/\s+/).length;
    const wpm = elapsedMinutes > 0 ? Math.round(wordsTyped / elapsedMinutes) : 0;
    
    // Calculate accuracy
    const targetText = challenge.challenge_data?.sentence || '';
    let correct = 0;
    for (let i = 0; i < Math.min(typedText.length, targetText.length); i++) {
      if (typedText[i] === targetText[i]) {
        correct++;
      }
    }
    const accuracy = typedText.length > 0 
      ? Math.round((correct / typedText.length) * 100) 
      : 100;
    
    setStats({
      wpm,
      accuracy,
      keystrokes: typedText.length,
      errors: typedText.length - correct
    });
    
    // Check if typing is complete
    if (typedText === targetText) {
      setIsComplete(true);
    } else {
      setIsComplete(false);
    }
  }, [typedText, challenge]);
  
  const handleTextChange = (e) => {
    setTypedText(e.target.value);
  };
  
  const handleSubmit = async () => {
    if (!isComplete || !keystrokeDynamicsRef.current) {
      return;
    }
    
    // Collect behavioral data
    const behavioralData = await keystrokeDynamicsRef.current.getFeatures();
    
    // Include typed text metadata (not the text itself)
    const challengeResponse = {
      ...behavioralData,
      challenge_id: challenge.challenge_id,
      challenge_type: 'typing',
      completed: true,
      time_taken: Date.now() - startTimeRef.current,
      stats: stats
    };
    
    // Reset for next challenge
    keystrokeDynamicsRef.current.reset();
    setTypedText('');
    setIsComplete(false);
    
    // Call parent callback
    if (onComplete) {
      onComplete(challengeResponse);
    }
  };
  
  const targetSentence = challenge?.challenge_data?.sentence || 'Loading...';
  const progress = (typedText.length / targetSentence.length) * 100;
  
  return (
    <ChallengeContainer>
      <ChallengeHeader>
        <FaKeyboard />
        <div>
          <h2>Typing Challenge {challengeNumber}/{totalChallenges}</h2>
          <p style={{ margin: 0, color: '#999', fontSize: '14px' }}>
            Type the sentence below naturally, as you normally would
          </p>
        </div>
      </ChallengeHeader>
      
      <Instruction>
        {challenge?.challenge_data?.instruction || 'Type the following sentence naturally:'}
      </Instruction>
      
      <SentenceDisplay>
        {targetSentence}
      </SentenceDisplay>
      
      <TypingInput
        value={typedText}
        onChange={handleTextChange}
        placeholder="Start typing here..."
        autoFocus
        isCorrect={typedText === targetSentence ? true : typedText.length > 0 ? undefined : undefined}
      />
      
      <ProgressBar>
        <ProgressFill progress={Math.min(progress, 100)} />
      </ProgressBar>
      
      <Stats>
        <StatItem>
          <div className="label">Speed</div>
          <div className="value">{stats.wpm} WPM</div>
        </StatItem>
        <StatItem>
          <div className="label">Accuracy</div>
          <div className="value">{stats.accuracy}%</div>
        </StatItem>
        <StatItem>
          <div className="label">Keystrokes</div>
          <div className="value">{stats.keystrokes}</div>
        </StatItem>
        <StatItem>
          <div className="label">Errors</div>
          <div className="value">{stats.errors}</div>
        </StatItem>
      </Stats>
      
      {isComplete && (
        <div style={{ 
          background: '#e8f5e9', 
          color: '#2e7d32', 
          padding: '12px', 
          borderRadius: '8px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <FaCheckCircle />
          <span>Perfect! You've typed the sentence correctly.</span>
        </div>
      )}
      
      <Button onClick={handleSubmit} disabled={!isComplete}>
        {isComplete ? (
          <>
            Submit & Continue
            <FaArrowRight />
          </>
        ) : (
          'Complete typing to continue'
        )}
      </Button>
    </ChallengeContainer>
  );
};

export default TypingChallenge;


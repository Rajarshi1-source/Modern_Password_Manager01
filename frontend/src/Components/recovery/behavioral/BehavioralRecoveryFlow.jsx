/**
 * Behavioral Recovery Flow Component
 * 
 * Main orchestrator for the 5-day behavioral recovery process
 * Manages challenge sequence and progress tracking
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import axios from 'axios';
import { FaShieldAlt, FaCheckCircle } from 'react-icons/fa';

import TypingChallenge from './TypingChallenge';
import MouseChallenge from './MouseChallenge';
import CognitiveChallenge from './CognitiveChallenge';
import RecoveryProgress from './RecoveryProgress';
import SimilarityScore from './SimilarityScore';

const Container = styled.div`
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px;
`;

const Content = styled.div`
  max-width: 900px;
  margin: 0 auto;
`;

const Header = styled.div`
  text-align: center;
  color: white;
  margin-bottom: 40px;
  
  h1 {
    font-size: 36px;
    margin: 0 0 12px 0;
    font-weight: 700;
  }
  
  p {
    font-size: 18px;
    opacity: 0.95;
    margin: 0;
  }
`;

const Alert = styled.div`
  background: ${props => props.type === 'error' ? '#f44336' : props.type === 'success' ? '#4caf50' : '#2196f3'};
  color: white;
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
`;

const SuccessContainer = styled.div`
  background: white;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  
  svg {
    font-size: 72px;
    color: #4caf50;
    margin-bottom: 24px;
  }
  
  h2 {
    font-size: 32px;
    color: #333;
    margin: 0 0 16px 0;
  }
  
  p {
    color: #666;
    font-size: 16px;
    line-height: 1.6;
    margin-bottom: 32px;
  }
`;

const Button = styled.button`
  padding: 16px 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
  
  &:hover {
    transform: translateY(-2px);
  }
`;

const LoadingSpinner = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  
  .spinner {
    width: 50px;
    height: 50px;
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

// Use relative paths in development to leverage Vite proxy
const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

const BehavioralRecoveryFlow = ({ email, attemptId: initialAttemptId }) => {
  const navigate = useNavigate();
  
  const [attemptId, setAttemptId] = useState(initialAttemptId);
  const [recoveryAttempt, setRecoveryAttempt] = useState(null);
  const [currentChallenge, setCurrentChallenge] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [completed, setCompleted] = useState(false);
  
  // Initialize recovery or load existing attempt
  useEffect(() => {
    if (attemptId) {
      loadRecoveryStatus();
    } else if (email) {
      initiateRecovery();
    }
  }, []);
  
  /**
   * Initiate new behavioral recovery
   */
  const initiateRecovery = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API_URL}/api/behavioral-recovery/initiate/`, {
        email
      });
      
      if (response.data.success) {
        setAttemptId(response.data.data.attempt_id);
        setCurrentChallenge(response.data.data.first_challenge);
        setRecoveryAttempt({
          attempt_id: response.data.data.attempt_id,
          ...response.data.data.timeline,
          challenges_completed: 0,
          overall_similarity: 0
        });
      }
    } catch (err) {
      console.error('Error initiating recovery:', err);
      setError(err.response?.data?.message || 'Failed to initiate recovery');
    } finally {
      setLoading(false);
    }
  };
  
  /**
   * Load recovery attempt status
   */
  const loadRecoveryStatus = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.get(`${API_URL}/api/behavioral-recovery/status/${attemptId}/`);
      
      if (response.data.success) {
        setRecoveryAttempt(response.data.data);
        
        // Get next challenge
        await loadNextChallenge();
      }
    } catch (err) {
      console.error('Error loading recovery status:', err);
      setError('Failed to load recovery status');
    } finally {
      setLoading(false);
    }
  };
  
  /**
   * Load next challenge
   */
  const loadNextChallenge = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/behavioral-recovery/challenges/${attemptId}/next/`);
      
      if (response.data.success && response.data.data.challenge) {
        setCurrentChallenge(response.data.data.challenge);
      } else {
        // No more challenges - recovery complete or ready for completion
        setCurrentChallenge(null);
      }
    } catch (err) {
      console.error('Error loading next challenge:', err);
    }
  };
  
  /**
   * Handle challenge completion
   */
  const handleChallengeComplete = async (challengeResponse) => {
    setLoading(true);
    setError('');
    
    try {
      // Submit challenge response
      const response = await axios.post(`${API_URL}/api/behavioral-recovery/submit-challenge/`, {
        attempt_id: attemptId,
        challenge_id: currentChallenge.challenge_id,
        behavioral_data: challengeResponse
      });
      
      if (response.data.success) {
        // Update recovery attempt with new similarity scores
        setRecoveryAttempt(prev => ({
          ...prev,
          challenges_completed: prev.challenges_completed + 1,
          overall_similarity: response.data.data.overall_similarity
        }));
        
        // Load next challenge
        if (response.data.data.next_challenge) {
          setCurrentChallenge(response.data.data.next_challenge);
        } else {
          // All challenges completed
          setCurrentChallenge(null);
          
          // Check if similarity threshold met
          if (response.data.data.overall_similarity >= 0.87) {
            setCompleted(true);
          }
        }
      }
    } catch (err) {
      console.error('Error submitting challenge:', err);
      setError(err.response?.data?.message || 'Failed to submit challenge');
    } finally {
      setLoading(false);
    }
  };
  
  /**
   * Complete recovery with new password
   */
  const handleCompleteRecovery = () => {
    // Navigate to password reset page
    navigate('/password-recovery/finalize', {
      state: { attemptId, similarityScore: recoveryAttempt?.overall_similarity }
    });
  };
  
  // Render loading state
  if (loading && !recoveryAttempt) {
    return (
      <Container>
        <Content>
          <Header>
            <FaShieldAlt style={{ fontSize: '48px', marginBottom: '16px' }} />
            <h1>Behavioral Recovery</h1>
            <p>Initializing recovery process...</p>
          </Header>
          <LoadingSpinner>
            <div className="spinner" />
          </LoadingSpinner>
        </Content>
      </Container>
    );
  }
  
  // Render error state
  if (error) {
    return (
      <Container>
        <Content>
          <Alert type="error">
            {error}
          </Alert>
          <Button onClick={() => navigate('/password-recovery')}>
            Back to Recovery Options
          </Button>
        </Content>
      </Container>
    );
  }
  
  // Render completion state
  if (completed) {
    return (
      <Container>
        <Content>
          <SuccessContainer>
            <FaCheckCircle />
            <h2>Recovery Authorized!</h2>
            <p>
              Your behavioral similarity score of {(recoveryAttempt.overall_similarity * 100).toFixed(1)}%
              meets our security threshold. You can now reset your password.
            </p>
            <Button onClick={handleCompleteRecovery}>
              Reset Password Now
            </Button>
          </SuccessContainer>
        </Content>
      </Container>
    );
  }
  
  // Render active recovery flow
  return (
    <Container>
      <Content>
        <Header>
          <FaShieldAlt style={{ fontSize: '48px', marginBottom: '16px' }} />
          <h1>Behavioral Recovery</h1>
          <p>Verify your identity through behavioral patterns</p>
        </Header>
        
        {recoveryAttempt && (
          <RecoveryProgress recoveryAttempt={recoveryAttempt} />
        )}
        
        {recoveryAttempt && recoveryAttempt.overall_similarity > 0 && (
          <SimilarityScore 
            overallScore={recoveryAttempt.overall_similarity}
            breakdown={recoveryAttempt.similarity_scores}
          />
        )}
        
        {currentChallenge && (
          <>
            {currentChallenge.challenge_type === 'typing' && (
              <TypingChallenge
                challenge={currentChallenge}
                onComplete={handleChallengeComplete}
                challengeNumber={recoveryAttempt?.challenges_completed + 1 || 1}
                totalChallenges={recoveryAttempt?.challenges_total || 20}
              />
            )}
            
            {currentChallenge.challenge_type === 'mouse' && (
              <MouseChallenge
                challenge={currentChallenge}
                onComplete={handleChallengeComplete}
                challengeNumber={recoveryAttempt?.challenges_completed + 1 || 1}
                totalChallenges={recoveryAttempt?.challenges_total || 20}
              />
            )}
            
            {currentChallenge.challenge_type === 'cognitive' && (
              <CognitiveChallenge
                challenge={currentChallenge}
                onComplete={handleChallengeComplete}
                challengeNumber={recoveryAttempt?.challenges_completed + 1 || 1}
                totalChallenges={recoveryAttempt?.challenges_total || 20}
              />
            )}
          </>
        )}
        
        {!currentChallenge && recoveryAttempt && !completed && (
          <Alert type="info">
            All challenges completed for today. Return tomorrow to continue your recovery.
          </Alert>
        )}
      </Content>
    </Container>
  );
};

export default BehavioralRecoveryFlow;


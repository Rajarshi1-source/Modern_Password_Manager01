import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './TemporalChallengeResponse.css';

export const TemporalChallengeResponse = () => {
  const { challengeId } = useParams();
  const navigate = useNavigate();
  const [challenge, setChallenge] = useState(null);
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(null);
  
  useEffect(() => {
    fetchChallenge();
  }, [challengeId]);
  
  useEffect(() => {
    if (challenge && challenge.expires_at) {
      const timer = setInterval(() => {
        const now = new Date().getTime();
        const expiry = new Date(challenge.expires_at).getTime();
        const diff = expiry - now;
        
        if (diff <= 0) {
          setTimeRemaining('Expired');
          clearInterval(timer);
        } else {
          const hours = Math.floor(diff / (1000 * 60 * 60));
          const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
          setTimeRemaining(`${hours}h ${minutes}m remaining`);
        }
      }, 1000);
      
      return () => clearInterval(timer);
    }
  }, [challenge]);
  
  const fetchChallenge = async () => {
    try {
      const response = await fetch(`/api/auth/quantum-recovery/challenges/${challengeId}/`, {
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error('Challenge not found');
      }
      
      const data = await response.json();
      setChallenge({
        ...data,
        question: data.encrypted_challenge_data, // In production, this would be decrypted
        challenge_number: data.challenge_number || 1,
        total_challenges: data.total_challenges || 5
      });
    } catch (err) {
      console.error('Failed to fetch challenge:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    
    const startTime = new Date().getTime();
    
    try {
      const res = await fetch('/api/auth/quantum-recovery/respond_to_challenge/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          attempt_id: challenge.recovery_attempt_id,
          challenge_id: challengeId,
          user_response: response,
          response_time_seconds: Math.floor((new Date().getTime() - startTime) / 1000)
        })
      });
      
      const data = await res.json();
      
      setResult({
        correct: data.correct || false,
        trust_score: data.trust_score || 0,
        message: data.message || (data.correct ? 'Correct answer!' : 'Incorrect answer')
      });
      
      // Redirect to progress page after 3 seconds
      if (data.correct) {
        setTimeout(() => {
          navigate(`/recovery/progress/${challenge.recovery_attempt_id}`);
        }, 3000);
      }
    } catch (err) {
      setResult({ 
        correct: false, 
        error: err.message,
        message: 'Failed to submit response'
      });
    } finally {
      setSubmitting(false);
    }
  };
  
  if (loading) {
    return (
      <div className="challenge-loading">
        <div className="spinner-large"></div>
        <p>Loading challenge...</p>
      </div>
    );
  }
  
  if (!challenge) {
    return (
      <div className="challenge-error">
        <h2>❌ Challenge Not Found</h2>
        <p>This challenge may have expired or been completed.</p>
        <button onClick={() => navigate('/recovery')}>Return to Recovery</button>
      </div>
    );
  }
  
  return (
    <div className="challenge-response">
      <div className="challenge-header">
        <h1>🔐 Identity Verification Challenge</h1>
        <div className="challenge-progress">
          <span className="progress-text">
            Challenge {challenge.challenge_number} of {challenge.total_challenges}
          </span>
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: `${(challenge.challenge_number / challenge.total_challenges) * 100}%` }}
            ></div>
          </div>
        </div>
      </div>
      
      <div className="challenge-card">
        <div className="challenge-question-box">
          <h3>Your Challenge:</h3>
          <p className="challenge-question">{challenge.question}</p>
        </div>
        
        {!result && (
          <form onSubmit={handleSubmit} className="challenge-form">
            <div className="form-group">
              <label htmlFor="response">Your Answer:</label>
              <input
                id="response"
                type="text"
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                placeholder="Enter your answer"
                required
                disabled={submitting}
                autoFocus
              />
            </div>
            
            <button 
              type="submit" 
              disabled={submitting || !response.trim()}
              className="btn-submit"
            >
              {submitting ? (
                <>
                  <span className="spinner"></span>
                  Submitting...
                </>
              ) : (
                'Submit Answer'
              )}
            </button>
          </form>
        )}
        
        {result && (
          <div className={`result-box ${result.correct ? 'success' : 'error'}`}>
            <div className="result-icon">
              {result.correct ? '✅' : '❌'}
            </div>
            <h3>{result.message}</h3>
            {result.trust_score !== undefined && (
              <div className="trust-score">
                <span className="label">Trust Score:</span>
                <span className="score">{(result.trust_score * 100).toFixed(1)}%</span>
              </div>
            )}
            {result.correct && (
              <p className="redirect-notice">Redirecting to progress page...</p>
            )}
          </div>
        )}
        
        <div className="challenge-footer">
          {timeRemaining && (
            <div className="time-remaining">
              ⏰ {timeRemaining}
            </div>
          )}
          <div className="help-text">
            <p>Answer based on your actual account history and behavior</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TemporalChallengeResponse;


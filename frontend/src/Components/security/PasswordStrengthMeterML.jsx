/**
 * ML-Powered Password Strength Meter
 * 
 * Uses LSTM neural network to predict password strength in real-time
 * Provides detailed feedback and recommendations
 */

import React, { useState, useEffect, useMemo } from 'react';
import styled from 'styled-components';
import { debounce } from 'lodash';
import mlSecurityService from '../../services/mlSecurityService';

const Container = styled.div`
  margin-bottom: 20px;
`;

const StrengthBar = styled.div`
  height: 6px;
  background: ${props => props.theme?.backgroundSecondary || '#f0f0f0'};
  border-radius: 3px;
  margin-bottom: 8px;
  overflow: hidden;
  position: relative;
`;

const StrengthIndicator = styled.div`
  height: 100%;
  width: ${props => props.$strength}%;
  background: ${props => {
    if (props.$strengthLevel === 'very_weak') return '#dc3545';
    if (props.$strengthLevel === 'weak') return '#fd7e14';
    if (props.$strengthLevel === 'moderate') return '#ffc107';
    if (props.$strengthLevel === 'strong') return '#28a745';
    if (props.$strengthLevel === 'very_strong') return '#20c997';
    return '#6c757d';
  }};
  transition: width 0.3s ease, background-color 0.3s ease;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.3) 50%,
      transparent 100%
    );
    animation: shimmer 2s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
`;

const StrengthLabel = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  margin-bottom: 8px;
  
  .strength-text {
    font-weight: 600;
    color: ${props => {
      if (props.$strengthLevel === 'very_weak') return '#dc3545';
      if (props.$strengthLevel === 'weak') return '#fd7e14';
      if (props.$strengthLevel === 'moderate') return '#ffc107';
      if (props.$strengthLevel === 'strong') return '#28a745';
      if (props.$strengthLevel === 'very_strong') return '#20c997';
      return '#6c757d';
    }};
  }
  
  .confidence {
    font-size: 12px;
    color: ${props => props.theme?.textSecondary || '#6c757d'};
  }
`;

const FeatureGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
  margin: 12px 0;
`;

const Feature = styled.div`
  display: flex;
  align-items: center;
  font-size: 12px;
  color: ${props => props.met ? '#28a745' : '#6c757d'};
  
  .icon {
    margin-right: 6px;
    font-size: 14px;
  }
`;

const RecommendationsList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 12px 0 0 0;
  
  li {
    padding: 8px 12px;
    margin-bottom: 6px;
    background: ${props => props.theme?.backgroundSecondary || '#f8f9fa'};
    border-left: 3px solid #ffc107;
    border-radius: 4px;
    font-size: 13px;
    color: ${props => props.theme?.textPrimary || '#333'};
  }
`;

const LoadingIndicator = styled.div`
  font-size: 12px;
  color: ${props => props.theme?.textSecondary || '#6c757d'};
  font-style: italic;
  margin-top: 4px;
`;

const ErrorMessage = styled.div`
  font-size: 13px;
  color: #dc3545;
  margin-top: 8px;
  padding: 8px;
  background: #f8d7da;
  border-radius: 4px;
`;

const MLBadge = styled.span`
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 10px;
  margin-left: 8px;
  font-weight: 600;
`;

const PasswordStrengthMeterML = ({ password, showRecommendations = true, onStrengthChange }) => {
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Debounced prediction function
  const debouncedPredict = useMemo(
    () =>
      debounce(async (pwd) => {
        if (!pwd) {
          setPrediction(null);
          return;
        }
        
        setLoading(true);
        setError(null);
        
        try {
          const result = await mlSecurityService.predictPasswordStrength(pwd);
          setPrediction(result);
          
          // Notify parent component of strength change
          if (onStrengthChange) {
            onStrengthChange(result.strength, result.confidence);
          }
        } catch (err) {
          setError(err.message || 'Failed to analyze password');
          console.error('Password strength prediction error:', err);
        } finally {
          setLoading(false);
        }
      }, 500),
    [onStrengthChange]
  );
  
  // Effect to predict strength when password changes
  useEffect(() => {
    debouncedPredict(password);
    
    // Cleanup
    return () => {
      debouncedPredict.cancel();
    };
  }, [password, debouncedPredict]);
  
  // Calculate strength percentage for progress bar
  const strengthPercentage = useMemo(() => {
    if (!prediction) return 0;
    
    const strengthMap = {
      'very_weak': 20,
      'weak': 40,
      'moderate': 60,
      'strong': 80,
      'very_strong': 100
    };
    
    return strengthMap[prediction.strength] || 0;
  }, [prediction]);
  
  // Format strength label
  const strengthLabel = useMemo(() => {
    if (!prediction) return '';
    
    return prediction.strength
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }, [prediction]);
  
  // Don't render anything if no password
  if (!password) {
    return (
      <Container>
        <StrengthLabel>
          <span className="strength-text">Password Strength</span>
          <MLBadge>ML-Powered</MLBadge>
        </StrengthLabel>
        <StrengthBar>
          <StrengthIndicator $strength={0} $strengthLevel="none" />
        </StrengthBar>
      </Container>
    );
  }
  
  return (
    <Container>
      <StrengthLabel $strengthLevel={prediction?.strength}>
        <span className="strength-text">
          {loading ? 'Analyzing...' : strengthLabel || 'Password Strength'}
          <MLBadge>ML-Powered</MLBadge>
        </span>
        {prediction && !loading && (
          <span className="confidence">
            Confidence: {(prediction.confidence * 100).toFixed(0)}%
          </span>
        )}
      </StrengthLabel>
      
      <StrengthBar>
        <StrengthIndicator
          $strength={strengthPercentage}
          $strengthLevel={prediction?.strength}
        />
      </StrengthBar>
      
      {loading && <LoadingIndicator>Analyzing with neural network...</LoadingIndicator>}
      
      {error && <ErrorMessage>{error}</ErrorMessage>}
      
      {prediction && !loading && (
        <>
          {/* Feature Indicators */}
          <FeatureGrid>
            <Feature met={prediction.features.length >= 12}>
              <span className="icon">{prediction.features.length >= 12 ? '✓' : '○'}</span>
              Length: {prediction.features.length}
            </Feature>
            <Feature met={prediction.features.has_uppercase}>
              <span className="icon">{prediction.features.has_uppercase ? '✓' : '○'}</span>
              Uppercase
            </Feature>
            <Feature met={prediction.features.has_lowercase}>
              <span className="icon">{prediction.features.has_lowercase ? '✓' : '○'}</span>
              Lowercase
            </Feature>
            <Feature met={prediction.features.has_numbers}>
              <span className="icon">{prediction.features.has_numbers ? '✓' : '○'}</span>
              Numbers
            </Feature>
            <Feature met={prediction.features.has_special}>
              <span className="icon">{prediction.features.has_special ? '✓' : '○'}</span>
              Special Chars
            </Feature>
            <Feature met={!prediction.features.contains_common_patterns}>
              <span className="icon">{!prediction.features.contains_common_patterns ? '✓' : '○'}</span>
              No Patterns
            </Feature>
          </FeatureGrid>
          
          {/* Advanced Metrics */}
          <FeatureGrid>
            <Feature met={prediction.features.entropy > 60}>
              <span className="icon">🔐</span>
              Entropy: {prediction.features.entropy.toFixed(1)}
            </Feature>
            <Feature met={prediction.features.guessability_score < 30}>
              <span className="icon">🎯</span>
              Guessability: {prediction.features.guessability_score.toFixed(0)}%
            </Feature>
          </FeatureGrid>
          
          {/* Recommendations */}
          {showRecommendations && prediction.recommendations && prediction.recommendations.length > 0 && (
            <RecommendationsList>
              {prediction.recommendations.map((rec, idx) => (
                <li key={idx}>{rec}</li>
              ))}
            </RecommendationsList>
          )}
        </>
      )}
    </Container>
  );
};

export default PasswordStrengthMeterML;


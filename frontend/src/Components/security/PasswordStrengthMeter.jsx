import React, { useMemo } from 'react';
import styled from 'styled-components';

const Container = styled.div`
  margin-bottom: 20px;
`;

const StrengthBar = styled.div`
  height: 4px;
  background: ${props => props.theme.backgroundSecondary};
  border-radius: 2px;
  margin-bottom: 4px;
  overflow: hidden;
`;

const StrengthIndicator = styled.div`
  height: 100%;
  width: ${props => props.$strength}%;
  background: ${props => {
    if (props.$strength < 30) return props.theme.danger;
    if (props.$strength < 60) return props.theme.warning;
    return props.theme.success;
  }};
  transition: width 0.3s ease;
`;

const StrengthLabel = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  
  span:first-child {
    color: ${props => {
      if (props.$strength < 30) return props.theme.danger;
      if (props.$strength < 60) return props.theme.warning;
      return props.theme.success;
    }};
    font-weight: 500;
  }
  
  span:last-child {
    color: ${props => props.theme.textSecondary};
  }
`;

const PasswordStrengthMeter = ({ password }) => {
  // Calculate password strength
  const { strength, label, suggestion } = useMemo(() => {
    // No password
    if (!password) {
      return { strength: 0, label: 'None', suggestion: 'Enter a password' };
    }
    
    let score = 0;
    
    // Length
    score += Math.min(password.length * 4, 40);
    
    // Character variety
    if (/[A-Z]/.test(password)) score += 10;
    if (/[a-z]/.test(password)) score += 10;
    if (/[0-9]/.test(password)) score += 10;
    if (/[^A-Za-z0-9]/.test(password)) score += 15;
    
    // Repeating characters and patterns decrease score
    const repeats = password.length - new Set(password).size;
    score -= repeats * 2;
    
    // Sequential characters decrease score
    let sequential = 0;
    for (let i = 0; i < password.length - 1; i++) {
      if (password.charCodeAt(i + 1) - password.charCodeAt(i) === 1) {
        sequential++;
      }
    }
    score -= sequential * 2;
    
    // Normalize score between 0-100
    const normalizedScore = Math.max(0, Math.min(100, score));
    
    // Determine label and suggestion
    let label, suggestion;
    if (normalizedScore < 30) {
      label = 'Weak';
      suggestion = 'Add more characters and mix character types';
    } else if (normalizedScore < 60) {
      label = 'Moderate';
      suggestion = 'Add special characters or increase length';
    } else if (normalizedScore < 80) {
      label = 'Strong';
      suggestion = 'Good password, consider adding more variety';
    } else {
      label = 'Very Strong';
      suggestion = 'Excellent password!';
    }
    
    return { strength: normalizedScore, label, suggestion };
  }, [password]);
  
  return (
    <Container>
      <StrengthBar>
        <StrengthIndicator $strength={strength} />
      </StrengthBar>
      <StrengthLabel $strength={strength}>
        <span>{label}</span>
        <span>{suggestion}</span>
      </StrengthLabel>
    </Container>
  );
};

export default PasswordStrengthMeter;

import React from 'react';
import styled, { keyframes } from 'styled-components';

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
`;

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: ${props => props.$inline ? '0' : '20px'};
  width: ${props => props.$inline ? 'auto' : '100%'};
`;

const Spinner = styled.div`
  width: ${props => props.size}px;
  height: ${props => props.size}px;
  border: ${props => Math.max(2, props.size / 10)}px solid ${props => props.theme.bgLight};
  border-top: ${props => Math.max(2, props.size / 10)}px solid ${props => props.theme.primary};
  border-radius: 50%;
  animation: ${spin} 1s linear infinite;
`;

const LoadingText = styled.div`
  margin-top: 12px;
  color: ${props => props.theme.textSecondary};
  font-size: 14px;
  font-weight: 500;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

// Screen reader only text
const SROnly = styled.span`
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
`;

const LoadingIndicator = ({ 
  size = 40,
  text,
  inline = false,
  ariaLabel = 'Loading content',
  ...props
}) => {
  return (
    <Container 
      role="status" 
      aria-live="polite"
      aria-label={ariaLabel}
      $inline={inline}
      {...props}
    >
      <Spinner size={size} />
      {text && <LoadingText>{text}</LoadingText>}
      <SROnly>Loading...</SROnly>
    </Container>
  );
};

export default LoadingIndicator;

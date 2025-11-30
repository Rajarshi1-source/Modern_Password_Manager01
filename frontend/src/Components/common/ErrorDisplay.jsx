import React from 'react';
import styled from 'styled-components';
import { FaExclamationTriangle } from 'react-icons/fa';

const Container = styled.div`
  background-color: ${props => props.theme.errorLight};
  border-radius: 6px;
  padding: 12px 16px;
  margin: 16px 0;
  border-left: 4px solid ${props => props.theme.error};
  display: flex;
  align-items: center;
  gap: 12px;
  
  animation: slideIn 0.3s ease-out;
  
  @keyframes slideIn {
    from {
      transform: translateY(-10px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const IconContainer = styled.div`
  color: ${props => props.theme.error};
  font-size: 18px;
`;

const MessageContainer = styled.div`
  flex: 1;
`;

const Title = styled.div`
  font-weight: 500;
  margin-bottom: 4px;
  color: ${props => props.theme.error};
`;

const Message = styled.div`
  color: ${props => props.theme.textPrimary};
  font-size: 14px;
`;

const Button = styled.button`
  background-color: transparent;
  border: 1px solid ${props => props.theme.error};
  color: ${props => props.theme.error};
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  
  &:hover {
    background-color: ${props => props.theme.error};
    color: white;
  }
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.error};
    outline-offset: 2px;
  }
`;

const ErrorDisplay = ({ 
  title = 'An error occurred', 
  message, 
  onRetry,
  ...props
}) => {
  return (
    <Container role="alert" {...props}>
      <IconContainer>
        <FaExclamationTriangle />
      </IconContainer>
      <MessageContainer>
        <Title>{title}</Title>
        {message && <Message>{message}</Message>}
      </MessageContainer>
      {onRetry && (
        <Button 
          onClick={onRetry}
          aria-label="Retry action"
        >
          Retry
        </Button>
      )}
    </Container>
  );
};

export default ErrorDisplay;

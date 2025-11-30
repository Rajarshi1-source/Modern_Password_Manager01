import React from 'react';
import styled from 'styled-components';
import { FaExclamationTriangle, FaSync } from 'react-icons/fa';

const ErrorContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px 20px;
  text-align: center;
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 8px;
  margin: 20px;
`;

const ErrorIcon = styled.div`
  font-size: 4rem;
  color: ${props => props.theme.danger || '#dc3545'};
  margin-bottom: 24px;
`;

const ErrorTitle = styled.h2`
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 16px;
  color: ${props => props.theme.textPrimary || '#333'};
`;

const ErrorMessage = styled.p`
  font-size: 1rem;
  color: ${props => props.theme.textSecondary || '#666'};
  margin-bottom: 32px;
  max-width: 500px;
  line-height: 1.5;
`;

const ActionButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: ${props => props.theme.primary || '#007bff'};
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.theme.primaryDark || '#0056b3'};
    transform: translateY(-1px);
  }
  
  &:active {
    transform: translateY(0);
  }
`;

const ErrorDetails = styled.details`
  margin-top: 24px;
  max-width: 600px;
  
  summary {
    cursor: pointer;
    font-weight: 500;
    color: ${props => props.theme.textSecondary || '#666'};
    margin-bottom: 12px;
  }
  
  pre {
    background: ${props => props.theme.backgroundPrimary || '#f1f3f4'};
    padding: 16px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.875rem;
    text-align: left;
  }
`;

const ErrorFallback = ({ error, resetError }) => {
  const handleReportError = () => {
    // In a real app, send error to monitoring service
    console.error('User reported error:', error);
    
    // You could also copy error details to clipboard
    if (navigator.clipboard) {
      navigator.clipboard.writeText(error.stack || error.message);
    }
  };

  return (
    <ErrorContainer>
      <ErrorIcon>
        <FaExclamationTriangle />
      </ErrorIcon>
      
      <ErrorTitle>Something went wrong</ErrorTitle>
      
      <ErrorMessage>
        We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
      </ErrorMessage>
      
      <ActionButton onClick={resetError}>
        <FaSync />
        Try Again
      </ActionButton>
      
      {process.env.NODE_ENV === 'development' && error && (
        <ErrorDetails>
          <summary>Error Details (Development Only)</summary>
          <pre>{error.stack || error.message}</pre>
        </ErrorDetails>
      )}
    </ErrorContainer>
  );
};

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorInfo: null 
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { 
      hasError: true,
      error 
    };
  }

  componentDidCatch(error, errorInfo) {
    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error caught by boundary:', error, errorInfo);
    }
    
    // In production, send to error reporting service
    if (process.env.NODE_ENV === 'production') {
      // Example: Send to Sentry, LogRocket, etc.
      this.reportError(error, errorInfo);
    }
    
    this.setState({
      error,
      errorInfo
    });
  }

  reportError = (error, errorInfo) => {
    // Send error to monitoring service
    // This is where you'd integrate with services like:
    // - Sentry: Sentry.captureException(error)
    // - LogRocket: LogRocket.captureException(error)
    // - Custom analytics
    
    console.error('Error reported to monitoring service:', {
      error: error.toString(),
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href
    });
  };

  resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback 
          error={this.state.error}
          resetError={this.resetError}
        />
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
export { ErrorFallback };

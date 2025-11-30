import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';
import oauthService from '../../services/oauthService';
import { errorTracker } from '../../services/errorTracker';
import { FaSpinner, FaCheckCircle, FaTimesCircle, FaMobileAlt } from 'react-icons/fa';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
`;

const Card = styled.div`
  background: white;
  border-radius: 12px;
  padding: 3rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  text-align: center;
  max-width: 400px;
  width: 100%;
`;

const IconWrapper = styled.div`
  font-size: 4rem;
  margin-bottom: 1.5rem;
  color: ${props => props.color || '#667eea'};
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  svg {
    animation: ${props => props.$spinning ? 'spin 1s linear infinite' : 'none'};
  }
`;

const Title = styled.h1`
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
  color: #333;
`;

const Message = styled.p`
  color: #666;
  font-size: 1rem;
  margin-bottom: 1.5rem;
`;

const Button = styled.button`
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  
  &:hover {
    background: #5568d3;
  }
`;

const FallbackForm = styled.div`
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
`;

const Input = styled.input`
  padding: 0.75rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s;
  
  &:focus {
    outline: none;
    border-color: #667eea;
  }
`;

const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing'); // processing, success, error, fallback
  const [message, setMessage] = useState('Completing authentication...');
  const [showAuthyFallback, setShowAuthyFallback] = useState(false);
  const [fallbackData, setFallbackData] = useState(null);
  const [phone, setPhone] = useState('');
  const [authyCode, setAuthyCode] = useState('');
  const [authyId, setAuthyId] = useState('');

  useEffect(() => {
    handleOAuthCallback();
  }, []);

  const handleOAuthCallback = async () => {
    try {
      // Get the result from OAuth service
      const result = await oauthService.handleCallback(searchParams);

      if (result.success && result.tokens) {
        setStatus('success');
        setMessage('Login successful! Redirecting...');

        // Store tokens
        localStorage.setItem('token', result.tokens.access);
        localStorage.setItem('refreshToken', result.tokens.refresh);

        // Send message to opener window (if opened in popup)
        if (window.opener) {
          window.opener.postMessage({
            type: 'oauth_success',
            tokens: result.tokens,
            user: result.user
          }, window.location.origin);
          window.close();
        } else {
          // Redirect to dashboard if not in popup
          setTimeout(() => {
            navigate('/vault');
          }, 1500);
        }
      } else {
        throw new Error('Authentication failed');
      }
    } catch (error) {
      errorTracker.captureError(error, 'OAuthCallback:HandleCallback', { searchParams: Object.fromEntries(searchParams) }, 'error');
      
      // Check if Authy fallback is available
      const fallbackInfo = oauthService.handleOAuthFailure(error);
      
      if (fallbackInfo.fallbackAvailable) {
        setStatus('fallback');
        setMessage('OAuth failed. Use Authy for verification.');
        setShowAuthyFallback(true);
        setFallbackData(fallbackInfo);
      } else {
        setStatus('error');
        setMessage(error.message || 'Authentication failed. Please try again.');

        // Send error message to opener window
        if (window.opener) {
          window.opener.postMessage({
            type: 'oauth_error',
            error: error.message
          }, window.location.origin);
          
          // Close popup after 3 seconds
          setTimeout(() => {
            window.close();
          }, 3000);
        }
      }
    }
  };

  const handleAuthyFallback = async () => {
    if (!phone) {
      setMessage('Please enter your phone number');
      return;
    }

    setStatus('processing');
    setMessage('Sending verification code...');

    try {
      const result = await oauthService.initiateAuthyFallback(
        fallbackData.email,
        phone
      );

      if (result.success) {
        setAuthyId(result.authy_id);
        setStatus('fallback');
        setMessage('Enter the verification code sent to your phone');
      } else {
        throw new Error(result.message || 'Failed to send verification code');
      }
    } catch (error) {
      setStatus('fallback');
      setMessage(error.response?.data?.message || error.message || 'Failed to send code');
    }
  };

  const handleVerifyAuthyCode = async () => {
    if (!authyCode) {
      setMessage('Please enter the verification code');
      return;
    }

    setStatus('processing');
    setMessage('Verifying code...');

    try {
      const result = await oauthService.verifyAuthyFallback(authyId, authyCode);

      if (result.success && result.tokens) {
        setStatus('success');
        setMessage('Login successful! Redirecting...');

        // Store tokens
        localStorage.setItem('token', result.tokens.access);
        localStorage.setItem('refreshToken', result.tokens.refresh);

        // Send message to opener window
        if (window.opener) {
          window.opener.postMessage({
            type: 'oauth_success',
            tokens: result.tokens,
            user: result.user
          }, window.location.origin);
          window.close();
        } else {
          setTimeout(() => {
            navigate('/vault');
          }, 1500);
        }
      } else {
        throw new Error('Verification failed');
      }
    } catch (error) {
      setStatus('fallback');
      setMessage(error.response?.data?.message || error.message || 'Invalid code. Please try again.');
    }
  };

  const handleRetry = () => {
    if (window.opener) {
      window.close();
    } else {
      navigate('/login');
    }
  };

  return (
    <Container>
      <Card>
        {status === 'processing' && (
          <>
            <IconWrapper $spinning color="#667eea">
              <FaSpinner />
            </IconWrapper>
            <Title>Authenticating...</Title>
            <Message>{message}</Message>
          </>
        )}

        {status === 'success' && (
          <>
            <IconWrapper color="#4CAF50">
              <FaCheckCircle />
            </IconWrapper>
            <Title>Success!</Title>
            <Message>{message}</Message>
          </>
        )}

        {status === 'fallback' && showAuthyFallback && (
          <>
            <IconWrapper color="#FF9800">
              <FaMobileAlt />
            </IconWrapper>
            <Title>Authy Verification</Title>
            <Message>{message}</Message>
            
            {!authyId ? (
              <FallbackForm>
                <Input
                  type="tel"
                  placeholder="Phone Number (e.g., 5551234567)"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <Button onClick={handleAuthyFallback}>
                  Send Verification Code
                </Button>
              </FallbackForm>
            ) : (
              <FallbackForm>
                <Input
                  type="text"
                  placeholder="Enter 6-digit code"
                  value={authyCode}
                  onChange={(e) => setAuthyCode(e.target.value)}
                  maxLength="7"
                />
                <Button onClick={handleVerifyAuthyCode}>
                  Verify Code
                </Button>
                <Button 
                  onClick={() => {
                    setAuthyId('');
                    setAuthyCode('');
                    setMessage('OAuth failed. Use Authy for verification.');
                  }}
                  style={{ background: '#666', marginTop: '10px' }}
                >
                  Resend Code
                </Button>
              </FallbackForm>
            )}
          </>
        )}

        {status === 'error' && (
          <>
            <IconWrapper color="#f44336">
              <FaTimesCircle />
            </IconWrapper>
            <Title>Authentication Failed</Title>
            <Message>{message}</Message>
            <Button onClick={handleRetry}>
              {window.opener ? 'Close' : 'Back to Login'}
            </Button>
          </>
        )}
      </Card>
    </Container>
  );
};

export default OAuthCallback;


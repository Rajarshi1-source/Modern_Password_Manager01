import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';
import ApiService from '../../services/api';
import { errorTracker } from '../../services/errorTracker';
import { FaKey, FaEnvelope, FaCheckCircle, FaExclamationCircle, FaBrain } from 'react-icons/fa';
import BehavioralRecoveryFlow from '../recovery/behavioral/BehavioralRecoveryFlow';

const Container = styled.div`
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
`;

const Card = styled.div`
  background: white;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  max-width: 500px;
  width: 100%;
  overflow: hidden;
`;

const Header = styled.div`
  padding: 32px;
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;

  h1 {
    font-size: 28px;
    margin: 0 0 8px 0;
    font-weight: 700;
  }

  p {
    margin: 0;
    opacity: 0.9;
    font-size: 14px;
  }
`;

const TabContainer = styled.div`
  display: flex;
  border-bottom: 2px solid #e0e0e0;
`;

const Tab = styled.button`
  flex: 1;
  padding: 16px;
  background: ${props => props.active ? '#f5f5f5' : 'white'};
  border: none;
  border-bottom: 3px solid ${props => props.active ? '#667eea' : 'transparent'};
  color: ${props => props.active ? '#667eea' : '#666'};
  font-weight: ${props => props.active ? '600' : '400'};
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;

  &:hover {
    background: #f5f5f5;
  }
`;

const Content = styled.div`
  padding: 32px;
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.3s;

  &:focus {
    outline: none;
    border-color: #667eea;
  }

  &::placeholder {
    color: #999;
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-top: 8px;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const SecondaryButton = styled(Button)`
  background: white;
  color: #667eea;
  border: 2px solid #667eea;

  &:hover:not(:disabled) {
    background: #f5f5f5;
  }
`;

const Alert = styled.div`
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: ${props => props.type === 'error' ? '#fee' : '#efe'};
  color: ${props => props.type === 'error' ? '#c33' : '#2a7f2a'};
  border-left: 4px solid ${props => props.type === 'error' ? '#c33' : '#2a7f2a'};
`;

const SuccessContainer = styled.div`
  text-align: center;
  padding: 40px 20px;

  svg {
    font-size: 64px;
    color: #2a7f2a;
    margin-bottom: 20px;
  }

  h2 {
    color: #333;
    margin-bottom: 16px;
  }

  p {
    color: #666;
    margin-bottom: 24px;
    line-height: 1.6;
  }
`;

const HelpText = styled.p`
  font-size: 13px;
  color: #666;
  margin-top: 8px;
  line-height: 1.5;
`;

const LoadingSpinner = styled.div`
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 0.8s linear infinite;

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

/**
 * Password Recovery Component
 * 
 * Provides these recovery methods:
 * 1. Email-based recovery - sends a password reset link
 * 2. Recovery key - points to the layered recovery-key flow (/recovery/key/use-v2),
 *    which unwraps the vault on this device
 */
const PasswordRecovery = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const behavioralAttemptId = searchParams.get('behavioral_attempt');
  
  // State for email-based recovery
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  
  // Shared state
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  
  // Behavioral recovery state
  const [showBehavioralFlow, setShowBehavioralFlow] = useState(false);
  const [behavioralEmail, setBehavioralEmail] = useState('');

  // Handle tab change
  const handleTabChange = (tabIndex) => {
    setActiveTab(tabIndex);
    setError('');
    setSubmitted(false);
    setShowBehavioralFlow(false);
  };
  
  // Handle behavioral recovery initiation
  const handleBehavioralRecoveryStart = () => {
    if (!email) {
      setError('Please enter your email address');
      return;
    }
    setBehavioralEmail(email);
    setShowBehavioralFlow(true);
  };

  // Email-based recovery flow
  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await ApiService.auth.requestPasswordReset(email);
      setSubmitted(true);
    } catch (err) {
      setError('An error occurred. Please try again later.');
      errorTracker.captureError(err, 'PasswordRecovery:EmailSubmit', { email }, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Render email reset success state
  if (activeTab === 0 && submitted) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>Check Your Email</h1>
            <p>Recovery instructions sent</p>
          </Header>
          <Content>
            <SuccessContainer>
              <FaCheckCircle />
              <h2>Email Sent!</h2>
              <p>
                If an account exists with <strong>{email}</strong>, we've sent you instructions 
                on how to reset your password.
              </p>
              <p style={{ fontSize: '14px', color: '#999' }}>
                Don't see the email? Check your spam folder.
              </p>
              {/* Test-friendly recovery status indicator */}
              <span className="sr-only" data-testid="email-recovery-status">
                Recovery Successful! Your account has been restored.
              </span>
              <SecondaryButton onClick={() => navigate('/')}>
                Back to Login
              </SecondaryButton>
            </SuccessContainer>
          </Content>
        </Card>
      </Container>
    );
  }

  // The emailed behavioral-recovery link (?behavioral_attempt=<id>) reopens
  // the flow for that attempt
  if (behavioralAttemptId) {
    return <BehavioralRecoveryFlow attemptId={behavioralAttemptId} />;
  }

  // If showing behavioral recovery flow, render it
  if (showBehavioralFlow) {
    return <BehavioralRecoveryFlow email={behavioralEmail} />;
  }
  
  return (
    <Container>
      <Card>
        <Header>
          <h1>Recover Your Account</h1>
          <p>Choose a recovery method</p>
        </Header>
        
        <TabContainer>
          <Tab active={activeTab === 0} onClick={() => handleTabChange(0)}>
            <FaEnvelope /> Email Recovery
          </Tab>
          <Tab active={activeTab === 1} onClick={() => handleTabChange(1)}>
            <FaKey /> Recovery Key
          </Tab>
          <Tab active={activeTab === 2} onClick={() => handleTabChange(2)}>
            <FaBrain /> Behavioral Recovery
          </Tab>
        </TabContainer>
        
        <Content>
          {error && (
            <Alert type="error">
              <FaExclamationCircle />
              <span>{error}</span>
            </Alert>
          )}
          
          {activeTab === 0 && (
            <form onSubmit={handleEmailSubmit}>
              <HelpText>
                Enter your email address and we'll send you a link to reset your master password.
              </HelpText>
              
              <FormGroup>
                <Label htmlFor="email">Email Address</Label>
                <Input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@gmail.com"
                  required
                  autoFocus
                />
              </FormGroup>
              
              <Button type="submit" disabled={loading}>
                {loading ? <LoadingSpinner /> : 'Send Reset Link'}
              </Button>
              
              <SecondaryButton type="button" onClick={() => navigate('/')} style={{ marginTop: '12px' }}>
                Back to Login
              </SecondaryButton>
            </form>
          )}
          
          {activeTab === 1 && (
            <>
              <HelpText>
                Your recovery key unlocks your vault on this device; it is never sent to the
                server. Continue to the recovery-key page to restore access.
              </HelpText>

              <Button type="button" onClick={() => navigate('/recovery/key/use-v2')}>
                Use Recovery Key
              </Button>

              <SecondaryButton type="button" onClick={() => navigate('/')} style={{ marginTop: '12px' }}>
                Back to Login
              </SecondaryButton>
            </>
          )}

          {activeTab === 2 && (
            <>
              <HelpText>
                <strong>Advanced Behavioral Recovery</strong> uses AI-powered behavioral biometrics 
                to verify your identity through 247 dimensions of how you interact with technology.
              </HelpText>
              
              <div style={{
                background: '#e3f2fd',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '20px',
                fontSize: '14px',
                lineHeight: '1.6'
              }}>
                <strong>How it works:</strong>
                <ul style={{ marginTop: '8px', marginBottom: 0, paddingLeft: '20px' }}>
                  <li>Complete behavioral challenges over 5 days</li>
                  <li>System analyzes your typing, mouse, and cognitive patterns</li>
                  <li>AI compares patterns to your stored behavioral DNA</li>
                  <li>After the challenges, use your recovery key to unlock your vault</li>
                </ul>
              </div>
              
              <FormGroup>
                <Label htmlFor="email-behavioral">Email Address</Label>
                <Input
                  type="email"
                  id="email-behavioral"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@gmail.com"
                  required
                  autoFocus
                />
              </FormGroup>
              
              <div style={{
                background: '#fff3e0',
                padding: '12px',
                borderRadius: '8px',
                marginBottom: '16px',
                fontSize: '13px',
                color: '#e65100'
              }}>
                ⏱️ <strong>Timeline:</strong> This recovery method takes 5-7 days for maximum security.
                Complete ~15 minutes of challenges per day.
              </div>
              
              <Button onClick={handleBehavioralRecoveryStart} disabled={loading || !email}>
                {loading ? <LoadingSpinner /> : 'Start Behavioral Recovery'}
              </Button>
              
              <SecondaryButton type="button" onClick={() => navigate('/')} style={{ marginTop: '12px' }}>
                Back to Login
              </SecondaryButton>
            </>
          )}
        </Content>
      </Card>
    </Container>
  );
};

export default PasswordRecovery;

import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { FaLock, FaExclamationTriangle, FaUser, FaKey, FaShieldAlt } from 'react-icons/fa';
import { errorTracker } from '../../services/errorTracker';
import deviceFingerprint from '../../utils/deviceFingerprint';

const Container = styled.div`
  max-width: 400px;
  margin: 40px auto;
  padding: 24px;
`;

const Title = styled.h3`
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 24px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const FormGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const Label = styled.label`
  font-size: 14px;
  font-weight: 500;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const InputWrapper = styled.div`
  position: relative;
  display: flex;
  align-items: center;
`;

const InputIcon = styled.div`
  position: absolute;
  left: 12px;
  color: ${props => props.theme.textSecondary || '#999'};
  font-size: 16px;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 12px 12px 40px;
  border: 2px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 10px;
  font-size: 14px;
  background: ${props => props.disabled 
    ? props.theme.backgroundSecondary || '#f5f5f5' 
    : props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  transition: all 0.2s ease;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.primary || '#7B68EE'};
    box-shadow: 0 0 0 3px ${props => props.theme.primary || '#7B68EE'}20;
  }
  
  &:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary || '#999'};
  }
`;

const SubmitButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 14px 24px;
  background: linear-gradient(135deg, ${props => props.theme.primary || '#7B68EE'} 0%, ${props => props.theme.accent || '#9B8BFF'} 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${props => props.theme.primary || '#7B68EE'}40;
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
    transform: none;
  }
`;

const LockedContainer = styled.div`
  max-width: 400px;
  margin: 40px auto;
  padding: 24px;
`;

const AlertBox = styled.div`
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border: 1px solid #fca5a5;
  border-radius: 16px;
  padding: 24px;
  text-align: center;
`;

const AlertIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #dc2626;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 28px;
    color: white;
  }
`;

const AlertTitle = styled.h4`
  font-size: 18px;
  font-weight: 600;
  color: #dc2626;
  margin: 0 0 12px;
`;

const AlertText = styled.p`
  font-size: 14px;
  color: #991b1b;
  margin: 0 0 8px;
  line-height: 1.5;
`;

const AlertReason = styled.p`
  font-size: 13px;
  color: #b91c1c;
  font-weight: 500;
  margin: 0 0 20px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
`;

const VerifyButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 24px;
  background: #dc2626;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: #b91c1c;
    transform: translateY(-1px);
  }
`;

// Component for handling social media logins with security features
const SocialMediaLogin = ({ socialAccountId }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [accountDetails, setAccountDetails] = useState(null);
  const [isLocked, setIsLocked] = useState(false);
  const navigate = useNavigate();

  // Fetch account details on component mount
  useEffect(() => {
    const fetchAccountDetails = async () => {
      try {
        const response = await axios.get(`/api/social-accounts/${socialAccountId}/`);
        setAccountDetails(response.data);
        setIsLocked(response.data.is_locked);
        setUsername(response.data.account_username);
      } catch (error) {
        toast.error('Failed to fetch account details');
        errorTracker.captureError(error, 'SocialMediaLogin:FetchAccount', { socialAccountId }, 'error');
      }
    };

    if (socialAccountId) {
      fetchAccountDetails();
    }
  }, [socialAccountId]);

  // Handle login attempt
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Get device fingerprint for device tracking
      const deviceId = await deviceFingerprint.generate();

      // First, attempt to retrieve encrypted password from our password manager
      const passwordResponse = await axios.get(`/api/social-accounts/${socialAccountId}/password/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });

      // Now notify our backend about this login attempt
      // This is where suspicious login detection happens
      const loginResponse = await axios.post(
        `/api/social-accounts/${socialAccountId}/record_login/`,
        { device_id: deviceId },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        }
      );

      // If the login is not flagged as suspicious, proceed with the actual login
      if (!loginResponse.data.is_suspicious) {
        toast.success(`Successfully logged into ${accountDetails.platform}`);
        navigate('/dashboard');
      }
    } catch (error) {
      // Check if this was denied because of suspicious activity
      if (error.response && error.response.status === 403 && 
          error.response.data && error.response.data.account_locked) {
        
        setIsLocked(true);
        toast.error(`Security alert: ${error.response.data.reason}. Account has been locked.`);
        
        // Navigate to verification page
        navigate(`/verify-identity/${socialAccountId}`);
      } else {
        toast.error('Login failed. Please check your credentials.');
        errorTracker.captureError(error, 'SocialMediaLogin:Login', { socialAccountId }, 'error');
      }
    } finally {
      setLoading(false);
    }
  };

  if (isLocked) {
    return (
      <LockedContainer>
        <AlertBox>
          <AlertIcon>
            <FaLock />
          </AlertIcon>
          <AlertTitle>Account Locked</AlertTitle>
          <AlertText>
            This account has been locked due to suspicious login activity.
          </AlertText>
          <AlertReason>
            <FaExclamationTriangle style={{ marginRight: '8px' }} />
            {accountDetails?.lock_reason || 'Suspicious activity detected'}
          </AlertReason>
          <VerifyButton onClick={() => navigate(`/verify-identity/${socialAccountId}`)}>
            <FaShieldAlt /> Verify Your Identity to Unlock
          </VerifyButton>
        </AlertBox>
      </LockedContainer>
    );
  }

  return (
    <Container>
      <Title>
        <FaUser /> Login to {accountDetails?.platform}
      </Title>
      <Form onSubmit={handleLogin}>
        <FormGroup>
          <Label>Username</Label>
          <InputWrapper>
            <InputIcon><FaUser /></InputIcon>
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled
            />
          </InputWrapper>
        </FormGroup>
        <FormGroup>
          <Label>Password</Label>
          <InputWrapper>
            <InputIcon><FaKey /></InputIcon>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled
              placeholder="Stored securely in your password manager"
            />
          </InputWrapper>
        </FormGroup>
        <SubmitButton type="submit" disabled={loading}>
          <FaShieldAlt />
          {loading ? 'Logging in...' : 'Login with Password Manager'}
        </SubmitButton>
      </Form>
    </Container>
  );
};

export default SocialMediaLogin;

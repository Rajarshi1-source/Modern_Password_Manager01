import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import { FaExclamationTriangle, FaArrowLeft, FaPaperPlane, FaRedo, FaCheckCircle } from 'react-icons/fa';
import axios from 'axios';
import { toast } from 'react-hot-toast';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  successDark: '#059669',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Page = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 24px;
  min-height: 100vh;
  background: linear-gradient(180deg, ${colors.background} 0%, #f0f2ff 100%);
`;

const Card = styled.div`
  width: 100%;
  max-width: 480px;
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 20px;
  border: 1px solid ${colors.border};
  box-shadow: 0 12px 40px rgba(123, 104, 238, 0.12);
  padding: 32px;
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
`;

const HeaderIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.warning}25 0%, ${colors.warning}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    font-size: 24px;
    color: ${colors.warning};
  }
`;

const Title = styled.h3`
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: ${colors.text};
  line-height: 1.3;
`;

const InfoBanner = styled.div`
  background: linear-gradient(135deg, ${colors.warning}12 0%, ${colors.warning}06 100%);
  border: 1px solid ${colors.warning}30;
  border-left: 4px solid ${colors.warning};
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 24px;
`;

const BannerText = styled.p`
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: ${colors.textSecondary};
`;

const BannerReason = styled.p`
  margin: 6px 0;
  font-size: 14px;
  font-weight: 700;
  color: ${colors.text};
`;

const Intro = styled.p`
  font-size: 14px;
  color: ${colors.textSecondary};
  line-height: 1.6;
  text-align: center;
  margin: 0 0 20px 0;
`;

const PrimaryButton = styled.button`
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px ${colors.primary}40;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }

  &:disabled {
    background: ${colors.textSecondary};
    cursor: not-allowed;
    box-shadow: none;
    opacity: 0.6;
  }
`;

const VerifyButton = styled(PrimaryButton)`
  background: linear-gradient(135deg, ${colors.success} 0%, ${colors.successDark} 100%);
  box-shadow: 0 4px 14px ${colors.success}40;
  margin-bottom: 16px;

  &:hover:not(:disabled) {
    box-shadow: 0 6px 20px ${colors.success}50;
  }
`;

const FieldGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: ${colors.text};
  margin-bottom: 10px;
`;

const CodeInput = styled.input`
  width: 100%;
  padding: 16px;
  border-radius: 12px;
  border: 2px solid ${colors.border};
  background: ${colors.backgroundSecondary};
  color: ${colors.text};
  font-size: 22px;
  font-weight: 600;
  text-align: center;
  letter-spacing: 8px;
  box-sizing: border-box;
  transition: all 0.25s ease;

  &:focus {
    outline: none;
    border-color: ${colors.primary};
    background: ${colors.background};
    box-shadow: 0 0 0 4px ${colors.primary}15;
  }

  &::placeholder {
    color: ${colors.textSecondary};
    font-weight: 400;
    font-size: 15px;
    letter-spacing: normal;
  }
`;

const Countdown = styled.p`
  text-align: center;
  font-size: 14px;
  color: ${colors.textSecondary};
  margin: 0;
`;

const LinkButton = styled.button`
  background: none;
  border: none;
  color: ${colors.primary};
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s ease;

  &:hover:not(:disabled) {
    color: ${colors.primaryDark};
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const CenterRow = styled.div`
  text-align: center;
`;

const Footer = styled.div`
  border-top: 1px solid ${colors.border};
  margin-top: 24px;
  padding-top: 20px;
  text-align: center;
`;

const BackLink = styled.button`
  background: none;
  border: none;
  color: ${colors.textSecondary};
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s ease;

  &:hover {
    color: ${colors.text};
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
`;

const Spinner = styled.div`
  width: 48px;
  height: 48px;
  border: 4px solid ${colors.border};
  border-top-color: ${colors.primary};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`;

const VerifyIdentity = () => {
  const { socialAccountId } = useParams();
  const navigate = useNavigate();
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [accountDetails, setAccountDetails] = useState(null);
  const [accountError, setAccountError] = useState(false);
  const [codeRequested, setCodeRequested] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // Fetch account details
  const fetchAccountDetails = useCallback(async () => {
    try {
      setAccountError(false);
      const response = await axios.get(`/api/social-accounts/${socialAccountId}/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      setAccountDetails(response.data);
    } catch (error) {
      setAccountError(true);
      toast.error('Failed to fetch account details');
      console.error('Error fetching account:', error);
    }
  }, [socialAccountId]);

  useEffect(() => {
    if (socialAccountId) {
      fetchAccountDetails();
    }
  }, [socialAccountId, fetchAccountDetails]);

  // Countdown timer for verification code
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Request verification code
  const handleRequestCode = async () => {
    setLoading(true);
    try {
      await axios.post(`/api/social-accounts/${socialAccountId}/request_verification/`, {}, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });

      toast.success('Verification code sent to your email and phone');
      setCodeRequested(true);
      setCountdown(60); // 60-second countdown before requesting a new code
    } catch (error) {
      toast.error('Failed to send verification code');
      console.error('Error requesting code:', error);
    } finally {
      setLoading(false);
    }
  };

  // Verify identity and unlock account
  const handleVerify = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(
        `/api/social-accounts/${socialAccountId}/unlock_account/`,
        { verification_code: verificationCode },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        }
      );

      if (response.data.account_unlocked) {
        toast.success('Account successfully unlocked');
        navigate('/security/account-protection');
      } else {
        toast.error('Verification failed');
      }
    } catch (error) {
      toast.error('Identity verification failed');
      console.error('Verification error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (accountError && !accountDetails) {
    return (
      <Page>
        <Card>
          <Header>
            <HeaderIcon>
              <FaExclamationTriangle />
            </HeaderIcon>
            <Title>Unable to Load Account</Title>
          </Header>
          <InfoBanner>
            <BannerText>
              We couldn&apos;t load your account details. Please check your connection and try again.
            </BannerText>
          </InfoBanner>
          <PrimaryButton onClick={fetchAccountDetails}>
            <FaRedo /> Retry
          </PrimaryButton>
          <Footer>
            <BackLink onClick={() => navigate('/security/account-protection')}>
              <FaArrowLeft /> Back to Account Protection
            </BackLink>
          </Footer>
        </Card>
      </Page>
    );
  }

  if (!accountDetails) {
    return (
      <Page>
        <LoadingContainer>
          <Spinner />
        </LoadingContainer>
      </Page>
    );
  }

  return (
    <Page>
      <Card>
        <Header>
          <HeaderIcon>
            <FaExclamationTriangle />
          </HeaderIcon>
          <Title>Account Locked &mdash; Verify Your Identity</Title>
        </Header>

        <InfoBanner>
          <BannerText>
            Your {accountDetails.platform} account has been locked due to suspicious activity:
          </BannerText>
          <BannerReason>
            {accountDetails.lock_reason || 'Unauthorized access attempt'}
          </BannerReason>
          <BannerText>
            Please verify your identity to unlock your account.
          </BannerText>
        </InfoBanner>

        {!codeRequested ? (
          <>
            <Intro>
              We&apos;ll send a verification code to your registered email and phone.
            </Intro>
            <PrimaryButton onClick={handleRequestCode} disabled={loading}>
              <FaPaperPlane />
              {loading ? 'Sending...' : 'Send Verification Code'}
            </PrimaryButton>
          </>
        ) : (
          <form onSubmit={handleVerify}>
            <FieldGroup>
              <Label htmlFor="verificationCode">Enter Verification Code</Label>
              <CodeInput
                type="text"
                id="verificationCode"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value)}
                placeholder="Enter the 6-digit code"
                maxLength={6}
                required
              />
            </FieldGroup>

            <VerifyButton type="submit" disabled={loading || !verificationCode}>
              <FaCheckCircle />
              {loading ? 'Verifying...' : 'Verify and Unlock Account'}
            </VerifyButton>

            <CenterRow>
              {countdown > 0 ? (
                <Countdown>Request new code in {countdown} seconds</Countdown>
              ) : (
                <LinkButton type="button" onClick={handleRequestCode} disabled={loading}>
                  <FaRedo /> Request New Code
                </LinkButton>
              )}
            </CenterRow>
          </form>
        )}

        <Footer>
          <BackLink onClick={() => navigate('/security/account-protection')}>
            <FaArrowLeft /> Back to Account Protection
          </BackLink>
        </Footer>
      </Card>
    </Page>
  );
};

export default VerifyIdentity;

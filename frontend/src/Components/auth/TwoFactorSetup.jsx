import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import QRCode from 'qrcode.react';
import { FaQrcode, FaMobileAlt, FaKey, FaCheck, FaTimes, FaEnvelope, FaBell } from 'react-icons/fa';
import api from '../../services/api';
import { errorTracker } from '../../services/errorTracker';
import Button from '../common/Button';
import Input from '../common/Input';

const Container = styled.div`
  max-width: 600px;
  margin: 0 auto;
  padding: 2rem;
`;

const Title = styled.h2`
  margin-bottom: 1.5rem;
  text-align: center;
`;

const TabContainer = styled.div`
  display: flex;
  margin-bottom: 2rem;
  border-bottom: 1px solid ${props => props.theme.borderColor};
`;

const Tab = styled.button`
  flex: 1;
  padding: 1rem;
  background: ${props => props.active ? props.theme.cardBg : 'transparent'};
  border: none;
  border-bottom: 2px solid ${props => props.active ? props.theme.primary : 'transparent'};
  color: ${props => props.active ? props.theme.primary : props.theme.textSecondary};
  font-weight: ${props => props.active ? '600' : '400'};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  
  &:hover {
    color: ${props => props.theme.primary};
  }
`;

const SetupContainer = styled.div`
  padding: 1rem;
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
`;

const QRContainer = styled.div`
  display: flex;
  justify-content: center;
  margin: 2rem 0;
`;

const Instructions = styled.p`
  margin-bottom: 1.5rem;
  line-height: 1.5;
`;

const BackupCodesContainer = styled.div`
  margin: 1.5rem 0;
  background: ${props => props.theme.backgroundSecondary};
  padding: 1rem;
  border-radius: 8px;
  font-family: monospace;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
`;

const BackupCode = styled.div`
  padding: 0.5rem;
  background: ${props => props.theme.backgroundPrimary};
  border-radius: 4px;
  text-align: center;
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
`;

const ErrorMessage = styled.div`
  color: ${props => props.theme.error};
  margin: 1rem 0;
  padding: 0.5rem;
  background-color: ${props => props.theme.errorLight};
  border-radius: 4px;
`;

const SuccessMessage = styled.div`
  color: ${props => props.theme.success};
  margin: 1rem 0;
  padding: 0.5rem;
  background-color: ${props => props.theme.successLight};
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const TwoFactorSetup = ({ onComplete }) => {
  const [activeTab, setActiveTab] = useState('totp');
  const [setupData, setSetupData] = useState(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [countryCode, setCountryCode] = useState('1');
  const [deviceToken, setDeviceToken] = useState('');
  const [deviceType, setDeviceType] = useState('android');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  useEffect(() => {
    fetchSetupData();
  }, []);
  
  const fetchSetupData = async () => {
    try {
      setLoading(true);
      const response = await api.get('/auth/two_factor_auth/');
      setSetupData(response.data);
    } catch (error) {
      setError('Failed to fetch setup data. Please try again.');
      errorTracker.captureError(error, 'TwoFactorSetup:FetchSetupData', {}, 'error');
    } finally {
      setLoading(false);
    }
  };
  
  const handleVerifyTOTP = async () => {
    if (!verificationCode) {
      setError('Please enter the verification code');
      return;
    }
    
    try {
      setLoading(true);
      setError('');
      
      const response = await api.post('/auth/two_factor_auth/', {
        action: 'enable',
        mfa_type: 'totp',
        secret: setupData.setup_secret,
        code: verificationCode,
        backup_codes: setupData.backup_codes
      });
      
      setSuccess('Two-factor authentication has been enabled!');
      
      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to verify code. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSetupAuthy = async () => {
    if (!phoneNumber) {
      setError('Please enter your phone number');
      return;
    }
    
    try {
      setLoading(true);
      setError('');
      
      const response = await api.post('/auth/two_factor_auth/', {
        action: 'enable',
        mfa_type: 'authy',
        phone: phoneNumber,
        country_code: countryCode
      });
      
      setSuccess('Authy two-factor authentication has been enabled!');
      
      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to set up Authy. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSetupPush = async () => {
    if (!phoneNumber) {
      setError('Please enter your phone number');
      return;
    }
    
    try {
      setLoading(true);
      setError('');
      
      // For production app, we would get the device token from the mobile app
      // For this demo, we're using a placeholder
      const pushData = {
        action: 'enable',
        mfa_type: 'push',
        phone: phoneNumber,
        country_code: countryCode
      };
      
      // If device token is available (from mobile app), include it
      if (deviceToken) {
        pushData.device_token = deviceToken;
        pushData.device_type = deviceType;
      }
      
      const response = await api.post('/auth/two_factor_auth/', pushData);
      
      setSuccess('Push notification authentication has been enabled!');
      
      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to set up push notifications. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const renderTOTPSetup = () => (
    <>
      <Instructions>
        Scan the QR code below with an authenticator app like Google Authenticator, 
        Microsoft Authenticator, or Authy to set up two-factor authentication.
      </Instructions>
      
      {setupData && (
        <QRContainer>
          <QRCode 
            value={setupData.provisioning_uri || ''} 
            size={200}
            level="H"
          />
        </QRContainer>
      )}
      
      <FormGroup>
        <Input 
          label="Verification Code"
          placeholder="Enter the 6-digit code from your authenticator app"
          value={verificationCode}
          onChange={e => setVerificationCode(e.target.value)}
          autoComplete="off"
        />
      </FormGroup>
      
      <Instructions>
        <strong>Important:</strong> Please save these backup codes in a safe place. 
        You can use them to sign in if you lose access to your authenticator app.
      </Instructions>
      
      {setupData && setupData.backup_codes && (
        <BackupCodesContainer>
          {setupData.backup_codes.map((code, index) => (
            <BackupCode key={index}>{code}</BackupCode>
          ))}
        </BackupCodesContainer>
      )}
      
      <ButtonGroup>
        <Button onClick={() => setActiveTab('totp')} variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleVerifyTOTP} loading={loading} disabled={!verificationCode}>
          Verify and Enable
        </Button>
      </ButtonGroup>
    </>
  );
  
  const renderAuthySetup = () => (
    <>
      <Instructions>
        Enter your phone number to register with Authy. You'll receive a verification
        code via SMS or through the Authy app if you have it installed.
      </Instructions>
      
      <FormGroup>
        <Input 
          label="Country Code"
          placeholder="1"
          value={countryCode}
          onChange={e => setCountryCode(e.target.value)}
          autoComplete="tel-country-code"
        />
      </FormGroup>
      
      <FormGroup>
        <Input 
          label="Phone Number"
          placeholder="Enter your phone number"
          value={phoneNumber}
          onChange={e => setPhoneNumber(e.target.value)}
          autoComplete="tel"
        />
      </FormGroup>
      
      <ButtonGroup>
        <Button onClick={() => setActiveTab('totp')} variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleSetupAuthy} loading={loading} disabled={!phoneNumber}>
          Register with Authy
        </Button>
      </ButtonGroup>
    </>
  );
  
  const renderPushSetup = () => (
    <>
      <Instructions>
        Enable push notification authentication to receive login requests directly 
        on your mobile device. You'll need to install the mobile app and ensure it's logged in.
      </Instructions>
      
      <FormGroup>
        <Input 
          label="Country Code"
          placeholder="1"
          value={countryCode}
          onChange={e => setCountryCode(e.target.value)}
          autoComplete="tel-country-code"
        />
      </FormGroup>
      
      <FormGroup>
        <Input 
          label="Phone Number"
          placeholder="Enter your phone number"
          value={phoneNumber}
          onChange={e => setPhoneNumber(e.target.value)}
          autoComplete="tel"
        />
      </FormGroup>
      
      {/* Device token would typically be retrieved from the mobile app */}
      <Instructions>
        <strong>Note:</strong> For full functionality, please ensure you're logged in 
        on the mobile app. This will automatically register your device for push notifications.
      </Instructions>
      
      <ButtonGroup>
        <Button onClick={() => setActiveTab('totp')} variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleSetupPush} loading={loading} disabled={!phoneNumber}>
          Enable Push Authentication
        </Button>
      </ButtonGroup>
    </>
  );
  
  return (
    <Container>
      <Title>Set up Two-Factor Authentication</Title>
      
      <TabContainer>
        <Tab 
          active={activeTab === 'totp'} 
          onClick={() => setActiveTab('totp')}
        >
          <FaQrcode /> Authenticator App
        </Tab>
        <Tab 
          active={activeTab === 'authy'} 
          onClick={() => setActiveTab('authy')}
        >
          <FaMobileAlt /> Authy
        </Tab>
        <Tab 
          active={activeTab === 'push'} 
          onClick={() => setActiveTab('push')}
        >
          <FaBell /> Push Notification
        </Tab>
      </TabContainer>
      
      {error && (
        <ErrorMessage>
          <FaTimes /> {error}
        </ErrorMessage>
      )}
      
      {success && (
        <SuccessMessage>
          <FaCheck /> {success}
        </SuccessMessage>
      )}
      
      <SetupContainer>
        {activeTab === 'totp' && renderTOTPSetup()}
        {activeTab === 'authy' && renderAuthySetup()}
        {activeTab === 'push' && renderPushSetup()}
      </SetupContainer>
    </Container>
  );
};

export default TwoFactorSetup;
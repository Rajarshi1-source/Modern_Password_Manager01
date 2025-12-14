import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaShieldAlt, FaLock, FaExclamationTriangle, FaCheck, FaHistory, FaMobileAlt, FaEnvelope, FaComment, FaSmile, FaMicrophone, FaKey, FaInfoCircle, FaCheckCircle, FaCog } from 'react-icons/fa';
import mfaService from '../../services/mfaService';
import BiometricSetup from '../auth/BiometricSetup';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
`;

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

// Color Constants - matching vault page / settings
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  accent: '#A78BFA',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  background: '#0f0f1a',
  backgroundSecondary: '#1a1a2e',
  backgroundTertiary: '#252542',
  cardBg: '#1e1e35',
  cardBgHover: '#262649',
  text: '#ffffff',
  textSecondary: '#a0a0b8',
  textMuted: '#6b6b8a',
  border: '#2d2d4a',
  borderLight: '#3d3d5a'
};

const Container = styled.div`
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px;
  min-height: 100vh;
  background: linear-gradient(180deg, ${colors.background} 0%, ${colors.backgroundSecondary} 100%);
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 40px;
`;

const HeaderIcon = styled.div`
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  
  svg {
    font-size: 32px;
    color: ${colors.primary};
  }
`;

const Title = styled.h2`
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.accent} 50%, ${colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 12px 0;
  letter-spacing: -0.5px;
`;

const Subtitle = styled.p`
  font-size: 16px;
  color: ${colors.textSecondary};
  margin: 0;
`;

const Section = styled.div`
  background: ${colors.cardBg};
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 24px;
  border: 1px solid ${colors.border};
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$delay || '0s'};
  animation-fill-mode: backwards;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    box-shadow: 0 8px 32px rgba(123, 104, 238, 0.1);
  }
`;

const SectionHeader = styled.div`
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${colors.border};
  display: flex;
  align-items: center;
  gap: 14px;
`;

const SectionIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}20 0%, ${props => props.$color || colors.primary}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 24px;
    color: ${props => props.$color || colors.primary};
  }
`;

const SectionHeaderContent = styled.div`
  flex: 1;
  
  h3 {
    font-size: 20px;
    font-weight: 700;
    color: ${colors.text};
    margin: 0 0 4px 0;
  }
  
  p {
    font-size: 14px;
    color: ${colors.textSecondary};
    margin: 0;
  }
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
`;

const Card = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%);
  border: 2px solid ${props => props.$active ? colors.primary : colors.border};
  border-radius: 16px;
  padding: 24px;
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index ? `${props.$index * 0.05}s` : '0s'};
  animation-fill-mode: backwards;
  
  &:hover {
    border-color: ${props => props.$active ? colors.primary : colors.borderLight};
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.15);
  }
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
`;

const CardIconWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const CardIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}30 0%, ${props => props.$color || colors.primary}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 20px;
    color: ${props => props.$color || colors.primary};
  }
  
  span {
    font-size: 24px;
  }
`;

const CardTitle = styled.h4`
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: ${colors.text};
`;

const CardDescription = styled.p`
  font-size: 14px;
  color: ${colors.textSecondary};
  margin: 0 0 16px 0;
  line-height: 1.5;
`;

const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  ${props => {
    if (props.$variant === 'success') return `
      background: linear-gradient(135deg, ${colors.success}30 0%, ${colors.success}20 100%);
      color: ${colors.success};
    `;
    if (props.$variant === 'warning') return `
      background: linear-gradient(135deg, ${colors.warning}30 0%, ${colors.warning}20 100%);
      color: ${colors.warning};
    `;
    if (props.$variant === 'danger') return `
      background: linear-gradient(135deg, ${colors.danger}30 0%, ${colors.danger}20 100%);
      color: ${colors.danger};
    `;
    return `
      background: ${colors.backgroundTertiary};
      color: ${colors.textSecondary};
    `;
  }}
`;

const StatCard = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%);
  border: 1px solid ${colors.border};
  border-radius: 16px;
  padding: 24px;
  text-align: center;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index ? `${props.$index * 0.05}s` : '0s'};
  animation-fill-mode: backwards;
  transition: all 0.3s ease;
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.15);
    border-color: ${colors.borderLight};
  }
`;

const StatIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}20 0%, ${props => props.$color || colors.primary}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 24px;
    color: ${props => props.$color || colors.primary};
  }
`;

const StatValue = styled.div`
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary} 0%, ${props => props.$colorEnd || colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 4px;
`;

const StatLabel = styled.div`
  font-size: 14px;
  color: ${colors.textSecondary};
  font-weight: 500;
`;

const RiskLevel = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 16px;
  
  ${props => props.$level === 'low' && `
    background: linear-gradient(135deg, ${colors.success}20 0%, ${colors.success}10 100%);
    color: ${colors.success};
    border: 1px solid ${colors.success}40;
  `}
  
  ${props => props.$level === 'medium' && `
    background: linear-gradient(135deg, ${colors.warning}20 0%, ${colors.warning}10 100%);
    color: ${colors.warning};
    border: 1px solid ${colors.warning}40;
  `}
  
  ${props => props.$level === 'high' && `
    background: linear-gradient(135deg, ${colors.danger}20 0%, ${colors.danger}10 100%);
    color: ${colors.danger};
    border: 1px solid ${colors.danger}40;
  `}
`;

const ToggleGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ToggleItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  background: ${colors.backgroundSecondary};
  border-radius: 14px;
  border: 1px solid transparent;
  transition: all 0.3s ease;
  
  &:hover {
    background: ${colors.cardBgHover};
    border-color: ${colors.border};
    transform: translateX(4px);
  }
`;

const ToggleInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
`;

const ToggleIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: ${props => props.$active 
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
    : colors.backgroundTertiary};
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  
  svg {
    color: ${props => props.$active ? '#fff' : colors.textMuted};
    font-size: 18px;
  }
`;

const ToggleContent = styled.div`
  flex: 1;
`;

const ToggleLabel = styled.span`
  font-size: 15px;
  font-weight: 600;
  color: ${colors.text};
  display: block;
  margin-bottom: 4px;
`;

const ToggleDescription = styled.span`
  font-size: 13px;
  color: ${colors.textSecondary};
`;

const ToggleSwitch = styled.div`
  width: 52px;
  height: 28px;
  background: ${props => props.$checked 
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
    : colors.backgroundTertiary};
  border: 2px solid ${props => props.$checked ? 'transparent' : colors.border};
  border-radius: 14px;
  position: relative;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: ${props => props.$checked ? `0 4px 12px ${colors.primary}40` : 'none'};
  
  &::after {
    content: '';
    position: absolute;
    width: 20px;
    height: 20px;
    background: ${props => props.$checked ? '#fff' : colors.textMuted};
    border-radius: 10px;
    top: 2px;
    left: ${props => props.$checked ? '26px' : '2px'};
    transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  }
`;

const HistoryTable = styled.div`
  margin-top: 16px;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid ${colors.border};
`;

const TableHeader = styled.div`
  display: grid;
  grid-template-columns: 1.5fr 1fr 1.2fr 1fr 0.8fr;
  gap: 16px;
  padding: 14px 20px;
  background: ${colors.backgroundTertiary};
  border-bottom: 1px solid ${colors.border};
`;

const TableHeaderCell = styled.div`
  font-size: 12px;
  font-weight: 700;
  color: ${colors.textMuted};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const TableRow = styled.div`
  display: grid;
  grid-template-columns: 1.5fr 1fr 1.2fr 1fr 0.8fr;
  gap: 16px;
  padding: 16px 20px;
  background: ${colors.backgroundSecondary};
  border-bottom: 1px solid ${colors.border};
  transition: all 0.2s ease;
  
  &:last-child {
    border-bottom: none;
  }
  
  &:hover {
    background: ${colors.cardBgHover};
  }
`;

const TableCell = styled.div`
  font-size: 14px;
  color: ${colors.text};
  display: flex;
  align-items: center;
`;

const SetupButton = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 10px;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 12px ${colors.primary}30;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px ${colors.primary}40;
  }
`;

const InfoBox = styled.div`
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primary}05 100%);
  border-left: 4px solid ${colors.primary};
  padding: 18px 20px;
  border-radius: 0 12px 12px 0;
  margin-top: 20px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  
  svg {
    color: ${colors.primary};
    font-size: 20px;
    flex-shrink: 0;
    margin-top: 2px;
  }
`;

const InfoText = styled.div`
  font-size: 14px;
  color: ${colors.textSecondary};
  line-height: 1.6;
  
  strong {
    color: ${colors.text};
    font-weight: 600;
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

const Spinner = styled.div`
  width: 48px;
  height: 48px;
  border: 3px solid ${colors.border};
  border-top-color: ${colors.primary};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-bottom: 20px;
`;

const LoadingText = styled.p`
  font-size: 16px;
  color: ${colors.textSecondary};
  font-weight: 500;
`;

const factorIcons = {
  totp: FaMobileAlt,
  sms: FaComment,
  email: FaEnvelope,
  face: FaSmile,
  voice: FaMicrophone,
  passkey: FaKey
};

const factorColors = {
  totp: colors.primary,
  sms: colors.info,
  email: colors.warning,
  face: colors.success,
  voice: '#EC4899',
  passkey: colors.accent
};

const AdaptiveMFASettings = () => {
  const [loading, setLoading] = useState(true);
  const [factors, setFactors] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [riskAssessment, setRiskAssessment] = useState(null);
  const [authHistory, setAuthHistory] = useState([]);
  const [showBiometricSetup, setShowBiometricSetup] = useState(false);
  
  useEffect(() => {
    loadMFASettings();
  }, []);
  
  const loadMFASettings = async () => {
    setLoading(true);
    try {
      const [factorsData, policyData, riskData, historyData] = await Promise.all([
        mfaService.getEnabledFactors(),
        mfaService.getMFAPolicy(),
        mfaService.assessRisk(),
        mfaService.getAuthHistory({ limit: 10 })
      ]);
      
      setFactors(factorsData.factors || []);
      setPolicy(policyData.policy || {});
      setRiskAssessment(riskData);
      setAuthHistory(historyData.attempts || []);
    } catch (error) {
      console.error('Failed to load MFA settings:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handlePolicyUpdate = async (field, value) => {
    try {
      const updatedPolicy = { ...policy, [field]: value };
      await mfaService.updateMFAPolicy(updatedPolicy);
      setPolicy(updatedPolicy);
    } catch (error) {
      console.error('Failed to update policy:', error);
    }
  };
  
  const handleBiometricSetupComplete = (type) => {
    setShowBiometricSetup(false);
    loadMFASettings();
  };
  
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };
  
  if (loading) {
    return (
      <Container>
        <LoadingContainer>
          <Spinner />
          <LoadingText>Loading MFA settings...</LoadingText>
        </LoadingContainer>
      </Container>
    );
  }
  
  if (showBiometricSetup) {
    return <BiometricSetup onComplete={handleBiometricSetupComplete} />;
  }
  
  const factorsList = [
    { id: 'totp', name: 'Authenticator App', description: 'Time-based one-time password' },
    { id: 'sms', name: 'SMS Code', description: 'Receive codes via SMS' },
    { id: 'email', name: 'Email Code', description: 'Receive codes via email' },
    { id: 'face', name: 'Face Recognition', description: 'Use your face to authenticate' },
    { id: 'voice', name: 'Voice Recognition', description: 'Use your voice to authenticate' },
    { id: 'passkey', name: 'Passkey/WebAuthn', description: 'Hardware or platform authenticator' }
  ];
  
  return (
    <Container>
      <Header>
        <HeaderIcon>
          <FaShieldAlt />
        </HeaderIcon>
        <Title>Adaptive Multi-Factor Authentication</Title>
        <Subtitle>Secure your account with intelligent, risk-based authentication</Subtitle>
      </Header>
      
      {/* Current Risk Level */}
      <Section $delay="0.1s">
        <SectionHeader>
          <SectionIcon $color={colors.primary}>
            <FaShieldAlt />
          </SectionIcon>
          <SectionHeaderContent>
            <h3>Current Security Status</h3>
            <p>Real-time assessment of your account security</p>
          </SectionHeaderContent>
        </SectionHeader>
        
        <Grid>
          <StatCard $index={0}>
            <StatIcon $color={
              riskAssessment?.risk_level === 'low' ? colors.success :
              riskAssessment?.risk_level === 'medium' ? colors.warning : colors.danger
            }>
              {riskAssessment?.risk_level === 'low' ? <FaCheck /> : <FaExclamationTriangle />}
            </StatIcon>
            <RiskLevel $level={riskAssessment?.risk_level || 'low'}>
              {riskAssessment?.risk_level === 'low' && <FaCheckCircle />}
              {riskAssessment?.risk_level === 'medium' && <FaExclamationTriangle />}
              {riskAssessment?.risk_level === 'high' && <FaExclamationTriangle />}
              {(riskAssessment?.risk_level || 'low').toUpperCase()} RISK
            </RiskLevel>
            <StatLabel style={{ marginTop: '12px' }}>
              Risk Score: {((riskAssessment?.risk_score || 0) * 100).toFixed(0)}%
            </StatLabel>
          </StatCard>
          
          <StatCard $index={1}>
            <StatIcon $color={colors.primary}>
              <FaLock />
            </StatIcon>
            <StatValue $color={colors.primary} $colorEnd={colors.primaryLight}>
              {riskAssessment?.required_factors?.length || 1}
            </StatValue>
            <StatLabel>Required Factors</StatLabel>
          </StatCard>
          
          <StatCard $index={2}>
            <StatIcon $color={colors.success}>
              <FaCheckCircle />
            </StatIcon>
            <StatValue $color={colors.success} $colorEnd="#34d399">
              {factors.length}
            </StatValue>
            <StatLabel>Active Methods</StatLabel>
          </StatCard>
        </Grid>
      </Section>
      
      {/* Enabled Factors */}
      <Section $delay="0.15s">
        <SectionHeader>
          <SectionIcon $color={colors.info}>
            <FaLock />
          </SectionIcon>
          <SectionHeaderContent>
            <h3>Authentication Methods</h3>
            <p>Configure your preferred security factors</p>
          </SectionHeaderContent>
        </SectionHeader>
        
        <Grid>
          {factorsList.map((factor, index) => {
            const isEnabled = factors.includes(factor.id);
            const IconComponent = factorIcons[factor.id] || FaLock;
            const iconColor = factorColors[factor.id] || colors.primary;
            
            return (
              <Card key={factor.id} $active={isEnabled} $index={index}>
                <CardHeader>
                  <CardIconWrapper>
                    <CardIcon $color={iconColor}>
                      <IconComponent />
                    </CardIcon>
                    <CardTitle>{factor.name}</CardTitle>
                  </CardIconWrapper>
                  {isEnabled && <Badge $variant="success">Active</Badge>}
                </CardHeader>
                <CardDescription>{factor.description}</CardDescription>
                {!isEnabled && (factor.id === 'face' || factor.id === 'voice') && (
                  <SetupButton onClick={() => setShowBiometricSetup(true)}>
                    <FaCog /> Set Up
                  </SetupButton>
                )}
              </Card>
            );
          })}
        </Grid>
        
        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Security Tip:</strong> Enable multiple authentication methods to ensure 
            you can always access your account, even if one method is unavailable.
          </InfoText>
        </InfoBox>
      </Section>
      
      {/* Adaptive MFA Policy */}
      <Section $delay="0.2s">
        <SectionHeader>
          <SectionIcon $color={colors.warning}>
            <FaCog />
          </SectionIcon>
          <SectionHeaderContent>
            <h3>Adaptive MFA Policy</h3>
            <p>Configure intelligent authentication rules</p>
          </SectionHeaderContent>
        </SectionHeader>
        
        <ToggleGroup>
          <ToggleItem>
            <ToggleInfo>
              <ToggleIcon $active={policy?.adaptive_mfa_enabled}>
                <FaShieldAlt />
              </ToggleIcon>
              <ToggleContent>
                <ToggleLabel>Enable Adaptive MFA</ToggleLabel>
                <ToggleDescription>Automatically adjust security based on risk</ToggleDescription>
              </ToggleContent>
            </ToggleInfo>
            <ToggleSwitch
              $checked={policy?.adaptive_mfa_enabled || false}
              onClick={() => handlePolicyUpdate('adaptive_mfa_enabled', !policy?.adaptive_mfa_enabled)}
            />
          </ToggleItem>
          
          <ToggleItem>
            <ToggleInfo>
              <ToggleIcon $active={policy?.require_mfa_on_new_device}>
                <FaMobileAlt />
              </ToggleIcon>
              <ToggleContent>
                <ToggleLabel>Require MFA on New Device</ToggleLabel>
                <ToggleDescription>Always verify when signing in from new devices</ToggleDescription>
              </ToggleContent>
            </ToggleInfo>
            <ToggleSwitch
              $checked={policy?.require_mfa_on_new_device || false}
              onClick={() => handlePolicyUpdate('require_mfa_on_new_device', !policy?.require_mfa_on_new_device)}
            />
          </ToggleItem>
          
          <ToggleItem>
            <ToggleInfo>
              <ToggleIcon $active={policy?.require_mfa_on_new_location}>
                <FaExclamationTriangle />
              </ToggleIcon>
              <ToggleContent>
                <ToggleLabel>Require MFA on New Location</ToggleLabel>
                <ToggleDescription>Verify when signing in from new locations</ToggleDescription>
              </ToggleContent>
            </ToggleInfo>
            <ToggleSwitch
              $checked={policy?.require_mfa_on_new_location || false}
              onClick={() => handlePolicyUpdate('require_mfa_on_new_location', !policy?.require_mfa_on_new_location)}
            />
          </ToggleItem>
          
          <ToggleItem>
            <ToggleInfo>
              <ToggleIcon $active={policy?.require_biometric_for_sensitive}>
                <FaSmile />
              </ToggleIcon>
              <ToggleContent>
                <ToggleLabel>Require Biometric for Sensitive Operations</ToggleLabel>
                <ToggleDescription>Use face or voice for critical actions</ToggleDescription>
              </ToggleContent>
            </ToggleInfo>
            <ToggleSwitch
              $checked={policy?.require_biometric_for_sensitive || false}
              onClick={() => handlePolicyUpdate('require_biometric_for_sensitive', !policy?.require_biometric_for_sensitive)}
            />
          </ToggleItem>
        </ToggleGroup>
      </Section>
      
      {/* Authentication History */}
      <Section $delay="0.25s">
        <SectionHeader>
          <SectionIcon $color={colors.success}>
            <FaHistory />
          </SectionIcon>
          <SectionHeaderContent>
            <h3>Recent Authentication Attempts</h3>
            <p>Monitor your account activity</p>
          </SectionHeaderContent>
        </SectionHeader>
        
        <HistoryTable>
          <TableHeader>
            <TableHeaderCell>Time</TableHeaderCell>
            <TableHeaderCell>Method</TableHeaderCell>
            <TableHeaderCell>Device</TableHeaderCell>
            <TableHeaderCell>Location</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
          </TableHeader>
          {authHistory.map((attempt, index) => (
            <TableRow key={index}>
              <TableCell>{formatDate(attempt.timestamp)}</TableCell>
              <TableCell style={{ textTransform: 'capitalize' }}>{attempt.factor_type}</TableCell>
              <TableCell>{attempt.device_info}</TableCell>
              <TableCell>{attempt.location || 'Unknown'}</TableCell>
              <TableCell>
                <Badge $variant={attempt.success ? 'success' : 'danger'}>
                  {attempt.success ? 'Success' : 'Failed'}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </HistoryTable>
      </Section>
    </Container>
  );
};

export default AdaptiveMFASettings;

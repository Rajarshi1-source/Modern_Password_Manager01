import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaShieldAlt, FaLock, FaExclamationTriangle, FaCheck, FaHistory } from 'react-icons/fa';
import mfaService from '../../services/mfaService';
import Button from '../common/Button';
import BiometricSetup from '../auth/BiometricSetup';

const Container = styled.div`
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
`;

const Title = styled.h2`
  margin-bottom: 2rem;
  color: var(--text-primary);
`;

const Section = styled.div`
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
`;

const SectionTitle = styled.h3`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  color: var(--text-primary);
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
`;

const Card = styled.div`
  background: var(--bg-primary);
  border: 2px solid ${props => props.active ? 'var(--primary)' : 'var(--border-color)'};
  border-radius: 8px;
  padding: 1.5rem;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: var(--primary);
  }
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
`;

const CardTitle = styled.h4`
  margin: 0;
  color: var(--text-primary);
`;

const Badge = styled.span`
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  
  ${props => props.variant === 'success' && `
    background: var(--success-light);
    color: var(--success);
  `}
  
  ${props => props.variant === 'warning' && `
    background: var(--warning-light);
    color: var(--warning);
  `}
  
  ${props => props.variant === 'danger' && `
    background: var(--danger-light);
    color: var(--danger);
  `}
`;

const Toggle = styled.label`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  user-select: none;
  
  input {
    position: relative;
    width: 48px;
    height: 24px;
    appearance: none;
    background: var(--border-color);
    border-radius: 12px;
    outline: none;
    cursor: pointer;
    transition: background 0.3s;
    
    &:checked {
      background: var(--primary);
    }
    
    &:before {
      content: '';
      position: absolute;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: white;
      top: 2px;
      left: 2px;
      transition: transform 0.3s;
    }
    
    &:checked:before {
      transform: translateX(24px);
    }
  }
  
  span {
    color: var(--text-primary);
    font-weight: 500;
  }
`;

const RiskLevel = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  
  ${props => props.level === 'low' && `
    background: var(--success-light);
    color: var(--success);
  `}
  
  ${props => props.level === 'medium' && `
    background: var(--warning-light);
    color: var(--warning);
  `}
  
  ${props => props.level === 'high' && `
    background: var(--danger-light);
    color: var(--danger);
  `}
`;

const HistoryTable = styled.table`
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  
  th, td {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-color);
  }
  
  th {
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
  
  td {
    color: var(--text-primary);
  }
`;

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
    return <Container><p>Loading MFA settings...</p></Container>;
  }
  
  if (showBiometricSetup) {
    return <BiometricSetup onComplete={handleBiometricSetupComplete} />;
  }
  
  return (
    <Container>
      <Title>Adaptive Multi-Factor Authentication</Title>
      
      {/* Current Risk Level */}
      <Section>
        <SectionTitle>
          <FaShieldAlt /> Current Security Status
        </SectionTitle>
        <Grid>
          <Card>
            <CardHeader>
              <CardTitle>Risk Level</CardTitle>
            </CardHeader>
            <RiskLevel level={riskAssessment?.risk_level || 'low'}>
              {riskAssessment?.risk_level === 'low' && <FaCheck />}
              {riskAssessment?.risk_level === 'medium' && <FaExclamationTriangle />}
              {riskAssessment?.risk_level === 'high' && <FaExclamationTriangle />}
              {(riskAssessment?.risk_level || 'low').toUpperCase()}
            </RiskLevel>
            <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Risk Score: {((riskAssessment?.risk_score || 0) * 100).toFixed(0)}%
            </p>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Required Factors</CardTitle>
            </CardHeader>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--primary)' }}>
              {riskAssessment?.required_factors?.length || 1}
            </div>
            <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              {riskAssessment?.required_factors?.join(', ') || 'Password'}
            </p>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Active Factors</CardTitle>
            </CardHeader>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--success)' }}>
              {factors.length}
            </div>
            <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Configured authentication methods
            </p>
          </Card>
        </Grid>
      </Section>
      
      {/* Enabled Factors */}
      <Section>
        <SectionTitle>
          <FaLock /> Authentication Methods
        </SectionTitle>
        <Grid>
          {[
            { id: 'totp', name: 'Authenticator App (TOTP)', icon: '📱' },
            { id: 'sms', name: 'SMS Code', icon: '💬' },
            { id: 'email', name: 'Email Code', icon: '📧' },
            { id: 'face', name: 'Face Recognition', icon: '😊' },
            { id: 'voice', name: 'Voice Recognition', icon: '🎤' },
            { id: 'passkey', name: 'Passkey/WebAuthn', icon: '🔐' }
          ].map(factor => {
            const isEnabled = factors.includes(factor.id);
            return (
              <Card key={factor.id} active={isEnabled}>
                <CardHeader>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.5rem' }}>{factor.icon}</span>
                    <CardTitle>{factor.name}</CardTitle>
                  </div>
                  {isEnabled && <Badge variant="success">Active</Badge>}
                </CardHeader>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  {factor.id === 'face' && 'Use your face to authenticate'}
                  {factor.id === 'voice' && 'Use your voice to authenticate'}
                  {factor.id === 'totp' && 'Time-based one-time password'}
                  {factor.id === 'sms' && 'Receive codes via SMS'}
                  {factor.id === 'email' && 'Receive codes via email'}
                  {factor.id === 'passkey' && 'Hardware or platform authenticator'}
                </p>
                {!isEnabled && (factor.id === 'face' || factor.id === 'voice') && (
                  <Button
                    size="small"
                    onClick={() => setShowBiometricSetup(true)}
                  >
                    Set Up
                  </Button>
                )}
              </Card>
            );
          })}
        </Grid>
      </Section>
      
      {/* Adaptive MFA Policy */}
      <Section>
        <SectionTitle>
          <FaShieldAlt /> Adaptive MFA Policy
        </SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Toggle>
            <input
              type="checkbox"
              checked={policy?.adaptive_mfa_enabled || false}
              onChange={(e) => handlePolicyUpdate('adaptive_mfa_enabled', e.target.checked)}
            />
            <span>Enable Adaptive MFA</span>
          </Toggle>
          
          <Toggle>
            <input
              type="checkbox"
              checked={policy?.require_mfa_on_new_device || false}
              onChange={(e) => handlePolicyUpdate('require_mfa_on_new_device', e.target.checked)}
            />
            <span>Require MFA on New Device</span>
          </Toggle>
          
          <Toggle>
            <input
              type="checkbox"
              checked={policy?.require_mfa_on_new_location || false}
              onChange={(e) => handlePolicyUpdate('require_mfa_on_new_location', e.target.checked)}
            />
            <span>Require MFA on New Location</span>
          </Toggle>
          
          <Toggle>
            <input
              type="checkbox"
              checked={policy?.require_biometric_for_sensitive || false}
              onChange={(e) => handlePolicyUpdate('require_biometric_for_sensitive', e.target.checked)}
            />
            <span>Require Biometric for Sensitive Operations</span>
          </Toggle>
        </div>
      </Section>
      
      {/* Authentication History */}
      <Section>
        <SectionTitle>
          <FaHistory /> Recent Authentication Attempts
        </SectionTitle>
        <HistoryTable>
          <thead>
            <tr>
              <th>Time</th>
              <th>Method</th>
              <th>Device</th>
              <th>Location</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {authHistory.map((attempt, index) => (
              <tr key={index}>
                <td>{formatDate(attempt.timestamp)}</td>
                <td>{attempt.factor_type}</td>
                <td>{attempt.device_info}</td>
                <td>{attempt.location || 'Unknown'}</td>
                <td>
                  <Badge variant={attempt.success ? 'success' : 'danger'}>
                    {attempt.success ? 'Success' : 'Failed'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </HistoryTable>
      </Section>
    </Container>
  );
};

export default AdaptiveMFASettings;


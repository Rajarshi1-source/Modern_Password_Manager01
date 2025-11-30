/**
 * Quantum-Resilient Recovery Setup Wizard
 * 
 * Multi-step wizard for setting up the Quantum-Resilient Social Mesh Recovery system
 * 
 * Steps:
 * 1. Introduction and explanation
 * 2. Guardian selection
 * 3. Device shard setup
 * 4. Biometric shard setup (optional)
 * 5. Temporal shard configuration
 * 6. Verification test
 * 7. Completion
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { 
  FaShieldAlt, 
  FaUsers, 
  FaMobileAlt, 
  FaFingerprint, 
  FaClock, 
  FaCheckCircle,
  FaArrowRight,
  FaArrowLeft,
  FaInfoCircle,
  FaTrash,
  FaPlus
} from 'react-icons/fa';
import ApiService from '../../services/api';
import { errorTracker } from '../../services/errorTracker';
import toast from 'react-hot-toast';

const Container = styled.div`
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px;
`;

const Wizard = styled.div`
  max-width: 900px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
`;

const Header = styled.div`
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 32px;
  text-align: center;
  
  h1 {
    margin: 0 0 8px 0;
    font-size: 28px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }
  
  p {
    margin: 0;
    opacity: 0.9;
    font-size: 16px;
  }
`;

const Progress = styled.div`
  display: flex;
  align-items: center;
  padding: 20px 32px;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
  overflow-x: auto;
`;

const ProgressStep = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  
  &:not(:last-child)::after {
    content: '';
    position: absolute;
    top: 20px;
    left: 50%;
    right: -50%;
    height: 2px;
    background: ${props => props.completed ? '#667eea' : '#e0e0e0'};
    z-index: 0;
  }
`;

const StepCircle = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: ${props => props.active ? '#667eea' : props.completed ? '#28a745' : '#e0e0e0'};
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  position: relative;
  z-index: 1;
  transition: all 0.3s;
`;

const StepLabel = styled.span`
  margin-top: 8px;
  font-size: 12px;
  color: ${props => props.active ? '#667eea' : '#666'};
  font-weight: ${props => props.active ? '600' : '400'};
  text-align: center;
`;

const Content = styled.div`
  padding: 40px 32px;
  min-height: 400px;
`;

const StepTitle = styled.h2`
  font-size: 24px;
  color: #333;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const StepDescription = styled.p`
  font-size: 16px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 32px;
`;

const InfoBox = styled.div`
  background: #e7f3ff;
  border-left: 4px solid #2196f3;
  padding: 16px;
  border-radius: 4px;
  margin-bottom: 24px;
  
  strong {
    display: block;
    margin-bottom: 8px;
    color: #1976d2;
  }
  
  p {
    margin: 4px 0;
    font-size: 14px;
    color: #555;
  }
`;

const GuardianList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
`;

const GuardianCard = styled.div`
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: border-color 0.3s;
  
  &:hover {
    border-color: #667eea;
  }
`;

const GuardianInfo = styled.div`
  flex: 1;
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
`;

const Checkbox = styled.label`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
  margin-top: 8px;
  
  input {
    cursor: pointer;
  }
`;

const Button = styled.button`
  padding: 14px 28px;
  background: ${props => props.secondary ? 'white' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'};
  color: ${props => props.secondary ? '#667eea' : 'white'};
  border: ${props => props.secondary ? '2px solid #667eea' : 'none'};
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
`;

const IconButton = styled.button`
  padding: 8px;
  background: ${props => props.danger ? '#dc3545' : '#f5f5f5'};
  color: ${props => props.danger ? 'white' : '#666'};
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => props.danger ? '#c82333' : '#e0e0e0'};
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 16px;
  margin-top: 32px;
  padding-top: 32px;
  border-top: 1px solid #e0e0e0;
  justify-content: space-between;
`;

const QuantumRecoverySetup = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  
  // Form data
  const [guardians, setGuardians] = useState([
    { email: '', requiresVideo: false },
    { email: '', requiresVideo: false },
    { email: '', requiresVideo: false }
  ]);
  const [deviceShardEnabled, setDeviceShardEnabled] = useState(true);
  const [biometricShardEnabled, setBiometricShardEnabled] = useState(false);
  const [temporalShardEnabled, setTemporalShardEnabled] = useState(true);
  const [deviceFingerprint, setDeviceFingerprint] = useState('');
  
  const steps = [
    { label: 'Introduction', icon: <FaShieldAlt /> },
    { label: 'Guardians', icon: <FaUsers /> },
    { label: 'Device', icon: <FaMobileAlt /> },
    { label: 'Biometric', icon: <FaFingerprint /> },
    { label: 'Temporal', icon: <FaClock /> },
    { label: 'Verification', icon: <FaCheckCircle /> },
    { label: 'Complete', icon: <FaCheckCircle /> }
  ];
  
  // Generate device fingerprint on mount
  useEffect(() => {
    const generateFingerprint = async () => {
      try {
        // Use FingerprintJS or similar library
        // For demo, generating random fingerprint
        const fp = `device_${Math.random().toString(36).substr(2, 9)}`;
        setDeviceFingerprint(fp);
      } catch (error) {
        console.error('Error generating fingerprint:', error);
      }
    };
    
    generateFingerprint();
  }, []);
  
  const addGuardian = () => {
    if (guardians.length < 5) {
      setGuardians([...guardians, { email: '', requiresVideo: false }]);
    }
  };
  
  const removeGuardian = (index) => {
    if (guardians.length > 3) {
      setGuardians(guardians.filter((_, i) => i !== index));
    }
  };
  
  const updateGuardian = (index, field, value) => {
    const updated = [...guardians];
    updated[index][field] = value;
    setGuardians(updated);
  };
  
  const handleNext = () => {
    // Validation for each step
    if (currentStep === 1) {
      // Validate guardians
      const validGuardians = guardians.filter(g => g.email && g.email.includes('@'));
      if (validGuardians.length < 3) {
        toast.error('Please add at least 3 valid guardian email addresses');
        return;
      }
    }
    
    if (currentStep === steps.length - 2) {
      // Last step before completion - submit
      handleSubmit();
      return;
    }
    
    setCurrentStep(currentStep + 1);
  };
  
  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };
  
  const handleSubmit = async () => {
    try {
      setLoading(true);
      
      const validGuardians = guardians.filter(g => g.email && g.email.includes('@'));
      
      const response = await ApiService.auth.setupQuantumRecovery({
        total_shards: 5,
        threshold_shards: 3,
        guardians: validGuardians.map(g => ({
          email: g.email,
          requires_video: g.requiresVideo
        })),
        enable_temporal_shard: temporalShardEnabled,
        enable_biometric_shard: biometricShardEnabled,
        enable_device_shard: deviceShardEnabled,
        device_fingerprint: deviceFingerprint
      });
      
      if (response.data.success) {
        setCurrentStep(steps.length - 1);
        toast.success('Quantum-Resilient Recovery configured successfully!');
      } else {
        throw new Error(response.data.error || 'Setup failed');
      }
      
    } catch (error) {
      console.error('Setup error:', error);
      errorTracker.captureError(error, 'QuantumRecoverySetup:Submit', {}, 'error');
      toast.error(error.message || 'Failed to setup recovery system');
    } finally {
      setLoading(false);
    }
  };
  
  const renderStepContent = () => {
    switch(currentStep) {
      case 0: // Introduction
        return (
          <>
            <StepTitle>
              <FaShieldAlt /> Welcome to Quantum-Resilient Recovery
            </StepTitle>
            <StepDescription>
              Set up the most advanced passkey recovery system available. This system protects you from:
            </StepDescription>
            
            <InfoBox>
              <strong>✅ What This Protects Against:</strong>
              <p>• Device loss or theft</p>
              <p>• Forgotten passwords</p>
              <p>• Quantum computer attacks (future-proof)</p>
              <p>• Coordinated attacks on guardians</p>
              <p>• Instant compromise attempts</p>
            </InfoBox>
            
            <InfoBox style={{ background: '#fff3e0', borderColor: '#ff9800' }}>
              <strong style={{ color: '#f57c00' }}>⚠️ Important Requirements:</strong>
              <p>• 3-5 trusted contacts (guardians)</p>
              <p>• 10 minutes of your time</p>
              <p>• Access to your devices</p>
              <p>• Willingness to test the system</p>
            </InfoBox>
            
            <StepDescription>
              Recovery takes 3-7 days and requires multiple forms of identity proof. This prevents attackers 
              from gaining instant access, even if they compromise some of your security layers.
            </StepDescription>
          </>
        );
      
      case 1: // Guardian Selection
        return (
          <>
            <StepTitle>
              <FaUsers /> Select Your Recovery Guardians
            </StepTitle>
            <StepDescription>
              Choose 3-5 trusted contacts who will help verify your identity during recovery.
              They will NOT see your vault contents or passwords.
            </StepDescription>
            
            <InfoBox>
              <strong>🔐 Zero-Knowledge Protection:</strong>
              <p>• Guardians never see your passwords or vault</p>
              <p>• Each guardian gets an encrypted shard</p>
              <p>• Guardians don't know who else is a guardian</p>
              <p>• Approval windows are randomized to prevent collusion</p>
            </InfoBox>
            
            <GuardianList>
              {guardians.map((guardian, index) => (
                <GuardianCard key={index}>
                  <div style={{ fontSize: '32px' }}>
                    <FaUsers />
                  </div>
                  <GuardianInfo>
                    <Input
                      type="email"
                      placeholder={`Guardian ${index + 1} email`}
                      value={guardian.email}
                      onChange={(e) => updateGuardian(index, 'email', e.target.value)}
                    />
                    <Checkbox>
                      <input
                        type="checkbox"
                        checked={guardian.requiresVideo}
                        onChange={(e) => updateGuardian(index, 'requiresVideo', e.target.checked)}
                      />
                      Require video verification
                    </Checkbox>
                  </GuardianInfo>
                  {guardians.length > 3 && (
                    <IconButton danger onClick={() => removeGuardian(index)}>
                      <FaTrash />
                    </IconButton>
                  )}
                </GuardianCard>
              ))}
            </GuardianList>
            
            {guardians.length < 5 && (
              <Button secondary onClick={addGuardian}>
                <FaPlus /> Add Another Guardian
              </Button>
            )}
          </>
        );
      
      case 2: // Device Shard
        return (
          <>
            <StepTitle>
              <FaMobileAlt /> Device Shard Setup
            </StepTitle>
            <StepDescription>
              Store a recovery shard on this device's secure storage.
            </StepDescription>
            
            <InfoBox>
              <strong>📱 Device Shard Benefits:</strong>
              <p>• Instant access if you still have this device</p>
              <p>• Stored in browser's secure storage</p>
              <p>• Encrypted with device fingerprint</p>
              <p>• Works offline</p>
            </InfoBox>
            
            <Checkbox>
              <input
                type="checkbox"
                checked={deviceShardEnabled}
                onChange={(e) => setDeviceShardEnabled(e.target.checked)}
              />
              Enable device shard (recommended)
            </Checkbox>
            
            {deviceShardEnabled && (
              <div style={{ marginTop: '16px', padding: '16px', background: '#f5f5f5', borderRadius: '8px' }}>
                <strong>Device Fingerprint:</strong>
                <p style={{ fontFamily: 'monospace', marginTop: '8px' }}>{deviceFingerprint}</p>
              </div>
            )}
          </>
        );
      
      case 3: // Biometric Shard
        return (
          <>
            <StepTitle>
              <FaFingerprint /> Biometric Shard (Optional)
            </StepTitle>
            <StepDescription>
              Use behavioral biometrics (typing patterns, mouse movements) to create an additional shard.
            </StepDescription>
            
            <InfoBox>
              <strong>🧬 Behavioral Biometrics:</strong>
              <p>• Learns your unique typing patterns</p>
              <p>• Analyzes mouse movement style</p>
              <p>• Tracks typical usage times and locations</p>
              <p>• Provides an additional security layer</p>
            </InfoBox>
            
            <Checkbox>
              <input
                type="checkbox"
                checked={biometricShardEnabled}
                onChange={(e) => setBiometricShardEnabled(e.target.checked)}
              />
              Enable biometric shard (requires 2+ weeks of data collection)
            </Checkbox>
          </>
        );
      
      case 4: // Temporal Shard
        return (
          <>
            <StepTitle>
              <FaClock /> Temporal Proof-of-Identity
            </StepTitle>
            <StepDescription>
              Enable time-distributed challenges to verify your identity over 3-7 days.
            </StepDescription>
            
            <InfoBox>
              <strong>⏳ Temporal Protection:</strong>
              <p>• 5 challenges sent over 3 days</p>
              <p>• Questions about your account history</p>
              <p>• Typical device and location verification</p>
              <p>• Prevents instant attacks</p>
            </InfoBox>
            
            <Checkbox>
              <input
                type="checkbox"
                checked={temporalShardEnabled}
                onChange={(e) => setTemporalShardEnabled(e.target.checked)}
              />
              Enable temporal challenges (strongly recommended)
            </Checkbox>
          </>
        );
      
      case 5: // Verification
        return (
          <>
            <StepTitle>
              <FaCheckCircle /> Ready to Activate
            </StepTitle>
            <StepDescription>
              Review your configuration and activate the recovery system.
            </StepDescription>
            
            <InfoBox>
              <strong>📋 Configuration Summary:</strong>
              <p>• Guardians: {guardians.filter(g => g.email).length}</p>
              <p>• Device Shard: {deviceShardEnabled ? 'Enabled' : 'Disabled'}</p>
              <p>• Biometric Shard: {biometricShardEnabled ? 'Enabled' : 'Disabled'}</p>
              <p>• Temporal Challenges: {temporalShardEnabled ? 'Enabled' : 'Disabled'}</p>
              <p>• Total Shards: 5 (minimum 3 needed for recovery)</p>
            </InfoBox>
            
            <InfoBox style={{ background: '#fff3e0', borderColor: '#ff9800' }}>
              <strong style={{ color: '#f57c00' }}>⚠️ Next Steps:</strong>
              <p>1. We'll send invitations to your guardians</p>
              <p>2. System activates once all guardians accept</p>
              <p>3. Test recovery quarterly to ensure it works</p>
            </InfoBox>
          </>
        );
      
      case 6: // Complete
        return (
          <>
            <StepTitle>
              <FaCheckCircle /> Setup Complete!
            </StepTitle>
            <StepDescription>
              Your Quantum-Resilient Recovery system is configured.
            </StepDescription>
            
            <InfoBox style={{ background: '#e8f5e9', borderColor: '#4caf50' }}>
              <strong style={{ color: '#2e7d32' }}>✅ What Happens Now:</strong>
              <p>• Guardian invitations sent</p>
              <p>• Recovery shards created and encrypted</p>
              <p>• System will activate once guardians accept</p>
              <p>• You'll receive confirmation email</p>
            </InfoBox>
            
            <InfoBox>
              <strong>🔄 Recommended Actions:</strong>
              <p>• Test recovery in 1 week (rehearsal mode)</p>
              <p>• Update guardians if contacts change</p>
              <p>• Review audit logs quarterly</p>
              <p>• Keep device shard synchronized</p>
            </InfoBox>
            
            <Button onClick={() => navigate('/settings/recovery')} style={{ width: '100%', marginTop: '24px' }}>
              Go to Recovery Settings
            </Button>
          </>
        );
      
      default:
        return null;
    }
  };
  
  return (
    <Container>
      <Wizard>
        <Header>
          <h1>
            <FaShieldAlt />
            Quantum-Resilient Recovery Setup
          </h1>
          <p>Next-generation passkey recovery with post-quantum security</p>
        </Header>
        
        <Progress>
          {steps.map((step, index) => (
            <ProgressStep key={index} completed={index < currentStep}>
              <StepCircle active={index === currentStep} completed={index < currentStep}>
                {index < currentStep ? <FaCheckCircle /> : index + 1}
              </StepCircle>
              <StepLabel active={index === currentStep}>
                {step.label}
              </StepLabel>
            </ProgressStep>
          ))}
        </Progress>
        
        <Content>
          {renderStepContent()}
          
          {currentStep < steps.length - 1 && (
            <ButtonGroup>
              <Button 
                secondary 
                onClick={handleBack} 
                disabled={currentStep === 0 || loading}
              >
                <FaArrowLeft /> Back
              </Button>
              
              <Button 
                onClick={handleNext} 
                disabled={loading}
              >
                {loading ? 'Processing...' : (currentStep === steps.length - 2 ? 'Complete Setup' : 'Next')} 
                <FaArrowRight />
              </Button>
            </ButtonGroup>
          )}
        </Content>
      </Wizard>
    </Container>
  );
};

export default QuantumRecoverySetup;


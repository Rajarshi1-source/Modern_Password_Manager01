/**
 * Behavioral Recovery Status Component
 * 
 * Displays behavioral recovery setup status in dashboard
 */

import React from 'react';
import styled from 'styled-components';
import { FaBrain, FaCheckCircle, FaClock, FaExclamationTriangle } from 'react-icons/fa';
import { useBehavioralRecovery } from '../../hooks/useBehavioralRecovery';

const StatusCard = styled.div`
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-left: 4px solid ${props => 
    props.status === 'ready' ? '#4caf50' :
    props.status === 'can_setup' ? '#2196f3' :
    '#ff9800'
  };
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  
  svg {
    font-size: 28px;
    color: ${props => props.color || '#667eea'};
  }
  
  h3 {
    margin: 0;
    font-size: 18px;
    color: #333;
  }
`;

const StatusBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: ${props => 
    props.status === 'ready' ? '#e8f5e9' :
    props.status === 'can_setup' ? '#e3f2fd' :
    '#fff3e0'
  };
  color: ${props => 
    props.status === 'ready' ? '#2e7d32' :
    props.status === 'can_setup' ? '#1565c0' :
    '#e65100'
  };
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin: 16px 0;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  width: ${props => props.progress}%;
  transition: width 0.5s;
`;

const InfoText = styled.p`
  color: #666;
  font-size: 14px;
  line-height: 1.6;
  margin: 12px 0;
`;

const Button = styled.button`
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
  margin-top: 16px;
  
  &:hover {
    transform: translateY(-2px);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 16px;
`;

const StatItem = styled.div`
  text-align: center;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 8px;
  
  .value {
    font-size: 20px;
    font-weight: 700;
    color: #667eea;
  }
  
  .label {
    font-size: 11px;
    color: #999;
    margin-top: 4px;
  }
`;

const BehavioralRecoveryStatus = () => {
  const {
    isCapturing,
    profileStats,
    profileCompleteness,
    profileAge,
    recoveryReadiness,
    createCommitments
  } = useBehavioralRecovery();
  
  const [creating, setCreating] = useState(false);
  
  const handleSetupRecovery = async () => {
    setCreating(true);
    try {
      await createCommitments();
      alert('Behavioral recovery set up successfully!');
    } catch (error) {
      console.error('Error setting up recovery:', error);
      alert('Failed to set up behavioral recovery. Please try again.');
    } finally {
      setCreating(false);
    }
  };
  
  const getStatusIcon = () => {
    switch (recoveryReadiness.status) {
      case 'ready':
        return <FaCheckCircle />;
      case 'can_setup':
        return <FaBrain />;
      default:
        return <FaClock />;
    }
  };
  
  const getIconColor = () => {
    switch (recoveryReadiness.status) {
      case 'ready':
        return '#4caf50';
      case 'can_setup':
        return '#2196f3';
      default:
        return '#ff9800';
    }
  };
  
  return (
    <StatusCard status={recoveryReadiness.status}>
      <Header color={getIconColor()}>
        {getStatusIcon()}
        <h3>Behavioral Recovery</h3>
      </Header>
      
      <StatusBadge status={recoveryReadiness.status}>
        {recoveryReadiness.status === 'ready' && <FaCheckCircle />}
        {recoveryReadiness.status === 'can_setup' && <FaBrain />}
        {recoveryReadiness.status === 'building' && <FaClock />}
        {recoveryReadiness.message}
      </StatusBadge>
      
      {recoveryReadiness.status === 'building' && (
        <>
          <ProgressBar>
            <ProgressFill progress={profileCompleteness} />
          </ProgressBar>
          <InfoText>
            Your behavioral profile is being built silently in the background as you use the app.
            This enables advanced AI-powered password recovery using behavioral biometrics.
          </InfoText>
          
          {profileStats && (
            <Stats>
              <StatItem>
                <div className="value">{profileStats.samplesCollected || 0}</div>
                <div className="label">Samples</div>
              </StatItem>
              <StatItem>
                <div className="value">{profileAge}</div>
                <div className="label">Days</div>
              </StatItem>
              <StatItem>
                <div className="value">{(profileStats.qualityScore * 100).toFixed(0)}%</div>
                <div className="label">Quality</div>
              </StatItem>
            </Stats>
          )}
        </>
      )}
      
      {recoveryReadiness.status === 'can_setup' && (
        <>
          <InfoText>
            Your behavioral profile is ready! Set up behavioral recovery now to enable 
            AI-powered password recovery using your unique behavioral patterns.
          </InfoText>
          <Button onClick={handleSetupRecovery} disabled={creating}>
            {creating ? 'Setting up...' : 'Set Up Behavioral Recovery'}
          </Button>
        </>
      )}
      
      {recoveryReadiness.status === 'ready' && (
        <>
          <InfoText>
            ✅ Behavioral recovery is active. If you forget your password, you can recover 
            it by completing behavioral challenges that verify your identity through AI analysis.
          </InfoText>
          
          {profileStats && (
            <Stats>
              <StatItem>
                <div className="value">{profileStats.dimensionsCaptured || 247}</div>
                <div className="label">Dimensions</div>
              </StatItem>
              <StatItem>
                <div className="value">{profileAge}</div>
                <div className="label">Days Active</div>
              </StatItem>
              <StatItem>
                <div className="value">{(profileStats.qualityScore * 100).toFixed(0)}%</div>
                <div className="label">Profile Quality</div>
              </StatItem>
            </Stats>
          )}
        </>
      )}
    </StatusCard>
  );
};

export default BehavioralRecoveryStatus;


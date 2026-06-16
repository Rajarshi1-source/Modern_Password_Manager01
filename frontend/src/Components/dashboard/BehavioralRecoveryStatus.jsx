/**
 * Behavioral Recovery Status Component
 *
 * Displays behavioral recovery setup status in dashboard
 */

import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaBrain, FaCheckCircle, FaClock } from 'react-icons/fa';
import { useBehavioralRecovery } from '../../hooks/useBehavioralRecovery';

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

// Status accent colors
const statusColor = status =>
  status === 'ready' ? colors.success :
  status === 'can_setup' ? colors.primary :
  colors.warning;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const StatusCard = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.background} 100%);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(123, 104, 238, 0.08);
  border: 1px solid ${colors.border};
  border-left: 4px solid ${props => statusColor(props.status)};
  animation: ${fadeIn} 0.4s ease-out;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.15);
    border-color: ${colors.borderLight};
    border-left-color: ${props => statusColor(props.status)};
  }
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;

  svg {
    font-size: 28px;
    color: ${props => props.color || colors.primary};
  }

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    color: ${colors.text};
  }
`;

const StatusBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: ${props =>
    props.status === 'ready' ? '#ecfdf5' :
    props.status === 'can_setup' ? colors.background :
    '#fffbeb'
  };
  color: ${props =>
    props.status === 'ready' ? '#047857' :
    props.status === 'can_setup' ? colors.primaryDark :
    '#b45309'
  };
  border: 1px solid ${props =>
    props.status === 'ready' ? '#a7f3d0' :
    props.status === 'can_setup' ? colors.border :
    '#fde68a'
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
  background: ${colors.border};
  border-radius: 4px;
  overflow: hidden;
  margin: 16px 0;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  width: ${props => props.progress}%;
  transition: width 0.5s;
`;

const InfoText = styled.p`
  color: ${colors.textSecondary};
  font-size: 14px;
  line-height: 1.6;
  margin: 12px 0;
`;

const Button = styled.button`
  padding: 14px 24px;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px ${colors.primary}40;
  margin-top: 16px;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    box-shadow: none;
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
  background: ${colors.background};
  border: 1px solid ${colors.border};
  border-radius: 10px;

  .value {
    font-size: 20px;
    font-weight: 700;
    color: ${colors.primary};
  }

  .label {
    font-size: 11px;
    color: ${colors.textSecondary};
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

  const getIconColor = () => statusColor(recoveryReadiness.status);

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

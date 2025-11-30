/**
 * Toast Notification Component for Real-time Breach Alerts
 * Displays popup notifications when new breaches are detected
 */

import React, { useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaExclamationTriangle, FaShieldAlt, FaTimes } from 'react-icons/fa';

const slideInRight = keyframes`
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

const ToastContainer = styled.div`
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  animation: ${slideInRight} 0.3s ease-out;
`;

const ToastCard = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  border-left: 4px solid ${props => props.severityColor};
  width: 400px;
  max-width: calc(100vw - 40px);
  overflow: hidden;
`;

const ToastContent = styled.div`
  padding: 20px;
`;

const ToastHeader = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
`;

const IconWrapper = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: ${props => props.severityColor};
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    color: white;
    font-size: 20px;
  }
`;

const ToastHeaderContent = styled.div`
  flex: 1;
  min-width: 0;
`;

const ToastTitle = styled.h3`
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 4px 0;
`;

const ToastMessage = styled.p`
  font-size: 14px;
  color: #666;
  margin: 0;
  line-height: 1.4;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;

  &:hover {
    background: #f0f0f0;
    color: #666;
  }
`;

const ToastMetadata = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
`;

const SeverityBadge = styled.span`
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: ${props => props.severityColor};
  color: white;
`;

const ConfidenceBadge = styled.span`
  font-size: 12px;
  color: #666;
`;

const ToastButton = styled.button`
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  }

  &:active {
    transform: translateY(0);
  }
`;

const BreachToast = ({ alert, onClose, onViewDetails, autoCloseDelay = 8000 }) => {
  const severityConfig = {
    CRITICAL: {
      color: '#dc3545',
      icon: FaExclamationTriangle,
      text: 'Critical'
    },
    HIGH: {
      color: '#fd7e14',
      icon: FaExclamationTriangle,
      text: 'High'
    },
    MEDIUM: {
      color: '#ffc107',
      icon: FaShieldAlt,
      text: 'Medium'
    },
    LOW: {
      color: '#17a2b8',
      icon: FaShieldAlt,
      text: 'Low'
    }
  };

  const config = severityConfig[alert.severity] || severityConfig.MEDIUM;
  const Icon = config.icon;

  useEffect(() => {
    if (autoCloseDelay > 0) {
      const timer = setTimeout(() => {
        onClose();
      }, autoCloseDelay);

      return () => clearTimeout(timer);
    }
  }, [autoCloseDelay, onClose]);

  const handleViewDetails = () => {
    onClose();
    if (onViewDetails) {
      onViewDetails(alert);
    }
  };

  return (
    <ToastContainer>
      <ToastCard severityColor={config.color}>
        <ToastContent>
          <ToastHeader>
            <IconWrapper severityColor={config.color}>
              <Icon />
            </IconWrapper>
            
            <ToastHeaderContent>
              <ToastTitle>Security Breach Detected</ToastTitle>
              <ToastMessage>
                {alert.title || 'Your credentials may have been compromised in a recent data breach.'}
              </ToastMessage>
            </ToastHeaderContent>

            <CloseButton onClick={onClose} aria-label="Close notification">
              <FaTimes />
            </CloseButton>
          </ToastHeader>

          <ToastMetadata>
            <SeverityBadge severityColor={config.color}>
              {config.text} Severity
            </SeverityBadge>
            {alert.confidence && (
              <ConfidenceBadge>
                Confidence: {(alert.confidence * 100).toFixed(0)}%
              </ConfidenceBadge>
            )}
          </ToastMetadata>

          <ToastButton onClick={handleViewDetails}>
            View Details & Take Action
          </ToastButton>
        </ToastContent>
      </ToastCard>
    </ToastContainer>
  );
};

export default BreachToast;


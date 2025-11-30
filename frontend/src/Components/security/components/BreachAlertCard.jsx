/**
 * Individual Breach Alert Card Component
 * Displays breach information in a card format
 */

import React from 'react';
import styled from 'styled-components';
import { FaExclamationTriangle, FaExternalLinkAlt, FaEye, FaCheckCircle } from 'react-icons/fa';
import { formatDistanceToNow } from 'date-fns';

const CardContainer = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-left: 4px solid ${props => props.severityColor};
  padding: 24px;
  transition: all 0.3s ease;
  opacity: ${props => props.isRead ? 0.7 : 1};

  &:hover {
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }
`;

const CardContent = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
`;

const MainContent = styled.div`
  flex: 1;
  min-width: 0;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
`;

const Title = styled.h3`
  font-size: 18px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  flex: 1;
  min-width: 0;
`;

const UnreadIndicator = styled.span`
  width: 8px;
  height: 8px;
  background: #dc3545;
  border-radius: 50%;
  flex-shrink: 0;
`;

const SeverityBadge = styled.span`
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: ${props => props.severityColor};
  color: white;
  text-transform: uppercase;
`;

const Metadata = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #666;
  margin-bottom: 16px;
  flex-wrap: wrap;

  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
`;

const Divider = styled.span`
  color: #ccc;
`;

const Actions = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
`;

const Button = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;

  ${props => props.primary ? `
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
    }
  ` : `
    background: #f0f0f0;
    color: #333;

    &:hover {
      background: #e0e0e0;
    }
  `}

  &:active {
    transform: translateY(0);
  }
`;

const IconWrapper = styled.div`
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${props => props.color};
  font-size: 24px;
  flex-shrink: 0;
`;

const BreachAlertCard = ({ alert, onMarkRead, onViewDetails }) => {
  const severityColors = {
    CRITICAL: '#dc3545',
    HIGH: '#fd7e14',
    MEDIUM: '#ffc107',
    LOW: '#17a2b8'
  };

  const severityColor = severityColors[alert.severity] || severityColors.MEDIUM;
  const isHighPriority = alert.severity === 'CRITICAL' || alert.severity === 'HIGH';

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch (error) {
      return 'Recently';
    }
  };

  return (
    <CardContainer severityColor={severityColor} isRead={alert.is_read}>
      <CardContent>
        <MainContent>
          <Header>
            <Title>{alert.breach_title || 'Security Breach Detected'}</Title>
            {!alert.is_read && <UnreadIndicator />}
            <SeverityBadge severityColor={severityColor}>
              {alert.severity}
            </SeverityBadge>
          </Header>

          <Metadata>
            <span>Detected {formatDate(alert.detected_at)}</span>
            <Divider>•</Divider>
            <span>
              Match Confidence: {((alert.similarity_score || 0) * 100).toFixed(1)}%
            </span>
            {alert.domain && (
              <>
                <Divider>•</Divider>
                <span>{alert.domain}</span>
              </>
            )}
          </Metadata>

          <Actions>
            <Button primary onClick={() => onViewDetails(alert)}>
              <FaExternalLinkAlt />
              View Details
            </Button>
            
            {!alert.is_read && (
              <Button onClick={() => onMarkRead(alert.id)}>
                <FaEye />
                Mark as Read
              </Button>
            )}
            
            {alert.is_read && (
              <Button>
                <FaCheckCircle />
                Reviewed
              </Button>
            )}
          </Actions>
        </MainContent>

        <IconWrapper color={isHighPriority ? '#dc3545' : '#ffc107'}>
          <FaExclamationTriangle />
        </IconWrapper>
      </CardContent>
    </CardContainer>
  );
};

export default BreachAlertCard;


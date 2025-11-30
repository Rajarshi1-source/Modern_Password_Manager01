/**
 * Breach Details Modal Component
 * Shows comprehensive information about a specific breach
 */

import React from 'react';
import styled from 'styled-components';
import { FaTimes, FaExclamationTriangle, FaShieldAlt, FaKey, FaCheck } from 'react-icons/fa';
import { format } from 'date-fns';

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
  backdrop-filter: blur(4px);
`;

const ModalContainer = styled.div`
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
`;

const ModalHeader = styled.div`
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  padding: 24px;
  color: white;
`;

const HeaderTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
`;

const ModalTitle = styled.h2`
  font-size: 24px;
  font-weight: 700;
  margin: 0;
`;

const CloseButton = styled.button`
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  svg {
    font-size: 20px;
  }
`;

const ModalBody = styled.div`
  padding: 24px;
  overflow-y: auto;
  flex: 1;
`;

const Section = styled.div`
  margin-bottom: 24px;

  &:last-child {
    margin-bottom: 0;
  }
`;

const SectionTitle = styled.h3`
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 12px 0;
`;

const SectionContent = styled.p`
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  margin: 0;
`;

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
`;

const InfoCard = styled.div`
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
`;

const InfoLabel = styled.p`
  font-size: 12px;
  color: #666;
  margin: 0 0 8px 0;
  text-transform: uppercase;
  font-weight: 600;
`;

const InfoValue = styled.p`
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
`;

const Badge = styled.span`
  display: inline-block;
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 600;
  background: ${props => props.color};
  color: white;
`;

const RecommendationsBox = styled.div`
  background: #fff3cd;
  border: 2px solid #ffc107;
  border-radius: 12px;
  padding: 20px;
`;

const RecommendationsTitle = styled.h4`
  font-size: 16px;
  font-weight: 700;
  color: #856404;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const RecommendationsList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const RecommendationItem = styled.li`
  font-size: 14px;
  color: #856404;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  line-height: 1.5;

  svg {
    color: #ffc107;
    flex-shrink: 0;
    margin-top: 2px;
  }
`;

const ModalFooter = styled.div`
  border-top: 1px solid #e0e0e0;
  padding: 20px 24px;
  background: #f8f9fa;
`;

const FooterButton = styled.button`
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
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

const BreachDetailModal = ({ alert, onClose }) => {
  if (!alert) return null;

  const severityColors = {
    CRITICAL: '#dc3545',
    HIGH: '#fd7e14',
    MEDIUM: '#ffc107',
    LOW: '#17a2b8'
  };

  const formatDate = (dateString) => {
    try {
      return format(new Date(dateString), 'MMM dd, yyyy • hh:mm a');
    } catch {
      return 'Unknown';
    }
  };

  const recommendations = [
    'Change your password immediately for this account',
    'Enable two-factor authentication (2FA) if not already enabled',
    'Check for any unauthorized access or suspicious activity',
    'Update passwords on any other accounts using the same credentials',
    'Monitor your accounts closely for the next few weeks',
    'Consider using a password manager for unique, strong passwords'
  ];

  return (
    <Overlay onClick={onClose}>
      <ModalContainer onClick={(e) => e.stopPropagation()}>
        <ModalHeader>
          <HeaderTop>
            <ModalTitle>Breach Details</ModalTitle>
            <CloseButton onClick={onClose} aria-label="Close modal">
              <FaTimes />
            </CloseButton>
          </HeaderTop>
        </ModalHeader>

        <ModalBody>
          <Section>
            <SectionTitle>Breach Information</SectionTitle>
            <SectionContent>
              {alert.breach_description || alert.breach_title || 'Your credentials have been found in a data breach. Immediate action is required to secure your account.'}
            </SectionContent>
          </Section>

          <Section>
            <InfoGrid>
              <InfoCard>
                <InfoLabel>Severity Level</InfoLabel>
                <Badge color={severityColors[alert.severity] || severityColors.MEDIUM}>
                  {alert.severity}
                </Badge>
              </InfoCard>

              <InfoCard>
                <InfoLabel>Match Confidence</InfoLabel>
                <InfoValue>
                  {((alert.similarity_score || alert.confidence_score || 0) * 100).toFixed(1)}%
                </InfoValue>
              </InfoCard>

              {alert.detected_at && (
                <InfoCard>
                  <InfoLabel>Detected At</InfoLabel>
                  <InfoValue style={{ fontSize: '14px' }}>
                    {formatDate(alert.detected_at)}
                  </InfoValue>
                </InfoCard>
              )}

              {alert.domain && (
                <InfoCard>
                  <InfoLabel>Affected Domain</InfoLabel>
                  <InfoValue style={{ fontSize: '14px' }}>
                    {alert.domain}
                  </InfoValue>
                </InfoCard>
              )}
            </InfoGrid>
          </Section>

          <Section>
            <RecommendationsBox>
              <RecommendationsTitle>
                <FaExclamationTriangle />
                Recommended Actions
              </RecommendationsTitle>
              <RecommendationsList>
                {recommendations.map((rec, index) => (
                  <RecommendationItem key={index}>
                    <FaShieldAlt />
                    <span>{rec}</span>
                  </RecommendationItem>
                ))}
              </RecommendationsList>
            </RecommendationsBox>
          </Section>
        </ModalBody>

        <ModalFooter>
          <FooterButton onClick={onClose}>
            <FaCheck /> Got It, I'll Take Action
          </FooterButton>
        </ModalFooter>
      </ModalContainer>
    </Overlay>
  );
};

export default BreachDetailModal;


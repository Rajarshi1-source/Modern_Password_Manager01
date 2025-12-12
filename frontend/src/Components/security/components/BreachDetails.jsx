import React from 'react';
import styled from 'styled-components';
import { FaTimes, FaExclamationTriangle } from 'react-icons/fa';

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
`;

const ModalContainer = styled.div`
  background: ${props => props.theme.cardBg || '#fff'};
  border-radius: 12px;
  max-width: 450px;
  width: calc(100% - 32px);
  margin: 16px;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideIn 0.3s ease-out;
  
  @keyframes slideIn {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
`;

const Title = styled.h2`
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const CloseButton = styled.button`
  background: ${props => props.theme.backgroundSecondary || '#f0f0f0'};
  border: none;
  color: ${props => props.theme.textSecondary || '#666'};
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => props.theme.danger || '#ef4444'};
    color: white;
  }
`;

const Content = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const BreachName = styled.h3`
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const Description = styled.p`
  font-size: 14px;
  color: ${props => props.theme.textSecondary || '#666'};
  line-height: 1.5;
  margin: 0;
`;

const InfoRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const InfoLabel = styled.span`
  font-size: 14px;
  font-weight: 500;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const InfoValue = styled.span`
  font-size: 14px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const SeverityBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  
  ${props => {
    switch(props.$severity) {
      case 'high':
      case 'critical':
        return `
          background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
          color: #dc2626;
        `;
      case 'medium':
        return `
          background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
          color: #d97706;
        `;
      default:
        return `
          background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
          color: #059669;
        `;
    }
  }}
`;

const ExposedDataContainer = styled.div`
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 8px;
  padding: 12px 16px;
`;

const ExposedDataLabel = styled.span`
  font-size: 12px;
  font-weight: 600;
  color: ${props => props.theme.textSecondary || '#666'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
  margin-bottom: 8px;
`;

const ExposedDataList = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const Footer = styled.div`
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
`;

const CloseButtonLarge = styled.button`
  padding: 10px 20px;
  background: ${props => props.theme.primary || '#7B68EE'};
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => props.theme.primaryDark || '#6B58DE'};
    transform: translateY(-1px);
  }
  
  &:active {
    transform: translateY(0);
  }
`;

const BreachDetails = ({ breach, onClose }) => {
  if (!breach) return null;

  return (
    <Overlay onClick={onClose}>
      <ModalContainer onClick={(e) => e.stopPropagation()}>
        <Header>
          <Title>Breach Details</Title>
          <CloseButton onClick={onClose} aria-label="Close">
            <FaTimes />
          </CloseButton>
        </Header>
        
        <Content>
          <div>
            <BreachName>{breach.breach_name}</BreachName>
            <Description>{breach.breach_description}</Description>
          </div>
          
          {breach.breach_date && (
            <InfoRow>
              <InfoLabel>Date:</InfoLabel>
              <InfoValue>
                {new Date(breach.breach_date).toLocaleDateString()}
              </InfoValue>
            </InfoRow>
          )}
          
          <InfoRow>
            <InfoLabel>Severity:</InfoLabel>
            <SeverityBadge $severity={breach.severity}>
              <FaExclamationTriangle />
              {breach.severity}
            </SeverityBadge>
          </InfoRow>
          
          {breach.exposed_data && Object.keys(breach.exposed_data).length > 0 && (
            <ExposedDataContainer>
              <ExposedDataLabel>Exposed Data</ExposedDataLabel>
              <ExposedDataList>
                {Object.keys(breach.exposed_data).join(', ')}
              </ExposedDataList>
            </ExposedDataContainer>
          )}
        </Content>
        
        <Footer>
          <CloseButtonLarge onClick={onClose}>
            Close
          </CloseButtonLarge>
        </Footer>
      </ModalContainer>
    </Overlay>
  );
};

export default BreachDetails;

import React from 'react';
import styled from 'styled-components';
import { motion } from 'framer-motion';
import { FaExclamationTriangle, FaCheckCircle, FaTimes } from 'react-icons/fa';
import { formatDistanceToNow } from 'date-fns';

const AlertContainer = styled(motion.div)`
  background: ${props => props.theme.dangerLight};
  border-left: 4px solid ${props => props.theme.danger};
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 16px;
  position: relative;
`;

const AlertHeader = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: ${props => props.expanded ? '12px' : '0'};
`;

const AlertTitle = styled.h3`
  margin: 0;
  color: ${props => props.theme.danger};
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const AlertContent = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textPrimary};
`;

const AlertMeta = styled.div`
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
`;

const AlertActions = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
`;

const Button = styled.button`
  background: ${props => props.primary ? props.theme.danger : 'transparent'};
  color: ${props => props.primary ? 'white' : props.theme.textPrimary};
  border: 1px solid ${props => props.primary ? 'transparent' : props.theme.borderColor};
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  
  &:hover {
    background: ${props => props.primary ? props.theme.dangerDark : props.theme.backgroundHover};
  }
`;

const CloseButton = styled.button`
  position: absolute;
  top: 12px;
  right: 12px;
  background: transparent;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  
  &:hover {
    color: ${props => props.theme.textPrimary};
  }
`;

const ExposedData = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
`;

const DataTag = styled.span`
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 12px;
`;

const BreachAlert = ({ 
  alert, 
  onResolve, 
  onFix, 
  onDismiss, 
  onViewDetails 
}) => {
  const exposedDataList = alert.exposed_data.split(',');
  
  return (
    <AlertContainer
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
    >
      <CloseButton onClick={onDismiss}>
        <FaTimes />
      </CloseButton>
      
      <AlertHeader>
        <AlertTitle>
          <FaExclamationTriangle /> {alert.breach_name} Data Breach
        </AlertTitle>
      </AlertHeader>
      
      <AlertContent>
        {alert.data_type === 'email' && (
          <p>Your email ({alert.identifier}) was found in the {alert.breach_name} data breach.</p>
        )}
        
        {alert.data_type === 'password' && (
          <p>Your password for {alert.identifier} was exposed in a data breach.</p>
        )}
        
        <p>The following information may have been exposed:</p>
        
        <ExposedData>
          {exposedDataList.map((data, index) => (
            <DataTag key={index}>{data.trim()}</DataTag>
          ))}
        </ExposedData>
      </AlertContent>
      
      <AlertMeta>
        <span>Breach date: {new Date(alert.breach_date).toLocaleDateString()}</span>
        <span>Detected {formatDistanceToNow(new Date(alert.detected_at))} ago</span>
      </AlertMeta>
      
      <AlertActions>
        <Button onClick={onViewDetails}>View Details</Button>
        <Button primary onClick={onFix}>
          {alert.data_type === 'password' ? 'Change Password' : 'Take Action'}
        </Button>
        <Button onClick={onResolve}>
          <FaCheckCircle /> Mark Resolved
        </Button>
      </AlertActions>
    </AlertContainer>
  );
};

export default BreachAlert;

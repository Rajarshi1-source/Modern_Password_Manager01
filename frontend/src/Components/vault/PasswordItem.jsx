import React, { useState } from 'react';
import styled from 'styled-components';
import { FaEye, FaEyeSlash, FaCopy, FaExternalLinkAlt } from 'react-icons/fa';
import { copyToClipboard } from '../../utils/clipboard';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Field = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const FieldLabel = styled.span`
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
`;

const FieldValue = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: ${props => props.monospace ? "'Courier New', monospace" : 'inherit'};
  font-size: 14px;
`;

const ActionButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 4px;
  
  &:hover {
    color: ${props => props.theme.accent};
  }
`;

const ProtectedValue = styled.span`
  letter-spacing: ${props => props.visible ? 'normal' : '0.15em'};
`;

const PasswordItem = ({ data, isDecrypted = true }) => {
  const [passwordVisible, setPasswordVisible] = useState(false);
  
  const handleCopy = (text, label) => {
    if (!isDecrypted) {
      alert('Please decrypt the item first');
      return;
    }
    copyToClipboard(text);
    // Show toast notification
    alert(`Copied ${label} to clipboard`);
  };

  const togglePasswordVisibility = () => {
    if (!isDecrypted) {
      alert('Please decrypt the item first');
      return;
    }
    setPasswordVisible(!passwordVisible);
  };

  const openWebsite = () => {
    if (data.url) {
      window.open(data.url, '_blank', 'noopener,noreferrer');
    }
  };
  
  if (!isDecrypted) {
    return (
      <Container>
        <div style={{ textAlign: 'center', color: '#999', padding: '20px' }}>
          Click to decrypt this item
        </div>
      </Container>
    );
  }

  return (
    <Container>
      {data.username && (
        <Field>
          <FieldLabel>Username</FieldLabel>
          <FieldValue>
            {data.username}
            <ActionButton onClick={() => handleCopy(data.username, 'username')}>
              <FaCopy />
            </ActionButton>
          </FieldValue>
        </Field>
      )}
      
      <Field>
        <FieldLabel>Password</FieldLabel>
        <FieldValue monospace>
          <ProtectedValue visible={passwordVisible}>
            {passwordVisible ? data.password : '••••••••••••'}
          </ProtectedValue>
          <ActionButton onClick={togglePasswordVisibility}>
            {passwordVisible ? <FaEyeSlash /> : <FaEye />}
          </ActionButton>
          <ActionButton onClick={() => handleCopy(data.password, 'password')}>
            <FaCopy />
          </ActionButton>
        </FieldValue>
      </Field>
      
      {data.url && (
        <Field>
          <FieldLabel>Website</FieldLabel>
          <FieldValue>
            {data.url}
            <ActionButton onClick={() => handleCopy(data.url, 'URL')}>
              <FaCopy />
            </ActionButton>
            <ActionButton onClick={openWebsite}>
              <FaExternalLinkAlt />
            </ActionButton>
          </FieldValue>
        </Field>
      )}
      
      {data.notes && (
        <Field>
          <FieldLabel>Notes</FieldLabel>
          <FieldValue>{data.notes}</FieldValue>
        </Field>
      )}
    </Container>
  );
};

export default PasswordItem;

import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaEye, FaEyeSlash, FaCopy, FaExternalLinkAlt, FaCheckCircle, FaUser, FaLock, FaGlobe, FaStickyNote } from 'react-icons/fa';
import { copyToClipboard } from '../../utils/clipboard';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  background: '#ffffff',
  backgroundSecondary: '#f8f9ff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: ${fadeIn} 0.3s ease-out;
`;

const Field = styled.div`
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.25s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    background: ${colors.background};
  }
`;

const FieldInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
`;

const FieldIcon = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 14px;
    color: ${colors.primary};
  }
`;

const FieldContent = styled.div`
  flex: 1;
  min-width: 0;
`;

const FieldLabel = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: ${colors.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
  margin-bottom: 4px;
`;

const FieldValue = styled.div`
  font-size: 14px;
  font-weight: 500;
  color: ${colors.text};
  font-family: ${props => props.$monospace ? "'JetBrains Mono', 'Fira Code', monospace" : 'inherit'};
  letter-spacing: ${props => props.$monospace ? '0.5px' : 'normal'};
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const Actions = styled.div`
  display: flex;
  gap: 4px;
  margin-left: 12px;
`;

const ActionButton = styled.button`
  background: transparent;
  border: none;
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    color: ${colors.primary};
    background: ${colors.border};
  }
  
  &.success {
    color: ${colors.success};
  }
`;

const CopiedBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: ${colors.success};
  font-weight: 600;
  padding: 4px 8px;
  background: ${colors.success}15;
  border-radius: 6px;
  animation: ${fadeIn} 0.2s ease;
`;

const EncryptedState = styled.div`
  text-align: center;
  padding: 32px 20px;
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.border}30 100%);
  border-radius: 14px;
  border: 2px dashed ${colors.border};
`;

const EncryptedIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
  
  svg {
    font-size: 24px;
    color: ${colors.primary};
  }
`;

const EncryptedText = styled.p`
  color: ${colors.textSecondary};
  font-size: 14px;
  margin: 0;
`;

const NotesField = styled.div`
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  border-radius: 12px;
  padding: 14px 16px;
  transition: all 0.25s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    background: ${colors.background};
  }
`;

const NotesHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
`;

const NotesContent = styled.div`
  font-size: 14px;
  color: ${colors.text};
  line-height: 1.6;
  white-space: pre-wrap;
`;

const PasswordItem = ({ data, isDecrypted = true }) => {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [copiedField, setCopiedField] = useState(null);
  
  const handleCopy = (text, label) => {
    if (!isDecrypted) {
      alert('Please decrypt the item first');
      return;
    }
    copyToClipboard(text);
    setCopiedField(label);
    setTimeout(() => setCopiedField(null), 2000);
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
        <EncryptedState>
          <EncryptedIcon>
            <FaLock />
          </EncryptedIcon>
          <EncryptedText>Click to decrypt this item</EncryptedText>
        </EncryptedState>
      </Container>
    );
  }

  return (
    <Container>
      {data.username && (
        <Field>
          <FieldInfo>
            <FieldIcon>
              <FaUser />
            </FieldIcon>
            <FieldContent>
              <FieldLabel>Username</FieldLabel>
              <FieldValue>{data.username}</FieldValue>
            </FieldContent>
          </FieldInfo>
          <Actions>
            {copiedField === 'username' ? (
              <CopiedBadge><FaCheckCircle /> Copied</CopiedBadge>
            ) : (
              <ActionButton onClick={() => handleCopy(data.username, 'username')}>
                <FaCopy />
              </ActionButton>
            )}
          </Actions>
        </Field>
      )}
      
      <Field>
        <FieldInfo>
          <FieldIcon>
            <FaLock />
          </FieldIcon>
          <FieldContent>
            <FieldLabel>Password</FieldLabel>
            <FieldValue $monospace>
              {passwordVisible ? data.password : '••••••••••••'}
            </FieldValue>
          </FieldContent>
        </FieldInfo>
        <Actions>
          <ActionButton onClick={togglePasswordVisibility}>
            {passwordVisible ? <FaEyeSlash /> : <FaEye />}
          </ActionButton>
          {copiedField === 'password' ? (
            <CopiedBadge><FaCheckCircle /> Copied</CopiedBadge>
          ) : (
            <ActionButton onClick={() => handleCopy(data.password, 'password')}>
              <FaCopy />
            </ActionButton>
          )}
        </Actions>
      </Field>
      
      {data.url && (
        <Field>
          <FieldInfo>
            <FieldIcon>
              <FaGlobe />
            </FieldIcon>
            <FieldContent>
              <FieldLabel>Website</FieldLabel>
              <FieldValue>{data.url}</FieldValue>
            </FieldContent>
          </FieldInfo>
          <Actions>
            {copiedField === 'url' ? (
              <CopiedBadge><FaCheckCircle /> Copied</CopiedBadge>
            ) : (
              <ActionButton onClick={() => handleCopy(data.url, 'url')}>
                <FaCopy />
              </ActionButton>
            )}
            <ActionButton onClick={openWebsite}>
              <FaExternalLinkAlt />
            </ActionButton>
          </Actions>
        </Field>
      )}
      
      {data.notes && (
        <NotesField>
          <NotesHeader>
            <FieldIcon>
              <FaStickyNote />
            </FieldIcon>
            <FieldLabel style={{ marginBottom: 0 }}>Notes</FieldLabel>
          </NotesHeader>
          <NotesContent>{data.notes}</NotesContent>
        </NotesField>
      )}
    </Container>
  );
};

export default PasswordItem;

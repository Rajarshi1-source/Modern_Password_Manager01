import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaEye, FaEyeSlash, FaCopy, FaPen, FaTrash, FaExclamationTriangle, FaLock } from 'react-icons/fa';
import { useVault } from '../../contexts/VaultContext';
import { formatDate } from '../../utils/dateUtils';
import { passwordStrength } from '../../utils/passwordUtils';

const Container = styled.div`
  background: ${props => props.theme.cardBg};
  border-radius: 12px;
  padding: 24px;
  max-width: 500px;
  width: 100%;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid ${props => props.theme.borderColor};
  padding-bottom: 16px;
`;

const Title = styled.h2`
  margin: 0;
  font-size: 20px;
`;

const Actions = styled.div`
  display: flex;
  gap: 12px;
`;

const ActionButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 8px;
  font-size: 16px;
  border-radius: 4px;
  
  &:hover {
    color: ${props => props.theme.primary};
    background: ${props => props.theme.bgHover};
  }
`;

const FieldGroup = styled.div`
  margin-bottom: 16px;
`;

const FieldLabel = styled.div`
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
  margin-bottom: 4px;
`;

const FieldValue = styled.div`
  font-size: 14px;
  padding: 8px 12px;
  background: ${props => props.theme.inputBg};
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const PasswordStrengthBar = styled.div`
  height: 4px;
  width: 100%;
  background: ${props => props.theme.bgLight};
  border-radius: 2px;
  margin-top: 8px;
  overflow: hidden;
`;

const StrengthIndicator = styled.div`
  height: 100%;
  width: ${props => props.$strength}%;
  background: ${props => {
    if (props.$strength < 30) return '#FF4136'; // Weak
    if (props.$strength < 70) return '#FFDC00'; // Medium
    return '#2ECC40'; // Strong
  }};
  transition: width 0.3s;
`;

const PasswordWarning = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px;
  background: #FFF3CD;
  color: #856404;
  border-radius: 4px;
  font-size: 12px;
`;

const Footer = styled.div`
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid ${props => props.theme.borderColor};
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
  display: flex;
  justify-content: space-between;
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 16px;
`;

const LoadingSpinner = styled.div`
  border: 3px solid ${props => props.theme.borderColor};
  border-top: 3px solid ${props => props.theme.accent};
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const ErrorContainer = styled.div`
  background: #fee;
  border: 1px solid #fcc;
  border-radius: 8px;
  padding: 16px;
  color: #c33;
  text-align: center;
`;

const DecryptButton = styled.button`
  background: ${props => props.theme.accent};
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 24px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  
  &:hover {
    opacity: 0.9;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const VaultItemDetail = ({ item, onEdit, onDelete }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [currentItem, setCurrentItem] = useState(item);
  const [isDecrypting, setIsDecrypting] = useState(false);
  const [decryptError, setDecryptError] = useState(null);
  const { decryptItem } = useVault();
  
  const isLazyLoaded = item._lazyLoaded && !item._decrypted;
  
  // Decrypt item on mount if lazy-loaded
  useEffect(() => {
    if (isLazyLoaded && decryptItem) {
      handleDecrypt();
    }
  }, [item.item_id]);
  
  const handleDecrypt = async () => {
    setIsDecrypting(true);
    setDecryptError(null);
    try {
      const decrypted = await decryptItem(item.item_id);
      setCurrentItem(decrypted);
    } catch (error) {
      console.error('Failed to decrypt item:', error);
      setDecryptError(error.message || 'Failed to decrypt item');
    } finally {
      setIsDecrypting(false);
    }
  };
  
  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    // Show toast notification
  };
  
  // Show loading state
  if (isDecrypting) {
    return (
      <Container>
        <LoadingContainer>
          <LoadingSpinner />
          <div>Decrypting item...</div>
        </LoadingContainer>
      </Container>
    );
  }
  
  // Show error state
  if (decryptError) {
    return (
      <Container>
        <ErrorContainer>
          <FaExclamationTriangle size={24} />
          <div style={{ marginTop: '8px' }}>{decryptError}</div>
          <DecryptButton onClick={handleDecrypt} style={{ margin: '16px auto 0' }}>
            Try Again
          </DecryptButton>
        </ErrorContainer>
      </Container>
    );
  }
  
  // Render different details based on item type
  const renderDetailsForType = () => {
    const type = currentItem.type || currentItem.item_type;
    switch(type) {
      case 'password':
        const strength = passwordStrength(currentItem.data.password);
        
        return (
          <>
            {currentItem.data.url && (
              <FieldGroup>
                <FieldLabel>Website</FieldLabel>
                <FieldValue>{currentItem.data.url}</FieldValue>
              </FieldGroup>
            )}
            
            <FieldGroup>
              <FieldLabel>Username</FieldLabel>
              <FieldValue>
                {currentItem.data.username || currentItem.data.email}
                <FaCopy onClick={() => handleCopy(currentItem.data.username || currentItem.data.email)} />
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Password</FieldLabel>
              <FieldValue>
                {showPassword ? currentItem.data.password : '••••••••••••'}
                <div>
                  <ActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </ActionButton>
                  <ActionButton onClick={() => handleCopy(currentItem.data.password)}>
                    <FaCopy />
                  </ActionButton>
                </div>
              </FieldValue>
              
              <PasswordStrengthBar>
                <StrengthIndicator $strength={strength.score} />
              </PasswordStrengthBar>
              
              {strength.warnings.length > 0 && (
                <PasswordWarning>
                  <FaExclamationTriangle /> {strength.warnings[0]}
                </PasswordWarning>
              )}
            </FieldGroup>
            
            {currentItem.data.notes && (
              <FieldGroup>
                <FieldLabel>Notes</FieldLabel>
                <FieldValue>{currentItem.data.notes}</FieldValue>
              </FieldGroup>
            )}
          </>
        );
        
      case 'card':
        return (
          <>
            <FieldGroup>
              <FieldLabel>Cardholder Name</FieldLabel>
              <FieldValue>{currentItem.data.cardholderName}</FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Card Number</FieldLabel>
              <FieldValue>
                {showPassword ? currentItem.data.cardNumber : 
                  '•••• •••• •••• ' + currentItem.data.cardNumber.slice(-4)}
                <div>
                  <ActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </ActionButton>
                  <ActionButton onClick={() => handleCopy(currentItem.data.cardNumber)}>
                    <FaCopy />
                  </ActionButton>
                </div>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Expiration Date</FieldLabel>
              <FieldValue>{currentItem.data.expirationMonth}/{currentItem.data.expirationYear}</FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>CVV</FieldLabel>
              <FieldValue>
                {showPassword ? currentItem.data.cvv : '•••'}
                <div>
                  <ActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </ActionButton>
                </div>
              </FieldValue>
            </FieldGroup>
          </>
        );
        
      case 'identity':
        return (
          <>
            <FieldGroup>
              <FieldLabel>Full Name</FieldLabel>
              <FieldValue>{currentItem.data.fullName}</FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Email</FieldLabel>
              <FieldValue>
                {currentItem.data.email}
                <FaCopy onClick={() => handleCopy(currentItem.data.email)} />
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Phone</FieldLabel>
              <FieldValue>{currentItem.data.phone}</FieldValue>
            </FieldGroup>
            
            <FieldGroup>
              <FieldLabel>Address</FieldLabel>
              <FieldValue>
                {currentItem.data.address}<br />
                {currentItem.data.city}, {currentItem.data.state} {currentItem.data.zipCode}<br />
                {currentItem.data.country}
              </FieldValue>
            </FieldGroup>
          </>
        );
        
      case 'note':
        return (
          <FieldGroup>
            <FieldLabel>Secure Note</FieldLabel>
            <FieldValue style={{ whiteSpace: 'pre-wrap', minHeight: '150px' }}>
              {currentItem.data.note}
            </FieldValue>
          </FieldGroup>
        );
        
      default:
        return null;
    }
  };
  
  return (
    <Container>
      <Header>
        <Title>{currentItem.data?.name || currentItem.data?.title || 'Unnamed Item'}</Title>
        <Actions>
          <ActionButton onClick={() => onEdit(currentItem)}>
            <FaPen />
          </ActionButton>
          <ActionButton onClick={() => onDelete(currentItem.id)}>
            <FaTrash />
          </ActionButton>
        </Actions>
      </Header>
      
      {renderDetailsForType()}
      
      <Footer>
        <span>Created: {formatDate(currentItem.created_at)}</span>
        <span>Updated: {formatDate(currentItem.updated_at)}</span>
      </Footer>
    </Container>
  );
};

export default VaultItemDetail;
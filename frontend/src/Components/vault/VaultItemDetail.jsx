import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaEye, FaEyeSlash, FaCopy, FaPen, FaTrash, FaExclamationTriangle, FaLock, FaCheckCircle, FaGlobe, FaUser, FaCreditCard, FaIdCard, FaStickyNote, FaCalendar, FaSync } from 'react-icons/fa';
import { useVault } from '../../contexts/VaultContext';
import { formatDate } from '../../utils/dateUtils';
import { passwordStrength } from '../../utils/passwordUtils';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

// Colors
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#ffffff',
  backgroundSecondary: '#f8f9ff',
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.backgroundSecondary} 100%);
  border-radius: 20px;
  padding: 28px;
  max-width: 520px;
  width: 100%;
  box-shadow: 0 8px 32px rgba(123, 104, 238, 0.12);
  border: 1px solid ${colors.border};
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${colors.border};
`;

const TitleSection = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const TypeIconBadge = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 22px;
    color: ${colors.primary};
  }
`;

const TitleContent = styled.div``;

const Title = styled.h2`
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 700;
  color: ${colors.text};
`;

const TypeLabel = styled.span`
  font-size: 13px;
  color: ${colors.textSecondary};
  text-transform: capitalize;
`;

const Actions = styled.div`
  display: flex;
  gap: 8px;
`;

const ActionButton = styled.button`
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 10px;
  font-size: 15px;
  border-radius: 10px;
  transition: all 0.25s ease;
  
  &:hover {
    color: ${colors.primary};
    background: ${colors.border};
    border-color: ${colors.borderLight};
    transform: translateY(-2px);
  }
  
  &.danger:hover {
    color: ${colors.danger};
    background: #fff5f5;
    border-color: #fed7d7;
  }
`;

const FieldGroup = styled.div`
  margin-bottom: 16px;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$delay || '0s'};
  animation-fill-mode: backwards;
`;

const FieldLabel = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: ${colors.textSecondary};
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 6px;
  
  svg {
    font-size: 12px;
    color: ${colors.primary};
  }
`;

const FieldValue = styled.div`
  font-size: 15px;
  padding: 14px 16px;
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.25s ease;
  color: ${colors.text};
  
  &:hover {
    border-color: ${colors.borderLight};
    background: #ffffff;
  }
`;

const ValueText = styled.span`
  flex: 1;
  word-break: break-word;
  font-family: ${props => props.$monospace ? "'JetBrains Mono', 'Fira Code', monospace" : 'inherit'};
  letter-spacing: ${props => props.$monospace ? '0.5px' : 'normal'};
`;

const ValueActions = styled.div`
  display: flex;
  gap: 4px;
  margin-left: 12px;
`;

const SmallActionButton = styled.button`
  background: transparent;
  border: none;
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 8px;
  font-size: 14px;
  border-radius: 8px;
  transition: all 0.2s ease;
  
  &:hover {
    color: ${colors.primary};
    background: ${colors.border};
  }
`;

const CopiedToast = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: ${colors.success};
  font-weight: 600;
  animation: ${fadeIn} 0.2s ease;
`;

const PasswordStrengthBar = styled.div`
  height: 6px;
  width: 100%;
  background: ${colors.border};
  border-radius: 3px;
  margin-top: 10px;
  overflow: hidden;
`;

const StrengthIndicator = styled.div`
  height: 100%;
  width: ${props => props.$strength}%;
  background: ${props => {
    if (props.$strength < 30) return `linear-gradient(90deg, ${colors.danger} 0%, #f87171 100%)`;
    if (props.$strength < 70) return `linear-gradient(90deg, ${colors.warning} 0%, #fbbf24 100%)`;
    return `linear-gradient(90deg, ${colors.success} 0%, #34d399 100%)`;
  }};
  border-radius: 3px;
  transition: width 0.5s ease;
`;

const StrengthLabel = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
`;

const StrengthText = styled.span`
  font-weight: 600;
  color: ${props => {
    if (props.$strength < 30) return colors.danger;
    if (props.$strength < 70) return colors.warning;
    return colors.success;
  }};
`;

const PasswordWarning = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, ${colors.warning}15 0%, ${colors.warning}08 100%);
  border-left: 3px solid ${colors.warning};
  border-radius: 0 10px 10px 0;
  font-size: 13px;
  color: ${colors.text};
  
  svg {
    color: ${colors.warning};
    flex-shrink: 0;
  }
`;

const Footer = styled.div`
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid ${colors.border};
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const FooterItem = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: ${colors.textSecondary};
  
  svg {
    font-size: 12px;
    color: ${colors.primary};
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  gap: 20px;
`;

const LoadingSpinner = styled.div`
  width: 48px;
  height: 48px;
  border: 3px solid ${colors.border};
  border-top: 3px solid ${colors.primary};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`;

const LoadingText = styled.div`
  font-size: 15px;
  color: ${colors.textSecondary};
  font-weight: 500;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

const ErrorContainer = styled.div`
  background: linear-gradient(135deg, ${colors.danger}10 0%, ${colors.danger}05 100%);
  border: 1px solid ${colors.danger}30;
  border-radius: 16px;
  padding: 32px 24px;
  text-align: center;
`;

const ErrorIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: ${colors.danger}15;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 24px;
    color: ${colors.danger};
  }
`;

const ErrorText = styled.div`
  font-size: 15px;
  color: ${colors.text};
  margin-bottom: 20px;
`;

const RetryButton = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 10px;
  padding: 12px 24px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.25s ease;
  box-shadow: 0 4px 14px ${colors.primary}40;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }
`;

const VaultItemDetail = ({ item, onEdit, onDelete }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [currentItem, setCurrentItem] = useState(item);
  const [isDecrypting, setIsDecrypting] = useState(false);
  const [decryptError, setDecryptError] = useState(null);
  const [copiedField, setCopiedField] = useState(null);
  const { decryptItem } = useVault();
  
  const isLazyLoaded = item._lazyLoaded && !item._decrypted;
  
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
  
  const handleCopy = (text, fieldName) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };
  
  const getTypeIcon = () => {
    const type = currentItem.type || currentItem.item_type;
    switch(type) {
      case 'password': return <FaLock />;
      case 'card': return <FaCreditCard />;
      case 'identity': return <FaIdCard />;
      case 'note': return <FaStickyNote />;
      default: return <FaLock />;
    }
  };
  
  const getStrengthLabel = (score) => {
    if (score < 30) return 'Weak';
    if (score < 70) return 'Medium';
    return 'Strong';
  };

  if (isDecrypting) {
    return (
      <Container>
        <LoadingContainer>
          <LoadingSpinner />
          <LoadingText>Decrypting item...</LoadingText>
        </LoadingContainer>
      </Container>
    );
  }
  
  if (decryptError) {
    return (
      <Container>
        <ErrorContainer>
          <ErrorIcon>
            <FaExclamationTriangle />
          </ErrorIcon>
          <ErrorText>{decryptError}</ErrorText>
          <RetryButton onClick={handleDecrypt}>
            <FaSync /> Try Again
          </RetryButton>
        </ErrorContainer>
      </Container>
    );
  }
  
  const renderDetailsForType = () => {
    const type = currentItem.type || currentItem.item_type;
    switch(type) {
      case 'password':
        const strength = passwordStrength(currentItem.data?.password || '');
        
        return (
          <>
            {currentItem.data?.url && (
              <FieldGroup $delay="0.1s">
                <FieldLabel><FaGlobe /> Website</FieldLabel>
                <FieldValue>
                  <ValueText>{currentItem.data.url}</ValueText>
                  <ValueActions>
                    {copiedField === 'url' ? (
                      <CopiedToast><FaCheckCircle /> Copied!</CopiedToast>
                    ) : (
                      <SmallActionButton onClick={() => handleCopy(currentItem.data.url, 'url')}>
                        <FaCopy />
                      </SmallActionButton>
                    )}
                  </ValueActions>
                </FieldValue>
              </FieldGroup>
            )}
            
            <FieldGroup $delay="0.15s">
              <FieldLabel><FaUser /> Username</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.username || currentItem.data?.email}</ValueText>
                <ValueActions>
                  {copiedField === 'username' ? (
                    <CopiedToast><FaCheckCircle /> Copied!</CopiedToast>
                  ) : (
                    <SmallActionButton onClick={() => handleCopy(currentItem.data?.username || currentItem.data?.email, 'username')}>
                      <FaCopy />
                    </SmallActionButton>
                  )}
                </ValueActions>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.2s">
              <FieldLabel><FaLock /> Password</FieldLabel>
              <FieldValue>
                <ValueText $monospace>
                  {showPassword ? currentItem.data?.password : '••••••••••••'}
                </ValueText>
                <ValueActions>
                  <SmallActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </SmallActionButton>
                  {copiedField === 'password' ? (
                    <CopiedToast><FaCheckCircle /> Copied!</CopiedToast>
                  ) : (
                    <SmallActionButton onClick={() => handleCopy(currentItem.data?.password, 'password')}>
                      <FaCopy />
                    </SmallActionButton>
                  )}
                </ValueActions>
              </FieldValue>
              
              <PasswordStrengthBar>
                <StrengthIndicator $strength={strength.score} />
              </PasswordStrengthBar>
              <StrengthLabel>
                <span>Password Strength</span>
                <StrengthText $strength={strength.score}>{getStrengthLabel(strength.score)}</StrengthText>
              </StrengthLabel>
              
              {strength.warnings && strength.warnings.length > 0 && (
                <PasswordWarning>
                  <FaExclamationTriangle /> {strength.warnings[0]}
                </PasswordWarning>
              )}
            </FieldGroup>
            
            {currentItem.data?.notes && (
              <FieldGroup $delay="0.25s">
                <FieldLabel><FaStickyNote /> Notes</FieldLabel>
                <FieldValue style={{ minHeight: '80px', alignItems: 'flex-start' }}>
                  <ValueText style={{ whiteSpace: 'pre-wrap' }}>{currentItem.data.notes}</ValueText>
                </FieldValue>
              </FieldGroup>
            )}
          </>
        );
        
      case 'card':
        return (
          <>
            <FieldGroup $delay="0.1s">
              <FieldLabel><FaUser /> Cardholder Name</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.cardholderName}</ValueText>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.15s">
              <FieldLabel><FaCreditCard /> Card Number</FieldLabel>
              <FieldValue>
                <ValueText $monospace>
                  {showPassword ? currentItem.data?.cardNumber : 
                    '•••• •••• •••• ' + (currentItem.data?.cardNumber?.slice(-4) || '****')}
                </ValueText>
                <ValueActions>
                  <SmallActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </SmallActionButton>
                  {copiedField === 'card' ? (
                    <CopiedToast><FaCheckCircle /> Copied!</CopiedToast>
                  ) : (
                    <SmallActionButton onClick={() => handleCopy(currentItem.data?.cardNumber, 'card')}>
                      <FaCopy />
                    </SmallActionButton>
                  )}
                </ValueActions>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.2s">
              <FieldLabel><FaCalendar /> Expiration Date</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.expirationMonth}/{currentItem.data?.expirationYear}</ValueText>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.25s">
              <FieldLabel><FaLock /> CVV</FieldLabel>
              <FieldValue>
                <ValueText $monospace>{showPassword ? currentItem.data?.cvv : '•••'}</ValueText>
                <ValueActions>
                  <SmallActionButton onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </SmallActionButton>
                </ValueActions>
              </FieldValue>
            </FieldGroup>
          </>
        );
        
      case 'identity':
        return (
          <>
            <FieldGroup $delay="0.1s">
              <FieldLabel><FaUser /> Full Name</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.fullName}</ValueText>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.15s">
              <FieldLabel>📧 Email</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.email}</ValueText>
                <ValueActions>
                  {copiedField === 'email' ? (
                    <CopiedToast><FaCheckCircle /> Copied!</CopiedToast>
                  ) : (
                    <SmallActionButton onClick={() => handleCopy(currentItem.data?.email, 'email')}>
                      <FaCopy />
                    </SmallActionButton>
                  )}
                </ValueActions>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.2s">
              <FieldLabel>📱 Phone</FieldLabel>
              <FieldValue>
                <ValueText>{currentItem.data?.phone}</ValueText>
              </FieldValue>
            </FieldGroup>
            
            <FieldGroup $delay="0.25s">
              <FieldLabel>📍 Address</FieldLabel>
              <FieldValue style={{ minHeight: '80px', alignItems: 'flex-start' }}>
                <ValueText style={{ whiteSpace: 'pre-wrap' }}>
                  {currentItem.data?.address}{'\n'}
                  {currentItem.data?.city}, {currentItem.data?.state} {currentItem.data?.zipCode}{'\n'}
                  {currentItem.data?.country}
                </ValueText>
              </FieldValue>
            </FieldGroup>
          </>
        );
        
      case 'note':
        return (
          <FieldGroup $delay="0.1s">
            <FieldLabel><FaStickyNote /> Secure Note</FieldLabel>
            <FieldValue style={{ minHeight: '200px', alignItems: 'flex-start' }}>
              <ValueText style={{ whiteSpace: 'pre-wrap' }}>{currentItem.data?.note}</ValueText>
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
        <TitleSection>
          <TypeIconBadge>
            {getTypeIcon()}
          </TypeIconBadge>
          <TitleContent>
            <Title>{currentItem.data?.name || currentItem.data?.title || 'Unnamed Item'}</Title>
            <TypeLabel>{currentItem.type || currentItem.item_type}</TypeLabel>
          </TitleContent>
        </TitleSection>
        <Actions>
          <ActionButton onClick={() => onEdit(currentItem)}>
            <FaPen />
          </ActionButton>
          <ActionButton className="danger" onClick={() => onDelete(currentItem.id)}>
            <FaTrash />
          </ActionButton>
        </Actions>
      </Header>
      
      {renderDetailsForType()}
      
      <Footer>
        <FooterItem>
          <FaCalendar /> Created: {formatDate(currentItem.created_at)}
        </FooterItem>
        <FooterItem>
          <FaSync /> Updated: {formatDate(currentItem.updated_at)}
        </FooterItem>
      </Footer>
    </Container>
  );
};

export default VaultItemDetail;

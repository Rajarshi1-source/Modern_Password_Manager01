import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaKey, FaCreditCard, FaIdCard, FaStickyNote, FaStar, FaRegStar, FaEye, FaEyeSlash, FaLock, FaChevronDown, FaChevronUp } from 'react-icons/fa';
import { useVault } from '../../contexts/VaultContext';
import PasswordItem from './PasswordItem';
import CardItem from './CardItem';
import IdentityItem from './IdentityItem';
import SecureNoteItem from './SecureNoteItem';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const slideDown = keyframes`
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 500px; }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#ffffff',
  backgroundSecondary: '#f8f9ff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff',
  starActive: '#FFD700'
};

const ItemContainer = styled.div`
  background: linear-gradient(135deg, ${colors.background} 0%, ${colors.backgroundSecondary} 100%);
  border-radius: 16px;
  padding: 0;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(123, 104, 238, 0.08);
  border: 1px solid ${colors.border};
  cursor: pointer;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  animation: ${fadeIn} 0.4s ease-out;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  
  &:hover {
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.15);
    border-color: ${colors.borderLight};
    transform: translateY(-2px);
  }
  
  &:hover::before {
    opacity: 1;
  }
`;

const ItemHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  background: ${props => props.$expanded ? colors.backgroundSecondary : 'transparent'};
  border-bottom: ${props => props.$expanded ? `1px solid ${colors.border}` : 'none'};
  transition: all 0.3s ease;
`;

const ItemInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
`;

const ItemIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  
  svg {
    font-size: 18px;
    color: ${colors.primary};
  }
  
  ${ItemContainer}:hover & {
    background: linear-gradient(135deg, ${colors.primary}30 0%, ${colors.primaryLight}25 100%);
  }
`;

const ItemDetails = styled.div`
  flex: 1;
`;

const ItemTitle = styled.h3`
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: ${colors.text};
  display: flex;
  align-items: center;
  gap: 10px;
`;

const ItemSubtitle = styled.div`
  font-size: 13px;
  color: ${colors.textSecondary};
  text-transform: capitalize;
`;

const EncryptedBadge = styled.span`
  font-size: 10px;
  font-weight: 600;
  color: ${colors.primary};
  padding: 3px 8px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  
  svg {
    font-size: 8px;
  }
`;

const Actions = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
`;

const ActionButton = styled.button`
  background: transparent;
  border: none;
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 10px;
  border-radius: 10px;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    background: ${colors.border};
    color: ${colors.primary};
    transform: scale(1.1);
  }
  
  &.favorite {
    color: ${props => props.$active ? colors.starActive : colors.textSecondary};
    
    &:hover {
      color: ${colors.starActive};
      background: #fffbeb;
    }
  }
`;

const ExpandButton = styled.button`
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  
  &:hover {
    background: ${colors.border};
    color: ${colors.primary};
  }
  
  svg {
    transition: transform 0.3s ease;
  }
`;

const ExpandedContent = styled.div`
  padding: 20px;
  animation: ${slideDown} 0.3s ease-out;
  background: ${colors.background};
`;

const LoadingMessage = styled.div`
  padding: 24px;
  text-align: center;
  color: ${colors.textSecondary};
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  animation: ${pulse} 1.5s ease-in-out infinite;
  
  &::before {
    content: '';
    width: 16px;
    height: 16px;
    border: 2px solid ${colors.border};
    border-top-color: ${colors.primary};
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

const VaultItem = ({ item, onEdit, onDelete }) => {
  const [expanded, setExpanded] = useState(false);
  const [favorite, setFavorite] = useState(item.favorite);
  const [isDecrypting, setIsDecrypting] = useState(false);
  const [decryptedItem, setDecryptedItem] = useState(item);
  const { decryptItem } = useVault();
  
  const isLazyLoaded = item._lazyLoaded && !item._decrypted;

  const toggleFavorite = (e) => {
    e.stopPropagation();
    setFavorite(!favorite);
    // Call API to update favorite status
  };

  const getItemIcon = () => {
    const type = item.type || item.item_type;
    switch (type) {
      case 'password':
        return <FaKey />;
      case 'card':
        return <FaCreditCard />;
      case 'identity':
        return <FaIdCard />;
      case 'note':
        return <FaStickyNote />;
      default:
        return <FaKey />;
    }
  };
  
  const getTypeLabel = () => {
    const type = item.type || item.item_type;
    switch (type) {
      case 'password': return 'Login Credential';
      case 'card': return 'Payment Card';
      case 'identity': return 'Personal Identity';
      case 'note': return 'Secure Note';
      default: return 'Vault Item';
    }
  };

  const handleToggleExpand = async (e) => {
    e.stopPropagation();
    
    // If expanding and item is lazy-loaded, decrypt first
    if (!expanded && isLazyLoaded) {
      setIsDecrypting(true);
      try {
        const decrypted = await decryptItem(item.item_id);
        setDecryptedItem(decrypted);
        setExpanded(true);
      } catch (error) {
        console.error('Failed to decrypt item:', error);
        alert('Failed to decrypt item. Please try again.');
      } finally {
        setIsDecrypting(false);
      }
    } else {
      setExpanded(!expanded);
    }
  };

  const renderItemDetails = () => {
    if (!expanded) return null;
    
    if (isDecrypting) {
      return <LoadingMessage>Decrypting...</LoadingMessage>;
    }
    
    const currentItem = decryptedItem;
    const type = currentItem.type || currentItem.item_type;
    
    switch (type) {
      case 'password':
        return <PasswordItem data={currentItem.data} />;
      case 'card':
        return <CardItem data={currentItem.data} />;
      case 'identity':
        return <IdentityItem data={currentItem.data} />;
      case 'note':
        return <SecureNoteItem data={currentItem.data} />;
      default:
        return null;
    }
  };

  return (
    <ItemContainer onClick={handleToggleExpand}>
      <ItemHeader $expanded={expanded}>
        <ItemInfo>
          <ItemIcon>{getItemIcon()}</ItemIcon>
          <ItemDetails>
            <ItemTitle>
              {isLazyLoaded 
                ? item.preview?.title || 'Encrypted Item'
                : item.data?.name || 'Unnamed Item'}
              {isLazyLoaded && (
                <EncryptedBadge>
                  <FaLock /> Encrypted
                </EncryptedBadge>
              )}
            </ItemTitle>
            <ItemSubtitle>{getTypeLabel()}</ItemSubtitle>
          </ItemDetails>
        </ItemInfo>
        
        <Actions>
          <ActionButton 
            className="favorite"
            $active={favorite}
            onClick={toggleFavorite}
            aria-label={favorite ? 'Remove from favorites' : 'Add to favorites'}
          >
            {favorite ? <FaStar /> : <FaRegStar />}
          </ActionButton>
          <ActionButton onClick={(e) => {
            e.stopPropagation();
            onEdit(item);
          }}>
            <FaEye />
          </ActionButton>
          <ExpandButton onClick={handleToggleExpand}>
            {expanded ? (
              <>Hide <FaChevronUp /></>
            ) : (
              <>View <FaChevronDown /></>
            )}
          </ExpandButton>
        </Actions>
      </ItemHeader>
      
      {(expanded || isDecrypting) && (
        <ExpandedContent>
          {renderItemDetails()}
        </ExpandedContent>
      )}
    </ItemContainer>
  );
};

export default VaultItem;

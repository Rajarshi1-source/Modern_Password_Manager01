import React, { useState } from 'react';
import styled from 'styled-components';
import { FaKey, FaCreditCard, FaIdCard, FaStickyNote, FaStar, FaRegStar, FaEye, FaEyeSlash, FaLock } from 'react-icons/fa';
import { motion } from 'framer-motion';
import { useVault } from '../../contexts/VaultContext';
import PasswordItem from './PasswordItem';
import CardItem from './CardItem';
import IdentityItem from './IdentityItem';
import SecureNoteItem from './SecureNoteItem';

const ItemContainer = styled(motion.div)`
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
  
  &:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }
`;

const ItemHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: ${props => props.expanded ? '16px' : '0'};
`;

const ItemTitle = styled.h3`
  margin: 0;
  font-size: 16px;
  color: ${props => props.theme.textPrimary};
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ItemIcon = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: ${props => props.theme.accentLight};
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${props => props.theme.accent};
`;

const Actions = styled.div`
  display: flex;
  gap: 8px;
`;

const ActionButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
    color: ${props => props.theme.accent};
  }
`;

const EncryptedBadge = styled.span`
  font-size: 10px;
  color: ${props => props.theme.accent};
  margin-left: 8px;
  padding: 2px 6px;
  background: ${props => props.theme.accentLight};
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
`;

const LoadingMessage = styled.div`
  padding: 12px;
  text-align: center;
  color: ${props => props.theme.textSecondary};
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

  const handleToggleExpand = async () => {
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
    <ItemContainer
      onClick={handleToggleExpand}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <ItemHeader expanded={expanded}>
        <ItemTitle>
          <ItemIcon>{getItemIcon()}</ItemIcon>
          {isLazyLoaded 
            ? item.preview?.title || 'Encrypted Item'
            : item.data?.name || 'Unnamed Item'}
          {isLazyLoaded && (
            <EncryptedBadge>
              <FaLock size={8} /> Encrypted
            </EncryptedBadge>
          )}
        </ItemTitle>
        <Actions>
          <ActionButton onClick={toggleFavorite}>
            {favorite ? <FaStar color="#FFD700" /> : <FaRegStar />}
          </ActionButton>
          <ActionButton onClick={(e) => {
            e.stopPropagation();
            onEdit(item);
          }}>
            <FaEye />
          </ActionButton>
        </Actions>
      </ItemHeader>
      {renderItemDetails()}
    </ItemContainer>
  );
};

export default VaultItem;

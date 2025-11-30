import React, { useRef, useState } from 'react';
import { FaKey, FaCreditCard, FaIdCard, FaStickyNote, FaStar, FaEllipsisV, FaLock } from 'react-icons/fa';
import styled from 'styled-components';
import { motion } from 'framer-motion';
import { useAccessibility } from '../../contexts/AccessibilityContext';
import { useVault } from '../../contexts/VaultContext';

const Card = styled(motion.div)`
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  position: relative;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  
  &:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
  }
  
  &:focus-within {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
  
  ${props => props.emergencyMode && `
    border-left: 4px solid ${props.theme.warning};
  `}
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const CardTitle = styled.h3`
  margin: 0;
  font-size: 16px;
  color: ${props => props.theme.textPrimary};
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  max-width: 80%;
`;

const IconWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const TypeIcon = styled.div`
  color: ${props => props.theme.primary};
  font-size: 18px;
`;

const FavoriteIcon = styled.button`
  color: ${props => props.isFavorite ? '#FFD700' : props.theme.textSecondary};
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 4px;
  
  &:hover {
    background: ${props => props.theme.bgHover};
  }
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
`;

const CardContent = styled.div`
  margin-bottom: 12px;
`;

const ItemDetail = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
  margin-bottom: 4px;
  display: flex;
  align-items: center;
`;

const ActionMenu = styled.div`
  position: absolute;
  top: 8px;
  right: 8px;
`;

const MenuButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  
  &:hover {
    background: ${props => props.theme.bgHover};
    color: ${props => props.theme.textPrimary};
  }
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
`;

const MenuDropdown = styled.div`
  position: absolute;
  top: 100%;
  right: 0;
  background: ${props => props.theme.cardBg};
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 10;
  min-width: 150px;
  display: ${props => props.isOpen ? 'block' : 'none'};
`;

const MenuItem = styled.button`
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  
  &:hover {
    background: ${props => props.theme.bgHover};
  }
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
`;

const EmergencyBadge = styled.div`
  position: absolute;
  top: 8px;
  left: 8px;
  background: ${props => props.theme.warningLight};
  color: ${props => props.theme.warning};
  font-size: 10px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
`;

const EncryptedBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: ${props => props.theme.accentLight || '#e3f2fd'};
  color: ${props => props.theme.accent || '#1976d2'};
  font-size: 10px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
`;

const LoadingOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  z-index: 5;
`;

const VaultItemCard = ({ 
  item, 
  onClick, 
  onToggleFavorite, 
  onEdit,
  onDelete,
  readOnly = false,
  emergencyMode = false
}) => {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [isDecrypting, setIsDecrypting] = useState(false);
  const cardRef = useRef(null);
  const { handleKeyNavigation } = useAccessibility();
  const { decryptItem } = useVault();
  const menuRef = useRef(null);
  
  // Check if item is lazy-loaded
  const isLazyLoaded = item._lazyLoaded && !item._decrypted;
  const isDecrypted = item._decrypted;
  
  const getTypeIcon = () => {
    const type = item.type || item.item_type;
    switch(type) {
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
  
  const getPrimaryDetail = () => {
    // For lazy-loaded items, show preview info
    if (isLazyLoaded) {
      const type = item.item_type || item.type;
      switch(type) {
        case 'password':
          return 'Encrypted Password';
        case 'card':
          return 'Encrypted Card';
        case 'identity':
          return 'Encrypted Identity';
        case 'note':
          return 'Encrypted Note';
        default:
          return 'Encrypted Data';
      }
    }
    
    // For decrypted items, show actual data
    const type = item.type || item.item_type;
    switch(type) {
      case 'password':
        return item.data?.username || item.data?.email || '';
      case 'card':
        return item.data?.cardType ? `${item.data.cardType} •••• ${item.data.last4}` : '';
      case 'identity':
        return item.data?.email || '';
      case 'note':
        return 'Secure Note';
      default:
        return '';
    }
  };
  
  const getSecondaryDetail = () => {
    // For lazy-loaded items, show modified date
    if (isLazyLoaded) {
      return item.preview?.lastModified 
        ? `Modified: ${new Date(item.preview.lastModified).toLocaleDateString()}`
        : '';
    }
    
    // For decrypted items, show actual data
    const type = item.type || item.item_type;
    switch(type) {
      case 'password':
        return item.data?.url || '';
      case 'card':
        return item.data?.cardholderName || '';
      case 'identity':
        return item.data?.fullName || '';
      default:
        return '';
    }
  };
  
  const handleClick = async (e) => {
    if (menuOpen) return;
    
    // If item is lazy-loaded, decrypt it first
    if (isLazyLoaded && decryptItem) {
      setIsDecrypting(true);
      try {
        const decryptedItem = await decryptItem(item.item_id);
        if (onClick) {
          onClick(decryptedItem);
        }
      } catch (error) {
        console.error('Failed to decrypt item:', error);
        alert('Failed to decrypt item. Please try again.');
      } finally {
        setIsDecrypting(false);
      }
    } else if (onClick) {
      onClick(item);
    }
  };
  
  const handleKeyDown = (e) => {
    // Enter or Space to select item
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick(e);
    }
  };
  
  const toggleMenu = (e) => {
    e.stopPropagation();
    setMenuOpen(!menuOpen);
  };
  
  // Close menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpen]);
  
  return (
    <Card
      ref={cardRef}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex="0"
      role="button"
      aria-pressed="false"
      aria-label={`${item.data.name || 'Item'}, ${item.type}`}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.2 }}
      emergencyMode={emergencyMode}
    >
      {isDecrypting && (
        <LoadingOverlay>
          <div>Decrypting...</div>
        </LoadingOverlay>
      )}
      
      {emergencyMode && (
        <EmergencyBadge aria-hidden="true">
          Emergency Access
        </EmergencyBadge>
      )}
      
      <CardHeader>
        <CardTitle>
          {isLazyLoaded 
            ? item.preview?.title || 'Encrypted Item'
            : item.data?.name || 'Unnamed Item'}
          {isLazyLoaded && (
            <EncryptedBadge>
              <FaLock size={8} /> Encrypted
            </EncryptedBadge>
          )}
        </CardTitle>
        <IconWrapper>
          <TypeIcon>{getTypeIcon()}</TypeIcon>
          
          {!readOnly && (
            <FavoriteIcon 
              onClick={(e) => {
                e.stopPropagation();
                onToggleFavorite(item.id);
              }}
              isFavorite={item.favorite}
              aria-label={item.favorite ? 'Remove from favorites' : 'Add to favorites'}
              aria-pressed={item.favorite}
            >
              <FaStar />
            </FavoriteIcon>
          )}
        </IconWrapper>
      </CardHeader>
      
      <CardContent>
        <ItemDetail>{getPrimaryDetail()}</ItemDetail>
        {getSecondaryDetail() && (
          <ItemDetail>{getSecondaryDetail()}</ItemDetail>
        )}
      </CardContent>
      
      {!readOnly && (
        <ActionMenu ref={menuRef}>
          <MenuButton 
            onClick={toggleMenu}
            aria-label="Item actions menu"
            aria-expanded={menuOpen}
            aria-haspopup="true"
          >
            <FaEllipsisV />
          </MenuButton>
          
          <MenuDropdown 
            isOpen={menuOpen}
            role="menu"
            aria-label="Item actions"
          >
            <MenuItem 
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                onEdit(item);
              }}
              role="menuitem"
            >
              Edit
            </MenuItem>
            <MenuItem 
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                onDelete(item.id);
              }}
              role="menuitem"
            >
              Delete
            </MenuItem>
          </MenuDropdown>
        </ActionMenu>
      )}
    </Card>
  );
};

export default VaultItemCard;
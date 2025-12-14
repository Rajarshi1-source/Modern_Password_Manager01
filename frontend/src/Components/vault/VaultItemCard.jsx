import React, { useRef, useState } from 'react';
import { FaKey, FaCreditCard, FaIdCard, FaStickyNote, FaStar, FaEllipsisV, FaLock } from 'react-icons/fa';
import styled from 'styled-components';
import { motion } from 'framer-motion';
import { useAccessibility } from '../../contexts/AccessibilityContext';
import { useVault } from '../../contexts/VaultContext';

const Card = styled(motion.div)`
  background: linear-gradient(135deg, #ffffff 0%, #fafaff 100%);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(123, 104, 238, 0.08);
  position: relative;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid #e8e4ff;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #7B68EE 0%, #9B8BFF 100%);
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 32px rgba(123, 104, 238, 0.18);
    border-color: #d4ccff;
  }
  
  &:hover::before {
    opacity: 1;
  }
  
  &:focus-within {
    outline: none;
    border-color: #7B68EE;
    box-shadow: 0 0 0 4px rgba(123, 104, 238, 0.15);
  }
  
  ${props => props.emergencyMode && `
    border-left: 4px solid #f59e0b;
    
    &::before {
      background: linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%);
    }
  `}
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
`;

const CardTitle = styled.h3`
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  max-width: 75%;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const IconWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const TypeIcon = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #e8e4ff 0%, #d4ccff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7B68EE;
  font-size: 16px;
`;

const FavoriteIcon = styled.button`
  color: ${props => props.isFavorite ? '#FFD700' : '#a0a0b8'};
  background: ${props => props.isFavorite ? '#fffbeb' : 'transparent'};
  border: none;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.25s ease;
  
  &:hover {
    background: #fffbeb;
    color: #FFD700;
    transform: scale(1.1);
  }
  
  &:focus-visible {
    outline: 2px solid #7B68EE;
    outline-offset: 2px;
  }
`;

const CardContent = styled.div`
  margin-bottom: 8px;
  padding: 12px;
  background: #f8f9ff;
  border-radius: 10px;
`;

const ItemDetail = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textSecondary || '#6b7280'};
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const ActionMenu = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
`;

const MenuButton = styled.button`
  background: #f8f9ff;
  border: none;
  color: ${props => props.theme.textSecondary || '#6b7280'};
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.25s ease;
  
  &:hover {
    background: #e8e4ff;
    color: #7B68EE;
  }
  
  &:focus-visible {
    outline: 2px solid #7B68EE;
    outline-offset: 2px;
  }
`;

const MenuDropdown = styled.div`
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 10;
  min-width: 160px;
  display: ${props => props.isOpen ? 'block' : 'none'};
  border: 1px solid #e8e4ff;
  overflow: hidden;
`;

const MenuItem = styled.button`
  display: block;
  width: 100%;
  text-align: left;
  padding: 12px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  transition: all 0.2s ease;
  
  &:hover {
    background: #f8f9ff;
    color: #7B68EE;
  }
  
  &:focus-visible {
    outline: 2px solid #7B68EE;
    outline-offset: -2px;
  }
  
  &:last-child {
    color: #e53e3e;
    
    &:hover {
      background: #fff5f5;
      color: #c53030;
    }
  }
`;

const EmergencyBadge = styled.div`
  position: absolute;
  top: 12px;
  left: 12px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
  font-size: 10px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const EncryptedBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: linear-gradient(135deg, #e8e4ff 0%, #d4ccff 100%);
  color: #7B68EE;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 6px;
  margin-left: 8px;
`;

const LoadingOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  z-index: 5;
  backdrop-filter: blur(4px);
  
  div {
    font-weight: 600;
    color: #7B68EE;
  }
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
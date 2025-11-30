import React, { useState, useMemo, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { FaSearch, FaPlus, FaFilter, FaStar } from 'react-icons/fa';
import VaultItemCard from './VaultItemCard';
import { motion, AnimatePresence } from 'framer-motion';
import { useAccessibility } from '../../contexts/AccessibilityContext';
import { useVault } from '../../contexts/VaultContext';
import LoadingIndicator from '../common/LoadingIndicator';
import ErrorDisplay from '../common/ErrorDisplay';

const Container = styled.div`
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
`;

const Title = styled.h1`
  margin: 0;
  font-size: 24px;
  font-weight: 600;
`;

const AddButton = styled.button`
  background: ${props => props.theme.accent};
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 500;
  
  &:hover {
    background: ${props => props.theme.accentHover};
  }
`;

const SearchContainer = styled.div`
  position: relative;
  margin-bottom: 20px;
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 12px 16px 12px 40px;
  border-radius: 8px;
  border: 1px solid ${props => props.theme.borderColor};
  background: ${props => props.theme.backgroundSecondary};
  color: ${props => props.theme.textPrimary};
  font-size: 16px;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.accent};
    box-shadow: 0 0 0 2px ${props => props.theme.accentLight};
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary};
  }
`;

const SearchIcon = styled.div`
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: ${props => props.theme.textSecondary};
`;

const FiltersContainer = styled.div`
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  overflow-x: auto;
  padding-bottom: 4px;
  
  &::-webkit-scrollbar {
    height: 4px;
  }
  
  &::-webkit-scrollbar-track {
    background: ${props => props.theme.backgroundSecondary};
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.borderColor};
    border-radius: 2px;
  }
`;

const FilterButton = styled.button`
  background: ${props => props.active ? props.theme.accentLight : props.theme.backgroundSecondary};
  color: ${props => props.active ? props.theme.accent : props.theme.textSecondary};
  border: 1px solid ${props => props.active ? props.theme.accent : props.theme.borderColor};
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  cursor: pointer;
  
  &:hover {
    border-color: ${props => props.theme.accent};
  }
`;

const VaultGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 16px;
  margin-top: 16px;
  
  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px;
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  margin-top: 16px;
`;

const EmptyTitle = styled.h3`
  margin-bottom: 8px;
  color: ${props => props.theme.textPrimary};
`;

const EmptyMessage = styled.p`
  color: ${props => props.theme.textSecondary};
  margin-bottom: 16px;
`;

const VaultList = ({ 
  items = [], 
  loading = false, 
  error = null,
  onItemClick,
  onToggleFavorite,
  onEditItem,
  onDeleteItem,
  onRetry,
  emergencyMode = false,
  readOnly = false
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [decryptingSearch, setDecryptingSearch] = useState(false);
  const itemRefs = useRef([]);
  const { handleKeyNavigation } = useAccessibility();
  const { decryptItem } = useVault();
  
  const filters = [
    { id: 'all', label: 'All Items', icon: null },
    { id: 'password', label: 'Passwords', icon: null },
    { id: 'card', label: 'Payment Cards', icon: null },
    { id: 'identity', label: 'Personal Info', icon: null },
    { id: 'note', label: 'Secure Notes', icon: null },
  ];
  
  const filteredItems = useMemo(() => {
    return items.filter(item => {
      // Filter by type - use item_type for lazy-loaded items
      const itemType = item.type || item.item_type;
      if (activeFilter !== 'all' && itemType !== activeFilter) {
        return false;
      }
      
      // Filter by favorites
      if (showFavoritesOnly && !item.favorite) {
        return false;
      }
      
      // Search term filter - if lazy-loaded, only search by preview data
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        
        // For lazy-loaded items, search is limited to preview data
        if (item._lazyLoaded && !item._decrypted) {
          const previewMatch = item.preview?.title?.toLowerCase().includes(searchLower);
          const typeMatch = item.item_type?.toLowerCase().includes(searchLower);
          return previewMatch || typeMatch;
        }
        
        // For decrypted items, full search
        const nameMatch = item.data?.name?.toLowerCase().includes(searchLower);
        const usernameMatch = item.data?.username?.toLowerCase().includes(searchLower);
        const urlMatch = item.data?.url?.toLowerCase().includes(searchLower);
        
        return nameMatch || usernameMatch || urlMatch;
      }
      
      return true;
    });
  }, [items, activeFilter, searchTerm, showFavoritesOnly]);
  
  const handleSearch = (e) => {
    setSearchTerm(e.target.value);
  };
  
  const toggleFilter = (filterId) => {
    setActiveFilter(filterId);
  };
  
  const toggleFavorites = () => {
    setShowFavoritesOnly(!showFavoritesOnly);
  };
  
  // Set up refs for keyboard navigation
  useEffect(() => {
    itemRefs.current = itemRefs.current.slice(0, items.length);
  }, [items]);
  
  const handleKeyDown = (e) => {
    handleKeyNavigation(e, itemRefs.current);
    
    // Handle grid navigation with arrow keys
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault();
      const currentIndex = itemRefs.current.findIndex(ref => ref.current === document.activeElement);
      if (currentIndex === -1) return;
      
      const columns = Math.floor(window.innerWidth / 300);
      const nextIndex = e.key === 'ArrowRight' 
        ? Math.min(currentIndex + 1, items.length - 1)
        : Math.max(currentIndex - 1, 0);
      
      itemRefs.current[nextIndex].current?.focus();
    }
  };
  
  if (loading) {
    return <LoadingIndicator text="Loading vault items..." />;
  }
  
  if (error) {
    return (
      <ErrorDisplay 
        title="Failed to load vault items" 
        message={error} 
        onRetry={onRetry}
      />
    );
  }
  
  if (items.length === 0) {
    return (
      <EmptyState>
        <EmptyTitle>No items found</EmptyTitle>
        <EmptyMessage>
          {emergencyMode 
            ? "This vault has no items or you don't have permission to view them."
            : "You haven't added any items to your vault yet."}
        </EmptyMessage>
      </EmptyState>
    );
  }
  
  return (
    <Container>
      <Header>
        <Title>Secure Vault</Title>
        <AddButton onClick={onItemClick}>
          <FaPlus /> Add Item
        </AddButton>
      </Header>
      
      <SearchContainer>
        <SearchIcon>
          <FaSearch />
        </SearchIcon>
        <SearchInput 
          type="text" 
          placeholder="Search vault..."
          value={searchTerm}
          onChange={handleSearch}
        />
      </SearchContainer>
      
      <FiltersContainer>
        {filters.map(filter => (
          <FilterButton
            key={filter.id}
            active={activeFilter === filter.id}
            onClick={() => toggleFilter(filter.id)}
          >
            {filter.icon} {filter.label}
          </FilterButton>
        ))}
        <FilterButton
          active={showFavoritesOnly}
          onClick={toggleFavorites}
        >
          <FaStar /> Favorites
        </FilterButton>
      </FiltersContainer>
      
      <VaultGrid 
        role="grid" 
        aria-label="Vault items" 
        onKeyDown={handleKeyDown}
      >
        {filteredItems.map((item, index) => (
          <div 
            key={item.id} 
            role="gridcell"
            ref={el => itemRefs.current[index] = el}
          >
            <VaultItemCard
              item={item}
              onClick={onItemClick}
              onToggleFavorite={onToggleFavorite}
              onEdit={onEditItem}
              onDelete={onDeleteItem}
              readOnly={readOnly}
              emergencyMode={emergencyMode}
            />
          </div>
        ))}
      </VaultGrid>
    </Container>
  );
};

export default VaultList;

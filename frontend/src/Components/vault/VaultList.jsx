import React, { useState, useMemo, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { FaSearch, FaPlus, FaStar } from 'react-icons/fa';
import VaultItemCard from './VaultItemCard';
import { useAccessibility } from '../../contexts/AccessibilityContext';
import LoadingIndicator from '../common/LoadingIndicator';
import ErrorDisplay from '../common/ErrorDisplay';

const Container = styled.div`
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${props => props.theme.borderColor || '#e8e4ff'};
`;

const Title = styled.h1`
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  display: flex;
  align-items: center;
  gap: 12px;
  
  &::before {
    content: '🔐';
    font-size: 1.5rem;
  }
`;

const AddButton = styled.button`
  background: linear-gradient(135deg, #7B68EE 0%, #9B8BFF 100%);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 600;
  font-size: 15px;
  box-shadow: 0 4px 14px rgba(123, 104, 238, 0.35);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(123, 104, 238, 0.45);
  }
  
  &:active {
    transform: translateY(0);
  }
`;

const SearchContainer = styled.div`
  position: relative;
  margin-bottom: 24px;
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 16px 20px 16px 52px;
  border-radius: 14px;
  border: 2px solid ${props => props.theme.borderColor || '#e8e4ff'};
  background: ${props => props.theme.backgroundSecondary || '#fafaff'};
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  font-size: 16px;
  transition: all 0.25s ease;
  
  &:hover {
    border-color: #d4ccff;
    background: #ffffff;
  }
  
  &:focus {
    outline: none;
    border-color: #7B68EE;
    background: #ffffff;
    box-shadow: 0 0 0 4px rgba(123, 104, 238, 0.15);
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary || '#a0a0b8'};
  }
`;

const SearchIcon = styled.div`
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  color: #7B68EE;
  font-size: 18px;
`;

const FiltersContainer = styled.div`
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  overflow-x: auto;
  padding: 4px;
  background: ${props => props.theme.backgroundSecondary || '#f8f9ff'};
  border-radius: 14px;
  
  &::-webkit-scrollbar {
    height: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  
  &::-webkit-scrollbar-thumb {
    background: #d4ccff;
    border-radius: 3px;
  }
`;

const FilterButton = styled.button`
  background: ${props => props.active 
    ? 'linear-gradient(135deg, #7B68EE 0%, #9B8BFF 100%)' 
    : 'transparent'};
  color: ${props => props.active ? '#ffffff' : props.theme.textSecondary || '#6b7280'};
  border: none;
  border-radius: 10px;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: ${props => props.active ? '0 4px 12px rgba(123, 104, 238, 0.3)' : 'none'};
  
  &:hover {
    background: ${props => props.active 
      ? 'linear-gradient(135deg, #6B58DE 0%, #8B7BEF 100%)'
      : 'rgba(123, 104, 238, 0.1)'};
    color: ${props => props.active ? '#ffffff' : '#7B68EE'};
  }
`;

const VaultGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
  
  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 60px 40px;
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
  border-radius: 20px;
  margin-top: 20px;
  border: 2px dashed #d4ccff;
`;

const EmptyIcon = styled.div`
  font-size: 4rem;
  margin-bottom: 16px;
`;

const EmptyTitle = styled.h3`
  margin-bottom: 12px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  font-size: 1.5rem;
  font-weight: 700;
`;

const EmptyMessage = styled.p`
  color: ${props => props.theme.textSecondary || '#6b7280'};
  margin-bottom: 20px;
  font-size: 1rem;
  line-height: 1.6;
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
  const itemRefs = useRef([]);
  const { handleKeyNavigation } = useAccessibility();
  
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
      
      const nextIndex = e.key === 'ArrowRight' 
        ? Math.min(currentIndex + 1, items.length - 1)
        : Math.max(currentIndex - 1, 0);
      
      itemRefs.current[nextIndex]?.current?.focus();
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
        <EmptyIcon>{emergencyMode ? '🔒' : '📭'}</EmptyIcon>
        <EmptyTitle>No items found</EmptyTitle>
        <EmptyMessage>
          {emergencyMode 
            ? "This vault has no items or you don't have permission to view them."
            : "You haven't added any items to your vault yet. Click 'Add Item' to get started!"}
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

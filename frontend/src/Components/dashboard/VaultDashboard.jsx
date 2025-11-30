import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaSearch, FaPlus, FaLock, FaCreditCard, FaIdCard, FaStickyNote, FaStar } from 'react-icons/fa';
import VaultItemCard from '../vault/VaultItemCard';
import EmptyState from '../common/EmptyState';

const Container = styled.div`
  padding: 24px;
  max-width: 1200px;
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
`;

const SearchBar = styled.div`
  position: relative;
  width: 100%;
  max-width: 400px;
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 12px 16px 12px 40px;
  border-radius: 8px;
  border: 1px solid ${props => props.theme.borderColor};
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.primary};
  }
`;

const SearchIcon = styled.div`
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: ${props => props.theme.textSecondary};
`;

const AddButton = styled.button`
  background: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  
  &:hover {
    background: ${props => props.theme.primaryDark};
  }
`;

const TabsContainer = styled.div`
  display: flex;
  margin-bottom: 24px;
  border-bottom: 1px solid ${props => props.theme.borderColor};
`;

const Tab = styled.button`
  background: none;
  border: none;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: ${props => props.active ? '600' : '400'};
  color: ${props => props.active ? props.theme.primary : props.theme.textSecondary};
  cursor: pointer;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: ${props => props.active ? props.theme.primary : 'transparent'};
  }
  
  &:hover {
    color: ${props => props.theme.primary};
  }
`;

const TabIcon = styled.span`
  margin-right: 8px;
  display: inline-flex;
  align-items: center;
`;

const ItemsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
`;

const VaultDashboard = ({ items, onToggleFavorite, onSelectItem, onAddItem }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [filteredItems, setFilteredItems] = useState([]);
  
  useEffect(() => {
    filterItems();
  }, [items, searchQuery, activeTab]);
  
  const filterItems = () => {
    let filtered = [...items];
    
    // Filter by tab
    if (activeTab !== 'all') {
      if (activeTab === 'favorites') {
        filtered = filtered.filter(item => item.favorite);
      } else {
        filtered = filtered.filter(item => item.type === activeTab);
      }
    }
    
    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(item => {
        // Search in item name/title
        const nameMatch = (item.data.name || item.data.title || '').toLowerCase().includes(query);
        
        // Search in username/email for passwords
        const usernameMatch = item.type === 'password' && 
          ((item.data.username || '').toLowerCase().includes(query) || 
           (item.data.email || '').toLowerCase().includes(query));
        
        // Search in URL for passwords
        const urlMatch = item.type === 'password' && 
          (item.data.url || '').toLowerCase().includes(query);
        
        // Search in notes
        const notesMatch = (item.data.notes || item.data.note || '').toLowerCase().includes(query);
        
        return nameMatch || usernameMatch || urlMatch || notesMatch;
      });
    }
    
    setFilteredItems(filtered);
  };
  
  const getItemCountByType = (type) => {
    return items.filter(item => item.type === type).length;
  };
  
  const getFavoritesCount = () => {
    return items.filter(item => item.favorite).length;
  };
  
  return (
    <Container>
      <Header>
        <Title>Vault</Title>
        
        <div style={{ display: 'flex', gap: '16px' }}>
          <SearchBar>
            <SearchIcon>
              <FaSearch />
            </SearchIcon>
            <SearchInput 
              placeholder="Search vault..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </SearchBar>
          
          <AddButton onClick={onAddItem}>
            <FaPlus /> Add Item
          </AddButton>
        </div>
      </Header>
      
      <TabsContainer>
        <Tab 
          active={activeTab === 'all'} 
          onClick={() => setActiveTab('all')}
        >
          <TabIcon>All Items ({items.length})</TabIcon>
        </Tab>
        
        <Tab 
          active={activeTab === 'favorites'} 
          onClick={() => setActiveTab('favorites')}
        >
          <TabIcon><FaStar /></TabIcon>
          Favorites ({getFavoritesCount()})
        </Tab>
        
        <Tab 
          active={activeTab === 'password'} 
          onClick={() => setActiveTab('password')}
        >
          <TabIcon><FaLock /></TabIcon>
          Passwords ({getItemCountByType('password')})
        </Tab>
        
        <Tab 
          active={activeTab === 'card'} 
          onClick={() => setActiveTab('card')}
        >
          <TabIcon><FaCreditCard /></TabIcon>
          Payment Cards ({getItemCountByType('card')})
        </Tab>
        
        <Tab 
          active={activeTab === 'identity'} 
          onClick={() => setActiveTab('identity')}
        >
          <TabIcon><FaIdCard /></TabIcon>
          Identities ({getItemCountByType('identity')})
        </Tab>
        
        <Tab 
          active={activeTab === 'note'} 
          onClick={() => setActiveTab('note')}
        >
          <TabIcon><FaStickyNote /></TabIcon>
          Secure Notes ({getItemCountByType('note')})
        </Tab>
      </TabsContainer>
      
      {filteredItems.length > 0 ? (
        <ItemsGrid>
          {filteredItems.map(item => (
            <VaultItemCard 
              key={item.id}
              item={item}
              onToggleFavorite={onToggleFavorite}
              onSelect={onSelectItem}
            />
          ))}
        </ItemsGrid>
      ) : (
        <EmptyState 
          icon={<FaLock size={48} />}
          title="No items found"
          description={
            searchQuery 
              ? "No items match your search. Try different keywords." 
              : activeTab === 'all' 
                ? "Your vault is empty. Add your first item to get started." 
                : `You don't have any ${activeTab === 'favorites' ? 'favorites' : activeTab + 's'} yet.`
          }
          actionText={searchQuery ? "Clear search" : "Add item"}
          onAction={searchQuery ? () => setSearchQuery('') : onAddItem}
        />
      )}
    </Container>
  );
};

export default VaultDashboard;

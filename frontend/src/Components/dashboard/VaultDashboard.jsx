import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaSearch, FaPlus, FaLock, FaCreditCard, FaIdCard, FaStickyNote, FaStar } from 'react-icons/fa';
import VaultItemCard from '../vault/VaultItemCard';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${colors.border};
  gap: 16px;
  flex-wrap: wrap;
`;

const Title = styled.h1`
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: ${colors.text};
  display: flex;
  align-items: center;
  gap: 12px;

  &::before {
    content: '🔐';
    font-size: 1.5rem;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 16px;
  align-items: center;
`;

const SearchBar = styled.div`
  position: relative;
  width: 100%;
  max-width: 360px;
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 14px 16px 14px 48px;
  border-radius: 14px;
  border: 2px solid ${colors.border};
  background: ${colors.background};
  color: ${colors.text};
  font-size: 15px;
  transition: all 0.25s ease;

  &:hover {
    border-color: ${colors.borderLight};
    background: ${colors.backgroundSecondary};
  }

  &:focus {
    outline: none;
    border-color: ${colors.primary};
    background: ${colors.backgroundSecondary};
    box-shadow: 0 0 0 4px ${colors.primary}15;
  }

  &::placeholder {
    color: ${colors.textSecondary};
  }
`;

const SearchIcon = styled.div`
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: ${colors.primary};
  font-size: 16px;
`;

const AddButton = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 14px 22px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
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

const TabsContainer = styled.div`
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  overflow-x: auto;
  padding: 4px;
  background: ${colors.background};
  border-radius: 14px;

  &::-webkit-scrollbar {
    height: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: ${colors.borderLight};
    border-radius: 3px;
  }
`;

const Tab = styled.button`
  background: ${props => props.active
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%)`
    : 'transparent'};
  color: ${props => props.active ? '#ffffff' : colors.textSecondary};
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
      ? `linear-gradient(135deg, ${colors.primaryDark} 0%, #8B7BEF 100%)`
      : 'rgba(123, 104, 238, 0.1)'};
    color: ${props => props.active ? '#ffffff' : colors.primary};
  }
`;

const TabIcon = styled.span`
  display: inline-flex;
  align-items: center;
`;

const ItemsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;

  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 60px 40px;
  background: linear-gradient(135deg, ${colors.background} 0%, #f0f2ff 100%);
  border-radius: 20px;
  margin-top: 20px;
  border: 2px dashed ${colors.borderLight};
  animation: ${fadeIn} 0.4s ease-out;
`;

const EmptyIcon = styled.div`
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;

  svg {
    font-size: 36px;
    color: ${colors.primary};
  }
`;

const EmptyTitle = styled.h3`
  margin: 0 0 12px 0;
  color: ${colors.text};
  font-size: 1.5rem;
  font-weight: 700;
`;

const EmptyMessage = styled.p`
  color: ${colors.textSecondary};
  margin: 0 auto 24px;
  max-width: 420px;
  font-size: 1rem;
  line-height: 1.6;
`;

const EmptyAction = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 14px 28px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px ${colors.primary}40;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }
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

        <HeaderActions>
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
        </HeaderActions>
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
        <EmptyState>
          <EmptyIcon>
            <FaLock />
          </EmptyIcon>
          <EmptyTitle>No items found</EmptyTitle>
          <EmptyMessage>
            {searchQuery
              ? 'No items match your search. Try different keywords.'
              : activeTab === 'all'
                ? 'Your vault is empty. Add your first item to get started.'
                : `You don't have any ${activeTab === 'favorites' ? 'favorites' : activeTab + 's'} yet.`}
          </EmptyMessage>
          <EmptyAction onClick={searchQuery ? () => setSearchQuery('') : onAddItem}>
            {searchQuery ? 'Clear search' : 'Add item'}
          </EmptyAction>
        </EmptyState>
      )}
    </Container>
  );
};

export default VaultDashboard;

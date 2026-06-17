import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import { toast } from 'react-hot-toast';
import { FaSearch, FaPlus, FaLock, FaCreditCard, FaIdCard, FaStickyNote, FaStar, FaTimes, FaTrash, FaExclamationTriangle } from 'react-icons/fa';
import VaultItemCard from '../vault/VaultItemCard';
import PasswordItemForm from '../forms/PasswordItemForm';

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

const ModalOverlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
  animation: ${fadeIn} 0.2s ease-out;
`;

const ModalContent = styled.div`
  background: ${colors.backgroundSecondary};
  border-radius: 20px;
  padding: 28px;
  max-width: 560px;
  width: 100%;
  max-height: 86vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
`;

const ModalClose = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  background: ${colors.background};
  border: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 10px;
  border-radius: 10px;
  display: flex;
  transition: all 0.2s ease;

  &:hover {
    color: ${colors.danger};
    background: ${colors.danger}15;
    border-color: ${colors.danger}40;
  }
`;

const ConfirmCard = styled(ModalContent)`
  max-width: 420px;
  text-align: center;
`;

const ConfirmIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: ${colors.danger}15;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 18px;

  svg {
    font-size: 28px;
    color: ${colors.danger};
  }
`;

const ConfirmTitle = styled.h3`
  margin: 0 0 10px 0;
  font-size: 20px;
  font-weight: 700;
  color: ${colors.text};
`;

const ConfirmText = styled.p`
  margin: 0 0 24px 0;
  font-size: 14px;
  line-height: 1.6;
  color: ${colors.textSecondary};

  strong {
    color: ${colors.text};
  }
`;

const ConfirmActions = styled.div`
  display: flex;
  gap: 12px;
  justify-content: center;
`;

const CancelButton = styled.button`
  padding: 12px 24px;
  background: ${colors.background};
  color: ${colors.textSecondary};
  border: 1px solid ${colors.border};
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    background: ${colors.border};
    color: ${colors.text};
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const DangerButton = styled.button`
  padding: 12px 24px;
  background: linear-gradient(135deg, ${colors.danger} 0%, #dc2626 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 14px ${colors.danger}40;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.danger}50;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    box-shadow: none;
    transform: none;
  }
`;

const VaultDashboard = ({
  items,
  onToggleFavorite,
  onUpdateItem,
  onDeleteItem,
  onDecryptItem,
  onAddItem,
  canEdit = false
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [filteredItems, setFilteredItems] = useState([]);

  // Read-write state
  const [editingItem, setEditingItem] = useState(null); // decrypted item being edited
  const [openingEditor, setOpeningEditor] = useState(false); // decrypting before edit
  const [deletingItem, setDeletingItem] = useState(null); // item pending delete confirmation
  const [isDeleting, setIsDeleting] = useState(false);

  const filterItems = useCallback(() => {
    let filtered = [...items];

    // Filter by tab (items may use `type` or `item_type`)
    if (activeTab !== 'all') {
      if (activeTab === 'favorites') {
        filtered = filtered.filter(item => item.favorite);
      } else {
        filtered = filtered.filter(item => (item.type || item.item_type) === activeTab);
      }
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(item => {
        const type = item.type || item.item_type;
        const data = item.data || {};

        // Search in item name/title
        const nameMatch = (data.name || data.title || '').toLowerCase().includes(query);

        // Search in username/email for passwords
        const usernameMatch = type === 'password' &&
          ((data.username || '').toLowerCase().includes(query) ||
           (data.email || '').toLowerCase().includes(query));

        // Search in URL for passwords
        const urlMatch = type === 'password' &&
          (data.url || '').toLowerCase().includes(query);

        // Search in notes
        const notesMatch = (data.notes || data.note || '').toLowerCase().includes(query);

        return nameMatch || usernameMatch || urlMatch || notesMatch;
      });
    }

    setFilteredItems(filtered);
  }, [items, searchQuery, activeTab]);

  useEffect(() => {
    filterItems();
  }, [filterItems]);

  const getItemCountByType = (type) => {
    return items.filter(item => (item.type || item.item_type) === type).length;
  };

  const getFavoritesCount = () => {
    return items.filter(item => item.favorite).length;
  };

  // --- Read-write handlers ---------------------------------------------------

  // Favorite is metadata-only (PR A): never re-encrypts. Optimistic update +
  // rollback live in the context; here we just surface failures.
  const handleToggleFavorite = async (id) => {
    if (!onToggleFavorite) return;
    try {
      await onToggleFavorite(id);
    } catch {
      toast.error('Could not update favorite. Please try again.');
    }
  };

  // Open the editor for an item. Editing re-encrypts the secret, so it requires
  // an unlocked vault; PasswordItemForm only covers password-type items, and
  // lazy-loaded items must be decrypted first.
  const handleEditRequest = async (item) => {
    if (!item) return;
    const type = item.type || item.item_type;

    if (type !== 'password') {
      // No inline editor for cards/identities/notes — send the user to the
      // full vault where those types are managed.
      toast('Open the main vault to edit this item type.');
      if (onAddItem) onAddItem();
      return;
    }

    if (!canEdit) {
      toast.error('Unlock your vault to edit items.');
      if (onAddItem) onAddItem();
      return;
    }

    // Decrypt lazy-loaded items before editing so the form is pre-filled.
    if (!item.data && onDecryptItem && item.item_id) {
      setOpeningEditor(true);
      try {
        const decrypted = await onDecryptItem(item.item_id);
        setEditingItem(decrypted);
      } catch {
        toast.error('Failed to decrypt this item.');
        return;
      } finally {
        setOpeningEditor(false);
      }
    } else {
      setEditingItem(item);
    }
  };

  const handleEditSubmit = async (values, formikHelpers) => {
    if (!editingItem || !onUpdateItem) return;
    try {
      // Preserve any unknown fields already on the item; form values win.
      const updated = {
        ...editingItem,
        type: 'password',
        data: { ...(editingItem.data || {}), ...values }
      };
      await onUpdateItem(updated);
      toast.success('Item updated.');
      setEditingItem(null);
    } catch {
      toast.error('Failed to save changes. Please try again.');
    } finally {
      formikHelpers?.setSubmitting?.(false);
    }
  };

  const handleDeleteRequest = (id) => {
    // Items carry a DB `id` (used by context.deleteItem); fall back to
    // item_id defensively in case a variant lacks it.
    const item = items.find(i => (i.id ?? i.item_id) === id);
    if (item) setDeletingItem(item);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingItem || !onDeleteItem) return;
    setIsDeleting(true);
    try {
      await onDeleteItem(deletingItem.id ?? deletingItem.item_id);
      toast.success('Item deleted.');
      setDeletingItem(null);
    } catch {
      toast.error('Failed to delete item. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  const editTitle = (item) =>
    (item?.data?.name || item?.preview?.title || item?.data?.title || 'this item');

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
              key={item.id ?? item.item_id}
              item={item}
              onClick={handleEditRequest}
              onToggleFavorite={handleToggleFavorite}
              onEdit={handleEditRequest}
              onDelete={handleDeleteRequest}
              readOnly={false}
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

      {/* Decrypting a lazy-loaded item before opening the editor */}
      {openingEditor && (
        <ModalOverlay>
          <ConfirmCard>
            <ConfirmTitle>Decrypting…</ConfirmTitle>
            <ConfirmText>Preparing this item for editing.</ConfirmText>
          </ConfirmCard>
        </ModalOverlay>
      )}

      {/* Edit modal — re-encrypts via the existing updateItem path on submit */}
      {editingItem && (
        <ModalOverlay onClick={() => setEditingItem(null)}>
          <ModalContent onClick={e => e.stopPropagation()}>
            <ModalClose onClick={() => setEditingItem(null)} aria-label="Close editor">
              <FaTimes />
            </ModalClose>
            <PasswordItemForm
              initialValues={{ ...editingItem.data, id: editingItem.id ?? editingItem.item_id }}
              onSubmit={handleEditSubmit}
              onCancel={() => setEditingItem(null)}
            />
          </ModalContent>
        </ModalOverlay>
      )}

      {/* Delete confirmation */}
      {deletingItem && (
        <ModalOverlay onClick={() => !isDeleting && setDeletingItem(null)}>
          <ConfirmCard onClick={e => e.stopPropagation()}>
            <ConfirmIcon>
              <FaExclamationTriangle />
            </ConfirmIcon>
            <ConfirmTitle>Delete this item?</ConfirmTitle>
            <ConfirmText>
              <strong>{editTitle(deletingItem)}</strong> will be permanently removed
              from your vault. This action cannot be undone.
            </ConfirmText>
            <ConfirmActions>
              <CancelButton onClick={() => setDeletingItem(null)} disabled={isDeleting}>
                Cancel
              </CancelButton>
              <DangerButton onClick={handleDeleteConfirm} disabled={isDeleting}>
                <FaTrash /> {isDeleting ? 'Deleting...' : 'Delete'}
              </DangerButton>
            </ConfirmActions>
          </ConfirmCard>
        </ModalOverlay>
      )}
    </Container>
  );
};

export default VaultDashboard;

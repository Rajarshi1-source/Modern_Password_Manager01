import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { Plus, Users, Lock, Folder, RefreshCw, Settings, Share2, Activity } from 'lucide-react';
import CreateFolderModal from './CreateFolderModal';
import FolderDetailsModal from './FolderDetailsModal';
import InvitationsModal from './InvitationsModal';

const DashboardContainer = styled.div`
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
`;

const Title = styled.h1`
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 1rem;
`;

const Button = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: ${props => props.primary ? 'var(--primary, #4A6CF7)' : 'var(--secondary, #f5f5f5)'};
  color: ${props => props.primary ? 'white' : 'var(--text-primary, #1a1a1a)'};
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.primary ? 'var(--primary-dark, #3651d4)' : 'var(--hover, #e5e5e5)'};
    transform: translateY(-1px);
  }
  
  ${props => props.badge && `
    position: relative;
    
    &::after {
      content: '${props.badge}';
      position: absolute;
      top: -8px;
      right: -8px;
      background: #f44336;
      color: white;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.25rem 0.5rem;
      border-radius: 999px;
      min-width: 20px;
      text-align: center;
    }
  `}
`;

const FolderGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
`;

const FolderCard = styled.div`
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }
`;

const FolderHeader = styled.div`
  display: flex;
  align-items: start;
  gap: 1rem;
  margin-bottom: 1rem;
`;

const FolderIcon = styled.div`
  width: 48px;
  height: 48px;
  background: var(--primary-light, #e8f0fe);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary, #4A6CF7);
  flex-shrink: 0;
`;

const FolderInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

const FolderName = styled.div`
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const FolderOwner = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
`;

const FolderStats = styled.div`
  display: flex;
  gap: 1.5rem;
  margin-bottom: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border, #e0e0e0);
`;

const Stat = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
`;

const RoleBadge = styled.span`
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${props => {
    switch (props.role) {
      case 'owner': return '#4A6CF7';
      case 'admin': return '#7C3AED';
      case 'editor': return '#10B981';
      case 'viewer': return '#6B7280';
      default: return '#6B7280';
    }
  }};
  color: white;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-secondary, #666);
  
  svg {
    margin: 0 auto 1rem;
    opacity: 0.3;
  }
`;

const LoadingSpinner = styled.div`
  text-align: center;
  padding: 2rem;
  font-size: 1.125rem;
  color: var(--text-secondary, #666);
`;

const TabContainer = styled.div`
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--border, #e0e0e0);
`;

const Tab = styled.button`
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary, #666);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: -2px;
  
  ${props => props.active && `
    color: var(--primary, #4A6CF7);
    border-bottom-color: var(--primary, #4A6CF7);
  `}
  
  &:hover {
    color: var(--primary, #4A6CF7);
  }
`;

function SharedFoldersDashboard() {
  const [folders, setFolders] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showInvitationsModal, setShowInvitationsModal] = useState(false);
  const [pendingInvitations, setPendingInvitations] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [foldersRes, invitationsRes] = await Promise.all([
        axios.get('/api/vault/shared-folders/'),
        axios.get('/api/vault/shared-folders/invitations/pending/')
      ]);
      
      setFolders(foldersRes.data || []);
      setPendingInvitations(invitationsRes.data || []);
    } catch (error) {
      console.error('Failed to load shared folders:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFolderClick = (folder) => {
    setSelectedFolder(folder);
    setShowDetailsModal(true);
  };

  const filteredFolders = folders.filter(folder => {
    if (activeTab === 'all') return true;
    if (activeTab === 'owned') return folder.role === 'owner';
    if (activeTab === 'shared') return folder.role !== 'owner';
    return true;
  });

  if (loading) {
    return <LoadingSpinner>Loading shared folders...</LoadingSpinner>;
  }

  return (
    <DashboardContainer>
      <Header>
        <Title>Shared Folders</Title>
        <HeaderActions>
          {pendingInvitations.length > 0 && (
            <Button 
              onClick={() => setShowInvitationsModal(true)}
              badge={pendingInvitations.length}
            >
              <Share2 size={18} />
              Invitations
            </Button>
          )}
          <Button onClick={loadData}>
            <RefreshCw size={18} />
            Refresh
          </Button>
          <Button primary onClick={() => setShowCreateModal(true)}>
            <Plus size={18} />
            Create Folder
          </Button>
        </HeaderActions>
      </Header>

      <TabContainer>
        <Tab active={activeTab === 'all'} onClick={() => setActiveTab('all')}>
          All Folders
        </Tab>
        <Tab active={activeTab === 'owned'} onClick={() => setActiveTab('owned')}>
          Owned by Me
        </Tab>
        <Tab active={activeTab === 'shared'} onClick={() => setActiveTab('shared')}>
          Shared with Me
        </Tab>
      </TabContainer>

      {filteredFolders.length === 0 ? (
        <EmptyState>
          <Folder size={64} />
          <h3>No shared folders yet</h3>
          <p>Create a shared folder to collaborate securely with others.</p>
          <Button primary onClick={() => setShowCreateModal(true)} style={{ marginTop: '1rem' }}>
            <Plus size={18} />
            Create Your First Folder
          </Button>
        </EmptyState>
      ) : (
        <FolderGrid>
          {filteredFolders.map(folder => (
            <FolderCard key={folder.id} onClick={() => handleFolderClick(folder)}>
              <FolderHeader>
                <FolderIcon>
                  {folder.require_2fa ? <Lock size={24} /> : <Folder size={24} />}
                </FolderIcon>
                <FolderInfo>
                  <FolderName>{folder.name}</FolderName>
                  <FolderOwner>
                    Owner: {folder.owner} • <RoleBadge role={folder.role}>{folder.role}</RoleBadge>
                  </FolderOwner>
                </FolderInfo>
              </FolderHeader>
              
              {folder.description && (
                <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #666)', marginBottom: '1rem' }}>
                  {folder.description}
                </div>
              )}
              
              <FolderStats>
                <Stat>
                  <Users size={16} />
                  {folder.members_count} member{folder.members_count !== 1 ? 's' : ''}
                </Stat>
                <Stat>
                  <Lock size={16} />
                  {folder.items_count} item{folder.items_count !== 1 ? 's' : ''}
                </Stat>
              </FolderStats>
            </FolderCard>
          ))}
        </FolderGrid>
      )}

      {showCreateModal && (
        <CreateFolderModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            loadData();
          }}
        />
      )}

      {showDetailsModal && selectedFolder && (
        <FolderDetailsModal
          folder={selectedFolder}
          onClose={() => {
            setShowDetailsModal(false);
            setSelectedFolder(null);
          }}
          onRefresh={loadData}
        />
      )}

      {showInvitationsModal && (
        <InvitationsModal
          invitations={pendingInvitations}
          onClose={() => setShowInvitationsModal(false)}
          onRefresh={loadData}
        />
      )}
    </DashboardContainer>
  );
}

export default SharedFoldersDashboard;


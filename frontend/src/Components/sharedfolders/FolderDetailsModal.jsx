import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { 
  X, Users, Lock, Settings, Trash2, UserPlus, Mail, 
  Shield, Eye, Edit, Check, MoreVertical, AlertCircle 
} from 'lucide-react';
import toast from 'react-hot-toast';

const Overlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
`;

const Modal = styled.div`
  background: white;
  border-radius: 16px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
`;

const Header = styled.div`
  padding: 2rem;
  border-bottom: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
`;

const HeaderLeft = styled.div`
  flex: 1;
`;

const Title = styled.h2`
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 0.5rem 0;
`;

const Subtitle = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
`;

const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${props => {
    switch (props.type) {
      case 'owner': return '#4A6CF7';
      case 'admin': return '#7C3AED';
      case 'editor': return '#10B981';
      case 'viewer': return '#6B7280';
      case '2fa': return '#f59e0b';
      default: return '#6B7280';
    }
  }};
  color: white;
`;

const CloseButton = styled.button`
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0.5rem;
  border-radius: 8px;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--hover, #f5f5f5);
    color: var(--text-primary, #1a1a1a);
  }
`;

const TabContainer = styled.div`
  display: flex;
  gap: 0.5rem;
  padding: 0 2rem;
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

const Content = styled.div`
  padding: 2rem;
`;

const Section = styled.div`
  margin-bottom: 2rem;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const SectionTitle = styled.h3`
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const MemberList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
`;

const MemberCard = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: var(--background-secondary, #f9fafb);
  border-radius: 8px;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--hover, #f0f0f0);
  }
`;

const MemberAvatar = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary, #4A6CF7);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
`;

const MemberInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

const MemberName = styled.div`
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.25rem;
`;

const MemberEmail = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const MemberActions = styled.div`
  display: flex;
  gap: 0.5rem;
  align-items: center;
`;

const Select = styled.select`
  padding: 0.5rem 0.75rem;
  border: 2px solid var(--border, #e0e0e0);
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  background: white;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
  }
`;

const IconButton = styled.button`
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0.5rem;
  border-radius: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--hover, #e5e5e5);
    color: ${props => props.danger ? '#dc2626' : 'var(--text-primary, #1a1a1a)'};
  }
`;

const Button = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 0.875rem;
  
  ${props => props.primary ? `
    background: var(--primary, #4A6CF7);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-dark, #3651d4);
      transform: translateY(-1px);
    }
  ` : props.danger ? `
    background: #dc2626;
    color: white;
    
    &:hover:not(:disabled) {
      background: #b91c1c;
      transform: translateY(-1px);
    }
  ` : `
    background: var(--secondary, #f5f5f5);
    color: var(--text-primary, #1a1a1a);
    
    &:hover:not(:disabled) {
      background: var(--hover, #e5e5e5);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid var(--border, #e0e0e0);
  border-radius: 8px;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
    box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
  }
`;

const InviteForm = styled.div`
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary, #666);
  font-size: 0.875rem;
`;

const ErrorBox = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  margin-bottom: 1rem;
  color: #991b1b;
  font-size: 0.875rem;
`;

const DangerZone = styled.div`
  border: 2px solid #dc2626;
  border-radius: 12px;
  padding: 1.5rem;
  background: #fef2f2;
`;

const DangerZoneTitle = styled.h4`
  color: #dc2626;
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const DangerZoneText = styled.p`
  color: #991b1b;
  font-size: 0.875rem;
  margin: 0 0 1rem 0;
  line-height: 1.5;
`;

function FolderDetailsModal({ folder, onClose, onRefresh }) {
  const [activeTab, setActiveTab] = useState('members');
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [inviting, setInviting] = useState(false);

  useEffect(() => {
    loadMembers();
  }, [folder.id]);

  const loadMembers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/vault/shared-folders/${folder.id}/members/`);
      setMembers(response.data || []);
      setError('');
    } catch (err) {
      console.error('Failed to load members:', err);
      setError('Failed to load folder members');
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim()) {
      toast.error('Please enter an email address');
      return;
    }

    setInviting(true);
    try {
      await axios.post(`/api/vault/shared-folders/${folder.id}/invite/`, {
        email: inviteEmail,
        role: inviteRole
      });
      toast.success(`Invitation sent to ${inviteEmail}`);
      setInviteEmail('');
      setInviteRole('viewer');
      loadMembers();
    } catch (err) {
      console.error('Failed to send invitation:', err);
      toast.error(err.response?.data?.error || 'Failed to send invitation');
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (memberId, newRole) => {
    try {
      await axios.patch(`/api/vault/shared-folders/${folder.id}/members/${memberId}/`, {
        role: newRole
      });
      toast.success('Member role updated');
      loadMembers();
    } catch (err) {
      console.error('Failed to update role:', err);
      toast.error('Failed to update member role');
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!confirm('Are you sure you want to remove this member from the folder?')) {
      return;
    }

    try {
      await axios.delete(`/api/vault/shared-folders/${folder.id}/members/${memberId}/`);
      toast.success('Member removed');
      loadMembers();
    } catch (err) {
      console.error('Failed to remove member:', err);
      toast.error('Failed to remove member');
    }
  };

  const handleDeleteFolder = async () => {
    if (!confirm(`Are you sure you want to delete "${folder.name}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await axios.delete(`/api/vault/shared-folders/${folder.id}/`);
      toast.success('Folder deleted successfully');
      onRefresh();
      onClose();
    } catch (err) {
      console.error('Failed to delete folder:', err);
      toast.error('Failed to delete folder');
    }
  };

  const canManage = folder.role === 'owner' || folder.role === 'admin';

  return (
    <Overlay onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Modal>
        <Header>
          <HeaderLeft>
            <Title>{folder.name}</Title>
            <Subtitle>
              <span>Owner: {folder.owner}</span>
              <Badge type={folder.role}>{folder.role}</Badge>
              {folder.require_2fa && <Badge type="2fa"><Shield size={12} /> 2FA Required</Badge>}
            </Subtitle>
            {folder.description && (
              <div style={{ marginTop: '0.75rem', color: 'var(--text-secondary, #666)' }}>
                {folder.description}
              </div>
            )}
          </HeaderLeft>
          <CloseButton onClick={onClose}>
            <X size={20} />
          </CloseButton>
        </Header>

        <TabContainer>
          <Tab active={activeTab === 'members'} onClick={() => setActiveTab('members')}>
            <Users size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
            Members ({members.length})
          </Tab>
          <Tab active={activeTab === 'settings'} onClick={() => setActiveTab('settings')}>
            <Settings size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
            Settings
          </Tab>
        </TabContainer>

        <Content>
          {error && (
            <ErrorBox>
              <AlertCircle size={18} />
              {error}
            </ErrorBox>
          )}

          {activeTab === 'members' && (
            <>
              {canManage && (
                <Section>
                  <SectionTitle>
                    <UserPlus size={20} />
                    Invite Members
                  </SectionTitle>
                  <InviteForm>
                    <Input
                      type="email"
                      placeholder="Email address"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleInvite()}
                    />
                    <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                      <option value="viewer">Viewer</option>
                      <option value="editor">Editor</option>
                      <option value="admin">Admin</option>
                    </Select>
                    <Button primary onClick={handleInvite} disabled={inviting}>
                      {inviting ? 'Sending...' : 'Invite'}
                    </Button>
                  </InviteForm>
                </Section>
              )}

              <Section>
                <SectionTitle>
                  <Users size={20} />
                  Current Members
                </SectionTitle>
                {loading ? (
                  <EmptyState>Loading members...</EmptyState>
                ) : members.length === 0 ? (
                  <EmptyState>No members yet</EmptyState>
                ) : (
                  <MemberList>
                    {members.map(member => (
                      <MemberCard key={member.id}>
                        <MemberAvatar>
                          {member.name ? member.name.charAt(0).toUpperCase() : member.email.charAt(0).toUpperCase()}
                        </MemberAvatar>
                        <MemberInfo>
                          <MemberName>{member.name || 'No name'}</MemberName>
                          <MemberEmail>{member.email}</MemberEmail>
                        </MemberInfo>
                        <MemberActions>
                          {canManage && member.role !== 'owner' ? (
                            <>
                              <Select
                                value={member.role}
                                onChange={(e) => handleRoleChange(member.id, e.target.value)}
                              >
                                <option value="viewer">Viewer</option>
                                <option value="editor">Editor</option>
                                <option value="admin">Admin</option>
                              </Select>
                              <IconButton danger onClick={() => handleRemoveMember(member.id)}>
                                <Trash2 size={18} />
                              </IconButton>
                            </>
                          ) : (
                            <Badge type={member.role}>{member.role}</Badge>
                          )}
                        </MemberActions>
                      </MemberCard>
                    ))}
                  </MemberList>
                )}
              </Section>
            </>
          )}

          {activeTab === 'settings' && (
            <>
              {canManage ? (
                <Section>
                  <DangerZone>
                    <DangerZoneTitle>
                      <AlertCircle size={20} />
                      Danger Zone
                    </DangerZoneTitle>
                    <DangerZoneText>
                      Deleting this folder will remove all items and revoke access for all members. This action cannot be undone.
                    </DangerZoneText>
                    <Button danger onClick={handleDeleteFolder}>
                      <Trash2 size={18} />
                      Delete Folder
                    </Button>
                  </DangerZone>
                </Section>
              ) : (
                <EmptyState>
                  <Lock size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
                  <div>You don't have permission to modify folder settings</div>
                </EmptyState>
              )}
            </>
          )}
        </Content>
      </Modal>
    </Overlay>
  );
}

export default FolderDetailsModal;


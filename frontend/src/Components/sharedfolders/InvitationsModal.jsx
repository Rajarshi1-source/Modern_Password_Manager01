import React, { useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { X, Mail, Check, XCircle, Clock, Users, Shield, Info } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDistanceToNow } from 'date-fns';

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
  max-width: 700px;
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
  align-items: center;
`;

const Title = styled.h2`
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
`;

const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  background: var(--primary, #4A6CF7);
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

const Content = styled.div`
  padding: 2rem;
`;

const InfoBox = styled.div`
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  
  svg {
    flex-shrink: 0;
    color: #0284c7;
  }
  
  .content {
    font-size: 0.875rem;
    color: #0c4a6e;
    line-height: 1.5;
  }
`;

const InvitationList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1rem;
`;

const InvitationCard = styled.div`
  border: 2px solid var(--border, #e0e0e0);
  border-radius: 12px;
  padding: 1.5rem;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: var(--primary, #4A6CF7);
    box-shadow: 0 4px 12px rgba(74, 108, 247, 0.15);
  }
`;

const InvitationHeader = styled.div`
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

const InvitationInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

const FolderName = styled.div`
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.25rem;
`;

const InviterInfo = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
  margin-bottom: 0.5rem;
`;

const InvitationMeta = styled.div`
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
`;

const MetaItem = styled.div`
  display: flex;
  align-items: center;
  gap: 0.375rem;
`;

const RoleBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${props => {
    switch (props.role) {
      case 'admin': return '#7C3AED';
      case 'editor': return '#10B981';
      case 'viewer': return '#6B7280';
      default: return '#6B7280';
    }
  }};
  color: white;
`;

const InvitationActions = styled.div`
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border, #e0e0e0);
`;

const Button = styled.button`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
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
  ` : `
    background: transparent;
    color: var(--text-secondary, #666);
    border: 2px solid var(--border, #e0e0e0);
    
    &:hover:not(:disabled) {
      background: var(--hover, #f5f5f5);
      border-color: #999;
      color: var(--text-primary, #1a1a1a);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 3rem 2rem;
  color: var(--text-secondary, #666);
  
  svg {
    margin: 0 auto 1rem;
    opacity: 0.3;
  }
  
  h3 {
    font-size: 1.125rem;
    font-weight: 600;
    margin: 0 0 0.5rem 0;
    color: var(--text-primary, #1a1a1a);
  }
  
  p {
    font-size: 0.875rem;
    margin: 0;
  }
`;

const LoadingSpinner = styled.div`
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary, #666);
`;

function InvitationsModal({ invitations: initialInvitations, onClose, onRefresh }) {
  const [invitations, setInvitations] = useState(initialInvitations);
  const [processing, setProcessing] = useState({});

  const handleAccept = async (invitationId) => {
    setProcessing(prev => ({ ...prev, [invitationId]: 'accepting' }));
    
    try {
      await axios.post(`/api/vault/shared-folders/invitations/${invitationId}/accept/`);
      toast.success('Invitation accepted!');
      
      // Remove from list
      setInvitations(prev => prev.filter(inv => inv.id !== invitationId));
      
      // Refresh parent
      onRefresh();
    } catch (err) {
      console.error('Failed to accept invitation:', err);
      toast.error(err.response?.data?.error || 'Failed to accept invitation');
    } finally {
      setProcessing(prev => {
        const newState = { ...prev };
        delete newState[invitationId];
        return newState;
      });
    }
  };

  const handleDecline = async (invitationId) => {
    setProcessing(prev => ({ ...prev, [invitationId]: 'declining' }));
    
    try {
      await axios.post(`/api/vault/shared-folders/invitations/${invitationId}/decline/`);
      toast.success('Invitation declined');
      
      // Remove from list
      setInvitations(prev => prev.filter(inv => inv.id !== invitationId));
    } catch (err) {
      console.error('Failed to decline invitation:', err);
      toast.error('Failed to decline invitation');
    } finally {
      setProcessing(prev => {
        const newState = { ...prev };
        delete newState[invitationId];
        return newState;
      });
    }
  };

  return (
    <Overlay onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Modal>
        <Header>
          <Title>
            <Mail size={24} />
            Folder Invitations
            {invitations.length > 0 && <Badge>{invitations.length}</Badge>}
          </Title>
          <CloseButton onClick={onClose}>
            <X size={20} />
          </CloseButton>
        </Header>

        <Content>
          {invitations.length > 0 && (
            <InfoBox>
              <Info size={20} />
              <div className="content">
                You've been invited to collaborate on {invitations.length} shared folder{invitations.length !== 1 ? 's' : ''}. 
                Review the details and accept or decline each invitation.
              </div>
            </InfoBox>
          )}

          {invitations.length === 0 ? (
            <EmptyState>
              <Check size={64} />
              <h3>All caught up!</h3>
              <p>You don't have any pending folder invitations.</p>
            </EmptyState>
          ) : (
            <InvitationList>
              {invitations.map(invitation => (
                <InvitationCard key={invitation.id}>
                  <InvitationHeader>
                    <FolderIcon>
                      {invitation.folder.require_2fa ? <Shield size={24} /> : <Users size={24} />}
                    </FolderIcon>
                    <InvitationInfo>
                      <FolderName>{invitation.folder_name}</FolderName>
                      <InviterInfo>
                        Invited by <strong>{invitation.invited_by}</strong>
                      </InviterInfo>
                      {invitation.folder.description && (
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #666)', marginTop: '0.5rem' }}>
                          {invitation.folder.description}
                        </div>
                      )}
                    </InvitationInfo>
                  </InvitationHeader>

                  <InvitationMeta>
                    <MetaItem>
                      <RoleBadge role={invitation.role}>{invitation.role}</RoleBadge>
                    </MetaItem>
                    {invitation.folder.require_2fa && (
                      <MetaItem>
                        <Shield size={14} />
                        2FA Required
                      </MetaItem>
                    )}
                    <MetaItem>
                      <Clock size={14} />
                      {formatDistanceToNow(new Date(invitation.created_at), { addSuffix: true })}
                    </MetaItem>
                  </InvitationMeta>

                  <InvitationActions>
                    <Button
                      primary
                      onClick={() => handleAccept(invitation.id)}
                      disabled={processing[invitation.id]}
                    >
                      {processing[invitation.id] === 'accepting' ? (
                        'Accepting...'
                      ) : (
                        <>
                          <Check size={18} />
                          Accept
                        </>
                      )}
                    </Button>
                    <Button
                      onClick={() => handleDecline(invitation.id)}
                      disabled={processing[invitation.id]}
                    >
                      {processing[invitation.id] === 'declining' ? (
                        'Declining...'
                      ) : (
                        <>
                          <XCircle size={18} />
                          Decline
                        </>
                      )}
                    </Button>
                  </InvitationActions>
                </InvitationCard>
              ))}
            </InvitationList>
          )}
        </Content>
      </Modal>
    </Overlay>
  );
}

export default InvitationsModal;


import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaUserPlus, FaUserShield, FaExclamationTriangle, FaCheck, FaTimes, FaHourglassHalf, FaKey, FaCog, FaTrash, FaShieldAlt } from 'react-icons/fa';
import api from '../../../services/api';
import Button from '../../common/Button';
import Input from '../../common/Input';
import Modal from '../../common/Modal';
import Select from '../../common/Select';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
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
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  padding: 32px 24px;
  max-width: 1000px;
  margin: 0 auto;
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 40px;
`;

const HeaderIcon = styled.div`
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  
  svg {
    font-size: 32px;
    color: ${colors.primary};
  }
`;

const PageTitle = styled.h1`
  font-size: 32px;
  font-weight: 800;
  margin: 0 0 12px 0;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

const PageSubtitle = styled.p`
  color: ${colors.textSecondary};
  font-size: 16px;
  margin: 0;
`;

const Section = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 28px;
  box-shadow: 0 4px 20px rgba(123, 104, 238, 0.08);
  border: 1px solid ${colors.border};
  animation: ${fadeIn} 0.4s ease-out;
  animation-delay: ${props => props.$delay || '0s'};
  animation-fill-mode: backwards;
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid ${colors.border};
`;

const SectionIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}20 0%, ${props => props.$color || colors.primary}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 20px;
    color: ${props => props.$color || colors.primary};
  }
`;

const SectionTitle = styled.h2`
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: ${colors.text};
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 48px 24px;
  background: linear-gradient(135deg, ${colors.background} 0%, ${colors.border}30 100%);
  border-radius: 16px;
  border: 2px dashed ${colors.border};
`;

const EmptyIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 24px;
    color: ${colors.primary};
    opacity: 0.6;
  }
`;

const EmptyText = styled.p`
  color: ${colors.textSecondary};
  font-size: 15px;
  margin: 0;
`;

const ContactList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
`;

const ContactCard = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-radius: 16px;
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  transition: all 0.25s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    box-shadow: 0 4px 12px rgba(123, 104, 238, 0.08);
    transform: translateX(4px);
  }
`;

const ContactInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const ContactName = styled.div`
  font-weight: 700;
  font-size: 16px;
  color: ${colors.text};
`;

const ContactMeta = styled.div`
  font-size: 13px;
  color: ${colors.textSecondary};
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
`;

const MetaBadge = styled.span`
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  background: ${props => {
    if (props.$variant === 'success') return `${colors.success}15`;
    if (props.$variant === 'warning') return `${colors.warning}15`;
    if (props.$variant === 'danger') return `${colors.danger}15`;
    return `${colors.primary}15`;
  }};
  color: ${props => {
    if (props.$variant === 'success') return colors.success;
    if (props.$variant === 'warning') return colors.warning;
    if (props.$variant === 'danger') return colors.danger;
    return colors.primary;
  }};
`;

const RequestCard = styled.div`
  padding: 20px;
  border-radius: 16px;
  background: ${colors.backgroundSecondary};
  border: 1px solid ${colors.border};
  margin-bottom: 14px;
  position: relative;
  transition: all 0.25s ease;
  
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    border-radius: 4px 0 0 4px;
    background: ${props => {
      if (props.$status === 'pending') return colors.warning;
      if (props.$status === 'approved' || props.$status === 'auto_approved') return colors.success;
      if (props.$status === 'rejected') return colors.danger;
      return colors.primary;
    }};
  }
  
  &:hover {
    border-color: ${colors.borderLight};
    box-shadow: 0 4px 12px rgba(123, 104, 238, 0.08);
  }
`;

const RequestHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
`;

const RequestTitle = styled.div`
  font-weight: 700;
  font-size: 16px;
  color: ${colors.text};
`;

const RequestStatus = styled.div`
  font-size: 12px;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 20px;
  background: ${props => {
    if (props.$status === 'pending') return `${colors.warning}15`;
    if (props.$status === 'approved' || props.$status === 'auto_approved') return `${colors.success}15`;
    if (props.$status === 'rejected') return `${colors.danger}15`;
    return `${colors.primary}15`;
  }};
  color: ${props => {
    if (props.$status === 'pending') return colors.warning;
    if (props.$status === 'approved' || props.$status === 'auto_approved') return colors.success;
    if (props.$status === 'rejected') return colors.danger;
    return colors.primary;
  }};
`;

const RequestInfo = styled.div`
  font-size: 14px;
  color: ${colors.textSecondary};
  margin-bottom: 12px;
  line-height: 1.6;
`;

const RequestActions = styled.div`
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
`;

const ActionGroup = styled.div`
  display: flex;
  gap: 10px;
`;

const ActionButton = styled.button`
  padding: 10px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  
  &.primary {
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
    color: white;
    box-shadow: 0 2px 8px ${colors.primary}30;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px ${colors.primary}40;
    }
  }
  
  &.success {
    background: linear-gradient(135deg, ${colors.success} 0%, #059669 100%);
    color: white;
    box-shadow: 0 2px 8px ${colors.success}30;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px ${colors.success}40;
    }
  }
  
  &.danger {
    background: linear-gradient(135deg, ${colors.danger} 0%, #dc2626 100%);
    color: white;
    box-shadow: 0 2px 8px ${colors.danger}30;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px ${colors.danger}40;
    }
  }
  
  &.secondary {
    background: ${colors.background};
    color: ${colors.text};
    border: 1px solid ${colors.border};
    
    &:hover {
      background: ${colors.border};
    }
  }
`;

const AddButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 16px;
  margin-top: 20px;
  background: linear-gradient(135deg, ${colors.primary}10 0%, ${colors.primaryLight}08 100%);
  border: 2px dashed ${colors.border};
  color: ${colors.primary};
  border-radius: 14px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  
  &:hover {
    background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}12 100%);
    border-color: ${colors.primary};
    transform: translateY(-2px);
  }
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const LoadingState = styled.div`
  text-align: center;
  padding: 60px;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

const EmergencyAccess = () => {
  const [contacts, setContacts] = useState({ my_emergency_contacts: [], i_am_trusted_for: [] });
  const [requests, setRequests] = useState({ my_requests: [], others_requests: [] });
  const [loading, setLoading] = useState(true);
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  
  const [newContactEmail, setNewContactEmail] = useState('');
  const [waitingPeriod, setWaitingPeriod] = useState(24);
  const [accessType, setAccessType] = useState('view');
  const [selectedContact, setSelectedContact] = useState(null);
  const [requestReason, setRequestReason] = useState('');
  
  useEffect(() => {
    loadContacts();
    loadRequests();
    
    const interval = setInterval(loadRequests, 30000);
    return () => clearInterval(interval);
  }, []);
  
  const loadContacts = async () => {
    try {
      const response = await api.get('/user/emergency-contacts/');
      setContacts(response.data);
    } catch (error) {
      console.error('Error loading emergency contacts:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadRequests = async () => {
    try {
      const response = await api.get('/user/emergency-access-requests/');
      setRequests(response.data);
    } catch (error) {
      console.error('Error loading access requests:', error);
    }
  };
  
  const handleAddContact = async () => {
    try {
      setLoading(true);
      await api.post('/user/emergency-contacts/', {
        email: newContactEmail,
        waiting_period_hours: waitingPeriod,
        access_type: accessType
      });
      
      setNewContactEmail('');
      setWaitingPeriod(24);
      setAccessType('view');
      setShowAddModal(false);
      loadContacts();
    } catch (error) {
      console.error('Error adding emergency contact:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRemoveContact = async (contactId) => {
    if (window.confirm('Are you sure you want to remove this emergency contact?')) {
      try {
        setLoading(true);
        await api.delete('/user/emergency-contacts/', { data: { contact_id: contactId } });
        loadContacts();
      } catch (error) {
        console.error('Error removing emergency contact:', error);
      } finally {
        setLoading(false);
      }
    }
  };
  
  const handleUpdateSettings = async () => {
    if (!selectedContact) return;
    
    try {
      setLoading(true);
      await api.put(`/user/emergency-contacts/${selectedContact.id}/`, {
        waiting_period_hours: waitingPeriod,
        access_type: accessType
      });
      setShowSettingsModal(false);
      loadContacts();
    } catch (error) {
      console.error('Error updating emergency contact:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRequestAccess = async () => {
    if (!selectedContact) return;
    
    try {
      setLoading(true);
      await api.post('/user/emergency-request/', {
        contact_id: selectedContact.id,
        reason: requestReason
      });
      setShowRequestModal(false);
      setRequestReason('');
      loadRequests();
    } catch (error) {
      console.error('Error requesting emergency access:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRespondToInvitation = async (contactId, response) => {
    try {
      setLoading(true);
      await api.post('/user/emergency-invitation-response/', {
        contact_id: contactId,
        response: response
      });
      loadContacts();
    } catch (error) {
      console.error('Error responding to invitation:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRespondToRequest = async (requestId, response) => {
    try {
      setLoading(true);
      await api.post('/user/emergency-request-response/', {
        request_id: requestId,
        response: response
      });
      loadRequests();
    } catch (error) {
      console.error('Error responding to access request:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
  };
  
  const formatTimeRemaining = (timestamp) => {
    if (!timestamp) return 'N/A';
    
    const now = new Date();
    const target = new Date(timestamp);
    const diff = target - now;
    
    if (diff <= 0) return 'Now';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    return `${hours}h ${minutes}m`;
  };
  
  const renderMyContacts = () => (
    <Section $delay="0.1s">
      <SectionHeader>
        <SectionIcon $color={colors.primary}>
          <FaUserShield />
        </SectionIcon>
        <SectionTitle>My Emergency Contacts</SectionTitle>
      </SectionHeader>
      
      {contacts.my_emergency_contacts.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaUserShield />
          </EmptyIcon>
          <EmptyText>You haven't added any emergency contacts yet.</EmptyText>
        </EmptyState>
      ) : (
        <ContactList>
          {contacts.my_emergency_contacts.map(contact => (
            <ContactCard key={contact.id}>
              <ContactInfo>
                <ContactName>👤 {contact.username}</ContactName>
                <ContactMeta>
                  {contact.email}
                  <MetaBadge>{contact.access_type === 'view' ? '👁️ View Only' : '✏️ Full Access'}</MetaBadge>
                  <MetaBadge>⏱️ {contact.waiting_period_hours}h wait</MetaBadge>
                  <MetaBadge $variant={
                    contact.status === 'pending' ? 'warning' : 
                    contact.status === 'approved' ? 'success' : 'danger'
                  }>
                    {contact.status === 'pending' ? '⏳ Pending' : 
                     contact.status === 'approved' ? '✅ Approved' : '❌ Rejected'}
                  </MetaBadge>
                </ContactMeta>
              </ContactInfo>
              
              <ActionGroup>
                <ActionButton 
                  className="secondary"
                  onClick={() => {
                    setSelectedContact(contact);
                    setWaitingPeriod(contact.waiting_period_hours);
                    setAccessType(contact.access_type);
                    setShowSettingsModal(true);
                  }}
                >
                  <FaCog /> Settings
                </ActionButton>
                <ActionButton 
                  className="danger"
                  onClick={() => handleRemoveContact(contact.id)}
                >
                  <FaTrash /> Remove
                </ActionButton>
              </ActionGroup>
            </ContactCard>
          ))}
        </ContactList>
      )}
      
      <AddButton onClick={() => setShowAddModal(true)}>
        <FaUserPlus /> Add Emergency Contact
      </AddButton>
    </Section>
  );
  
  const renderTrustedAccounts = () => (
    <Section $delay="0.15s">
      <SectionHeader>
        <SectionIcon $color={colors.success}>
          <FaShieldAlt />
        </SectionIcon>
        <SectionTitle>Accounts I'm Trusted For</SectionTitle>
      </SectionHeader>
      
      {contacts.i_am_trusted_for.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaShieldAlt />
          </EmptyIcon>
          <EmptyText>You are not an emergency contact for any accounts.</EmptyText>
        </EmptyState>
      ) : (
        <ContactList>
          {contacts.i_am_trusted_for.map(contact => (
            <ContactCard key={contact.id}>
              <ContactInfo>
                <ContactName>🔐 {contact.username}'s Vault</ContactName>
                <ContactMeta>
                  <MetaBadge>{contact.access_type === 'view' ? '👁️ View Only' : '✏️ Full Access'}</MetaBadge>
                  <MetaBadge>⏱️ {contact.waiting_period_hours}h wait</MetaBadge>
                  <MetaBadge $variant={
                    contact.status === 'pending' ? 'warning' : 
                    contact.status === 'approved' ? 'success' : 'danger'
                  }>
                    {contact.status === 'pending' ? '⏳ Pending' : 
                     contact.status === 'approved' ? '✅ Approved' : '❌ Rejected'}
                  </MetaBadge>
                </ContactMeta>
              </ContactInfo>
              
              <ActionGroup>
                {contact.status === 'pending' && (
                  <>
                    <ActionButton 
                      className="success"
                      onClick={() => handleRespondToInvitation(contact.id, 'approved')}
                    >
                      <FaCheck /> Accept
                    </ActionButton>
                    <ActionButton 
                      className="danger"
                      onClick={() => handleRespondToInvitation(contact.id, 'rejected')}
                    >
                      <FaTimes /> Reject
                    </ActionButton>
                  </>
                )}
                
                {contact.status === 'approved' && (
                  <ActionButton 
                    className="primary"
                    onClick={() => {
                      setSelectedContact(contact);
                      setShowRequestModal(true);
                    }}
                  >
                    <FaKey /> Request Access
                  </ActionButton>
                )}
              </ActionGroup>
            </ContactCard>
          ))}
        </ContactList>
      )}
    </Section>
  );
  
  const renderMyRequests = () => (
    <Section $delay="0.2s">
      <SectionHeader>
        <SectionIcon $color={colors.warning}>
          <FaHourglassHalf />
        </SectionIcon>
        <SectionTitle>My Access Requests</SectionTitle>
      </SectionHeader>
      
      {requests.my_requests.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaHourglassHalf />
          </EmptyIcon>
          <EmptyText>You haven't requested emergency access to any vaults.</EmptyText>
        </EmptyState>
      ) : (
        <div>
          {requests.my_requests.map(request => (
            <RequestCard key={request.id} $status={request.status}>
              <RequestHeader>
                <RequestTitle>🔐 {request.vault_owner}'s Vault</RequestTitle>
                <RequestStatus $status={request.status}>
                  {request.status === 'pending' ? '⏳ Waiting' : 
                   request.status === 'approved' || request.status === 'auto_approved' ? '✅ Approved' : '❌ Rejected'}
                </RequestStatus>
              </RequestHeader>
              
              <RequestInfo>
                📅 Requested: {formatTimestamp(request.requested_at)}
              </RequestInfo>
              
              {request.status === 'pending' && (
                <RequestInfo>
                  ⏱️ Auto-approve in: <strong>{formatTimeRemaining(request.auto_approve_at)}</strong>
                </RequestInfo>
              )}
              
              {(request.status === 'approved' || request.status === 'auto_approved') && (
                <>
                  <RequestInfo>
                    🔑 Access type: {request.access_type === 'view' ? 'View Only' : 'Full Access'}
                  </RequestInfo>
                  <RequestInfo>
                    ⏰ Expires: {formatTimestamp(request.expires_at)}
                  </RequestInfo>
                  <RequestActions>
                    <ActionButton 
                      className="primary"
                      as="a"
                      href={`/emergency-vault/${request.id}`}
                      target="_blank"
                    >
                      <FaKey /> Access Vault
                    </ActionButton>
                  </RequestActions>
                </>
              )}
            </RequestCard>
          ))}
        </div>
      )}
    </Section>
  );
  
  const renderOthersRequests = () => (
    <Section $delay="0.25s">
      <SectionHeader>
        <SectionIcon $color={colors.danger}>
          <FaExclamationTriangle />
        </SectionIcon>
        <SectionTitle>Access Requests to My Vault</SectionTitle>
      </SectionHeader>
      
      {requests.others_requests.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaExclamationTriangle />
          </EmptyIcon>
          <EmptyText>No one has requested emergency access to your vault.</EmptyText>
        </EmptyState>
      ) : (
        <div>
          {requests.others_requests.map(request => (
            <RequestCard key={request.id} $status={request.status}>
              <RequestHeader>
                <RequestTitle>⚠️ {request.emergency_contact} is requesting access</RequestTitle>
                <RequestStatus $status={request.status}>
                  {request.status === 'pending' ? '⏳ Waiting' : 
                   request.status === 'approved' || request.status === 'auto_approved' ? '✅ Approved' : '❌ Rejected'}
                </RequestStatus>
              </RequestHeader>
              
              <RequestInfo>
                📅 Requested: {formatTimestamp(request.requested_at)}
              </RequestInfo>
              
              {request.reason && (
                <RequestInfo>
                  📝 Reason: {request.reason}
                </RequestInfo>
              )}
              
              {request.status === 'pending' && (
                <>
                  <RequestInfo>
                    ⏱️ Auto-approve in: <strong>{formatTimeRemaining(request.auto_approve_at)}</strong>
                  </RequestInfo>
                  <RequestActions>
                    <ActionButton 
                      className="success"
                      onClick={() => handleRespondToRequest(request.id, 'approved')}
                    >
                      <FaCheck /> Approve
                    </ActionButton>
                    <ActionButton 
                      className="danger"
                      onClick={() => handleRespondToRequest(request.id, 'rejected')}
                    >
                      <FaTimes /> Reject
                    </ActionButton>
                  </RequestActions>
                </>
              )}
              
              {(request.status === 'approved' || request.status === 'auto_approved') && (
                <RequestInfo>
                  ⏰ Access expires: {formatTimestamp(request.expires_at)}
                </RequestInfo>
              )}
            </RequestCard>
          ))}
        </div>
      )}
    </Section>
  );
  
  if (loading && contacts.my_emergency_contacts.length === 0) {
    return (
      <Container>
        <LoadingState>
          <HeaderIcon>
            <FaShieldAlt />
          </HeaderIcon>
          <PageSubtitle>Loading emergency access...</PageSubtitle>
        </LoadingState>
      </Container>
    );
  }
  
  return (
    <Container>
      <Header>
        <HeaderIcon>
          <FaShieldAlt />
        </HeaderIcon>
        <PageTitle>Emergency Access</PageTitle>
        <PageSubtitle>Manage trusted contacts who can access your vault in emergencies</PageSubtitle>
      </Header>
      
      {renderMyContacts()}
      {renderTrustedAccounts()}
      {renderMyRequests()}
      {renderOthersRequests()}
      
      {/* Add Contact Modal */}
      <Modal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Add Emergency Contact"
      >
        <FormGroup>
          <Input
            label="Email Address"
            type="email"
            value={newContactEmail}
            onChange={(e) => setNewContactEmail(e.target.value)}
            placeholder="Enter email address"
            required
          />
        </FormGroup>
        
        <FormGroup>
          <Select
            label="Access Type"
            value={accessType}
            onChange={(e) => setAccessType(e.target.value)}
            options={[
              { value: 'view', label: 'View Only' },
              { value: 'full', label: 'Full Access' },
            ]}
          />
        </FormGroup>
        
        <FormGroup>
          <Input
            label="Waiting Period (hours)"
            type="number"
            value={waitingPeriod}
            onChange={(e) => setWaitingPeriod(e.target.value)}
            helperText="Time before emergency access is automatically granted"
            inputProps={{ min: 1, max: 720 }}
          />
        </FormGroup>
        
        <ActionGroup>
          <Button variant="secondary" onClick={() => setShowAddModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleAddContact}
            disabled={!newContactEmail || loading}
          >
            Add Contact
          </Button>
        </ActionGroup>
      </Modal>
      
      {/* Contact Settings Modal */}
      <Modal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        title="Emergency Contact Settings"
      >
        {selectedContact && (
          <>
            <FormGroup>
              <Input
                label="Email Address"
                value={selectedContact.email}
                disabled
              />
            </FormGroup>
            
            <FormGroup>
              <Select
                label="Access Type"
                value={accessType}
                onChange={(e) => setAccessType(e.target.value)}
                options={[
                  { value: 'view', label: 'View Only' },
                  { value: 'full', label: 'Full Access' },
                ]}
              />
            </FormGroup>
            
            <FormGroup>
              <Input
                label="Waiting Period (hours)"
                type="number"
                value={waitingPeriod}
                onChange={(e) => setWaitingPeriod(e.target.value)}
                helperText="Time before emergency access is automatically granted"
                inputProps={{ min: 1, max: 720 }}
              />
            </FormGroup>
            
            <ActionGroup>
              <Button variant="secondary" onClick={() => setShowSettingsModal(false)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleUpdateSettings}
                disabled={loading}
              >
                Save Changes
              </Button>
            </ActionGroup>
          </>
        )}
      </Modal>
      
      {/* Request Access Modal */}
      <Modal
        isOpen={showRequestModal}
        onClose={() => setShowRequestModal(false)}
        title="Request Emergency Access"
      >
        {selectedContact && (
          <>
            <FormGroup>
              <Input
                label="Account"
                value={`${selectedContact.username}'s Vault`}
                disabled
              />
            </FormGroup>
            
            <FormGroup>
              <Input
                label="Reason for Access"
                type="textarea"
                value={requestReason}
                onChange={(e) => setRequestReason(e.target.value)}
                placeholder="Explain why you need emergency access"
                inputProps={{ rows: 4 }}
              />
            </FormGroup>
            
            <div style={{ 
              marginBottom: '16px', 
              padding: '14px',
              background: `${colors.warning}10`,
              borderRadius: '12px',
              borderLeft: `3px solid ${colors.warning}`,
              fontSize: '14px',
              color: colors.text
            }}>
              <strong>⚠️ Note:</strong> If approved or after {selectedContact.waiting_period_hours} hours, 
              you'll receive {selectedContact.access_type === 'view' ? 'view-only' : 'full'} access 
              to this vault.
            </div>
            
            <ActionGroup>
              <Button variant="secondary" onClick={() => setShowRequestModal(false)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleRequestAccess}
                disabled={loading}
              >
                Request Access
              </Button>
            </ActionGroup>
          </>
        )}
      </Modal>
    </Container>
  );
};

export default EmergencyAccess;

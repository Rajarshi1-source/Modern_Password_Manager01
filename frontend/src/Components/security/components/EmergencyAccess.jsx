import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaUserPlus, FaUserShield, FaExclamationTriangle, FaCheck, FaTimes, FaHourglassHalf, FaKey } from 'react-icons/fa';
import api from '../../../services/api';
import Button from '../../common/Button';
import Input from '../../common/Input';
import Modal from '../../common/Modal';
import Select from '../../common/Select';

const Container = styled.div`
  padding: 24px;
`;

const Section = styled.div`
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
`;

const SectionTitle = styled.h2`
  font-size: 18px;
  margin-top: 0;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 24px;
  color: ${props => props.theme.textSecondary};
`;

const ContactList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ContactCard = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-radius: 6px;
  background: ${props => props.theme.backgroundPrimary};
`;

const ContactInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const ContactName = styled.div`
  font-weight: 500;
`;

const ContactMeta = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
`;

const RequestCard = styled.div`
  padding: 16px;
  border-radius: 6px;
  background: ${props => props.theme.backgroundPrimary};
  margin-bottom: 12px;
  
  ${props => props.status === 'pending' && `
    border-left: 3px solid ${props.theme.warning};
  `}
  
  ${props => props.status === 'approved' || props.status === 'auto_approved' ? `
    border-left: 3px solid ${props.theme.success};
  ` : ''}
  
  ${props => props.status === 'rejected' ? `
    border-left: 3px solid ${props.theme.error};
  ` : ''}
`;

const RequestHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
`;

const RequestTitle = styled.div`
  font-weight: 500;
`;

const RequestStatus = styled.div`
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  
  ${props => props.status === 'pending' && `
    background: ${props.theme.warningLight};
    color: ${props.theme.warning};
  `}
  
  ${props => props.status === 'approved' || props.status === 'auto_approved' ? `
    background: ${props.theme.successLight};
    color: ${props.theme.success};
  ` : ''}
  
  ${props => props.status === 'rejected' ? `
    background: ${props.theme.errorLight};
    color: ${props.theme.error};
  ` : ''}
`;

const RequestInfo = styled.div`
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
  margin-bottom: 12px;
`;

const RequestActions = styled.div`
  display: flex;
  gap: 8px;
  justify-content: flex-end;
`;

const ActionGroup = styled.div`
  display: flex;
  gap: 8px;
  justify-content: flex-end;
`;

const FormGroup = styled.div`
  margin-bottom: 16px;
`;

const EmergencyAccess = () => {
  const [contacts, setContacts] = useState({ my_emergency_contacts: [], i_am_trusted_for: [] });
  const [requests, setRequests] = useState({ my_requests: [], others_requests: [] });
  const [loading, setLoading] = useState(true);
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  
  // Form states
  const [newContactEmail, setNewContactEmail] = useState('');
  const [waitingPeriod, setWaitingPeriod] = useState(24);
  const [accessType, setAccessType] = useState('view');
  const [selectedContact, setSelectedContact] = useState(null);
  const [requestReason, setRequestReason] = useState('');
  
  // Load contacts and requests
  useEffect(() => {
    loadContacts();
    loadRequests();
    
    // Set up polling for requests status
    const interval = setInterval(loadRequests, 30000); // Check every 30 seconds
    
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
      
      // Reset form
      setNewContactEmail('');
      setWaitingPeriod(24);
      setAccessType('view');
      setShowAddModal(false);
      
      // Reload contacts
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
        await api.delete('/user/emergency-contacts/', {
          data: { contact_id: contactId }
        });
        
        // Reload contacts
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
      
      // Reload contacts
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
      
      // Reload requests
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
      
      // Reload contacts
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
      
      // Reload requests
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
    <Section>
      <SectionTitle>
        <FaUserShield /> My Emergency Contacts
      </SectionTitle>
      
      {contacts.my_emergency_contacts.length === 0 ? (
        <EmptyState>
          <p>You haven't added any emergency contacts yet.</p>
        </EmptyState>
      ) : (
        <ContactList>
          {contacts.my_emergency_contacts.map(contact => (
            <ContactCard key={contact.id}>
              <ContactInfo>
                <ContactName>{contact.username}</ContactName>
                <ContactMeta>
                  {contact.email} • {contact.access_type === 'view' ? 'View Only' : 'Full Access'} • 
                  {contact.waiting_period_hours}h waiting period
                </ContactMeta>
                <ContactMeta>
                  Status: {contact.status === 'pending' ? 'Pending Approval' : 
                          contact.status === 'approved' ? 'Approved' : 'Rejected'}
                </ContactMeta>
              </ContactInfo>
              
              <ActionGroup>
                <Button 
                  size="small" 
                  variant="secondary"
                  onClick={() => {
                    setSelectedContact(contact);
                    setWaitingPeriod(contact.waiting_period_hours);
                    setAccessType(contact.access_type);
                    setShowSettingsModal(true);
                  }}
                >
                  Settings
                </Button>
                <Button 
                  size="small" 
                  variant="danger"
                  onClick={() => handleRemoveContact(contact.id)}
                >
                  Remove
                </Button>
              </ActionGroup>
            </ContactCard>
          ))}
        </ContactList>
      )}
      
      <Button 
        style={{ marginTop: '16px' }} 
        onClick={() => setShowAddModal(true)}
      >
        <FaUserPlus /> Add Emergency Contact
      </Button>
    </Section>
  );
  
  const renderTrustedAccounts = () => (
    <Section>
      <SectionTitle>
        <FaUserShield /> Accounts I'm Trusted For
      </SectionTitle>
      
      {contacts.i_am_trusted_for.length === 0 ? (
        <EmptyState>
          <p>You are not an emergency contact for any accounts.</p>
        </EmptyState>
      ) : (
        <ContactList>
          {contacts.i_am_trusted_for.map(contact => (
            <ContactCard key={contact.id}>
              <ContactInfo>
                <ContactName>{contact.username}'s Vault</ContactName>
                <ContactMeta>
                  {contact.access_type === 'view' ? 'View Only' : 'Full Access'} • 
                  {contact.waiting_period_hours}h waiting period
                </ContactMeta>
                <ContactMeta>
                  Status: {contact.status === 'pending' ? 'Pending Approval' : 
                          contact.status === 'approved' ? 'Approved' : 'Rejected'}
                </ContactMeta>
              </ContactInfo>
              
              <ActionGroup>
                {contact.status === 'pending' && (
                  <>
                    <Button 
                      size="small" 
                      variant="primary"
                      onClick={() => handleRespondToInvitation(contact.id, 'approved')}
                    >
                      <FaCheck /> Accept
                    </Button>
                    <Button 
                      size="small" 
                      variant="danger"
                      onClick={() => handleRespondToInvitation(contact.id, 'rejected')}
                    >
                      <FaTimes /> Reject
                    </Button>
                  </>
                )}
                
                {contact.status === 'approved' && (
                  <Button 
                    size="small" 
                    variant="primary"
                    onClick={() => {
                      setSelectedContact(contact);
                      setShowRequestModal(true);
                    }}
                  >
                    <FaKey /> Request Access
                  </Button>
                )}
              </ActionGroup>
            </ContactCard>
          ))}
        </ContactList>
      )}
    </Section>
  );
  
  const renderMyRequests = () => (
    <Section>
      <SectionTitle>
        <FaHourglassHalf /> My Access Requests
      </SectionTitle>
      
      {requests.my_requests.length === 0 ? (
        <EmptyState>
          <p>You haven't requested emergency access to any vaults.</p>
        </EmptyState>
      ) : (
        <div>
          {requests.my_requests.map(request => (
            <RequestCard key={request.id} status={request.status}>
              <RequestHeader>
                <RequestTitle>{request.vault_owner}'s Vault</RequestTitle>
                <RequestStatus status={request.status}>
                  {request.status === 'pending' ? 'Waiting' : 
                   request.status === 'approved' || request.status === 'auto_approved' ? 'Approved' : 'Rejected'}
                </RequestStatus>
              </RequestHeader>
              
              <RequestInfo>
                Requested: {formatTimestamp(request.requested_at)}
              </RequestInfo>
              
              {request.status === 'pending' && (
                <RequestInfo>
                  Auto-approve in: {formatTimeRemaining(request.auto_approve_at)}
                </RequestInfo>
              )}
              
              {(request.status === 'approved' || request.status === 'auto_approved') && (
                <>
                  <RequestInfo>
                    Access type: {request.access_type === 'view' ? 'View Only' : 'Full Access'}
                  </RequestInfo>
                  <RequestInfo>
                    Expires: {formatTimestamp(request.expires_at)}
                  </RequestInfo>
                  <RequestActions>
                    <Button 
                      variant="primary"
                      as="a"
                      href={`/emergency-vault/${request.id}`}
                      target="_blank"
                    >
                      <FaKey /> Access Vault
                    </Button>
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
    <Section>
      <SectionTitle>
        <FaExclamationTriangle /> Access Requests to My Vault
      </SectionTitle>
      
      {requests.others_requests.length === 0 ? (
        <EmptyState>
          <p>No one has requested emergency access to your vault.</p>
        </EmptyState>
      ) : (
        <div>
          {requests.others_requests.map(request => (
            <RequestCard key={request.id} status={request.status}>
              <RequestHeader>
                <RequestTitle>{request.emergency_contact} is requesting access</RequestTitle>
                <RequestStatus status={request.status}>
                  {request.status === 'pending' ? 'Waiting' : 
                   request.status === 'approved' || request.status === 'auto_approved' ? 'Approved' : 'Rejected'}
                </RequestStatus>
              </RequestHeader>
              
              <RequestInfo>
                Requested: {formatTimestamp(request.requested_at)}
              </RequestInfo>
              
              {request.reason && (
                <RequestInfo>
                  Reason: {request.reason}
                </RequestInfo>
              )}
              
              {request.status === 'pending' && (
                <>
                  <RequestInfo>
                    Auto-approve in: {formatTimeRemaining(request.auto_approve_at)}
                  </RequestInfo>
                  <RequestActions>
                    <Button 
                      variant="primary"
                      onClick={() => handleRespondToRequest(request.id, 'approved')}
                    >
                      <FaCheck /> Approve
                    </Button>
                    <Button 
                      variant="danger"
                      onClick={() => handleRespondToRequest(request.id, 'rejected')}
                    >
                      <FaTimes /> Reject
                    </Button>
                  </RequestActions>
                </>
              )}
              
              {(request.status === 'approved' || request.status === 'auto_approved') && (
                <RequestInfo>
                  Access expires: {formatTimestamp(request.expires_at)}
                </RequestInfo>
              )}
            </RequestCard>
          ))}
        </div>
      )}
    </Section>
  );
  
  return (
    <Container>
      <h1>Emergency Access</h1>
      
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
            
            <div style={{ marginBottom: '16px' }}>
              <strong>Note:</strong> If approved or after {selectedContact.waiting_period_hours} hours, 
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

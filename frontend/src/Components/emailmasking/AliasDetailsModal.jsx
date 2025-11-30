import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { X, Mail, Calendar, Activity, AlertCircle } from 'lucide-react';

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
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
`;

const Header = styled.div`
  padding: 2rem;
  border-bottom: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: space-between;
  align-items: start;
`;

const HeaderInfo = styled.div`
  flex: 1;
`;

const Title = styled.h2`
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 0.5rem 0;
  word-break: break-all;
`;

const Subtitle = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
`;

const CloseButton = styled.button`
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0.5rem;
  flex-shrink: 0;
  
  &:hover {
    color: var(--text-primary, #1a1a1a);
  }
`;

const Body = styled.div`
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
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
`;

const InfoCard = styled.div`
  background: var(--secondary, #f5f5f5);
  padding: 1rem;
  border-radius: 8px;
`;

const InfoLabel = styled.div`
  font-size: 0.75rem;
  color: var(--text-secondary, #666);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.5rem;
`;

const InfoValue = styled.div`
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--primary, #4A6CF7);
`;

const ActivityList = styled.div`
  max-height: 300px;
  overflow-y: auto;
`;

const ActivityItem = styled.div`
  padding: 1rem;
  border-bottom: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: space-between;
  align-items: start;
  
  &:last-child {
    border-bottom: none;
  }
`;

const ActivityInfo = styled.div`
  flex: 1;
`;

const ActivityType = styled.div`
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.25rem;
`;

const ActivityDetails = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
`;

const ActivityTime = styled.div`
  font-size: 0.75rem;
  color: var(--text-secondary, #666);
  white-space: nowrap;
`;

const StatusBadge = styled.span`
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${props => props.active ? '#d4edda' : '#f8d7da'};
  color: ${props => props.active ? '#155724' : '#721c24'};
`;

const LoadingSpinner = styled.div`
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary, #666);
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary, #666);
  font-size: 0.875rem;
`;

const Footer = styled.div`
  padding: 1.5rem 2rem;
  border-top: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
`;

const Button = styled.button`
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--secondary, #f5f5f5);
  color: var(--text-primary, #1a1a1a);
  
  &:hover {
    background: var(--hover, #e5e5e5);
  }
`;

function AliasDetailsModal({ alias, onClose, onRefresh }) {
  const [activity, setActivity] = useState([]);
  const [loadingActivity, setLoadingActivity] = useState(true);

  useEffect(() => {
    loadActivity();
  }, [alias.id]);

  const loadActivity = async () => {
    setLoadingActivity(true);
    try {
      const response = await axios.get(`/api/email-masking/aliases/${alias.id}/activity/`);
      setActivity(response.data.activities || []);
    } catch (error) {
      console.error('Failed to load alias activity:', error);
    } finally {
      setLoadingActivity(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatActivityType = (type) => {
    const types = {
      'received': '📧 Email Received',
      'forwarded': '✅ Email Forwarded',
      'blocked': '🚫 Email Blocked',
      'spam': '⚠️ Spam Detected',
      'created': '✨ Alias Created',
      'deleted': '🗑️ Alias Deleted',
      'disabled': '⏸️ Alias Disabled',
      'enabled': '▶️ Alias Enabled'
    };
    return types[type] || type;
  };

  return (
    <Overlay onClick={onClose}>
      <Modal onClick={(e) => e.stopPropagation()}>
        <Header>
          <HeaderInfo>
            <Title>{alias.alias_email}</Title>
            <Subtitle>
              <StatusBadge active={alias.status === 'active'}>
                {alias.status}
              </StatusBadge>
              {' • '}
              Provider: {alias.provider}
              {alias.alias_name && ` • ${alias.alias_name}`}
            </Subtitle>
          </HeaderInfo>
          <CloseButton onClick={onClose}>
            <X size={24} />
          </CloseButton>
        </Header>

        <Body>
          <Section>
            <SectionTitle>
              <Mail size={20} />
              Overview
            </SectionTitle>
            {alias.description && (
              <InfoCard>
                <InfoLabel>Description</InfoLabel>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-primary, #1a1a1a)' }}>
                  {alias.description}
                </div>
              </InfoCard>
            )}
          </Section>

          <Section>
            <SectionTitle>
              <Activity size={20} />
              Statistics
            </SectionTitle>
            <InfoGrid>
              <InfoCard>
                <InfoLabel>Emails Received</InfoLabel>
                <InfoValue>{alias.emails_received || 0}</InfoValue>
              </InfoCard>
              <InfoCard>
                <InfoLabel>Emails Forwarded</InfoLabel>
                <InfoValue>{alias.emails_forwarded || 0}</InfoValue>
              </InfoCard>
              <InfoCard>
                <InfoLabel>Emails Blocked</InfoLabel>
                <InfoValue>{alias.emails_blocked || 0}</InfoValue>
              </InfoCard>
            </InfoGrid>
          </Section>

          <Section>
            <SectionTitle>
              <Calendar size={20} />
              Timeline
            </SectionTitle>
            <InfoGrid>
              <InfoCard>
                <InfoLabel>Created</InfoLabel>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-primary, #1a1a1a)' }}>
                  {formatDate(alias.created_at)}
                </div>
              </InfoCard>
              <InfoCard>
                <InfoLabel>Last Used</InfoLabel>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-primary, #1a1a1a)' }}>
                  {formatDate(alias.last_used_at)}
                </div>
              </InfoCard>
              {alias.expires_at && (
                <InfoCard>
                  <InfoLabel>Expires</InfoLabel>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-primary, #1a1a1a)' }}>
                    {formatDate(alias.expires_at)}
                  </div>
                </InfoCard>
              )}
            </InfoGrid>
          </Section>

          <Section>
            <SectionTitle>
              <AlertCircle size={20} />
              Recent Activity
            </SectionTitle>
            {loadingActivity ? (
              <LoadingSpinner>Loading activity...</LoadingSpinner>
            ) : activity.length === 0 ? (
              <EmptyState>No activity recorded yet</EmptyState>
            ) : (
              <ActivityList>
                {activity.map((item, index) => (
                  <ActivityItem key={index}>
                    <ActivityInfo>
                      <ActivityType>{formatActivityType(item.activity_type)}</ActivityType>
                      {item.sender_email && (
                        <ActivityDetails>From: {item.sender_email}</ActivityDetails>
                      )}
                      {item.subject && (
                        <ActivityDetails>Subject: {item.subject}</ActivityDetails>
                      )}
                    </ActivityInfo>
                    <ActivityTime>{formatDate(item.timestamp)}</ActivityTime>
                  </ActivityItem>
                ))}
              </ActivityList>
            )}
          </Section>
        </Body>

        <Footer>
          <Button onClick={onClose}>Close</Button>
        </Footer>
      </Modal>
    </Overlay>
  );
}

export default AliasDetailsModal;


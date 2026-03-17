import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import {
  Shield, Send, Download, RefreshCw, Plus, Clock,
  Lock, Eye, EyeOff, Globe, Hash, AlertTriangle,
  CheckCircle, XCircle, Users, Activity, Zap, Key
} from 'lucide-react';
import fheSharingService from '../../services/fhe/fheSharingService';
import CreateHomomorphicShareModal from './CreateHomomorphicShareModal';
import AutofillTokenCard from './AutofillTokenCard';

const shimmer = keyframes`
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 108, 247, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(74, 108, 247, 0); }
`;

const Container = styled.div`
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  animation: ${fadeIn} 0.4s ease;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  gap: 1rem;
  flex-wrap: wrap;
`;

const TitleSection = styled.div`
  flex: 1;
`;

const Title = styled.h1`
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
`;

const TitleIcon = styled.div`
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #4A6CF7, #7C3AED);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
`;

const Subtitle = styled.p`
  color: var(--text-secondary, #666);
  font-size: 0.95rem;
  margin: 0;
  max-width: 600px;
  line-height: 1.5;
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 0.75rem;
  flex-shrink: 0;
`;

const Button = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.25rem;
  background: ${p => p.$primary
    ? 'linear-gradient(135deg, #4A6CF7, #6366F1)'
    : 'var(--secondary, #f5f5f5)'};
  color: ${p => p.$primary ? 'white' : 'var(--text-primary, #1a1a1a)'};
  border: ${p => p.$primary ? 'none' : '1px solid var(--border, #e0e0e0)'};
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;

  &:hover {
    transform: translateY(-1px);
    box-shadow: ${p => p.$primary
      ? '0 4px 14px rgba(74, 108, 247, 0.35)'
      : '0 2px 8px rgba(0, 0, 0, 0.1)'};
  }

  &:active { transform: translateY(0); }
  &:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
`;

const StatusBar = styled.div`
  display: flex;
  gap: 1.5rem;
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, rgba(74, 108, 247, 0.06), rgba(124, 58, 237, 0.06));
  border-radius: 12px;
  margin-bottom: 2rem;
  flex-wrap: wrap;
`;

const StatusItem = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary, #666);

  strong {
    color: var(--text-primary, #1a1a1a);
    font-weight: 700;
    font-size: 1.1rem;
  }
`;

const StatusDot = styled.span`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${p => p.$active ? '#10B981' : '#EF4444'};
  animation: ${p => p.$active ? pulse : 'none'} 2s infinite;
`;

const TabContainer = styled.div`
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  background: var(--secondary, #f5f5f5);
  padding: 4px;
  border-radius: 12px;
  width: fit-content;
`;

const Tab = styled.button`
  padding: 0.65rem 1.25rem;
  background: ${p => p.$active ? 'white' : 'transparent'};
  border: none;
  border-radius: 8px;
  color: ${p => p.$active ? 'var(--primary, #4A6CF7)' : 'var(--text-secondary, #666)'};
  font-weight: ${p => p.$active ? '600' : '500'};
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: ${p => p.$active ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'};

  &:hover { color: var(--primary, #4A6CF7); }
`;

const TabBadge = styled.span`
  background: ${p => p.$active ? 'var(--primary, #4A6CF7)' : 'var(--border, #ddd)'};
  color: ${p => p.$active ? 'white' : 'var(--text-secondary, #666)'};
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  min-width: 20px;
  text-align: center;
`;

const SharesTable = styled.div`
  background: white;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  border: 1px solid var(--border, #eee);
`;

const TableHeader = styled.div`
  display: grid;
  grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 120px;
  gap: 1rem;
  padding: 0.85rem 1.5rem;
  background: var(--secondary, #f8f9fa);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #888);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border, #eee);
`;

const TableRow = styled.div`
  display: grid;
  grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 120px;
  gap: 1rem;
  padding: 1rem 1.5rem;
  align-items: center;
  border-bottom: 1px solid var(--border, #f0f0f0);
  transition: background 0.15s;
  animation: ${fadeIn} 0.3s ease;
  animation-fill-mode: both;

  &:hover { background: rgba(74, 108, 247, 0.03); }
  &:last-child { border-bottom: none; }
`;

const RecipientInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
`;

const Avatar = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4A6CF7, #7C3AED);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
`;

const RecipientName = styled.div`
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary, #1a1a1a);
`;

const RecipientDomains = styled.div`
  font-size: 0.8rem;
  color: var(--text-secondary, #888);
  display: flex;
  align-items: center;
  gap: 0.25rem;
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${p => {
    if (p.$status === 'active') return 'rgba(16, 185, 129, 0.1)';
    if (p.$status === 'expired') return 'rgba(245, 158, 11, 0.1)';
    if (p.$status === 'revoked') return 'rgba(239, 68, 68, 0.1)';
    return 'rgba(156, 163, 175, 0.1)';
  }};
  color: ${p => {
    if (p.$status === 'active') return '#059669';
    if (p.$status === 'expired') return '#D97706';
    if (p.$status === 'revoked') return '#DC2626';
    return '#6B7280';
  }};
`;

const UsageDisplay = styled.div`
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
  display: flex;
  align-items: center;
  gap: 0.3rem;
`;

const ExpiryDisplay = styled.div`
  font-size: 0.8rem;
  color: ${p => p.$soon ? '#D97706' : 'var(--text-secondary, #888)'};
  display: flex;
  align-items: center;
  gap: 0.3rem;
`;

const RevokeButton = styled.button`
  padding: 0.4rem 0.8rem;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  background: transparent;
  color: #DC2626;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(239, 68, 68, 0.08);
    border-color: #DC2626;
  }

  &:disabled { opacity: 0.4; cursor: not-allowed; }
`;

const ReceivedGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.25rem;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-secondary, #666);

  svg { margin: 0 auto 1.25rem; opacity: 0.25; }
  h3 { font-size: 1.2rem; margin-bottom: 0.5rem; color: var(--text-primary, #333); }
  p { max-width: 420px; margin: 0 auto; line-height: 1.6; }
`;

const LoadingSkeleton = styled.div`
  height: ${p => p.$h || '60px'};
  border-radius: 10px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: ${shimmer} 1.5s infinite;
  margin-bottom: 0.75rem;
`;

const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 10px;
  color: #B91C1C;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
`;


function HomomorphicSharingDashboard() {
  const [activeTab, setActiveTab] = useState('sent');
  const [sentShares, setSentShares] = useState([]);
  const [receivedShares, setReceivedShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [serviceStatus, setServiceStatus] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sentRes, receivedRes, statusRes] = await Promise.allSettled([
        fheSharingService.listMyShares(includeInactive),
        fheSharingService.listReceivedShares(),
        fheSharingService.getShareStatus(),
      ]);

      if (sentRes.status === 'fulfilled') setSentShares(sentRes.value?.shares || []);
      if (receivedRes.status === 'fulfilled') setReceivedShares(receivedRes.value?.shares || []);
      if (statusRes.status === 'fulfilled') setServiceStatus(statusRes.value);
    } catch (err) {
      setError(err.error || 'Failed to load sharing data');
    } finally {
      setLoading(false);
    }
  }, [includeInactive]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRevoke = async (shareId) => {
    if (!window.confirm('Revoke this share? The recipient will no longer be able to autofill.')) return;
    try {
      await fheSharingService.revokeShare(shareId);
      loadData();
    } catch (err) {
      setError(err.error || 'Failed to revoke share');
    }
  };

  const getShareStatus = (share) => {
    if (!share.is_active) return 'revoked';
    if (share.is_expired) return 'expired';
    if (share.is_usage_limit_reached) return 'limit';
    return 'active';
  };

  const formatExpiry = (expiresAt) => {
    if (!expiresAt) return 'Never';
    const date = new Date(expiresAt);
    const now = new Date();
    const diffMs = date - now;
    const diffHours = Math.floor(diffMs / 3600000);
    if (diffHours < 0) return 'Expired';
    if (diffHours < 24) return `${diffHours}h left`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d left`;
  };

  const isExpiringSoon = (expiresAt) => {
    if (!expiresAt) return false;
    const diffMs = new Date(expiresAt) - new Date();
    return diffMs > 0 && diffMs < 86400000;
  };

  const activeCount = sentShares.filter(s => s.is_active && !s.is_expired).length;

  return (
    <Container>
      <Header>
        <TitleSection>
          <Title>
            <TitleIcon><Shield size={22} /></TitleIcon>
            Homomorphic Password Sharing
          </Title>
          <Subtitle>
            Share passwords with FHE encryption — recipients can autofill but <strong>cannot see</strong> the password.
            Zero-knowledge sharing for teams and contractors.
          </Subtitle>
        </TitleSection>
        <HeaderActions>
          <Button onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Refresh
          </Button>
          <Button $primary onClick={() => setShowCreateModal(true)}>
            <Plus size={16} />
            New Share
          </Button>
        </HeaderActions>
      </Header>

      {/* Status Bar */}
      <StatusBar>
        <StatusItem>
          <StatusDot $active={serviceStatus?.status === 'operational'} />
          FHE Sharing {serviceStatus?.status === 'operational' ? 'Operational' : 'Initializing'}
        </StatusItem>
        <StatusItem>
          <Send size={15} />
          Sent: <strong>{sentShares.length}</strong>
        </StatusItem>
        <StatusItem>
          <Download size={15} />
          Received: <strong>{receivedShares.length}</strong>
        </StatusItem>
        <StatusItem>
          <CheckCircle size={15} color="#10B981" />
          Active: <strong>{activeCount}</strong>
        </StatusItem>
        <StatusItem>
          <Lock size={15} color="#7C3AED" />
          <EyeOff size={15} />
          Autofill-Only Mode
        </StatusItem>
      </StatusBar>

      {error && (
        <ErrorBanner>
          <AlertTriangle size={18} />
          {error}
          <Button onClick={() => setError(null)} style={{ marginLeft: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}>
            Dismiss
          </Button>
        </ErrorBanner>
      )}

      {/* Tabs */}
      <TabContainer>
        <Tab $active={activeTab === 'sent'} onClick={() => setActiveTab('sent')}>
          <Send size={15} /> Shared by Me
          <TabBadge $active={activeTab === 'sent'}>{sentShares.length}</TabBadge>
        </Tab>
        <Tab $active={activeTab === 'received'} onClick={() => setActiveTab('received')}>
          <Download size={15} /> Shared with Me
          <TabBadge $active={activeTab === 'received'}>{receivedShares.length}</TabBadge>
        </Tab>
        <Tab $active={activeTab === 'activity'} onClick={() => setActiveTab('activity')}>
          <Activity size={15} /> Activity
        </Tab>
      </TabContainer>

      {/* Loading State */}
      {loading && (
        <div>
          {[1, 2, 3].map(i => <LoadingSkeleton key={i} $h="64px" />)}
        </div>
      )}

      {/* Shared by Me Tab */}
      {!loading && activeTab === 'sent' && (
        <>
          {sentShares.length === 0 ? (
            <EmptyState>
              <Shield size={64} />
              <h3>No Shares Created Yet</h3>
              <p>
                Share a password with a team member. They'll be able to autofill it
                on specific websites, but they'll never see the actual password.
              </p>
              <Button $primary onClick={() => setShowCreateModal(true)} style={{ margin: '1.5rem auto 0' }}>
                <Plus size={16} /> Create Your First Share
              </Button>
            </EmptyState>
          ) : (
            <SharesTable>
              <TableHeader>
                <div>Recipient</div>
                <div>Domains</div>
                <div>Status</div>
                <div>Usage</div>
                <div>Expires</div>
                <div>Actions</div>
              </TableHeader>
              {sentShares.map((share, idx) => {
                const status = getShareStatus(share);
                return (
                  <TableRow key={share.id} style={{ animationDelay: `${idx * 50}ms` }}>
                    <RecipientInfo>
                      <Avatar>
                        {(share.recipient_username || '?')[0].toUpperCase()}
                      </Avatar>
                      <div>
                        <RecipientName>{share.recipient_username}</RecipientName>
                        <RecipientDomains>
                          <Key size={12} />
                          Autofill only
                        </RecipientDomains>
                      </div>
                    </RecipientInfo>
                    <RecipientDomains>
                      <Globe size={13} />
                      {share.bound_domains?.length > 0
                        ? share.bound_domains.join(', ')
                        : 'Any domain'}
                    </RecipientDomains>
                    <div>
                      <StatusBadge $status={status}>
                        {status === 'active' && <><CheckCircle size={12} /> Active</>}
                        {status === 'expired' && <><Clock size={12} /> Expired</>}
                        {status === 'revoked' && <><XCircle size={12} /> Revoked</>}
                        {status === 'limit' && <><AlertTriangle size={12} /> Limit</>}
                      </StatusBadge>
                    </div>
                    <UsageDisplay>
                      <Hash size={14} />
                      {share.use_count}{share.remaining_uses != null ? `/${share.use_count + share.remaining_uses}` : '/∞'}
                    </UsageDisplay>
                    <ExpiryDisplay $soon={isExpiringSoon(share.expires_at)}>
                      <Clock size={13} />
                      {formatExpiry(share.expires_at)}
                    </ExpiryDisplay>
                    <div>
                      {share.is_active && (
                        <RevokeButton onClick={() => handleRevoke(share.id)}>
                          Revoke
                        </RevokeButton>
                      )}
                    </div>
                  </TableRow>
                );
              })}
            </SharesTable>
          )}
        </>
      )}

      {/* Shared with Me Tab */}
      {!loading && activeTab === 'received' && (
        <>
          {receivedShares.length === 0 ? (
            <EmptyState>
              <Download size={64} />
              <h3>No Shares Received</h3>
              <p>
                When someone shares a password with you via FHE, it will appear here.
                You'll be able to autofill the password without ever seeing it.
              </p>
            </EmptyState>
          ) : (
            <ReceivedGrid>
              {receivedShares.map(share => (
                <AutofillTokenCard key={share.id} share={share} onUsed={loadData} />
              ))}
            </ReceivedGrid>
          )}
        </>
      )}

      {/* Activity Tab */}
      {!loading && activeTab === 'activity' && (
        <EmptyState>
          <Activity size={64} />
          <h3>Activity Log</h3>
          <p>
            View detailed activity logs for each share by clicking on a specific share
            in the "Shared by Me" tab.
          </p>
        </EmptyState>
      )}

      {/* Create Share Modal */}
      {showCreateModal && (
        <CreateHomomorphicShareModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            loadData();
          }}
        />
      )}
    </Container>
  );
}

export default HomomorphicSharingDashboard;

/**
 * Main Breach Alerts Dashboard Component
 * Real-time monitoring and management of security breach alerts
 */

import React, { useState, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { FaShieldAlt, FaBell, FaCheckCircle, FaFilter } from 'react-icons/fa';
import useBreachWebSocket from '../../../hooks/useBreachWebSocket';
import { useAuth } from '../../../hooks/useAuth';
import BreachToast from './BreachToast';
import BreachAlertCard from './BreachAlertCard';
import BreachDetailModal from './BreachDetailModal';
import ConnectionStatusBadge from './ConnectionStatusBadge';
import ConnectionHealthMonitor from './ConnectionHealthMonitor';
import { api } from '../../../services/api';
import { errorTracker } from '../../../services/errorTracker';

const DashboardContainer = styled.div`
  min-height: 100vh;
  background: #f5f7fa;
  padding: 32px;
`;

const Header = styled.div`
  max-width: 1200px;
  margin: 0 auto 32px;
`;

const HeaderTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 12px;
`;

const HeaderTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

const Title = styled.h1`
  font-size: 32px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;

  svg {
    color: #667eea;
    font-size: 36px;
  }
`;

const Subtitle = styled.p`
  font-size: 16px;
  color: #666;
  margin: 8px 0 0 0;
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
`;

const StatusIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const StatusDot = styled.div`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: ${props => props.connected ? '#28a745' : '#dc3545'};
  animation: ${props => props.connected ? 'pulse 2s infinite' : 'none'};

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }
`;

const StatusText = styled.span`
  font-size: 14px;
  color: #666;
  font-weight: 500;
`;

const UnreadBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #dc3545;
  color: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;

  svg {
    font-size: 16px;
  }
`;

const FiltersContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto 24px;
`;

const FilterButtons = styled.div`
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
`;

const FilterButton = styled.button`
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s;

  ${props => props.active ? `
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  ` : `
    background: white;
    color: #666;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

    &:hover {
      background: #f0f0f0;
    }
  `}
`;

const ContentContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
`;

const LoadingContainer = styled.div`
  text-align: center;
  padding: 60px 20px;
`;

const Spinner = styled.div`
  width: 50px;
  height: 50px;
  border: 4px solid #f0f0f0;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const LoadingText = styled.p`
  font-size: 16px;
  color: #666;
`;

const EmptyState = styled.div`
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 60px 40px;
  text-align: center;
`;

const EmptyIcon = styled.div`
  width: 80px;
  height: 80px;
  background: #e8f5e9;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;

  svg {
    font-size: 40px;
    color: #28a745;
  }
`;

const EmptyTitle = styled.h3`
  font-size: 24px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 12px 0;
`;

const EmptyText = styled.p`
  font-size: 16px;
  color: #666;
  margin: 0;
  line-height: 1.6;
`;

const AlertsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

// Maps a vault.BreachAlert record (what /api/ml-darkweb/breach-alerts/ returns)
// onto the field names BreachAlertCard / BreachDetailModal read. The dashboard
// lists alerts, not MLBreachMatch rows: `is_read` lives on the alert, and the
// WebSocket events and mark-alert-read all key on BreachAlert.id.
// The card colours on UPPERCASE severity but alerts store it lowercase, and the
// match confidence / monitored domain live in `exposed_data` / `identifier`.
// Only ML-created alerts carry a confidence, and only they store a domain in
// `identifier`; the breach-scan alerts store a vault item id or an email there,
// so it is shown for them as `affected_*` under a label matching `data_type`
// rather than mislabelled as a domain (Greptile P2) or dropped (Greptile P1).
const AFFECTED_LABELS = { email: 'Affected Email', password: 'Vault Item ID' };

const toDisplayAlert = (record) => {
  const exposed =
    record.exposed_data && typeof record.exposed_data === 'object' ? record.exposed_data : {};
  const confidence = typeof exposed.confidence === 'number' ? exposed.confidence : null;
  const hasAffected = confidence === null && record.identifier != null && record.identifier !== '';
  return {
    id: record.id,
    breach_title: record.breach_name,
    breach_description: record.breach_description,
    severity: String(record.severity || 'medium').toUpperCase(),
    detected_at: record.detected_at,
    is_read: Boolean(record.is_read),
    resolved: Boolean(record.resolved),
    similarity_score: confidence,
    confidence_score: confidence,
    domain: confidence !== null ? record.identifier || null : null,
    affected_label: hasAffected ? AFFECTED_LABELS[record.data_type] || 'Affected Item' : null,
    affected_value: hasAffected ? String(record.identifier) : null,
  };
};

const BreachAlertsDashboard = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [toastAlert, setToastAlert] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);
  
  // Get user ID from the auth context rather than localStorage. The
  // legacy `localStorage.getItem('user')` path was removed when
  // CodeQL alert #1048 (`js/clear-text-storage-of-sensitive-data`)
  // landed — persisting the user blob to localStorage made it XSS-
  // exfiltratable. Components that need user data now pull it from
  // the auth provider, which holds it in React state only.
  // `userId` is null until the user logs in (or until something
  // hydrates `user` from the API in the legacy flow); the
  // `if (userId) fetchAlerts()` gate below already handles that.
  const { user } = useAuth();
  const userId = user?.id ?? null;

  // Handle new real-time alerts
  const handleNewAlert = useCallback((alertData) => {
    console.log('New breach alert received:', alertData);
    
    // Show toast notification
    setToastAlert(alertData);
    
    // Add to alerts list
    const newAlert = {
      id: alertData.alert_id || Date.now(),
      breach_title: alertData.title || 'New Breach Detected',
      breach_description: alertData.description,
      severity: alertData.severity,
      detected_at: alertData.detected_at,
      similarity_score: alertData.confidence,
      confidence_score: alertData.confidence,
      is_read: false,
      domain: alertData.domain
    };
    
    setAlerts(prev => [newAlert, ...prev]);
  }, []);

  // Handle alert updates (e.g., marked as read)
  const handleAlertUpdate = useCallback((updateData) => {
    console.log('Alert update received:', updateData);
    
    if (updateData.update_type === 'marked_read') {
      setAlerts(prev =>
        prev.map(alert =>
          alert.id === updateData.alert_id
            ? { ...alert, is_read: true }
            : alert
        )
      );
    }
  }, []);

  // WebSocket connection with enhanced reconnection and health monitoring
  const { 
    isConnected, 
    connectionQuality,
    reconnectAttempts,
    unreadCount, 
    connectionError,
    reconnect 
  } = useBreachWebSocket(
    userId,
    handleNewAlert,
    handleAlertUpdate
  );

  // Fetch existing alerts from API
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true);
        setAlerts([]); // drop any previous user's alerts before merging this load in
        // Vite proxies /api to Django. The unprefixed path was served as
        // frontend HTML. Returns { success, count, has_more, alerts: [...] }, not a
        // bare list, one page at a time: keep going so older unread alerts are
        // reachable (the endpoint pages at 50).
        const loaded = [];
        let offset = 0;
        for (;;) {
          const { data } = await api.get('/api/ml-darkweb/breach-alerts/', { params: { offset } });
          const page = data?.alerts ?? [];
          loaded.push(...page);
          if (!data?.has_more || page.length === 0) break;
          offset += page.length;
        }
        // An alert arriving mid-load shifts the offset, so dedupe by id. Merge
        // into the current state instead of replacing it: WebSocket alerts that
        // arrived while the pages loaded stay, and a read-state update is never
        // reverted by an older fetched copy.
        const fetched = new Map(loaded.map(a => [a.id, toDisplayAlert(a)]));
        setAlerts(prev => {
          const live = prev.map(a => {
            const f = fetched.get(a.id);
            return f ? { ...f, is_read: f.is_read || a.is_read } : a;
          });
          const liveIds = new Set(prev.map(a => a.id));
          return [...live, ...[...fetched.values()].filter(a => !liveIds.has(a.id))];
        });
      } catch (error) {
        console.error('Error fetching alerts:', error);
        errorTracker.captureError(error, 'BreachAlertsDashboard:FetchAlerts', {}, 'error');
      } finally {
        setLoading(false);
      }
    };

    if (userId) {
      fetchAlerts();
    }
  }, [userId]);

  // Mark alert as read
  const handleMarkAsRead = async (alertId) => {
    try {
      // Persists BreachAlert.is_read and broadcasts `marked_read`. resolve_match
      // acted on an MLBreachMatch (a different table), so is_read was never saved.
      await api.post(`/api/ml-darkweb/mark-alert-read/${alertId}/`);

      setAlerts(prev =>
        prev.map(alert =>
          alert.id === alertId ? { ...alert, is_read: true } : alert
        )
      );
    } catch (error) {
      console.error('Error marking alert as read:', error);
      errorTracker.captureError(error, 'BreachAlertsDashboard:MarkRead', { alertId }, 'error');
    }
  };

  // View alert details
  const handleViewDetails = (alert) => {
    setSelectedAlert(alert);
    if (!alert.is_read) {
      handleMarkAsRead(alert.id);
    }
  };

  // Filter alerts
  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'unread') return !alert.is_read && !alert.resolved;
    if (filter === 'critical') return alert.severity === 'CRITICAL' || alert.severity === 'HIGH';
    return true;
  });

  const totalUnreadCount = alerts.filter(a => !a.is_read && !a.resolved).length;

  return (
    <DashboardContainer>
      {/* Toast Notification */}
      {toastAlert && (
        <BreachToast
          alert={toastAlert}
          onClose={() => setToastAlert(null)}
          onViewDetails={(alert) => {
            setToastAlert(null);
            setFilter('all');
            // Find the actual alert in the list if possible
            const actualAlert = alerts.find(a => a.id === alert.alert_id);
            if (actualAlert) {
              handleViewDetails(actualAlert);
            }
          }}
        />
      )}

      {/* Header */}
      <Header>
        <HeaderTop>
          <HeaderTitle>
            <Title>
              <FaShieldAlt />
              Security Breach Alerts
            </Title>
          </HeaderTitle>

          <HeaderActions>
            {/* Enhanced Connection Status with Quality Indicator */}
            <ConnectionStatusBadge
              isConnected={isConnected}
              connectionQuality={connectionQuality}
              reconnectAttempts={reconnectAttempts}
              onReconnect={reconnect}
            />

            {totalUnreadCount > 0 && (
              <UnreadBadge>
                <FaBell />
                {totalUnreadCount} unread
              </UnreadBadge>
            )}
          </HeaderActions>
        </HeaderTop>

        <Subtitle>
          Monitor and respond to potential credential compromises detected by our ML-powered system
        </Subtitle>
      </Header>

      {/* Filters */}
      <FiltersContainer>
        <FilterButtons>
          <FilterButton
            active={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            All Alerts
          </FilterButton>
          <FilterButton
            active={filter === 'unread'}
            onClick={() => setFilter('unread')}
          >
            Unread
          </FilterButton>
          <FilterButton
            active={filter === 'critical'}
            onClick={() => setFilter('critical')}
          >
            Critical/High
          </FilterButton>
        </FilterButtons>
      </FiltersContainer>

      {/* Content */}
      <ContentContainer>
        {loading ? (
          <LoadingContainer>
            <Spinner />
            <LoadingText>Loading security alerts...</LoadingText>
          </LoadingContainer>
        ) : filteredAlerts.length === 0 ? (
          <EmptyState>
            <EmptyIcon>
              <FaCheckCircle />
            </EmptyIcon>
            <EmptyTitle>All Clear!</EmptyTitle>
            <EmptyText>
              No security breaches detected for your monitored credentials.
              {filter !== 'all' && ' Try changing your filter to see other alerts.'}
            </EmptyText>
          </EmptyState>
        ) : (
          <AlertsList>
            {filteredAlerts.map(alert => (
              <BreachAlertCard
                key={alert.id}
                alert={alert}
                onMarkRead={handleMarkAsRead}
                onViewDetails={handleViewDetails}
              />
            ))}
          </AlertsList>
        )}
      </ContentContainer>

      {/* Details Modal */}
      {selectedAlert && (
        <BreachDetailModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}

      {/* Connection Health Monitor Widget */}
      <ConnectionHealthMonitor
        isConnected={isConnected}
        connectionQuality={connectionQuality}
        reconnectAttempts={reconnectAttempts}
      />
    </DashboardContainer>
  );
};

export default BreachAlertsDashboard;


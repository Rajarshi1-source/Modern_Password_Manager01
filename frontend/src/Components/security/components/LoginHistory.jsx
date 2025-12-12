import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { FaHistory, FaExclamationTriangle, FaCheckCircle, FaTimesCircle, FaGlobe, FaDesktop, FaMobileAlt, FaFilter, FaSync } from 'react-icons/fa';

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const Container = styled.div`
  animation: ${fadeIn} 0.3s ease-out;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
`;

const Title = styled.h3`
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  
  svg {
    color: ${props => props.theme.primary || '#7B68EE'};
  }
`;

const FilterGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  padding: 4px;
  border-radius: 12px;
`;

const FilterButton = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
  
  ${props => props.$active ? `
    background: ${props.theme.primary || '#7B68EE'};
    color: white;
    box-shadow: 0 2px 8px rgba(123, 104, 238, 0.3);
  ` : `
    background: transparent;
    color: ${props.theme.textSecondary || '#666'};
    
    &:hover {
      background: ${props.theme.cardBg || '#fff'};
      color: ${props.theme.textPrimary || '#1a1a2e'};
    }
  `}
`;

const RefreshButton = styled.button`
  padding: 8px 12px;
  border: 1px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 8px;
  background: ${props => props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textSecondary || '#666'};
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: ${props => props.theme.primary || '#7B68EE'};
    color: ${props => props.theme.primary || '#7B68EE'};
  }
  
  svg {
    animation: ${props => props.$loading ? spin : 'none'} 1s linear infinite;
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const Spinner = styled.div`
  width: 40px;
  height: 40px;
  border: 3px solid ${props => props.theme.backgroundSecondary || '#f0f0f0'};
  border-top-color: ${props => props.theme.primary || '#7B68EE'};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-bottom: 16px;
`;

const EmptyState = styled.div`
  background: linear-gradient(135deg, ${props => props.theme.primaryLight || '#f0edff'} 0%, ${props => props.theme.cardBg || '#fff'} 100%);
  border-radius: 16px;
  padding: 48px 24px;
  text-align: center;
  border: 1px dashed ${props => props.theme.borderColor || '#e0e0e0'};
`;

const EmptyIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: ${props => props.theme.primary || '#7B68EE'}20;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 28px;
    color: ${props => props.theme.primary || '#7B68EE'};
  }
`;

const EmptyTitle = styled.h4`
  margin: 0 0 8px;
  font-size: 18px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const EmptyText = styled.p`
  margin: 0;
  color: ${props => props.theme.textSecondary || '#666'};
  font-size: 14px;
`;

const HistoryList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const HistoryCard = styled.div`
  background: ${props => props.$suspicious 
    ? `linear-gradient(135deg, #fff5f5 0%, ${props.theme.cardBg || '#fff'} 100%)`
    : props.theme.cardBg || '#fff'};
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid ${props => props.$suspicious 
    ? props.theme.danger || '#ef4444' 
    : props.theme.borderColor || '#e0e0e0'};
  transition: all 0.2s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index * 0.05}s;
  animation-fill-mode: backwards;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    transform: translateY(-2px);
  }
`;

const CardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
`;

const DateInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const DateText = styled.span`
  font-size: 15px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const TimeText = styled.span`
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  
  ${props => {
    if (props.$variant === 'suspicious') {
      return `
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        color: #dc2626;
      `;
    }
    if (props.$variant === 'failed') {
      return `
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        color: #d97706;
      `;
    }
    return `
      background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
      color: #059669;
    `;
  }}
`;

const CardDetails = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
`;

const DetailItem = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 8px;
  
  svg {
    color: ${props => props.theme.primary || '#7B68EE'};
    font-size: 14px;
    flex-shrink: 0;
  }
`;

const DetailLabel = styled.span`
  font-size: 11px;
  color: ${props => props.theme.textSecondary || '#666'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const DetailValue = styled.span`
  font-size: 13px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  font-weight: 500;
  word-break: break-all;
`;

const DetailContent = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

const FailureReason = styled.div`
  margin-top: 12px;
  padding: 10px 14px;
  background: #fef2f2;
  border-radius: 8px;
  border-left: 3px solid #ef4444;
  
  span {
    font-size: 13px;
    color: #dc2626;
  }
`;

const ThreatScore = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  background: ${props => props.$score > 50 ? '#fef2f2' : '#fffbeb'};
  border-radius: 8px;
  
  span {
    font-size: 12px;
    font-weight: 600;
    color: ${props => props.$score > 50 ? '#dc2626' : '#d97706'};
  }
`;

const ThreatBar = styled.div`
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
`;

const ThreatFill = styled.div`
  height: 100%;
  width: ${props => props.$score}%;
  background: ${props => props.$score > 50 
    ? 'linear-gradient(90deg, #f87171 0%, #dc2626 100%)'
    : 'linear-gradient(90deg, #fbbf24 0%, #d97706 100%)'};
  border-radius: 3px;
  transition: width 0.3s ease;
`;

const LoginHistory = () => {
  const [loginAttempts, setLoginAttempts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  
  const fetchLoginHistory = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/security/account-protection/login-attempts/';
      if (filter === 'suspicious') {
        url += '?suspicious_only=true';
      }
      
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      
      setLoginAttempts(response.data.attempts || []);
    } catch (error) {
      toast.error('Failed to fetch login history');
      console.error('Error fetching login history:', error);
    } finally {
      setLoading(false);
    }
  }, [filter]);
  
  useEffect(() => {
    fetchLoginHistory();
  }, [filter, fetchLoginHistory]);
  
  const getStatusInfo = (attempt) => {
    if (attempt.is_suspicious) {
      return { label: 'Suspicious', variant: 'suspicious', icon: FaExclamationTriangle };
    }
    if (attempt.status === 'failed') {
      return { label: 'Failed', variant: 'failed', icon: FaTimesCircle };
    }
    return { label: 'Success', variant: 'success', icon: FaCheckCircle };
  };

  const formatDate = (dateString) => {
    try {
      return format(new Date(dateString), 'MMM d, yyyy');
    } catch (error) {
      return dateString;
    }
  };

  const formatTime = (dateString) => {
    try {
      return format(new Date(dateString), 'h:mm a');
    } catch (error) {
      return '';
    }
  };

  const getDeviceIcon = (userAgent) => {
    if (!userAgent) return FaDesktop;
    const ua = userAgent.toLowerCase();
    if (ua.includes('mobile') || ua.includes('android') || ua.includes('iphone')) {
      return FaMobileAlt;
    }
    return FaDesktop;
  };
  
  return (
    <Container>
      <Header>
        <Title>
          <FaHistory /> Login History
        </Title>
        <FilterGroup>
          <FilterButton 
            $active={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            <FaFilter /> All
          </FilterButton>
          <FilterButton 
            $active={filter === 'suspicious'}
            onClick={() => setFilter('suspicious')}
          >
            <FaExclamationTriangle /> Suspicious
          </FilterButton>
        </FilterGroup>
        <RefreshButton onClick={fetchLoginHistory} $loading={loading}>
          <FaSync /> Refresh
        </RefreshButton>
      </Header>

      {loading ? (
        <LoadingContainer>
          <Spinner />
          <span>Loading login history...</span>
        </LoadingContainer>
      ) : loginAttempts.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaHistory />
          </EmptyIcon>
          <EmptyTitle>No Login Attempts Found</EmptyTitle>
          <EmptyText>
            {filter === 'suspicious' 
              ? 'Great news! No suspicious login attempts detected.'
              : 'Your login history will appear here.'}
          </EmptyText>
        </EmptyState>
      ) : (
        <HistoryList>
          {loginAttempts.map((attempt, index) => {
            const statusInfo = getStatusInfo(attempt);
            const StatusIcon = statusInfo.icon;
            const DeviceIcon = getDeviceIcon(attempt.user_agent);
            
            return (
              <HistoryCard 
                key={attempt.id || index} 
                $suspicious={attempt.is_suspicious}
                $index={index}
              >
                <CardHeader>
                  <DateInfo>
                    <DateText>{formatDate(attempt.timestamp)}</DateText>
                    <TimeText>{formatTime(attempt.timestamp)}</TimeText>
                  </DateInfo>
                  <StatusBadge $variant={statusInfo.variant}>
                    <StatusIcon /> {statusInfo.label}
                  </StatusBadge>
                </CardHeader>
                
                <CardDetails>
                  <DetailItem>
                    <FaGlobe />
                    <DetailContent>
                      <DetailLabel>IP Address</DetailLabel>
                      <DetailValue>{attempt.ip_address || 'Unknown'}</DetailValue>
                    </DetailContent>
                  </DetailItem>
                  
                  {attempt.location && (
                    <DetailItem>
                      <FaGlobe />
                      <DetailContent>
                        <DetailLabel>Location</DetailLabel>
                        <DetailValue>{attempt.location}</DetailValue>
                      </DetailContent>
                    </DetailItem>
                  )}
                  
                  <DetailItem>
                    <DeviceIcon />
                    <DetailContent>
                      <DetailLabel>Device</DetailLabel>
                      <DetailValue>
                        {attempt.user_agent 
                          ? attempt.user_agent.split(' ')[0].substring(0, 30)
                          : 'Unknown Device'}
                      </DetailValue>
                    </DetailContent>
                  </DetailItem>
                </CardDetails>
                
                {attempt.failure_reason && (
                  <FailureReason>
                    <span>⚠️ {attempt.failure_reason}</span>
                  </FailureReason>
                )}
                
                {attempt.threat_score > 0 && (
                  <ThreatScore $score={attempt.threat_score}>
                    <span>Threat Score: {attempt.threat_score}%</span>
                    <ThreatBar>
                      <ThreatFill $score={attempt.threat_score} />
                    </ThreatBar>
                  </ThreatScore>
                )}
              </HistoryCard>
            );
          })}
        </HistoryList>
      )}
    </Container>
  );
};

export default LoginHistory;

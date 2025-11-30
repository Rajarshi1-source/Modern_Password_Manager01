import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { FaTimes, FaEnvelope, FaShieldAlt, FaBan, FaExclamationTriangle } from 'react-icons/fa';
import toast from 'react-hot-toast';

const Modal = styled.div`
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
  animation: fadeIn 0.3s ease;

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`;

const ModalContent = styled.div`
  background: white;
  border-radius: 16px;
  padding: 2rem;
  max-width: 900px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;

  @keyframes slideUp {
    from {
      transform: translateY(50px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid #e0e0e0;

  .header-content {
    flex: 1;

    h2 {
      font-size: 1.75rem;
      color: #333;
      font-weight: 700;
      margin-bottom: 0.5rem;
    }

    .alias-email {
      font-size: 1rem;
      color: #667eea;
      font-weight: 600;
      font-family: 'Courier New', monospace;
    }
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #999;
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;

    &:hover {
      color: #333;
      transform: rotate(90deg);
    }
  }
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
`;

const StatCard = styled.div`
  background: ${props => props.color || '#f5f5f5'};
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;

  .icon {
    font-size: 2rem;
    color: ${props => props.iconColor || '#666'};
    margin-bottom: 0.5rem;
  }

  .value {
    font-size: 2rem;
    font-weight: 700;
    color: #333;
    margin-bottom: 0.25rem;
  }

  .label {
    font-size: 0.875rem;
    color: #666;
    text-transform: uppercase;
  }
`;

const ActivityList = styled.div`
  margin-top: 2rem;

  h3 {
    font-size: 1.25rem;
    color: #333;
    margin-bottom: 1rem;
    font-weight: 600;
  }
`;

const ActivityItem = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background: ${props => {
    if (props.type === 'blocked' || props.type === 'spam') return '#fff5f5';
    if (props.type === 'forwarded') return '#f0f9ff';
    if (props.type === 'received') return '#f0fff4';
    return '#f9f9f9';
  }};
  border-left: 4px solid ${props => {
    if (props.type === 'blocked' || props.type === 'spam') return '#f44336';
    if (props.type === 'forwarded') return '#2196f3';
    if (props.type === 'received') return '#4caf50';
    return '#999';
  }};
  border-radius: 8px;
  margin-bottom: 0.75rem;

  .icon {
    font-size: 1.5rem;
    color: ${props => {
      if (props.type === 'blocked' || props.type === 'spam') return '#f44336';
      if (props.type === 'forwarded') return '#2196f3';
      if (props.type === 'received') return '#4caf50';
      return '#999';
    }};
    flex-shrink: 0;
    margin-top: 0.25rem;
  }

  .content {
    flex: 1;
    min-width: 0;

    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 0.5rem;
      gap: 1rem;
    }

    .activity-type {
      font-weight: 600;
      color: #333;
      font-size: 0.95rem;
      text-transform: capitalize;
    }

    .timestamp {
      font-size: 0.875rem;
      color: #666;
      flex-shrink: 0;
    }

    .sender {
      font-size: 0.875rem;
      color: #666;
      margin-bottom: 0.25rem;
      word-break: break-all;

      strong {
        color: #333;
      }
    }

    .subject {
      font-size: 0.875rem;
      color: #333;
      font-style: italic;
      word-break: break-word;
    }

    .details {
      margin-top: 0.5rem;
      font-size: 0.875rem;
      color: #666;
    }
  }
`;

const LoadingSpinner = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 3rem;

  &:after {
    content: '';
    width: 40px;
    height: 40px;
    border: 4px solid #e0e0e0;
    border-top-color: #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 3rem 2rem;
  color: #666;

  .icon {
    font-size: 3rem;
    color: #ddd;
    margin-bottom: 1rem;
  }

  p {
    font-size: 1rem;
  }
`;

const getActivityIcon = (type) => {
  switch (type) {
    case 'received':
      return <FaEnvelope />;
    case 'forwarded':
      return <FaShieldAlt />;
    case 'blocked':
    case 'spam':
      return <FaBan />;
    case 'created':
    case 'enabled':
      return <FaShieldAlt />;
    case 'disabled':
    case 'deleted':
      return <FaBan />;
    default:
      return <FaExclamationTriangle />;
  }
};

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  });
};

const AliasActivityModal = ({ alias, onClose }) => {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivity();
  }, [alias.id]);

  const loadActivity = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/email-masking/aliases/${alias.id}/activity/`);
      setActivities(response.data);
    } catch (error) {
      console.error('Error loading activity:', error);
      toast.error('Failed to load alias activity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClick={onClose}>
      <ModalContent onClick={(e) => e.stopPropagation()}>
        <Header>
          <div className="header-content">
            <h2>Alias Activity</h2>
            <div className="alias-email">{alias.alias_email}</div>
          </div>
          <button className="close-btn" onClick={onClose}>
            <FaTimes />
          </button>
        </Header>

        <StatsGrid>
          <StatCard color="#e3f2fd" iconColor="#2196f3">
            <div className="icon">
              <FaEnvelope />
            </div>
            <div className="value">{alias.emails_received}</div>
            <div className="label">Received</div>
          </StatCard>
          <StatCard color="#e8f5e9" iconColor="#4caf50">
            <div className="icon">
              <FaShieldAlt />
            </div>
            <div className="value">{alias.emails_forwarded}</div>
            <div className="label">Forwarded</div>
          </StatCard>
          <StatCard color="#ffebee" iconColor="#f44336">
            <div className="icon">
              <FaBan />
            </div>
            <div className="value">{alias.emails_blocked}</div>
            <div className="label">Blocked</div>
          </StatCard>
        </StatsGrid>

        <ActivityList>
          <h3>Recent Activity</h3>
          {loading ? (
            <LoadingSpinner />
          ) : activities.length === 0 ? (
            <EmptyState>
              <div className="icon">
                <FaEnvelope />
              </div>
              <p>No activity recorded yet</p>
            </EmptyState>
          ) : (
            activities.map((activity, index) => (
              <ActivityItem key={index} type={activity.activity_type}>
                <div className="icon">
                  {getActivityIcon(activity.activity_type)}
                </div>
                <div className="content">
                  <div className="header-row">
                    <span className="activity-type">
                      {activity.activity_type.replace('_', ' ')}
                    </span>
                    <span className="timestamp">
                      {formatTimestamp(activity.timestamp)}
                    </span>
                  </div>
                  {activity.sender_email && (
                    <div className="sender">
                      <strong>From:</strong> {activity.sender_email}
                    </div>
                  )}
                  {activity.subject && (
                    <div className="subject">
                      "{activity.subject}"
                    </div>
                  )}
                  {activity.details && Object.keys(activity.details).length > 0 && (
                    <div className="details">
                      {JSON.stringify(activity.details, null, 2)}
                    </div>
                  )}
                </div>
              </ActivityItem>
            ))
          )}
        </ActivityList>
      </ModalContent>
    </Modal>
  );
};

export default AliasActivityModal;


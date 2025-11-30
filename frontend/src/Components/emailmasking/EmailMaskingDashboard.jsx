import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import toast from 'react-hot-toast';
import { FaPlus, FaEnvelope, FaShieldAlt, FaCog, FaFilter } from 'react-icons/fa';
import AliasCard from './AliasCard';
import CreateAliasModal from './CreateAliasModal';
import ProviderSetup from './ProviderSetup';
import AliasActivityModal from './AliasActivityModal';
import analyticsService from '../../services/analyticsService';

const Container = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
`;

const Header = styled.div`
  text-align: center;
  color: white;
  margin-bottom: 3rem;

  h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
  }

  p {
    font-size: 1.1rem;
    opacity: 0.9;
  }
`;

const StatsContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
`;

const StatCard = styled.div`
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 1rem;

  .icon {
    font-size: 2.5rem;
    color: ${props => props.color || '#667eea'};
  }

  .content {
    flex: 1;

    .label {
      font-size: 0.875rem;
      color: #666;
      margin-bottom: 0.25rem;
    }

    .value {
      font-size: 1.75rem;
      font-weight: 700;
      color: #333;
    }
  }
`;

const ControlsBar = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1rem;
`;

const FilterBar = styled.div`
  display: flex;
  gap: 1rem;
  align-items: center;
`;

const FilterButton = styled.button`
  padding: 0.75rem 1.5rem;
  background: ${props => props.active ? 'white' : 'rgba(255, 255, 255, 0.2)'};
  color: ${props => props.active ? '#667eea' : 'white'};
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;

  &:hover {
    background: white;
    color: #667eea;
  }
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 1rem;
`;

const Button = styled.button`
  padding: 0.75rem 1.5rem;
  background: ${props => props.variant === 'secondary' ? 'white' : '#4A6CF7'};
  color: ${props => props.variant === 'secondary' ? '#667eea' : 'white'};
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const AliasesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 4rem 2rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);

  .icon {
    font-size: 4rem;
    color: #ddd;
    margin-bottom: 1rem;
  }

  h3 {
    font-size: 1.5rem;
    color: #333;
    margin-bottom: 0.5rem;
  }

  p {
    color: #666;
    margin-bottom: 1.5rem;
  }
`;

const LoadingSpinner = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4rem;

  &:after {
    content: '';
    width: 50px;
    height: 50px;
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

const EmailMaskingDashboard = () => {
  const [aliases, setAliases] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, active, disabled
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showProviderSetup, setShowProviderSetup] = useState(false);
  const [showActivityModal, setShowActivityModal] = useState(false);
  const [selectedAlias, setSelectedAlias] = useState(null);

  useEffect(() => {
    loadData();
    analyticsService.trackPageView('/email-masking');
    analyticsService.trackFeatureUsage('email_masking_dashboard');
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [aliasesRes, providersRes] = await Promise.all([
        axios.get('/api/email-masking/aliases/'),
        axios.get('/api/email-masking/providers/')
      ]);
      
      setAliases(aliasesRes.data);
      setProviders(providersRes.data);
    } catch (error) {
      console.error('Error loading email masking data:', error);
      toast.error('Failed to load email masking data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAlias = async (aliasData) => {
    try {
      await axios.post('/api/email-masking/aliases/create/', aliasData);
      toast.success('Email alias created successfully!');
      analyticsService.trackEvent('alias_created', { provider: aliasData.provider });
      loadData();
      setShowCreateModal(false);
    } catch (error) {
      console.error('Error creating alias:', error);
      toast.error(error.response?.data?.error || 'Failed to create alias');
    }
  };

  const handleToggleAlias = async (aliasId) => {
    try {
      const response = await axios.post(`/api/email-masking/aliases/${aliasId}/toggle/`);
      toast.success(response.data.message);
      analyticsService.trackEvent('alias_toggled', { alias_id: aliasId });
      loadData();
    } catch (error) {
      console.error('Error toggling alias:', error);
      toast.error('Failed to toggle alias');
    }
  };

  const handleDeleteAlias = async (aliasId) => {
    if (!window.confirm('Are you sure you want to delete this alias? This action cannot be undone.')) {
      return;
    }

    try {
      await axios.delete(`/api/email-masking/aliases/${aliasId}/`);
      toast.success('Alias deleted successfully');
      analyticsService.trackEvent('alias_deleted', { alias_id: aliasId });
      loadData();
    } catch (error) {
      console.error('Error deleting alias:', error);
      toast.error('Failed to delete alias');
    }
  };

  const handleViewActivity = (alias) => {
    setSelectedAlias(alias);
    setShowActivityModal(true);
    analyticsService.trackEvent('alias_activity_viewed', { alias_id: alias.id });
  };

  const handleEditAlias = async (aliasId, updates) => {
    try {
      await axios.patch(`/api/email-masking/aliases/${aliasId}/`, updates);
      toast.success('Alias updated successfully');
      analyticsService.trackEvent('alias_updated', { alias_id: aliasId });
      loadData();
    } catch (error) {
      console.error('Error updating alias:', error);
      toast.error('Failed to update alias');
    }
  };

  const filteredAliases = aliases.filter(alias => {
    if (filter === 'all') return true;
    return alias.status === filter;
  });

  const stats = {
    total: aliases.length,
    active: aliases.filter(a => a.status === 'active').length,
    received: aliases.reduce((sum, a) => sum + a.emails_received, 0),
    blocked: aliases.reduce((sum, a) => sum + a.emails_blocked, 0),
  };

  const hasConfiguredProvider = providers.some(p => p.is_active);

  if (loading) {
    return (
      <Container>
        <LoadingSpinner />
      </Container>
    );
  }

  return (
    <Container>
      <Header>
        <h1>
          <FaShieldAlt />
          Email Masking
        </h1>
        <p>Protect your privacy with disposable email addresses</p>
      </Header>

      <StatsContainer>
        <StatCard color="#667eea">
          <FaEnvelope className="icon" />
          <div className="content">
            <div className="label">Total Aliases</div>
            <div className="value">{stats.total}</div>
          </div>
        </StatCard>
        <StatCard color="#4caf50">
          <FaShieldAlt className="icon" />
          <div className="content">
            <div className="label">Active Aliases</div>
            <div className="value">{stats.active}</div>
          </div>
        </StatCard>
        <StatCard color="#2196f3">
          <FaEnvelope className="icon" />
          <div className="content">
            <div className="label">Emails Received</div>
            <div className="value">{stats.received}</div>
          </div>
        </StatCard>
        <StatCard color="#ff5722">
          <FaShieldAlt className="icon" />
          <div className="content">
            <div className="label">Emails Blocked</div>
            <div className="value">{stats.blocked}</div>
          </div>
        </StatCard>
      </StatsContainer>

      <ControlsBar>
        <FilterBar>
          <FaFilter style={{ color: 'white' }} />
          <FilterButton
            active={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            All
          </FilterButton>
          <FilterButton
            active={filter === 'active'}
            onClick={() => setFilter('active')}
          >
            Active
          </FilterButton>
          <FilterButton
            active={filter === 'disabled'}
            onClick={() => setFilter('disabled')}
          >
            Disabled
          </FilterButton>
        </FilterBar>

        <ActionButtons>
          <Button
            variant="secondary"
            onClick={() => setShowProviderSetup(true)}
          >
            <FaCog />
            Configure Providers
          </Button>
          <Button
            onClick={() => setShowCreateModal(true)}
            disabled={!hasConfiguredProvider}
          >
            <FaPlus />
            Create New Alias
          </Button>
        </ActionButtons>
      </ControlsBar>

      {!hasConfiguredProvider ? (
        <EmptyState>
          <div className="icon">
            <FaCog />
          </div>
          <h3>No Provider Configured</h3>
          <p>You need to configure an email masking provider before creating aliases</p>
          <Button onClick={() => setShowProviderSetup(true)}>
            <FaCog />
            Configure Provider
          </Button>
        </EmptyState>
      ) : filteredAliases.length === 0 ? (
        <EmptyState>
          <div className="icon">
            <FaEnvelope />
          </div>
          <h3>No Aliases Found</h3>
          <p>Create your first email alias to protect your privacy</p>
          <Button onClick={() => setShowCreateModal(true)}>
            <FaPlus />
            Create New Alias
          </Button>
        </EmptyState>
      ) : (
        <AliasesGrid>
          {filteredAliases.map(alias => (
            <AliasCard
              key={alias.id}
              alias={alias}
              onToggle={handleToggleAlias}
              onDelete={handleDeleteAlias}
              onViewActivity={handleViewActivity}
              onEdit={handleEditAlias}
            />
          ))}
        </AliasesGrid>
      )}

      {showCreateModal && (
        <CreateAliasModal
          providers={providers.filter(p => p.is_active)}
          onClose={() => setShowCreateModal(false)}
          onSubmit={handleCreateAlias}
        />
      )}

      {showProviderSetup && (
        <ProviderSetup
          onClose={() => setShowProviderSetup(false)}
          onSuccess={() => {
            loadData();
            setShowProviderSetup(false);
          }}
        />
      )}

      {showActivityModal && selectedAlias && (
        <AliasActivityModal
          alias={selectedAlias}
          onClose={() => {
            setShowActivityModal(false);
            setSelectedAlias(null);
          }}
        />
      )}
    </Container>
  );
};

export default EmailMaskingDashboard;

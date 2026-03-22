/**
 * SmartContractVaultDashboard
 * 
 * Main dashboard for managing blockchain-based conditional password vaults.
 * Shows vault list, stats, filters, and actions (check-in, unlock, vote, etc.).
 */

import React, { useState, useEffect, useCallback } from 'react';
import smartContractService from '../../services/smartContractService';
import './SmartContractVaultDashboard.css';

const CONDITION_ICONS = {
  time_lock: '⏰',
  dead_mans_switch: '💀',
  multi_sig: '🔑',
  dao_vote: '🗳️',
  price_oracle: '📈',
  escrow: '🤝',
};

const CONDITION_LABELS = {
  time_lock: 'Time Lock',
  dead_mans_switch: "Dead Man's Switch",
  multi_sig: 'Multi-Sig',
  dao_vote: 'DAO Vote',
  price_oracle: 'Price Oracle',
  escrow: 'Escrow',
};

const SmartContractVaultDashboard = () => {
  const [vaults, setVaults] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [conditionResults, setConditionResults] = useState({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [vaultsRes, configRes] = await Promise.all([
        smartContractService.listVaults(),
        smartContractService.getConfig(),
      ]);
      setVaults(vaultsRes.data || []);
      setConfig(configRes.data || {});
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load vaults');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Evaluate conditions for each vault
  useEffect(() => {
    if (vaults.length === 0) return;
    vaults.forEach(async (vault) => {
      if (vault.status !== 'active') return;
      try {
        const res = await smartContractService.getConditions(vault.id);
        setConditionResults(prev => ({ ...prev, [vault.id]: res.data }));
      } catch {
        // Silent fail for condition checks
      }
    });
  }, [vaults]);

  const handleCheckIn = async (vaultId) => {
    try {
      await smartContractService.checkIn(vaultId);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.error || 'Check-in failed');
    }
  };

  const handleUnlock = async (vaultId) => {
    try {
      const res = await smartContractService.unlockVault(vaultId);
      if (res.data.unlocked) {
        alert('🔓 Vault unlocked! Password has been released.');
      } else {
        alert(`Conditions not met: ${res.data.reason}`);
      }
      fetchData();
    } catch (err) {
      alert(err.response?.data?.error || 'Unlock failed');
    }
  };

  const handleCancel = async (vaultId) => {
    if (!window.confirm('Cancel this vault? This action cannot be undone.')) return;
    try {
      await smartContractService.deleteVault(vaultId);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.error || 'Cancel failed');
    }
  };

  const filteredVaults = filter === 'all'
    ? vaults
    : vaults.filter(v => v.condition_type === filter);

  const stats = {
    total: vaults.length,
    active: vaults.filter(v => v.status === 'active').length,
    unlocked: vaults.filter(v => v.status === 'unlocked').length,
    cancelled: vaults.filter(v => v.status === 'cancelled').length,
  };

  const formatTimeRemaining = (isoDate) => {
    if (!isoDate) return 'N/A';
    const diff = new Date(isoDate) - new Date();
    if (diff <= 0) return 'Expired';
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    if (days > 0) return `${days}d ${hours}h`;
    const mins = Math.floor((diff % 3600000) / 60000);
    return `${hours}h ${mins}m`;
  };

  const renderConditionInfo = (vault) => {
    const result = conditionResults[vault.id];
    
    switch (vault.condition_type) {
      case 'time_lock':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">Unlocks In</div>
            <div className="sc-vault-card__condition-value">
              {formatTimeRemaining(vault.unlock_at)}
            </div>
          </div>
        );
      case 'dead_mans_switch':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">Next Check-In</div>
            <div className="sc-vault-card__condition-value">
              Every {vault.check_in_interval_days} days
              {vault.last_check_in && (
                <> · Last: {new Date(vault.last_check_in).toLocaleDateString()}</>
              )}
            </div>
          </div>
        );
      case 'multi_sig':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">Approvals</div>
            <div className="sc-vault-card__condition-value">
              {result?.details?.current_approvals ?? '?'} / {result?.details?.required_approvals ?? '?'}
            </div>
          </div>
        );
      case 'dao_vote':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">Voting</div>
            <div className="sc-vault-card__condition-value">
              👍 {result?.details?.votes_for ?? 0} · 👎 {result?.details?.votes_against ?? 0}
              {result?.details?.voting_ended ? ' (Ended)' : ''}
            </div>
          </div>
        );
      case 'price_oracle':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">
              Price {vault.price_above ? 'Above' : 'Below'}
            </div>
            <div className="sc-vault-card__condition-value">
              ${Number(vault.price_threshold).toLocaleString()}
              {result?.details?.current_price && (
                <> · Now: ${Number(result.details.current_price).toLocaleString()}</>
              )}
            </div>
          </div>
        );
      case 'escrow':
        return (
          <div className="sc-vault-card__condition">
            <div className="sc-vault-card__condition-label">Escrow Status</div>
            <div className="sc-vault-card__condition-value">
              {result?.details?.status || 'Pending arbitrator release'}
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const renderActions = (vault) => {
    if (vault.status !== 'active') return null;

    return (
      <div className="sc-vault-card__actions">
        {vault.condition_type === 'dead_mans_switch' && (
          <button
            className="sc-vault-card__action-btn sc-vault-card__action-btn--primary"
            onClick={() => handleCheckIn(vault.id)}
          >
            ✓ Check In
          </button>
        )}
        <button
          className="sc-vault-card__action-btn"
          onClick={() => handleUnlock(vault.id)}
        >
          🔓 Unlock
        </button>
        <button
          className="sc-vault-card__action-btn sc-vault-card__action-btn--danger"
          onClick={() => handleCancel(vault.id)}
        >
          ✕
        </button>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="sc-dashboard">
        <div className="sc-loading">
          <div className="sc-loading__spinner" />
          Loading smart contract vaults...
        </div>
      </div>
    );
  }

  return (
    <div className="sc-dashboard" id="smart-contract-vault-dashboard">
      {/* Header */}
      <div className="sc-dashboard__header">
        <div>
          <div className="sc-dashboard__title-row">
            <span className="sc-dashboard__icon">⛓️</span>
            <h1 className="sc-dashboard__title">Smart Contract Vaults</h1>
          </div>
          <p className="sc-dashboard__subtitle">
            Blockchain-based conditional password access automation
          </p>
        </div>
        <button className="sc-dashboard__create-btn" id="create-vault-btn">
          <span>+</span> Create Vault
        </button>
      </div>

      {/* Error */}
      {error && <div className="sc-error">{error}</div>}

      {/* Stats */}
      <div className="sc-dashboard__stats">
        <div className="sc-stat-card">
          <div className="sc-stat-card__value">{stats.total}</div>
          <div className="sc-stat-card__label">Total Vaults</div>
        </div>
        <div className="sc-stat-card">
          <div className="sc-stat-card__value">{stats.active}</div>
          <div className="sc-stat-card__label">Active</div>
        </div>
        <div className="sc-stat-card">
          <div className="sc-stat-card__value">{stats.unlocked}</div>
          <div className="sc-stat-card__label">Unlocked</div>
        </div>
        <div className="sc-stat-card">
          <div className="sc-stat-card__value">{config?.network || '—'}</div>
          <div className="sc-stat-card__label">Network</div>
        </div>
      </div>

      {/* Filters */}
      <div className="sc-dashboard__filters">
        <button
          className={`sc-filter-chip ${filter === 'all' ? 'sc-filter-chip--active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All
        </button>
        {Object.entries(CONDITION_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`sc-filter-chip ${filter === key ? 'sc-filter-chip--active' : ''}`}
            onClick={() => setFilter(key)}
          >
            {CONDITION_ICONS[key]} {label}
          </button>
        ))}
      </div>

      {/* Vault Grid */}
      <div className="sc-vault-grid">
        {filteredVaults.length === 0 ? (
          <div className="sc-empty-state">
            <div className="sc-empty-state__icon">⛓️</div>
            <h3 className="sc-empty-state__title">No Smart Contract Vaults</h3>
            <p className="sc-empty-state__text">
              Create your first blockchain-powered conditional password vault
            </p>
            <button className="sc-dashboard__create-btn">+ Create Vault</button>
          </div>
        ) : (
          filteredVaults.map(vault => (
            <div
              key={vault.id}
              className={`sc-vault-card sc-vault-card--${vault.condition_type}`}
              id={`vault-card-${vault.id}`}
            >
              <div className="sc-vault-card__header">
                <h3 className="sc-vault-card__title">{vault.title}</h3>
                <span className={`sc-vault-card__status sc-vault-card__status--${vault.status}`}>
                  {vault.status_display}
                </span>
              </div>

              <div className="sc-vault-card__type">
                <span className="sc-vault-card__type-icon">
                  {CONDITION_ICONS[vault.condition_type]}
                </span>
                {CONDITION_LABELS[vault.condition_type]}
              </div>

              {renderConditionInfo(vault)}

              {vault.arbiscan_url && (
                <a
                  href={vault.arbiscan_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '0.75rem', color: '#818cf8' }}
                >
                  View on Arbiscan ↗
                </a>
              )}

              {renderActions(vault)}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default SmartContractVaultDashboard;

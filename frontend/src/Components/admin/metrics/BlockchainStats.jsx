/**
 * Blockchain Statistics Component (Phase 2B.2)
 * 
 * Displays blockchain anchoring statistics and costs
 */

import React from 'react';
import './BlockchainStats.css';

const BlockchainStats = ({ stats, costMetrics }) => {
  if (!stats) {
    return (
      <div className="blockchain-stats empty">
        <p>No blockchain statistics available.</p>
      </div>
    );
  }

  return (
    <div className="blockchain-stats">
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📦</div>
          <div className="stat-content">
            <div className="stat-label">Total Anchors</div>
            <div className="stat-value">{stats.total_anchors || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🆕</div>
          <div className="stat-content">
            <div className="stat-label">Recent Anchors</div>
            <div className="stat-value">{stats.recent_anchors || 0}</div>
            <div className="stat-sub">Last 30 days</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🧪</div>
          <div className="stat-content">
            <div className="stat-label">Testnet Anchors</div>
            <div className="stat-value">{stats.testnet_anchors || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🌐</div>
          <div className="stat-content">
            <div className="stat-label">Mainnet Anchors</div>
            <div className="stat-value">{stats.mainnet_anchors || 0}</div>
          </div>
        </div>
      </div>

      {costMetrics && (
        <div className="cost-breakdown">
          <h4>Cost Analysis</h4>
          <div className="cost-grid">
            <div className="cost-item">
              <span className="cost-label">Total Cost (ETH):</span>
              <span className="cost-value">{costMetrics.total_cost_eth?.toFixed(6) || '0'} ETH</span>
            </div>
            <div className="cost-item">
              <span className="cost-label">Total Cost (USD):</span>
              <span className="cost-value">${costMetrics.total_cost_usd?.toFixed(2) || '0'}</span>
            </div>
            <div className="cost-item">
              <span className="cost-label">Cost per Commitment:</span>
              <span className="cost-value">${costMetrics.cost_per_commitment?.toFixed(6) || '0'}</span>
            </div>
            <div className="cost-item">
              <span className="cost-label">Cost per Recovery:</span>
              <span className="cost-value">${costMetrics.cost_per_recovery?.toFixed(4) || '0'}</span>
            </div>
            <div className="cost-item">
              <span className="cost-label">Blockchain Transactions:</span>
              <span className="cost-value">{costMetrics.blockchain_transactions || 0}</span>
            </div>
          </div>

          <div className="cost-comparison">
            <p className="cost-note">
              <strong>Cost Efficiency:</strong> Current blockchain anchoring costs ~$0.02 per 1,000 commitments
              (97-98% savings vs. full validator network at $67K/month)
            </p>
          </div>
        </div>
      )}

      <div className="blockchain-info">
        <p>
          <strong>Network:</strong> Arbitrum L2 (Sepolia Testnet / One Mainnet)
        </p>
        <p>
          <strong>Batching:</strong> 1,000 commitments per Merkle root
        </p>
        <p>
          <strong>Verification:</strong> On-chain Merkle proof verification
        </p>
      </div>
    </div>
  );
};

export default BlockchainStats;


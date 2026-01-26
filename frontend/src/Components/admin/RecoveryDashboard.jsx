import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ApiService from '../../services/api';
import './RecoveryDashboard.css';

export const RecoveryDashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentAttempts, setRecentAttempts] = useState([]);
  const [securityAlerts, setSecurityAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      setError(null);
      const [statsData, attemptsData, alertsData] = await Promise.all([
        ApiService.quantumRecovery.adminDashboardStats(),
        ApiService.quantumRecovery.adminRecentAttempts({ limit: 20 }),
        ApiService.quantumRecovery.adminSecurityAlerts({ days: 7 })
      ]);

      setStats(statsData);
      setRecentAttempts(attemptsData.attempts);
      setSecurityAlerts(alertsData.alerts);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'completed': 'text-green-600',
      'failed': 'text-red-600',
      'cancelled': 'text-orange-600',
      'initiated': 'text-blue-600',
      'challenge_phase': 'text-yellow-600',
      'shard_collection': 'text-purple-600',
      'guardian_approval': 'text-indigo-600'
    };
    return colors[status] || 'text-gray-600';
  };

  const getSeverityColor = (severity) => {
    const colors = {
      'high': 'bg-red-100 text-red-800 border-red-300',
      'medium': 'bg-orange-100 text-orange-800 border-orange-300',
      'low': 'bg-yellow-100 text-yellow-800 border-yellow-300'
    };
    return colors[severity] || 'bg-gray-100 text-gray-800 border-gray-300';
  };

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading admin dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error-message">
          <h3>Error Loading Dashboard</h3>
          <p>{error}</p>
          <button onClick={fetchDashboardData} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>🛡️ Social Mesh Recovery Admin Dashboard</h1>
        <button onClick={fetchDashboardData} className="refresh-button">
          🔄 Refresh
        </button>
      </div>

      {/* Overview Statistics */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📊</div>
          <div className="stat-content">
            <h3>Total Attempts</h3>
            <p className="stat-value">{stats?.overview?.total_attempts || 0}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <h3>Success Rate</h3>
            <p className="stat-value">{stats?.overview?.success_rate || 0}%</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🎯</div>
          <div className="stat-content">
            <h3>Avg Trust Score</h3>
            <p className="stat-value">{(stats?.overview?.avg_trust_score * 100).toFixed(1) || 0}%</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⏳</div>
          <div className="stat-content">
            <h3>Active Attempts</h3>
            <p className="stat-value">{stats?.overview?.active_attempts || 0}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <h3>Active Guardians</h3>
            <p className="stat-value">{stats?.overview?.total_guardians || 0}</p>
          </div>
        </div>

        <div className="stat-card highlight-red">
          <div className="stat-icon">⚠️</div>
          <div className="stat-content">
            <h3>Security Alerts</h3>
            <p className="stat-value">{stats?.security?.suspicious_attempts || 0}</p>
          </div>
        </div>
      </div>

      {/* Security Alerts Section */}
      {securityAlerts.length > 0 && (
        <div className="security-alerts-section">
          <h2>🚨 Recent Security Alerts</h2>
          <div className="alerts-list">
            {securityAlerts.slice(0, 5).map((alert, index) => (
              <div key={index} className={`alert-card ${getSeverityColor(alert.severity)}`}>
                <div className="alert-header">
                  <span className="alert-type">{alert.type.replace('_', ' ').toUpperCase()}</span>
                  <span className="alert-time">
                    {new Date(alert.timestamp).toLocaleString()}
                  </span>
                </div>
                <div className="alert-body">
                  <p><strong>User:</strong> {alert.user_email}</p>
                  <p><strong>IP:</strong> {alert.ip_address}</p>
                  <p><strong>Details:</strong> {alert.details}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs-container">
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`tab ${activeTab === 'attempts' ? 'active' : ''}`}
            onClick={() => setActiveTab('attempts')}
          >
            Recent Attempts
          </button>
          <button
            className={`tab ${activeTab === 'trends' ? 'active' : ''}`}
            onClick={() => setActiveTab('trends')}
          >
            Trends
          </button>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'overview' && (
            <div className="overview-tab">
              <div className="status-breakdown">
                <h3>Status Breakdown</h3>
                <div className="status-chart">
                  {stats?.status_breakdown?.map((item) => (
                    <div key={item.status} className="status-item">
                      <span className={`status-label ${getStatusColor(item.status)}`}>
                        {item.status.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="status-count">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="today-stats">
                <h3>Today's Activity</h3>
                <div className="today-grid">
                  <div className="today-item">
                    <span className="today-label">Attempts Initiated</span>
                    <span className="today-value">{stats?.today?.attempts_initiated || 0}</span>
                  </div>
                  <div className="today-item">
                    <span className="today-label">Challenges Sent</span>
                    <span className="today-value">{stats?.today?.challenges_sent || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'attempts' && (
            <div className="attempts-tab">
              <h3>Recent Recovery Attempts</h3>
              <div className="attempts-table-container">
                <table className="attempts-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Status</th>
                      <th>Trust Score</th>
                      <th>Challenges</th>
                      <th>Initiated</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentAttempts.map((attempt) => (
                      <tr key={attempt.id}>
                        <td>{attempt.user_email}</td>
                        <td>
                          <span className={`status-badge ${getStatusColor(attempt.status)}`}>
                            {attempt.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          <span className={`trust-score ${attempt.trust_score >= 0.7 ? 'high' :
                              attempt.trust_score >= 0.5 ? 'medium' : 'low'
                            }`}>
                            {(attempt.trust_score * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td>
                          {attempt.challenges_completed}/{attempt.challenges_sent}
                        </td>
                        <td>
                          {new Date(attempt.initiated_at).toLocaleDateString()}
                        </td>
                        <td>
                          {attempt.recovery_successful ? '✅' :
                            attempt.honeypot_triggered ? '🍯' :
                              attempt.suspicious_activity ? '⚠️' : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'trends' && (
            <div className="trends-tab">
              <h3>7-Day Trends</h3>
              <div className="trend-chart">
                {stats?.trends?.daily_attempts?.map((day) => (
                  <div key={day.date} className="trend-bar">
                    <div
                      className="bar"
                      style={{ height: `${(day.count / 10) * 100}%` }}
                      title={`${day.count} attempts`}
                    >
                      <span className="bar-value">{day.count}</span>
                    </div>
                    <span className="bar-label">{day.date.split('-')[2]}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RecoveryDashboard;


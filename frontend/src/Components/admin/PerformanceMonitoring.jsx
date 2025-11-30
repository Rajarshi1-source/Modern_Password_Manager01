/**
 * Performance Monitoring Dashboard
 * ==================================
 * 
 * Admin dashboard for monitoring application performance, errors, and system health.
 * 
 * Features:
 * - Real-time performance metrics
 * - Error tracking and analysis
 * - System health monitoring
 * - Dependency status
 * - Performance alerts
 * - ML predictions
 */

import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { 
  FaServer, 
  FaDatabase, 
  FaExclamationTriangle, 
  FaChartLine, 
  FaClock,
  FaMemory,
  FaMicrochip,
  FaHdd,
  FaBug,
  FaCheckCircle,
  FaTimesCircle,
  FaExclamationCircle
} from 'react-icons/fa';

const Container = styled.div`
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  background: ${props => props.theme?.backgroundPrimary || '#f8f9fa'};
  min-height: 100vh;
`;

const Header = styled.div`
  margin-bottom: 32px;
`;

const Title = styled.h1`
  font-size: 32px;
  font-weight: 700;
  color: ${props => props.theme?.textPrimary || '#333'};
  margin-bottom: 8px;
`;

const Subtitle = styled.p`
  font-size: 16px;
  color: ${props => props.theme?.textSecondary || '#666'};
`;

const MetricsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
`;

const MetricCard = styled.div`
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  }
`;

const MetricHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
`;

const MetricTitle = styled.h3`
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.theme?.textSecondary || '#666'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const MetricIcon = styled.div`
  color: ${props => props.color || '#7B68EE'};
  font-size: 24px;
`;

const MetricValue = styled.div`
  font-size: 36px;
  font-weight: 700;
  color: ${props => props.color || props.theme?.textPrimary || '#333'};
  margin-bottom: 8px;
`;

const MetricSubtext = styled.div`
  font-size: 14px;
  color: ${props => props.theme?.textSecondary || '#666'};
`;

const Section = styled.div`
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
`;

const SectionTitle = styled.h2`
  font-size: 20px;
  font-weight: 600;
  color: ${props => props.theme?.textPrimary || '#333'};
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const TableHead = styled.thead`
  background: ${props => props.theme?.backgroundSecondary || '#f8f9fa'};
`;

const TableRow = styled.tr`
  border-bottom: 1px solid #e9ecef;

  &:last-child {
    border-bottom: none;
  }
`;

const TableHeader = styled.th`
  padding: 12px 16px;
  text-align: left;
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.theme?.textSecondary || '#666'};
`;

const TableData = styled.td`
  padding: 12px 16px;
  font-size: 14px;
  color: ${props => props.theme?.textPrimary || '#333'};
`;

const StatusBadge = styled.span`
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: ${props => {
    if (props.status === 'critical') return '#fee';
    if (props.status === 'warning') return '#fff3cd';
    if (props.status === 'success') return '#d4edda';
    return '#e9ecef';
  }};
  color: ${props => {
    if (props.status === 'critical') return '#dc3545';
    if (props.status === 'warning') return '#856404';
    if (props.status === 'success') return '#155724';
    return '#666';
  }};
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 8px;
`;

const ProgressFill = styled.div`
  height: 100%;
  width: ${props => props.percent}%;
  background: ${props => {
    if (props.percent >= 90) return '#dc3545';
    if (props.percent >= 70) return '#ffc107';
    return '#28a745';
  }};
  transition: width 0.3s ease;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: ${props => props.theme?.textSecondary || '#666'};
`;

const ErrorState = styled.div`
  padding: 48px;
  text-align: center;
  color: #dc3545;
`;

const RefreshButton = styled.button`
  padding: 8px 16px;
  background: #7B68EE;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #5A4AD1;
  }

  &:disabled {
    background: #ccc;
    cursor: not-allowed;
  }
`;

const PerformanceMonitoring = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    systemHealth: null,
    performanceSummary: null,
    errors: [],
    alerts: [],
    dependencies: []
  });
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    fetchData();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all performance data
      const [systemHealth, performanceSummary, errors, alerts, dependencies] = await Promise.all([
        axios.get('/api/performance/system-health/'),
        axios.get('/api/performance/summary/'),
        axios.get('/api/performance/errors/'),
        axios.get('/api/performance/alerts/'),
        axios.get('/api/performance/dependencies/')
      ]);

      setData({
        systemHealth: systemHealth.data.data,
        performanceSummary: performanceSummary.data.data,
        errors: errors.data.data?.errors || [],
        alerts: alerts.data.data?.alerts || [],
        dependencies: dependencies.data.data?.dependencies || []
      });

      setLastUpdate(new Date());
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch performance data:', err);
      setError('Failed to load performance data');
      setLoading(false);
    }
  };

  if (loading && !data.systemHealth) {
    return (
      <Container>
        <LoadingState>Loading performance data...</LoadingState>
      </Container>
    );
  }

  if (error && !data.systemHealth) {
    return (
      <Container>
        <ErrorState>{error}</ErrorState>
      </Container>
    );
  }

  const { systemHealth, performanceSummary, errors, alerts, dependencies } = data;

  return (
    <Container>
      <Header>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title>Performance Monitoring</Title>
            <Subtitle>
              Real-time application performance and system health monitoring
              {lastUpdate && ` • Last updated: ${lastUpdate.toLocaleTimeString()}`}
            </Subtitle>
          </div>
          <RefreshButton onClick={fetchData} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </RefreshButton>
        </div>
      </Header>

      {/* System Health Metrics */}
      <MetricsGrid>
        <MetricCard>
          <MetricHeader>
            <MetricTitle>CPU Usage</MetricTitle>
            <MetricIcon color="#7B68EE">
              <FaMicrochip />
            </MetricIcon>
          </MetricHeader>
          <MetricValue color={systemHealth?.cpu_percent > 80 ? '#dc3545' : '#28a745'}>
            {systemHealth?.cpu_percent?.toFixed(1) || 0}%
          </MetricValue>
          <ProgressBar>
            <ProgressFill percent={systemHealth?.cpu_percent || 0} />
          </ProgressBar>
        </MetricCard>

        <MetricCard>
          <MetricHeader>
            <MetricTitle>Memory Usage</MetricTitle>
            <MetricIcon color="#FF6B6B">
              <FaMemory />
            </MetricIcon>
          </MetricHeader>
          <MetricValue color={systemHealth?.memory_percent > 80 ? '#dc3545' : '#28a745'}>
            {systemHealth?.memory_percent?.toFixed(1) || 0}%
          </MetricValue>
          <MetricSubtext>
            {systemHealth?.memory_available_mb?.toFixed(0) || 0} MB available
          </MetricSubtext>
          <ProgressBar>
            <ProgressFill percent={systemHealth?.memory_percent || 0} />
          </ProgressBar>
        </MetricCard>

        <MetricCard>
          <MetricHeader>
            <MetricTitle>Disk Usage</MetricTitle>
            <MetricIcon color="#FFD166">
              <FaHdd />
            </MetricIcon>
          </MetricHeader>
          <MetricValue color={systemHealth?.disk_percent > 80 ? '#dc3545' : '#28a745'}>
            {systemHealth?.disk_percent?.toFixed(1) || 0}%
          </MetricValue>
          <MetricSubtext>
            {systemHealth?.disk_free_gb?.toFixed(1) || 0} GB free
          </MetricSubtext>
          <ProgressBar>
            <ProgressFill percent={systemHealth?.disk_percent || 0} />
          </ProgressBar>
        </MetricCard>

        <MetricCard>
          <MetricHeader>
            <MetricTitle>Avg Response Time</MetricTitle>
            <MetricIcon color="#00C897">
              <FaClock />
            </MetricIcon>
          </MetricHeader>
          <MetricValue>
            {performanceSummary?.avg_response_time?.toFixed(0) || 0}ms
          </MetricValue>
          <MetricSubtext>
            {performanceSummary?.total_requests || 0} requests
          </MetricSubtext>
        </MetricCard>
      </MetricsGrid>

      {/* Performance Alerts */}
      {alerts.length > 0 && (
        <Section>
          <SectionTitle>
            <FaExclamationTriangle /> Performance Alerts
          </SectionTitle>
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Severity</TableHeader>
                <TableHeader>Alert Type</TableHeader>
                <TableHeader>Message</TableHeader>
                <TableHeader>Time</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <tbody>
              {alerts.map((alert, index) => (
                <TableRow key={index}>
                  <TableData>
                    <StatusBadge status={alert.severity}>
                      {alert.severity}
                    </StatusBadge>
                  </TableData>
                  <TableData>{alert.alert_type}</TableData>
                  <TableData>{alert.message}</TableData>
                  <TableData>{new Date(alert.created_at).toLocaleString()}</TableData>
                  <TableData>
                    <StatusBadge status={alert.resolved ? 'success' : 'warning'}>
                      {alert.resolved ? 'Resolved' : 'Active'}
                    </StatusBadge>
                  </TableData>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </Section>
      )}

      {/* Recent Errors */}
      <Section>
        <SectionTitle>
          <FaBug /> Recent Errors
        </SectionTitle>
        {errors.length > 0 ? (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Type</TableHeader>
                <TableHeader>Message</TableHeader>
                <TableHeader>Path</TableHeader>
                <TableHeader>Count</TableHeader>
                <TableHeader>Last Occurrence</TableHeader>
              </TableRow>
            </TableHead>
            <tbody>
              {errors.slice(0, 10).map((error, index) => (
                <TableRow key={index}>
                  <TableData>{error.error_type}</TableData>
                  <TableData>{error.error_message}</TableData>
                  <TableData>{error.request_path}</TableData>
                  <TableData>{error.count || 1}</TableData>
                  <TableData>{new Date(error.timestamp).toLocaleString()}</TableData>
                </TableRow>
              ))}
            </tbody>
          </Table>
        ) : (
          <div style={{ textAlign: 'center', padding: '24px', color: '#28a745' }}>
            <FaCheckCircle size={48} />
            <p style={{ marginTop: '12px' }}>No errors in the last hour</p>
          </div>
        )}
      </Section>

      {/* Dependency Status */}
      <Section>
        <SectionTitle>
          <FaServer /> Dependency Status
        </SectionTitle>
        {dependencies.length > 0 ? (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Package</TableHeader>
                <TableHeader>Current Version</TableHeader>
                <TableHeader>Latest Version</TableHeader>
                <TableHeader>Vulnerabilities</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <tbody>
              {dependencies.map((dep, index) => (
                <TableRow key={index}>
                  <TableData>{dep.package_name}</TableData>
                  <TableData>{dep.current_version}</TableData>
                  <TableData>{dep.latest_version}</TableData>
                  <TableData>
                    {dep.vulnerability_count > 0 ? (
                      <StatusBadge status="critical">
                        {dep.vulnerability_count} vulnerabilities
                      </StatusBadge>
                    ) : (
                      <span>None</span>
                    )}
                  </TableData>
                  <TableData>
                    <StatusBadge 
                      status={
                        dep.vulnerability_count > 0 ? 'critical' :
                        dep.is_outdated ? 'warning' :
                        'success'
                      }
                    >
                      {dep.vulnerability_count > 0 ? 'Vulnerable' :
                       dep.is_outdated ? 'Outdated' :
                       'Up to date'}
                    </StatusBadge>
                  </TableData>
                </TableRow>
              ))}
            </tbody>
          </Table>
        ) : (
          <div style={{ textAlign: 'center', padding: '24px' }}>
            <p>No dependency data available</p>
          </div>
        )}
      </Section>
    </Container>
  );
};

export default PerformanceMonitoring;


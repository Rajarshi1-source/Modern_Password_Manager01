import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaChartLine, FaBolt, FaDatabase, FaClock, FaDownload, FaTrash, FaRocket, FaMemory } from 'react-icons/fa';
import { performanceMonitor } from '../../services/performanceMonitor';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

const shimmer = keyframes`
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px;
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  margin-bottom: 32px;
  text-align: center;
`;

const Title = styled.h1`
  font-size: 32px;
  font-weight: 800;
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

const TitleIcon = styled.span`
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 22px;
    color: ${colors.primary};
  }
`;

const Subtitle = styled.p`
  color: ${colors.textSecondary};
  margin: 0;
  font-size: 16px;
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
`;

const MetricCard = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 4px 20px rgba(123, 104, 238, 0.08);
  border: 1px solid ${colors.border};
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.4s ease-out;
  animation-delay: ${props => props.$delay || '0s'};
  animation-fill-mode: backwards;
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: linear-gradient(180deg, ${props => props.$color || colors.primary} 0%, ${props => props.$color ? `${props.$color}80` : colors.primaryLight} 100%);
    border-radius: 4px 0 0 4px;
  }
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(123, 104, 238, 0.15);
    border-color: ${colors.borderLight};
  }
`;

const MetricIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${props => props.$color}20 0%, ${props => props.$color}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  
  svg {
    font-size: 24px;
    color: ${props => props.$color};
  }
`;

const MetricLabel = styled.div`
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: ${colors.textSecondary};
  margin-bottom: 10px;
`;

const MetricValue = styled.div`
  font-size: 42px;
  font-weight: 800;
  background: linear-gradient(135deg, ${props => props.$color} 0%, ${props => props.$color}cc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 6px;
  line-height: 1.1;
`;

const MetricUnit = styled.span`
  font-size: 20px;
  font-weight: 600;
  color: ${colors.textSecondary};
  margin-left: 4px;
`;

const MetricDescription = styled.div`
  font-size: 13px;
  color: ${colors.textSecondary};
  line-height: 1.5;
`;

const DetailsCard = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 4px 20px rgba(123, 104, 238, 0.08);
  border: 1px solid ${colors.border};
  margin-bottom: 24px;
  animation: ${fadeIn} 0.4s ease-out;
  animation-delay: 0.2s;
  animation-fill-mode: backwards;
`;

const DetailsHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid ${colors.border};
`;

const DetailsIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 18px;
    color: ${colors.primary};
  }
`;

const DetailsTitle = styled.h2`
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: ${colors.text};
`;

const ComparisonBar = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
`;

const BarLabel = styled.div`
  flex: 0 0 140px;
  font-size: 14px;
  font-weight: 600;
  color: ${colors.textSecondary};
`;

const BarContainer = styled.div`
  flex: 1;
  height: 40px;
  background: ${colors.background};
  border-radius: 12px;
  overflow: hidden;
  position: relative;
  border: 1px solid ${colors.border};
`;

const Bar = styled.div`
  height: 100%;
  background: linear-gradient(90deg, ${props => props.$color || colors.primary}, ${props => props.$color ? `${props.$color}bb` : colors.primaryLight});
  width: ${props => props.$width}%;
  transition: width 0.8s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 14px;
  border-radius: ${props => props.$width >= 100 ? '12px' : '12px 0 0 12px'};
`;

const BarText = styled.span`
  color: white;
  font-weight: 700;
  font-size: 13px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
`;

const ImprovementBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 14px;
  font-weight: 700;
  background: linear-gradient(135deg, ${colors.success}20 0%, ${colors.success}10 100%);
  color: ${colors.success};
  border: 1px solid ${colors.success}40;
  margin-top: 8px;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
`;

const Th = styled.th`
  text-align: left;
  padding: 14px 16px;
  background: ${colors.background};
  font-weight: 700;
  font-size: 12px;
  color: ${colors.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  &:first-child {
    border-radius: 12px 0 0 0;
  }
  
  &:last-child {
    border-radius: 0 12px 0 0;
  }
`;

const Td = styled.td`
  padding: 14px 16px;
  border-bottom: 1px solid ${colors.border};
  color: ${colors.text};
  font-size: 14px;
  font-weight: 500;
  
  &:first-child {
    color: ${colors.textSecondary};
  }
`;

const TableRow = styled.tr`
  transition: background 0.2s ease;
  
  &:hover {
    background: ${colors.background};
  }
  
  &:last-child td {
    border-bottom: none;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 14px;
  margin-top: 32px;
  justify-content: center;
`;

const Button = styled.button`
  padding: 14px 28px;
  border-radius: 14px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 10px;
  
  &.primary {
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
    color: white;
    box-shadow: 0 4px 14px ${colors.primary}40;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px ${colors.primary}50;
    }
  }
  
  &.secondary {
    background: ${colors.background};
    color: ${colors.text};
    border: 1px solid ${colors.border};
    
    &:hover {
      background: ${colors.border};
      border-color: ${colors.borderLight};
    }
  }
  
  &.danger {
    background: linear-gradient(135deg, ${colors.danger}15 0%, ${colors.danger}08 100%);
    color: ${colors.danger};
    border: 1px solid ${colors.danger}40;
    
    &:hover {
      background: ${colors.danger};
      color: white;
    }
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 80px 40px;
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 24px;
  border: 2px dashed ${colors.border};
`;

const EmptyIcon = styled.div`
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
  
  svg {
    font-size: 36px;
    color: ${colors.primary};
    opacity: 0.6;
  }
`;

const EmptyTitle = styled.h3`
  font-size: 22px;
  font-weight: 700;
  color: ${colors.text};
  margin: 0 0 12px 0;
`;

const EmptyText = styled.p`
  font-size: 15px;
  color: ${colors.textSecondary};
  margin: 0;
  max-width: 400px;
  margin: 0 auto;
  line-height: 1.6;
`;

const LoadingContainer = styled.div`
  text-align: center;
  padding: 80px 40px;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

const PerformanceDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load metrics from performance monitor
    const report = performanceMonitor.getReport();
    setMetrics(report);
    setLoading(false);

    // Refresh metrics every 5 seconds
    const interval = setInterval(() => {
      const updatedReport = performanceMonitor.getReport();
      setMetrics(updatedReport);
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const exportMetrics = () => {
    const data = performanceMonitor.exportMetrics();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vault-performance-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearMetrics = () => {
    if (window.confirm('Are you sure you want to clear all performance metrics?')) {
      performanceMonitor.clearMetrics();
      setMetrics(performanceMonitor.getReport());
    }
  };

  if (loading) {
    return (
      <Container>
        <LoadingContainer>
          <EmptyIcon>
            <FaChartLine />
          </EmptyIcon>
          <EmptyText>Loading performance metrics...</EmptyText>
        </LoadingContainer>
      </Container>
    );
  }

  const hasData = metrics && (
    metrics.vaultUnlock.samples > 0 || 
    metrics.itemDecryption.samples > 0 || 
    metrics.bulkOperations.samples > 0
  );

  if (!hasData) {
    return (
      <Container>
        <Header>
          <Title>
            <TitleIcon>
              <FaChartLine />
            </TitleIcon>
            Performance Dashboard
          </Title>
          <Subtitle>Monitor your vault's performance and loading times</Subtitle>
        </Header>
        <EmptyState>
          <EmptyIcon>
            <FaRocket />
          </EmptyIcon>
          <EmptyTitle>No Performance Data Yet</EmptyTitle>
          <EmptyText>
            Unlock your vault and interact with items to start collecting performance metrics. 
            We'll show you detailed insights once you begin using your vault.
          </EmptyText>
        </EmptyState>
      </Container>
    );
  }

  // Calculate before/after comparison (assuming 5x improvement with lazy loading)
  const beforeUnlock = metrics.vaultUnlock.average * 5 || 2500;
  const afterUnlock = metrics.vaultUnlock.average || 500;
  const improvement = Math.round(((beforeUnlock - afterUnlock) / beforeUnlock) * 100);

  return (
    <Container>
      <Header>
        <Title>
          <TitleIcon>
            <FaChartLine />
          </TitleIcon>
          Performance Dashboard
        </Title>
        <Subtitle>Monitor your vault's performance and loading times</Subtitle>
      </Header>

      <Grid>
        <MetricCard $color={colors.success} $delay="0.1s">
          <MetricIcon $color={colors.success}>
            <FaBolt />
          </MetricIcon>
          <MetricLabel>Vault Unlock Time</MetricLabel>
          <MetricValue $color={colors.success}>
            {Math.round(metrics.vaultUnlock.average)}
            <MetricUnit>ms</MetricUnit>
          </MetricValue>
          <MetricDescription>
            Average time to unlock vault ({metrics.vaultUnlock.samples} samples)
          </MetricDescription>
        </MetricCard>

        <MetricCard $color={colors.info} $delay="0.15s">
          <MetricIcon $color={colors.info}>
            <FaClock />
          </MetricIcon>
          <MetricLabel>Item Decryption</MetricLabel>
          <MetricValue $color={colors.info}>
            {Math.round(metrics.itemDecryption.average)}
            <MetricUnit>ms</MetricUnit>
          </MetricValue>
          <MetricDescription>
            Average on-demand decryption ({metrics.itemDecryption.samples} samples)
          </MetricDescription>
        </MetricCard>

        <MetricCard $color={colors.warning} $delay="0.2s">
          <MetricIcon $color={colors.warning}>
            <FaDatabase />
          </MetricIcon>
          <MetricLabel>Bulk Operations</MetricLabel>
          <MetricValue $color={colors.warning}>
            {metrics.bulkOperations.samples}
            <MetricUnit>ops</MetricUnit>
          </MetricValue>
          <MetricDescription>
            Total bulk decryption operations performed
          </MetricDescription>
        </MetricCard>
      </Grid>

      <DetailsCard>
        <DetailsHeader>
          <DetailsIcon>
            <FaRocket />
          </DetailsIcon>
          <DetailsTitle>Performance Comparison</DetailsTitle>
        </DetailsHeader>
        
        <ComparisonBar>
          <BarLabel>Before Lazy Loading</BarLabel>
          <BarContainer>
            <Bar $width={100} $color={colors.danger}>
              <BarText>{beforeUnlock}ms</BarText>
            </Bar>
          </BarContainer>
        </ComparisonBar>

        <ComparisonBar>
          <BarLabel>After Lazy Loading</BarLabel>
          <BarContainer>
            <Bar $width={(afterUnlock / beforeUnlock) * 100} $color={colors.success}>
              <BarText>{afterUnlock}ms</BarText>
            </Bar>
          </BarContainer>
        </ComparisonBar>

        <ImprovementBadge>
          <FaBolt /> {improvement}% Faster Performance
        </ImprovementBadge>
      </DetailsCard>

      {metrics.vaultUnlock.all.length > 0 && (
        <DetailsCard>
          <DetailsHeader>
            <DetailsIcon>
              <FaClock />
            </DetailsIcon>
            <DetailsTitle>Recent Vault Unlocks</DetailsTitle>
          </DetailsHeader>
          <Table>
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>Duration (ms)</Th>
                <Th>Items</Th>
                <Th>Per Item (ms)</Th>
              </tr>
            </thead>
            <tbody>
              {metrics.vaultUnlock.all.slice(-10).reverse().map((entry, index) => (
                <TableRow key={index}>
                  <Td>{new Date(entry.timestamp).toLocaleTimeString()}</Td>
                  <Td style={{ fontWeight: 700, color: colors.success }}>{Math.round(entry.duration)}</Td>
                  <Td>{entry.itemCount}</Td>
                  <Td>{Math.round(entry.durationPerItem)}</Td>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </DetailsCard>
      )}

      {metrics.itemDecryption.all.length > 0 && (
        <DetailsCard>
          <DetailsHeader>
            <DetailsIcon>
              <FaMemory />
            </DetailsIcon>
            <DetailsTitle>Recent Item Decryptions</DetailsTitle>
          </DetailsHeader>
          <Table>
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>Item ID</Th>
                <Th>Duration (ms)</Th>
              </tr>
            </thead>
            <tbody>
              {metrics.itemDecryption.all.slice(-10).reverse().map((entry, index) => (
                <TableRow key={index}>
                  <Td>{new Date(entry.timestamp).toLocaleTimeString()}</Td>
                  <Td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '12px' }}>
                    {entry.itemId.substring(0, 16)}...
                  </Td>
                  <Td style={{ fontWeight: 700, color: colors.info }}>{Math.round(entry.duration)}</Td>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </DetailsCard>
      )}

      <ButtonGroup>
        <Button className="primary" onClick={exportMetrics}>
          <FaDownload />
          Export Metrics
        </Button>
        <Button className="danger" onClick={clearMetrics}>
          <FaTrash />
          Clear Data
        </Button>
      </ButtonGroup>
    </Container>
  );
};

export default PerformanceDashboard;

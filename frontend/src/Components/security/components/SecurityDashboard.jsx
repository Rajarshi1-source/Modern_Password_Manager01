import React, { useState, useEffect, useCallback, useMemo } from 'react';
import styled, { keyframes } from 'styled-components';
import { AnimatePresence } from 'framer-motion';
import { FaLock, FaUnlock, FaShieldAlt, FaSearch, FaSyncAlt, FaCheckCircle, FaHistory, FaBell, FaMobile, FaUserShield, FaArrowLeft, FaExclamationTriangle, FaTimesCircle, FaLink, FaCog, FaGlobe, FaToggleOn, FaToggleOff } from 'react-icons/fa';
import { toast } from 'react-hot-toast';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import BreachAlert from './BreachAlert';
import BreachDetails from './BreachDetails';
import LoginHistory from './LoginHistory';
import NotificationSettings from './NotificationSettings';
import DeviceManager from './DeviceManager';
import { useVault } from '../../../contexts/VaultContext';
import { DarkWebService } from '../../../services/darkWebService';

// Animations
const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
`;

// Color Constants - matching settings theme
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  accent: '#A78BFA',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  background: '#0f0f1a',
  backgroundSecondary: '#1a1a2e',
  backgroundTertiary: '#252542',
  cardBg: '#1e1e35',
  cardBgHover: '#262649',
  text: '#ffffff',
  textSecondary: '#a0a0b8',
  textMuted: '#6b6b8a',
  border: '#2d2d4a',
  borderLight: '#3d3d5a'
};

const PageWrapper = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: ${colors.background};
  overflow-y: auto;
  overflow-x: hidden;
`;

const Container = styled.div`
  padding: 32px 24px;
  max-width: 1000px;
  margin: 0 auto;
  min-height: 100vh;
  background: linear-gradient(180deg, ${colors.background} 0%, ${colors.backgroundSecondary} 100%);
  animation: ${fadeIn} 0.4s ease-out;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  flex-wrap: wrap;
  gap: 16px;
`;

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 20px;
`;

const BackButton = styled.button`
  background: rgba(123, 104, 238, 0.1);
  color: ${colors.textSecondary};
  border: 1px solid rgba(123, 104, 238, 0.3);
  border-radius: 12px;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  transition: all 0.3s ease;
  
  &:hover {
    background: rgba(123, 104, 238, 0.2);
    color: ${colors.primary};
    border-color: ${colors.primary};
    transform: translateX(-4px);
  }
  
  svg {
    transition: transform 0.3s ease;
  }
  
  &:hover svg {
    transform: translateX(-4px);
  }
`;

const TitleSection = styled.div``;

const Title = styled.h1`
  margin: 0 0 4px 0;
  font-size: 28px;
  font-weight: 800;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.accent} 50%, ${colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const TitleIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 22px;
    color: ${colors.primary};
  }
`;

const ScanButton = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 14px;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 700;
  font-size: 15px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 20px ${colors.primary}40;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 24px ${colors.primary}50;
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
    transform: none;
  }
  
  svg {
    animation: ${props => props.$loading ? spin : 'none'} 1s linear infinite;
  }
`;

// Score Card
const ScoreCard = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.backgroundSecondary} 100%);
  border-radius: 24px;
  padding: 28px 32px;
  margin-bottom: 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid ${colors.border};
  box-shadow: 0 8px 32px rgba(123, 104, 238, 0.1);
  animation: ${fadeIn} 0.4s ease-out;
`;

const ScoreInfo = styled.div`
  h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 700;
    color: ${colors.text};
  }
  
  p {
    margin: 0;
    color: ${colors.textSecondary};
    font-size: 15px;
  }
`;

const ScoreCircle = styled.div`
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 800;
  color: white;
  background: ${props => {
    if (props.$score >= 70) return `linear-gradient(135deg, ${colors.success} 0%, #059669 100%)`;
    if (props.$score >= 40) return `linear-gradient(135deg, ${colors.warning} 0%, #d97706 100%)`;
    return `linear-gradient(135deg, ${colors.danger} 0%, #dc2626 100%)`;
  }};
  box-shadow: ${props => {
    if (props.$score >= 70) return `0 8px 32px ${colors.success}50`;
    if (props.$score >= 40) return `0 8px 32px ${colors.warning}50`;
    return `0 8px 32px ${colors.danger}50`;
  }};
  
  span {
    font-size: 12px;
    font-weight: 600;
    opacity: 0.9;
    margin-top: 2px;
  }
`;

// Tab Navigation - Pill Style
const TabContainer = styled.div`
  margin-bottom: 32px;
`;

const TabList = styled.div`
  display: flex;
  background: ${colors.backgroundTertiary};
  padding: 6px;
  border-radius: 16px;
  margin-bottom: 28px;
  overflow-x: auto;
  gap: 4px;
`;

const Tab = styled.button`
  flex: 1;
  min-width: 120px;
  background: ${props => props.$active 
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
    : 'transparent'};
  border: none;
  padding: 14px 20px;
  border-radius: 12px;
  cursor: pointer;
  color: ${props => props.$active ? '#fff' : colors.textSecondary};
  font-weight: ${props => props.$active ? '700' : '600'};
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.3s ease;
  box-shadow: ${props => props.$active ? `0 4px 16px ${colors.primary}40` : 'none'};
  font-size: 14px;
  
  &:hover {
    color: ${props => props.$active ? '#fff' : colors.text};
    background: ${props => props.$active 
      ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
      : colors.cardBg};
  }
`;

// Section Styles
const Section = styled.div`
  background: ${colors.cardBg};
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 24px;
  border: 1px solid ${colors.border};
  animation: ${fadeIn} 0.3s ease-out;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    box-shadow: 0 8px 32px rgba(123, 104, 238, 0.1);
  }
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid ${colors.border};
`;

const SectionIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}20 0%, ${props => props.$color || colors.primary}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 20px;
    color: ${props => props.$color || colors.primary};
  }
`;

const SectionTitle = styled.h3`
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: ${colors.text};
`;

// Status Grid
const StatusGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 18px;
  margin-bottom: 28px;
`;

const StatusCard = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid ${colors.border};
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index * 0.05}s;
  animation-fill-mode: backwards;
  
  &:hover {
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.15);
    transform: translateY(-4px);
    border-color: ${colors.borderLight};
  }
`;

const StatusIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  background: ${props => {
    if (props.$variant === 'success') return `linear-gradient(135deg, ${colors.success}25 0%, ${colors.success}15 100%)`;
    if (props.$variant === 'warning') return `linear-gradient(135deg, ${colors.warning}25 0%, ${colors.warning}15 100%)`;
    if (props.$variant === 'danger') return `linear-gradient(135deg, ${colors.danger}25 0%, ${colors.danger}15 100%)`;
    return `linear-gradient(135deg, ${colors.primary}25 0%, ${colors.primary}15 100%)`;
  }};
  
  svg {
    font-size: 22px;
    color: ${props => {
      if (props.$variant === 'success') return colors.success;
      if (props.$variant === 'warning') return colors.warning;
      if (props.$variant === 'danger') return colors.danger;
      return colors.primary;
    }};
  }
`;

const StatusValue = styled.div`
  font-size: 32px;
  font-weight: 800;
  margin-bottom: 6px;
  background: ${props => {
    if (props.$variant === 'danger') return `linear-gradient(135deg, ${colors.danger} 0%, #f87171 100%)`;
    if (props.$variant === 'warning') return `linear-gradient(135deg, ${colors.warning} 0%, #fbbf24 100%)`;
    if (props.$variant === 'success') return `linear-gradient(135deg, ${colors.success} 0%, #34d399 100%)`;
    return `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%)`;
  }};
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

const StatusLabel = styled.div`
  font-size: 14px;
  color: ${colors.textSecondary};
  font-weight: 500;
`;

const ScanningBanner = styled.div`
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}08 100%);
  border: 1px solid ${colors.primary}30;
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  animation: ${pulse} 2s ease-in-out infinite;
`;

const ScanningText = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  font-weight: 600;
  font-size: 15px;
  color: ${colors.text};
  
  svg {
    color: ${colors.primary};
    animation: ${spin} 1s linear infinite;
    font-size: 18px;
  }
`;

const ProgressBar = styled.div`
  width: 200px;
  height: 10px;
  background: ${colors.backgroundTertiary};
  border-radius: 5px;
  overflow: hidden;
`;

const ProgressFill = styled.div`
  height: 100%;
  width: ${props => props.$progress}%;
  background: linear-gradient(90deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  transition: width 0.3s ease;
  border-radius: 5px;
`;

// Safe Banner
const SafeBanner = styled.div`
  background: linear-gradient(135deg, ${colors.success}15 0%, ${colors.success}08 100%);
  border: 1px solid ${colors.success}30;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 18px;
  animation: ${fadeIn} 0.4s ease-out;
`;

const SafeIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, ${colors.success} 0%, #059669 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px ${colors.success}30;
  
  svg {
    color: white;
    font-size: 26px;
  }
`;

const SafeContent = styled.div`
  flex: 1;
  
  h4 {
    margin: 0 0 6px;
    font-size: 18px;
    font-weight: 700;
    color: ${colors.success};
  }
  
  p {
    margin: 0;
    font-size: 14px;
    color: ${colors.textSecondary};
  }
`;

// Account Cards
const AccountList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
`;

const AccountCard = styled.div`
  background: ${props => props.$locked 
    ? `linear-gradient(135deg, ${colors.danger}08 0%, ${colors.backgroundSecondary} 100%)`
    : `linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%)`};
  border-radius: 16px;
  padding: 20px 24px;
  border: 1px solid ${props => props.$locked ? `${colors.danger}30` : colors.border};
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index * 0.05}s;
  animation-fill-mode: backwards;
  
  &:hover {
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.12);
    transform: translateY(-2px);
    border-color: ${props => props.$locked ? `${colors.danger}40` : colors.borderLight};
  }
`;

const AccountHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
`;

const AccountInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

const AccountIconWrapper = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: ${props => {
    const platform = props.$platform?.toLowerCase();
    if (platform === 'facebook') return 'linear-gradient(135deg, #1877f2 0%, #166fe5 100%)';
    if (platform === 'twitter' || platform === 'x') return 'linear-gradient(135deg, #1da1f2 0%, #0d8bd9 100%)';
    if (platform === 'instagram') return 'linear-gradient(135deg, #e4405f 0%, #c32aa3 100%)';
    if (platform === 'linkedin') return 'linear-gradient(135deg, #0077b5 0%, #005582 100%)';
    if (platform === 'google') return 'linear-gradient(135deg, #ea4335 0%, #fbbc05 100%)';
    return `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`;
  }};
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  
  svg {
    color: white;
    font-size: 22px;
  }
`;

const AccountDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const AccountName = styled.span`
  font-size: 16px;
  font-weight: 700;
  color: ${colors.text};
  text-transform: capitalize;
`;

const AccountUsername = styled.span`
  font-size: 13px;
  color: ${colors.textSecondary};
`;

const AccountBadges = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
`;

const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  
  ${props => {
    if (props.$variant === 'locked') return `
      background: linear-gradient(135deg, ${colors.danger}25 0%, ${colors.danger}15 100%);
      color: ${colors.danger};
    `;
    if (props.$variant === 'auto-lock') return `
      background: linear-gradient(135deg, ${colors.success}25 0%, ${colors.success}15 100%);
      color: ${colors.success};
    `;
    return `
      background: ${colors.backgroundTertiary};
      color: ${colors.textSecondary};
    `;
  }}
`;

const AccountReason = styled.div`
  margin-top: 14px;
  padding: 14px 16px;
  background: ${colors.danger}10;
  border-radius: 12px;
  border-left: 3px solid ${colors.danger};
  
  span {
    font-size: 14px;
    color: ${colors.danger};
  }
`;

const AccountActions = styled.div`
  display: flex;
  gap: 10px;
  margin-top: 18px;
  flex-wrap: wrap;
`;

const ActionButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  
  ${props => {
    if (props.$variant === 'unlock') return `
      background: linear-gradient(135deg, ${colors.success} 0%, #059669 100%);
      color: white;
      box-shadow: 0 4px 12px ${colors.success}30;
      &:hover { transform: translateY(-2px); box-shadow: 0 6px 16px ${colors.success}40; }
    `;
    if (props.$variant === 'lock') return `
      background: linear-gradient(135deg, ${colors.danger} 0%, #dc2626 100%);
      color: white;
      box-shadow: 0 4px 12px ${colors.danger}30;
      &:hover { transform: translateY(-2px); box-shadow: 0 6px 16px ${colors.danger}40; }
    `;
    return `
      background: ${colors.backgroundTertiary};
      color: ${colors.textSecondary};
      border: 1px solid ${colors.border};
      &:hover { border-color: ${colors.primary}; color: ${colors.primary}; }
    `;
  }}
`;

const EmptyState = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%);
  border-radius: 20px;
  padding: 60px 32px;
  text-align: center;
  border: 2px dashed ${colors.border};
  animation: ${fadeIn} 0.4s ease-out;
`;

const EmptyIcon = styled.div`
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  
  svg {
    font-size: 32px;
    color: ${colors.primary};
  }
`;

const EmptyTitle = styled.h4`
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 700;
  color: ${colors.text};
`;

const EmptyText = styled.p`
  margin: 0;
  color: ${colors.textSecondary};
  font-size: 15px;
  line-height: 1.6;
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: ${colors.textSecondary};
`;

const Spinner = styled.div`
  width: 48px;
  height: 48px;
  border: 3px solid ${colors.border};
  border-top-color: ${colors.primary};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-bottom: 20px;
`;

const SecurityDashboard = () => {
  const { items } = useVault();
  const navigate = useNavigate();
  const [socialAccounts, setSocialAccounts] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [alerts, setAlerts] = useState([]);
  const [scanProgress, setScanProgress] = useState(null);
  const [scanResults, setScanResults] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedBreach, setSelectedBreach] = useState(null);
  const [securityScore, setSecurityScore] = useState(0);
  
  const darkWebService = useMemo(() => new DarkWebService(), []);
  
  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const { data } = await axios.get('/api/security/dashboard/');
      setSocialAccounts(data.social_accounts || []);
    } catch (error) {
      toast.error('Failed to load social accounts');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const calculateSecurityScore = useCallback(async () => {
    try {
      const { data } = await axios.get('/api/security/score/');
      setSecurityScore(data.score || 75);
    } catch (error) {
      console.error('Failed to fetch security score', error);
      setSecurityScore(75);
    }
  }, []);
  
  const fetchBreachAlerts = useCallback(async () => {
    try {
      setIsLoading(true);
      const alerts = await darkWebService.getBreachAlerts();
      setAlerts(alerts);
    } catch (error) {
      console.error('Error fetching breach alerts:', error);
    } finally {
      setIsLoading(false);
    }
  }, [darkWebService]);
  
  useEffect(() => {
    fetchData();
    fetchBreachAlerts();
    calculateSecurityScore();
  }, [fetchData, fetchBreachAlerts, calculateSecurityScore]);

  const handleToggleLock = async (accountId, currentStatus) => {
    try {
      if (currentStatus) {
        await axios.post(`/api/security/social-accounts/${accountId}/unlock/`);
        toast.success('Account unlocked successfully');
      } else {
        await axios.post(`/api/security/social-accounts/${accountId}/lock/`);
        toast.success('Account locked successfully');
      }
      fetchData();
    } catch (error) {
      toast.error('Operation failed');
      console.error(error);
    }
  };

  const handleToggleAutoLock = async (accountId, enabled) => {
    try {
      await axios.patch(`/api/security/social-accounts/${accountId}/`, {
        auto_lock_enabled: !enabled
      });
      toast.success(`Auto-lock ${!enabled ? 'enabled' : 'disabled'} successfully`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update settings');
      console.error(error);
    }
  };
  
  const handleScanVault = async () => {
    try {
      setScanProgress({ current: 0, total: 0 });
      setScanResults(null);
      
      const results = await darkWebService.checkVaultPasswords(
        items,
        (progress) => setScanProgress(progress)
      );
      
      setScanResults(results);
      await darkWebService.startVaultScan();
      await fetchBreachAlerts();
      
    } catch (error) {
      console.error('Error scanning vault:', error);
    } finally {
      setScanProgress(null);
    }
  };
  
  const handleResolveAlert = async (alertId) => {
    try {
      await darkWebService.markBreachResolved(alertId);
      setAlerts(alerts.filter(alert => alert.id !== alertId));
    } catch (error) {
      console.error('Error resolving alert:', error);
    }
  };
  
  const handleDismissAlert = (alertId) => {
    setAlerts(alerts.filter(alert => alert.id !== alertId));
  };
  
  const handleFixPassword = (alert) => {
    console.log('Fix password for:', alert);
  };
  
  const handleViewDetails = (alert) => {
    setSelectedBreach(alert);
  };
  
  const getSecurityStatus = () => {
    const activeAlerts = alerts.filter(alert => !alert.resolved);
    
    if (activeAlerts.length === 0) return 'safe';
    if (activeAlerts.some(alert => alert.severity === 'high')) return 'danger';
    return 'warning';
  };
  
  const securityStatus = getSecurityStatus();
  const activeAlerts = alerts.filter(alert => !alert.resolved);
  
  const renderOverviewTab = () => (
    <div style={{ animation: `${fadeIn} 0.3s ease-out` }}>
      {scanProgress && (
        <ScanningBanner>
          <ScanningText>
            <FaSyncAlt /> Scanning your vault for security breaches...
          </ScanningText>
          <ProgressBar>
            <ProgressFill $progress={(scanProgress.current / Math.max(scanProgress.total, 1)) * 100} />
          </ProgressBar>
        </ScanningBanner>
      )}
      
      <Section>
        <SectionHeader>
          <SectionIcon $color={colors.primary}>
            <FaShieldAlt />
          </SectionIcon>
          <SectionTitle>Security Overview</SectionTitle>
        </SectionHeader>
        
        <StatusGrid>
          <StatusCard $index={0}>
            <StatusIcon $variant={securityStatus === 'safe' ? 'success' : securityStatus === 'warning' ? 'warning' : 'danger'}>
              {securityStatus === 'safe' ? <FaCheckCircle /> : <FaExclamationTriangle />}
            </StatusIcon>
            <StatusValue $variant={securityStatus === 'safe' ? 'success' : securityStatus === 'warning' ? 'warning' : 'danger'}>
              {securityStatus === 'safe' ? 'Safe' : securityStatus === 'warning' ? 'At Risk' : 'Alert'}
            </StatusValue>
            <StatusLabel>Overall Status</StatusLabel>
          </StatusCard>
          
          <StatusCard $index={1}>
            <StatusIcon $variant={activeAlerts.length > 0 ? 'danger' : 'success'}>
              <FaBell />
            </StatusIcon>
            <StatusValue $variant={activeAlerts.length > 0 ? 'danger' : 'success'}>
              {activeAlerts.length}
            </StatusValue>
            <StatusLabel>Active Alerts</StatusLabel>
          </StatusCard>
          
          {scanResults && (
            <StatusCard $index={2}>
              <StatusIcon $variant={scanResults.breached > 0 ? 'danger' : 'success'}>
                <FaTimesCircle />
              </StatusIcon>
              <StatusValue $variant={scanResults.breached > 0 ? 'danger' : 'success'}>
                {scanResults.breached}
              </StatusValue>
              <StatusLabel>Compromised</StatusLabel>
            </StatusCard>
          )}
          
          <StatusCard $index={3}>
            <StatusIcon>
              <FaLock />
            </StatusIcon>
            <StatusValue>
              {items.filter(item => item.type === 'password').length}
            </StatusValue>
            <StatusLabel>Total Passwords</StatusLabel>
          </StatusCard>
        </StatusGrid>
      </Section>
      
      <Section data-testid="alerts-section">
        <SectionHeader>
          <SectionIcon $color={activeAlerts.length > 0 ? colors.warning : colors.success}>
            {activeAlerts.length > 0 ? <FaExclamationTriangle /> : <FaCheckCircle />}
          </SectionIcon>
          <SectionTitle>
            {activeAlerts.length > 0 ? 'Active Security Alerts' : 'Security Status'}
          </SectionTitle>
        </SectionHeader>
        
        {activeAlerts.length > 0 && (
          <span className="sr-only" data-testid="breach-alert-indicator">
            Real-Time Breach Alert: Unauthorized Access Detected
          </span>
        )}
        
        <AnimatePresence>
          {activeAlerts.map(alert => (
            <BreachAlert
              key={alert.id}
              alert={alert}
              onResolve={() => handleResolveAlert(alert.id)}
              onFix={() => handleFixPassword(alert)}
              onDismiss={() => handleDismissAlert(alert.id)}
              onViewDetails={() => handleViewDetails(alert)}
            />
          ))}
        </AnimatePresence>
        
        {activeAlerts.length === 0 && !isLoading && (
          <SafeBanner data-testid="no-alerts-status">
            <SafeIcon>
              <FaCheckCircle />
            </SafeIcon>
            <SafeContent>
              <h4>✨ All Clear!</h4>
              <p>No security alerts detected. Your passwords appear to be safe.</p>
            </SafeContent>
            <span className="sr-only" data-testid="breach-status">
              No Breach Alerts Detected
            </span>
          </SafeBanner>
        )}
      </Section>
    </div>
  );
  
  const renderAccountsTab = () => (
    <Section>
      <SectionHeader>
        <SectionIcon $color={colors.info}>
          <FaUserShield />
        </SectionIcon>
        <SectionTitle>Connected Social Accounts</SectionTitle>
      </SectionHeader>
      
      {isLoading ? (
        <LoadingContainer>
          <Spinner />
          <span>Loading accounts...</span>
        </LoadingContainer>
      ) : socialAccounts.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaLink />
          </EmptyIcon>
          <EmptyTitle>No Connected Accounts</EmptyTitle>
          <EmptyText>
            You haven't connected any social media accounts yet. 
            Connect accounts to enable protection features.
          </EmptyText>
        </EmptyState>
      ) : (
        <AccountList>
          {socialAccounts.map((account, index) => (
            <AccountCard 
              key={account.id} 
              $locked={account.status === 'locked'}
              $index={index}
            >
              <AccountHeader>
                <AccountInfo>
                  <AccountIconWrapper $platform={account.platform}>
                    <FaGlobe />
                  </AccountIconWrapper>
                  <AccountDetails>
                    <AccountName>{account.platform}</AccountName>
                    <AccountUsername>
                      {account.username || account.account_id}
                    </AccountUsername>
                  </AccountDetails>
                </AccountInfo>
                <AccountBadges>
                  {account.status === 'locked' && (
                    <Badge $variant="locked">
                      <FaLock /> Locked
                    </Badge>
                  )}
                  {account.auto_lock_enabled && (
                    <Badge $variant="auto-lock">
                      <FaToggleOn /> Auto-Lock
                    </Badge>
                  )}
                </AccountBadges>
              </AccountHeader>
              
              {account.lock_reason && (
                <AccountReason>
                  <span>⚠️ {account.lock_reason}</span>
                </AccountReason>
              )}
              
              <AccountActions>
                <ActionButton 
                  $variant={account.status === 'locked' ? 'unlock' : 'lock'}
                  onClick={() => handleToggleLock(account.id, account.status === 'locked')}
                >
                  {account.status === 'locked' ? (
                    <><FaUnlock /> Unlock Account</>
                  ) : (
                    <><FaLock /> Lock Account</>
                  )}
                </ActionButton>
                <ActionButton 
                  onClick={() => handleToggleAutoLock(account.id, account.auto_lock_enabled)}
                >
                  {account.auto_lock_enabled ? (
                    <><FaToggleOff /> Disable Auto-Lock</>
                  ) : (
                    <><FaToggleOn /> Enable Auto-Lock</>
                  )}
                </ActionButton>
                <ActionButton>
                  <FaCog /> Settings
                </ActionButton>
              </AccountActions>
            </AccountCard>
          ))}
        </AccountList>
      )}
    </Section>
  );
  
  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverviewTab();
      case 'accounts':
        return renderAccountsTab();
      case 'devices':
        return <DeviceManager />;
      case 'history':
        return <LoginHistory />;
      case 'notifications':
        return <NotificationSettings />;
      default:
        return <div>Tab content not found</div>;
    }
  };
  
  return (
    <PageWrapper>
      <Container>
        <Header>
          <HeaderLeft>
            <BackButton onClick={() => navigate('/')}>
              <FaArrowLeft /> Back to Vault
            </BackButton>
            <TitleSection>
              <Title>
                <TitleIcon><FaShieldAlt /></TitleIcon>
                Security Dashboard
              </Title>
            </TitleSection>
          </HeaderLeft>
          <ScanButton onClick={handleScanVault} disabled={scanProgress !== null} $loading={scanProgress !== null}>
            <FaSearch /> Scan for Breaches
          </ScanButton>
        </Header>
        
        <ScoreCard>
          <ScoreInfo>
            <h2>🛡️ Your Security Score</h2>
            <p>Based on your current security settings and activity</p>
          </ScoreInfo>
          <ScoreCircle $score={securityScore}>
            {securityScore}%
            <span>Score</span>
          </ScoreCircle>
        </ScoreCard>

        <TabContainer>
          <TabList>
            <Tab 
              $active={activeTab === 'overview'} 
              onClick={() => setActiveTab('overview')}
            >
              <FaShieldAlt /> Overview
            </Tab>
            <Tab 
              $active={activeTab === 'accounts'} 
              onClick={() => setActiveTab('accounts')}
            >
              <FaUserShield /> Social Accounts
            </Tab>
            <Tab 
              $active={activeTab === 'devices'} 
              onClick={() => setActiveTab('devices')}
            >
              <FaMobile /> Devices
            </Tab>
            <Tab 
              $active={activeTab === 'history'} 
              onClick={() => setActiveTab('history')}
            >
              <FaHistory /> Login History
            </Tab>
            <Tab 
              $active={activeTab === 'notifications'} 
              onClick={() => setActiveTab('notifications')}
            >
              <FaBell /> Notifications
            </Tab>
          </TabList>
          
          {renderTabContent()}
        </TabContainer>
        
        {selectedBreach && (
          <BreachDetails 
            breach={selectedBreach} 
            onClose={() => setSelectedBreach(null)}
          />
        )}
      </Container>
    </PageWrapper>
  );
};

export default SecurityDashboard;

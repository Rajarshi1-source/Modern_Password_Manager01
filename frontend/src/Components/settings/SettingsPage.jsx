import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import preferencesService from '../../services/preferencesService';
import analyticsService from '../../services/analyticsService';
import ThemeSettings from './ThemeSettings';
import SecuritySettings from './SecuritySettings';
import NotificationSettings from './NotificationSettings';
import PrivacySettings from './PrivacySettings';
import { FaPalette, FaShieldAlt, FaBell, FaUserShield, FaArrowLeft, FaSync, FaDownload, FaUpload, FaUndo, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import {
  SettingsPageWrapper,
  SettingsContainer,
  SettingsHeader,
  TabContainer,
  Tab,
  ActionButtons,
  Button,
  Alert
} from './SettingsComponents';

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const BackButtonWrapper = styled.div`
  display: flex;
  justify-content: flex-start;
  margin-bottom: 24px;
`;

const BackButton = styled.button`
  background: rgba(123, 104, 238, 0.1);
  color: #a0a0b8;
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
    color: #7B68EE;
    border-color: #7B68EE;
    transform: translateX(-4px);
  }
  
  svg {
    transition: transform 0.3s ease;
  }
  
  &:hover svg {
    transform: translateX(-4px);
  }
`;

const ContentWrapper = styled.div`
  animation: ${fadeIn} 0.4s ease-out;
`;

const AlertWrapper = styled.div`
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 1000;
  max-width: 400px;
  animation: ${fadeIn} 0.3s ease-out;
  
  svg {
    font-size: 18px;
  }
`;

const SettingsPage = () => {
  const [activeTab, setActiveTab] = useState('theme');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    // Initialize preferences on mount
    preferencesService.initialize();
    
    // Track page view
    analyticsService.trackPageView('/settings');
    
    // Track feature usage
    analyticsService.trackFeatureUsage('settings_page');
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setMessage('');
    
    // Track tab navigation
    analyticsService.trackEvent('tab_change', 'settings_navigation', {
      from: activeTab,
      to: tab
    });
  };

  const showMessage = (msg, type) => {
    setMessage(msg);
    setMessageType(type);
    setTimeout(() => setMessage(''), 4000);
  };

  const handleExport = async () => {
    try {
      const preferences = await preferencesService.export();
      
      // Create blob and download
      const blob = new Blob([preferences], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `preferences_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      showMessage('✨ Preferences exported successfully!', 'success');
      
      // Track export
      analyticsService.trackEvent('export', 'preferences', {
        tab: activeTab
      });
    } catch (error) {
      console.error('Export failed:', error);
      showMessage('Failed to export preferences', 'error');
    }
  };

  const handleImport = async () => {
    try {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      
      input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
          await preferencesService.import(file);
          showMessage('✨ Preferences imported successfully! Reloading...', 'success');
          
          // Track import
          analyticsService.trackEvent('import', 'preferences', {
            tab: activeTab
          });
          
          // Reload page to apply imported preferences
          setTimeout(() => window.location.reload(), 2000);
        } catch (error) {
          console.error('Import failed:', error);
          showMessage('Failed to import preferences. Please check the file format.', 'error');
        }
      };
      
      input.click();
    } catch (error) {
      console.error('Import error:', error);
      showMessage('Failed to import preferences', 'error');
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to reset all settings to defaults? This action cannot be undone.')) {
      return;
    }
    
    try {
      await preferencesService.reset();
      showMessage('🔄 All settings have been reset to defaults. Reloading...', 'success');
      
      // Track reset
      analyticsService.trackEvent('reset', 'preferences', {
        tab: activeTab
      });
      
      // Reload page to apply defaults
      setTimeout(() => window.location.reload(), 2000);
    } catch (error) {
      console.error('Reset failed:', error);
      showMessage('Failed to reset preferences', 'error');
    }
  };

  const handleSync = async () => {
    try {
      await preferencesService.sync();
      showMessage('✅ Preferences synced successfully!', 'success');
      
      // Track sync
      analyticsService.trackEvent('sync', 'preferences');
    } catch (error) {
      console.error('Sync failed:', error);
      showMessage('Failed to sync preferences', 'error');
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'theme':
        return <ThemeSettings />;
      case 'security':
        return <SecuritySettings />;
      case 'notifications':
        return <NotificationSettings />;
      case 'privacy':
        return <PrivacySettings />;
      default:
        return <ThemeSettings />;
    }
  };

  return (
    <SettingsPageWrapper>
      <SettingsContainer>
        <BackButtonWrapper>
          <BackButton onClick={() => navigate(-1)}>
            <FaArrowLeft /> Back to Vault
          </BackButton>
        </BackButtonWrapper>

        <SettingsHeader>
          <h1>⚙️ Settings</h1>
          <p>Customize your password manager experience</p>
        </SettingsHeader>

        {message && (
          <AlertWrapper>
            <Alert type={messageType}>
              {messageType === 'success' && <FaCheckCircle />}
              {messageType === 'error' && <FaExclamationTriangle />}
              {message}
            </Alert>
          </AlertWrapper>
        )}

        <TabContainer>
          <Tab
            active={activeTab === 'theme'}
            onClick={() => handleTabChange('theme')}
          >
            <FaPalette /> Theme
          </Tab>
          <Tab
            active={activeTab === 'security'}
            onClick={() => handleTabChange('security')}
          >
            <FaShieldAlt /> Security
          </Tab>
          <Tab
            active={activeTab === 'notifications'}
            onClick={() => handleTabChange('notifications')}
          >
            <FaBell /> Notifications
          </Tab>
          <Tab
            active={activeTab === 'privacy'}
            onClick={() => handleTabChange('privacy')}
          >
            <FaUserShield /> Privacy
          </Tab>
        </TabContainer>

        <ContentWrapper key={activeTab}>
          {renderTabContent()}
        </ContentWrapper>

        <ActionButtons>
          <Button onClick={handleSync}>
            <FaSync /> Sync Now
          </Button>
          <Button onClick={handleExport}>
            <FaDownload /> Export
          </Button>
          <Button onClick={handleImport}>
            <FaUpload /> Import
          </Button>
          <Button variant="danger" onClick={handleReset}>
            <FaUndo /> Reset All
          </Button>
        </ActionButtons>
      </SettingsContainer>
    </SettingsPageWrapper>
  );
};

export default SettingsPage;

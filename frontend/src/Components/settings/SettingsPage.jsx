import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import preferencesService from '../../services/preferencesService';
import analyticsService from '../../services/analyticsService';
import ThemeSettings from './ThemeSettings';
import SecuritySettings from './SecuritySettings';
import NotificationSettings from './NotificationSettings';
import PrivacySettings from './PrivacySettings';
import {
  SettingsContainer,
  SettingsHeader,
  TabContainer,
  Tab,
  ActionButtons,
  Button,
  Alert
} from './SettingsComponents';

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
      
      setMessage('Preferences exported successfully!');
      setMessageType('success');
      
      // Track export
      analyticsService.trackEvent('export', 'preferences', {
        tab: activeTab
      });
    } catch (error) {
      console.error('Export failed:', error);
      setMessage('Failed to export preferences');
      setMessageType('error');
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
          setMessage('Preferences imported successfully! Reloading...');
          setMessageType('success');
          
          // Track import
          analyticsService.trackEvent('import', 'preferences', {
            tab: activeTab
          });
          
          // Reload page to apply imported preferences
          setTimeout(() => window.location.reload(), 2000);
        } catch (error) {
          console.error('Import failed:', error);
          setMessage('Failed to import preferences. Please check the file format.');
          setMessageType('error');
        }
      };
      
      input.click();
    } catch (error) {
      console.error('Import error:', error);
      setMessage('Failed to import preferences');
      setMessageType('error');
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to reset all settings to defaults? This action cannot be undone.')) {
      return;
    }
    
    try {
      await preferencesService.reset();
      setMessage('All settings have been reset to defaults. Reloading...');
      setMessageType('success');
      
      // Track reset
      analyticsService.trackEvent('reset', 'preferences', {
        tab: activeTab
      });
      
      // Reload page to apply defaults
      setTimeout(() => window.location.reload(), 2000);
    } catch (error) {
      console.error('Reset failed:', error);
      setMessage('Failed to reset preferences');
      setMessageType('error');
    }
  };

  const handleSync = async () => {
    try {
      await preferencesService.sync();
      setMessage('Preferences synced successfully!');
      setMessageType('success');
      
      // Track sync
      analyticsService.trackEvent('sync', 'preferences');
      
      setTimeout(() => setMessage(''), 3000);
    } catch (error) {
      console.error('Sync failed:', error);
      setMessage('Failed to sync preferences');
      setMessageType('error');
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
    <SettingsContainer>
      <SettingsHeader>
        <h1>Settings</h1>
        <p>Customize your password manager experience</p>
      </SettingsHeader>

      {message && <Alert type={messageType}>{message}</Alert>}

      <TabContainer>
        <Tab
          active={activeTab === 'theme'}
          onClick={() => handleTabChange('theme')}
        >
          🎨 Theme
        </Tab>
        <Tab
          active={activeTab === 'security'}
          onClick={() => handleTabChange('security')}
        >
          🔒 Security
        </Tab>
        <Tab
          active={activeTab === 'notifications'}
          onClick={() => handleTabChange('notifications')}
        >
          🔔 Notifications
        </Tab>
        <Tab
          active={activeTab === 'privacy'}
          onClick={() => handleTabChange('privacy')}
        >
          🔐 Privacy
        </Tab>
      </TabContainer>

      {renderTabContent()}

      <ActionButtons>
        <Button onClick={() => navigate(-1)}>
          Back
        </Button>
        <Button onClick={handleSync}>
          Sync Now
        </Button>
        <Button onClick={handleExport}>
          Export Settings
        </Button>
        <Button onClick={handleImport}>
          Import Settings
        </Button>
        <Button onClick={handleReset}>
          Reset to Defaults
        </Button>
      </ActionButtons>
    </SettingsContainer>
  );
};

export default SettingsPage;


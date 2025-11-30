import React, { useState, useEffect } from 'react';
import preferencesService from '../../services/preferencesService';
import {
  Section,
  SectionHeader,
  SettingItem,
  SettingInfo,
  SettingControl,
  Select,
  Input,
  ToggleSwitch,
  Alert
} from './SettingsComponents';

const PrivacySettings = () => {
  const [privacy, setPrivacy] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const loadPrivacy = () => {
      const privacyPrefs = preferencesService.get('privacy') || {};
      setPrivacy(privacyPrefs);
    };
    
    loadPrivacy();
  }, []);

  const updatePrivacy = async (key, value) => {
    const newPrivacy = { ...privacy, [key]: value };
    setPrivacy(newPrivacy);
    
    try {
      await preferencesService.set('privacy', key, value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save privacy preference:', error);
    }
  };

  return (
    <>
      {saved && <Alert type="success">Privacy settings saved successfully!</Alert>}
      
      <Section>
        <SectionHeader>
          <h2>Data Collection</h2>
          <p>Control what data we collect to improve your experience</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Analytics</h3>
            <p>Help us improve by sharing anonymous usage data</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.analytics !== false}
              onChange={(value) => updatePrivacy('analytics', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Error Reporting</h3>
            <p>Automatically send error reports to help fix bugs</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.errorReporting !== false}
              onChange={(value) => updatePrivacy('errorReporting', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Performance Monitoring</h3>
            <p>Share performance data to optimize the app</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.performanceMonitoring !== false}
              onChange={(value) => updatePrivacy('performanceMonitoring', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Crash Reports</h3>
            <p>Send crash reports to identify and fix issues</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.crashReports !== false}
              onChange={(value) => updatePrivacy('crashReports', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Usage Data</h3>
            <p>Collect data about how you use features</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.usageData || false}
              onChange={(value) => updatePrivacy('usageData', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <h2>History & Logs</h2>
          <p>Manage how long we keep your activity history</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Keep Login History</h3>
            <p>Store record of your login attempts</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.keepLoginHistory !== false}
              onChange={(value) => updatePrivacy('keepLoginHistory', value)}
            />
          </SettingControl>
        </SettingItem>

        {privacy.keepLoginHistory !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Login History Retention</h3>
              <p>Delete login history older than this</p>
            </SettingInfo>
            <SettingControl>
              <Select
                value={privacy.loginHistoryDays || 90}
                onChange={(e) => updatePrivacy('loginHistoryDays', parseInt(e.target.value))}
              >
                <option value="30">30 days</option>
                <option value="60">60 days</option>
                <option value="90">90 days</option>
                <option value="180">6 months</option>
                <option value="365">1 year</option>
              </Select>
            </SettingControl>
          </SettingItem>
        )}

        <SettingItem>
          <SettingInfo>
            <h3>Keep Audit Logs</h3>
            <p>Store record of vault item changes</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.keepAuditLogs !== false}
              onChange={(value) => updatePrivacy('keepAuditLogs', value)}
            />
          </SettingControl>
        </SettingItem>

        {privacy.keepAuditLogs !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Audit Log Retention</h3>
              <p>Delete audit logs older than this</p>
            </SettingInfo>
            <SettingControl>
              <Select
                value={privacy.auditLogDays || 365}
                onChange={(e) => updatePrivacy('auditLogDays', parseInt(e.target.value))}
              >
                <option value="90">90 days</option>
                <option value="180">6 months</option>
                <option value="365">1 year</option>
                <option value="730">2 years</option>
                <option value="-1">Forever</option>
              </Select>
            </SettingControl>
          </SettingItem>
        )}
      </Section>

      <Section>
        <SectionHeader>
          <h2>Data Rights</h2>
          <p>Exercise your data privacy rights</p>
        </SectionHeader>

        <Alert type="info">
          You have the right to access, export, or delete your personal data at any time. 
          Contact us if you have any privacy concerns.
        </Alert>
      </Section>
    </>
  );
};

export default PrivacySettings;


import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import preferencesService from '../../services/preferencesService';
import { FaBell, FaEnvelope, FaMobileAlt, FaDesktop, FaClock, FaShieldAlt, FaCheckCircle, FaInfoCircle, FaVolumeUp, FaExclamationTriangle } from 'react-icons/fa';
import {
  Section,
  SectionHeader,
  SectionHeaderContent,
  SectionIcon,
  SettingItem,
  SettingInfo,
  SettingControl,
  Select,
  ToggleSwitch,
  TimePicker,
  Alert,
  Badge,
  InfoBox,
  InfoText
} from './SettingsComponents';

const NotificationPreview = styled.div`
  background: #252542;
  border-radius: 12px;
  padding: 16px 20px;
  margin-top: 16px;
  border: 1px solid #2d2d4a;
  display: flex;
  align-items: center;
  gap: 16px;
`;

const NotificationIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #7B68EE 0%, #6B58DE 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    color: white;
    font-size: 20px;
  }
`;

const NotificationContent = styled.div`
  flex: 1;
  
  h4 {
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
  }
  
  p {
    margin: 0;
    font-size: 12px;
    color: #a0a0b8;
  }
`;

const NotificationTime = styled.span`
  font-size: 11px;
  color: #6b6b8a;
`;

const QuietHoursCard = styled.div`
  background: linear-gradient(135deg, #1a1a2e 0%, #252542 100%);
  border-radius: 14px;
  padding: 20px;
  margin-top: 16px;
  border: 1px solid #2d2d4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
`;

const QuietHoursInfo = styled.div`
  flex: 1;
  
  h4 {
    margin: 0 0 4px;
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  p {
    margin: 0;
    font-size: 13px;
    color: #a0a0b8;
  }
`;

const TimeRange = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  
  span {
    color: #6b6b8a;
    font-size: 14px;
  }
`;

const NotificationSettings = () => {
  const [notifications, setNotifications] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const loadNotifications = () => {
      const notificationPrefs = preferencesService.get('notifications') || {};
      setNotifications(notificationPrefs);
    };
    
    loadNotifications();
  }, []);

  const updateNotifications = async (key, value) => {
    const newNotifications = { ...notifications, [key]: value };
    setNotifications(newNotifications);
    
    try {
      await preferencesService.set('notifications', key, value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save notification preference:', error);
    }
  };

  return (
    <>
      {saved && (
        <Alert type="success">
          <FaCheckCircle /> Notification settings saved successfully!
        </Alert>
      )}
      
      <Section>
        <SectionHeader>
          <SectionIcon $color="#7B68EE">
            <FaBell />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Notification Channels</h2>
            <p>Choose how you want to receive alerts and updates</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaEnvelope style={{ color: '#3B82F6', marginRight: 8 }} />
              Email Notifications
            </h3>
            <p>Receive important security alerts and updates via email</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.emailNotifications !== false}
              onChange={(value) => updateNotifications('emailNotifications', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaDesktop style={{ color: '#10B981', marginRight: 8 }} />
              Push Notifications
              <Badge $variant="success">Recommended</Badge>
            </h3>
            <p>Get instant browser notifications for security events</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.pushNotifications !== false}
              onChange={(value) => updateNotifications('pushNotifications', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaMobileAlt style={{ color: '#EC4899', marginRight: 8 }} />
              SMS Alerts
              <Badge>Critical Only</Badge>
            </h3>
            <p>Receive text messages for critical security breaches</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.smsAlerts || false}
              onChange={(value) => updateNotifications('smsAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaVolumeUp style={{ color: '#F59E0B', marginRight: 8 }} />
              Sound Alerts
            </h3>
            <p>Play a sound when notifications arrive</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.soundAlerts !== false}
              onChange={(value) => updateNotifications('soundAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <NotificationPreview>
          <NotificationIcon>
            <FaShieldAlt />
          </NotificationIcon>
          <NotificationContent>
            <h4>Security Alert</h4>
            <p>New login detected from Chrome on Windows</p>
          </NotificationContent>
          <NotificationTime>Just now</NotificationTime>
        </NotificationPreview>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#F59E0B">
            <FaExclamationTriangle />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Alert Types</h2>
            <p>Configure which events trigger notifications</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Security Breaches</h3>
            <p>Alert when your credentials appear in a data breach</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.breachAlerts !== false}
              onChange={(value) => updateNotifications('breachAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>New Device Login</h3>
            <p>Alert when your account is accessed from a new device</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.newDeviceAlerts !== false}
              onChange={(value) => updateNotifications('newDeviceAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Password Expiry Reminders</h3>
            <p>Remind me when passwords need to be updated</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.passwordExpiryAlerts !== false}
              onChange={(value) => updateNotifications('passwordExpiryAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Weak Password Warnings</h3>
            <p>Alert when weak or reused passwords are detected</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.weakPasswordAlerts !== false}
              onChange={(value) => updateNotifications('weakPasswordAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Sharing Activity</h3>
            <p>Notify when passwords are shared or unshared</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.sharingAlerts !== false}
              onChange={(value) => updateNotifications('sharingAlerts', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#10B981">
            <FaClock />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Quiet Hours</h2>
            <p>Silence non-critical notifications during specific times</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Enable Quiet Hours</h3>
            <p>Pause non-urgent notifications during set hours</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.quietHoursEnabled || false}
              onChange={(value) => updateNotifications('quietHoursEnabled', value)}
            />
          </SettingControl>
        </SettingItem>

        {notifications.quietHoursEnabled && (
          <QuietHoursCard>
            <QuietHoursInfo>
              <h4>
                <FaClock style={{ color: '#10B981' }} />
                Quiet Period
              </h4>
              <p>Only critical security alerts will be sent during this time</p>
            </QuietHoursInfo>
            <TimeRange>
              <TimePicker
                value={notifications.quietHoursStart || '22:00'}
                onChange={(e) => updateNotifications('quietHoursStart', e.target.value)}
              />
              <span>to</span>
              <TimePicker
                value={notifications.quietHoursEnd || '07:00'}
                onChange={(e) => updateNotifications('quietHoursEnd', e.target.value)}
              />
            </TimeRange>
          </QuietHoursCard>
        )}

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Note:</strong> Critical security alerts (data breaches, unauthorized access) 
            will always be sent regardless of quiet hours settings.
          </InfoText>
        </InfoBox>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#3B82F6">
            <FaEnvelope />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Email Preferences</h2>
            <p>Control frequency of email communications</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Email Digest Frequency</h3>
            <p>How often to receive summary emails</p>
          </SettingInfo>
          <SettingControl>
            <Select
              value={notifications.emailDigestFrequency || 'weekly'}
              onChange={(e) => updateNotifications('emailDigestFrequency', e.target.value)}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="never">Never</option>
            </Select>
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Marketing Emails</h3>
            <p>Receive news, tips, and product updates</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.marketingEmails || false}
              onChange={(value) => updateNotifications('marketingEmails', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>
    </>
  );
};

export default NotificationSettings;

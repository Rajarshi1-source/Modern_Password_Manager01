import React, { useState, useEffect } from 'react';
import preferencesService from '../../services/preferencesService';
import {
  Section,
  SectionHeader,
  SettingItem,
  SettingInfo,
  SettingControl,
  ToggleSwitch,
  TimePicker,
  Slider,
  Alert
} from './SettingsComponents';

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
      {saved && <Alert type="success">Notification settings saved successfully!</Alert>}
      
      <Section>
        <SectionHeader>
          <h2>General Notifications</h2>
          <p>Manage how you receive notifications</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Enable Notifications</h3>
            <p>Turn all notifications on or off</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.enabled !== false}
              onChange={(value) => updateNotifications('enabled', value)}
            />
          </SettingControl>
        </SettingItem>

        {notifications.enabled !== false && (
          <>
            <SettingItem>
              <SettingInfo>
                <h3>Browser Notifications</h3>
                <p>Show desktop notifications</p>
              </SettingInfo>
              <SettingControl>
                <ToggleSwitch
                  checked={notifications.browser !== false}
                  onChange={(value) => updateNotifications('browser', value)}
                />
              </SettingControl>
            </SettingItem>

            <SettingItem>
              <SettingInfo>
                <h3>Email Notifications</h3>
                <p>Receive notifications via email</p>
              </SettingInfo>
              <SettingControl>
                <ToggleSwitch
                  checked={notifications.email !== false}
                  onChange={(value) => updateNotifications('email', value)}
                />
              </SettingControl>
            </SettingItem>

            <SettingItem>
              <SettingInfo>
                <h3>Push Notifications</h3>
                <p>Mobile push notifications (requires mobile app)</p>
              </SettingInfo>
              <SettingControl>
                <ToggleSwitch
                  checked={notifications.push || false}
                  onChange={(value) => updateNotifications('push', value)}
                />
              </SettingControl>
            </SettingItem>
          </>
        )}
      </Section>

      <Section>
        <SectionHeader>
          <h2>Notification Types</h2>
          <p>Choose which types of notifications to receive</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Breach Alerts</h3>
            <p>Notify when your credentials are found in a data breach</p>
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
            <h3>Security Alerts</h3>
            <p>Notify about suspicious activity and security events</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.securityAlerts !== false}
              onChange={(value) => updateNotifications('securityAlerts', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Account Activity</h3>
            <p>Notify about logins and account changes</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.accountActivity || false}
              onChange={(value) => updateNotifications('accountActivity', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Marketing</h3>
            <p>Receive tips, offers, and promotional content</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.marketing || false}
              onChange={(value) => updateNotifications('marketing', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Product Updates</h3>
            <p>Notify about new features and improvements</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.productUpdates !== false}
              onChange={(value) => updateNotifications('productUpdates', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <h2>Quiet Hours</h2>
          <p>Disable notifications during specific hours</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Enable Quiet Hours</h3>
            <p>Mute notifications during set hours</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.quietHoursEnabled || false}
              onChange={(value) => updateNotifications('quietHoursEnabled', value)}
            />
          </SettingControl>
        </SettingItem>

        {notifications.quietHoursEnabled && (
          <>
            <SettingItem>
              <SettingInfo>
                <h3>Start Time</h3>
                <p>When quiet hours begin</p>
              </SettingInfo>
              <SettingControl>
                <TimePicker
                  value={notifications.quietHoursStart || '22:00'}
                  onChange={(e) => updateNotifications('quietHoursStart', e.target.value)}
                />
              </SettingControl>
            </SettingItem>

            <SettingItem>
              <SettingInfo>
                <h3>End Time</h3>
                <p>When quiet hours end</p>
              </SettingInfo>
              <SettingControl>
                <TimePicker
                  value={notifications.quietHoursEnd || '08:00'}
                  onChange={(e) => updateNotifications('quietHoursEnd', e.target.value)}
                />
              </SettingControl>
            </SettingItem>
          </>
        )}
      </Section>

      <Section>
        <SectionHeader>
          <h2>Sound & Alerts</h2>
          <p>Configure notification sounds</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Notification Sound</h3>
            <p>Play sound with notifications</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={notifications.sound !== false}
              onChange={(value) => updateNotifications('sound', value)}
            />
          </SettingControl>
        </SettingItem>

        {notifications.sound !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Sound Volume</h3>
              <p>Adjust notification volume ({Math.round((notifications.soundVolume || 0.7) * 100)}%)</p>
            </SettingInfo>
            <SettingControl>
              <Slider
                min="0"
                max="1"
                step="0.1"
                value={notifications.soundVolume || 0.7}
                onChange={(e) => updateNotifications('soundVolume', parseFloat(e.target.value))}
              />
            </SettingControl>
          </SettingItem>
        )}
      </Section>
    </>
  );
};

export default NotificationSettings;


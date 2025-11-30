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

const SecuritySettings = () => {
  const [security, setSecurity] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const loadSecurity = () => {
      const securityPrefs = preferencesService.get('security') || {};
      setSecurity(securityPrefs);
    };
    
    loadSecurity();
  }, []);

  const updateSecurity = async (key, value) => {
    const newSecurity = { ...security, [key]: value };
    setSecurity(newSecurity);
    
    try {
      await preferencesService.set('security', key, value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save security preference:', error);
    }
  };

  return (
    <>
      {saved && <Alert type="success">Security settings saved successfully!</Alert>}
      
      <Section>
        <SectionHeader>
          <h2>Vault Security</h2>
          <p>Configure auto-lock and authentication settings</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Auto-Lock Vault</h3>
            <p>Automatically lock your vault after inactivity</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.autoLockEnabled !== false}
              onChange={(value) => updateSecurity('autoLockEnabled', value)}
            />
          </SettingControl>
        </SettingItem>

        {security.autoLockEnabled !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Auto-Lock Timeout</h3>
              <p>Lock after this many seconds of inactivity</p>
            </SettingInfo>
            <SettingControl>
              <Select
                value={security.autoLockTimeout || 300}
                onChange={(e) => updateSecurity('autoLockTimeout', parseInt(e.target.value))}
              >
                <option value="60">1 minute</option>
                <option value="300">5 minutes</option>
                <option value="600">10 minutes</option>
                <option value="900">15 minutes</option>
                <option value="1800">30 minutes</option>
                <option value="3600">1 hour</option>
              </Select>
            </SettingControl>
          </SettingItem>
        )}

        <SettingItem>
          <SettingInfo>
            <h3>Biometric Authentication</h3>
            <p>Use fingerprint or face recognition to unlock</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.biometricAuth !== false}
              onChange={(value) => updateSecurity('biometricAuth', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Two-Factor Authentication</h3>
            <p>Require 2FA for login (configure in Account Settings)</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.twoFactorAuth || false}
              onChange={(value) => updateSecurity('twoFactorAuth', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Require Re-authentication</h3>
            <p>Require password for sensitive operations</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.requireReauth !== false}
              onChange={(value) => updateSecurity('requireReauth', value)}
            />
          </SettingControl>
        </SettingItem>

        {security.requireReauth !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Re-authentication Timeout</h3>
              <p>Require re-auth after this many seconds</p>
            </SettingInfo>
            <SettingControl>
              <Select
                value={security.reauthTimeout || 3600}
                onChange={(e) => updateSecurity('reauthTimeout', parseInt(e.target.value))}
              >
                <option value="300">5 minutes</option>
                <option value="600">10 minutes</option>
                <option value="1800">30 minutes</option>
                <option value="3600">1 hour</option>
                <option value="7200">2 hours</option>
              </Select>
            </SettingControl>
          </SettingItem>
        )}
      </Section>

      <Section>
        <SectionHeader>
          <h2>Clipboard Security</h2>
          <p>Manage clipboard behavior for copied passwords</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Clear Clipboard</h3>
            <p>Automatically clear copied passwords</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.clearClipboard !== false}
              onChange={(value) => updateSecurity('clearClipboard', value)}
            />
          </SettingControl>
        </SettingItem>

        {security.clearClipboard !== false && (
          <SettingItem>
            <SettingInfo>
              <h3>Clipboard Timeout</h3>
              <p>Clear clipboard after this many seconds</p>
            </SettingInfo>
            <SettingControl>
              <Select
                value={security.clipboardTimeout || 30}
                onChange={(e) => updateSecurity('clipboardTimeout', parseInt(e.target.value))}
              >
                <option value="15">15 seconds</option>
                <option value="30">30 seconds</option>
                <option value="60">1 minute</option>
                <option value="120">2 minutes</option>
              </Select>
            </SettingControl>
          </SettingItem>
        )}
      </Section>

      <Section>
        <SectionHeader>
          <h2>Password Generator</h2>
          <p>Default settings for password generation</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Default Password Length</h3>
            <p>Number of characters for generated passwords</p>
          </SettingInfo>
          <SettingControl>
            <Input
              type="number"
              min="8"
              max="128"
              value={security.defaultPasswordLength || 16}
              onChange={(e) => updateSecurity('defaultPasswordLength', parseInt(e.target.value))}
              style={{ width: '80px' }}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Include Symbols</h3>
            <p>Use special characters (!@#$%^&*)</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.includeSymbols !== false}
              onChange={(value) => updateSecurity('includeSymbols', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Include Numbers</h3>
            <p>Use numeric characters (0-9)</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.includeNumbers !== false}
              onChange={(value) => updateSecurity('includeNumbers', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Include Uppercase</h3>
            <p>Use uppercase letters (A-Z)</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.includeUppercase !== false}
              onChange={(value) => updateSecurity('includeUppercase', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Include Lowercase</h3>
            <p>Use lowercase letters (a-z)</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.includeLowercase !== false}
              onChange={(value) => updateSecurity('includeLowercase', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <h2>Monitoring</h2>
          <p>Security monitoring and breach detection</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Breach Monitoring</h3>
            <p>Check passwords against known data breaches</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.breachMonitoring !== false}
              onChange={(value) => updateSecurity('breachMonitoring', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Dark Web Monitoring</h3>
            <p>Monitor the dark web for compromised credentials</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.darkWebMonitoring || false}
              onChange={(value) => updateSecurity('darkWebMonitoring', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>
    </>
  );
};

export default SecuritySettings;


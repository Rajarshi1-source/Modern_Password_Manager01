import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import preferencesService from '../../services/preferencesService';
import { FaShieldAlt, FaLock, FaClock, FaFingerprint, FaKey, FaClipboard, FaRandom, FaEye, FaExclamationTriangle, FaCheckCircle, FaInfoCircle, FaGlobe } from 'react-icons/fa';
import {
  Section,
  SectionHeader,
  SectionHeaderContent,
  SectionIcon,
  SettingItem,
  SettingInfo,
  SettingControl,
  Select,
  Input,
  ToggleSwitch,
  Alert,
  Badge,
  InfoBox,
  InfoText
} from './SettingsComponents';

const PasswordStrengthDemo = styled.div`
  background: #252542;
  border-radius: 12px;
  padding: 20px;
  margin-top: 16px;
  border: 1px solid #2d2d4a;
`;

const PasswordDemoLabel = styled.div`
  font-size: 12px;
  color: #6b6b8a;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const PasswordDemoValue = styled.div`
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  color: #10B981;
  letter-spacing: 1px;
  word-break: break-all;
  background: #1a1a2e;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #2d2d4a;
`;

const PasswordOptions = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 16px;
`;

const PasswordOption = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: ${props => props.$enabled ? '#10B981' : '#6b6b8a'};
  
  svg {
    font-size: 14px;
  }
`;

const TimeoutBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: linear-gradient(135deg, #7B68EE20 0%, #7B68EE10 100%);
  color: #9B8BFF;
  margin-left: 8px;
`;

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

  const generateSamplePassword = () => {
    const length = security.defaultPasswordLength || 16;
    let chars = '';
    if (security.includeLowercase !== false) chars += 'abcdefghijklmnopqrstuvwxyz';
    if (security.includeUppercase !== false) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    if (security.includeNumbers !== false) chars += '0123456789';
    if (security.includeSymbols !== false) chars += '!@#$%^&*';
    if (!chars) chars = 'abcdefghijklmnopqrstuvwxyz';
    
    let password = '';
    for (let i = 0; i < length; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
  };

  const formatTimeout = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
    return `${Math.floor(seconds / 3600)}hr`;
  };

  return (
    <>
      {saved && (
        <Alert type="success">
          <FaCheckCircle /> Security settings saved successfully!
        </Alert>
      )}
      
      <Section>
        <SectionHeader>
          <SectionIcon $color="#7B68EE">
            <FaLock />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Vault Security</h2>
            <p>Configure auto-lock and authentication settings</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaClock style={{ color: '#F59E0B', marginRight: 8 }} />
              Auto-Lock Vault
              {security.autoLockEnabled !== false && (
                <TimeoutBadge>
                  <FaClock size={10} />
                  {formatTimeout(security.autoLockTimeout || 300)}
                </TimeoutBadge>
              )}
            </h3>
            <p>Automatically lock your vault after a period of inactivity</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.autoLockEnabled !== false}
              onChange={(value) => updateSecurity('autoLockEnabled', value)}
            />
          </SettingControl>
        </SettingItem>

        {security.autoLockEnabled !== false && (
          <SettingItem $index={1}>
            <SettingInfo>
              <h3>Auto-Lock Timeout</h3>
              <p>Lock vault after this duration of inactivity</p>
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
            <h3>
              <FaFingerprint style={{ color: '#10B981', marginRight: 8 }} />
              Biometric Authentication
              <Badge $variant="success">Recommended</Badge>
            </h3>
            <p>Use fingerprint or face recognition to unlock your vault</p>
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
            <h3>
              <FaKey style={{ color: '#3B82F6', marginRight: 8 }} />
              Two-Factor Authentication
            </h3>
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
            <h3>
              <FaShieldAlt style={{ color: '#EC4899', marginRight: 8 }} />
              Require Re-authentication
            </h3>
            <p>Require password for sensitive operations like viewing or copying passwords</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.requireReauth !== false}
              onChange={(value) => updateSecurity('requireReauth', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#EF4444">
            <FaClipboard />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Clipboard Security</h2>
            <p>Protect copied passwords from being stolen</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Clear Clipboard Automatically</h3>
            <p>Remove copied passwords from clipboard after a short time</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.clearClipboard !== false}
              onChange={(value) => updateSecurity('clearClipboard', value)}
            />
          </SettingControl>
        </SettingItem>

        {security.clearClipboard !== false && (
          <SettingItem $index={1}>
            <SettingInfo>
              <h3>Clipboard Timeout</h3>
              <p>Clear clipboard after this duration</p>
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

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Security Tip:</strong> Shorter clipboard timeouts are more secure 
            but may require you to paste quickly. 30 seconds is recommended for most users.
          </InfoText>
        </InfoBox>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#10B981">
            <FaRandom />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Password Generator</h2>
            <p>Default settings for generating secure passwords</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Default Password Length</h3>
            <p>Number of characters for generated passwords (8-128)</p>
          </SettingInfo>
          <SettingControl>
            <Input
              type="number"
              min="8"
              max="128"
              value={security.defaultPasswordLength || 16}
              onChange={(e) => updateSecurity('defaultPasswordLength', parseInt(e.target.value))}
              style={{ width: '80px', textAlign: 'center' }}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Include Symbols (!@#$%^&*)</h3>
            <p>Use special characters for stronger passwords</p>
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
            <h3>Include Numbers (0-9)</h3>
            <p>Use numeric characters</p>
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
            <h3>Include Uppercase (A-Z)</h3>
            <p>Use uppercase letters</p>
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
            <h3>Include Lowercase (a-z)</h3>
            <p>Use lowercase letters</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={security.includeLowercase !== false}
              onChange={(value) => updateSecurity('includeLowercase', value)}
            />
          </SettingControl>
        </SettingItem>

        <PasswordStrengthDemo>
          <PasswordDemoLabel>Sample Generated Password</PasswordDemoLabel>
          <PasswordDemoValue>{generateSamplePassword()}</PasswordDemoValue>
          <PasswordOptions>
            <PasswordOption $enabled={security.includeLowercase !== false}>
              {security.includeLowercase !== false ? <FaCheckCircle /> : <FaExclamationTriangle />}
              Lowercase
            </PasswordOption>
            <PasswordOption $enabled={security.includeUppercase !== false}>
              {security.includeUppercase !== false ? <FaCheckCircle /> : <FaExclamationTriangle />}
              Uppercase
            </PasswordOption>
            <PasswordOption $enabled={security.includeNumbers !== false}>
              {security.includeNumbers !== false ? <FaCheckCircle /> : <FaExclamationTriangle />}
              Numbers
            </PasswordOption>
            <PasswordOption $enabled={security.includeSymbols !== false}>
              {security.includeSymbols !== false ? <FaCheckCircle /> : <FaExclamationTriangle />}
              Symbols
            </PasswordOption>
          </PasswordOptions>
        </PasswordStrengthDemo>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#F59E0B">
            <FaGlobe />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Breach Monitoring</h2>
            <p>Protect against compromised credentials</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaEye style={{ color: '#F59E0B', marginRight: 8 }} />
              Breach Monitoring
              <Badge $variant="success">Active</Badge>
            </h3>
            <p>Check your passwords against known data breaches</p>
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
            <h3>
              <FaExclamationTriangle style={{ color: '#EF4444', marginRight: 8 }} />
              Dark Web Monitoring
              <Badge $variant="new">Premium</Badge>
            </h3>
            <p>Scan the dark web for your compromised credentials</p>
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

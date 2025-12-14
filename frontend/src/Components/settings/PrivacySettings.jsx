import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import preferencesService from '../../services/preferencesService';
import { FaUserShield, FaChartBar, FaBug, FaTachometerAlt, FaHistory, FaClipboardList, FaDatabase, FaTrash, FaDownload, FaCheckCircle, FaInfoCircle, FaExclamationTriangle, FaLock } from 'react-icons/fa';
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
  Alert,
  Badge,
  InfoBox,
  InfoText,
  Button
} from './SettingsComponents';

const DataRightsCard = styled.div`
  background: linear-gradient(135deg, #252542 0%, #1a1a2e 100%);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid #2d2d4a;
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 16px;
`;

const DataRightsIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, #7B68EE20 0%, #7B68EE10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 28px;
    color: #7B68EE;
  }
`;

const DataRightsContent = styled.div`
  flex: 1;
  
  h4 {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 600;
    color: #ffffff;
  }
  
  p {
    margin: 0;
    font-size: 14px;
    color: #a0a0b8;
    line-height: 1.6;
  }
`;

const DataRightsActions = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const RetentionBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: ${props => {
    if (props.$days <= 30) return 'linear-gradient(135deg, #10B98130 0%, #10B98120 100%)';
    if (props.$days <= 90) return 'linear-gradient(135deg, #F59E0B30 0%, #F59E0B20 100%)';
    return 'linear-gradient(135deg, #EF444430 0%, #EF444420 100%)';
  }};
  color: ${props => {
    if (props.$days <= 30) return '#10B981';
    if (props.$days <= 90) return '#F59E0B';
    return '#EF4444';
  }};
`;

const PrivacyMeter = styled.div`
  background: #1a1a2e;
  border-radius: 12px;
  padding: 20px;
  margin-top: 20px;
  border: 1px solid #2d2d4a;
`;

const PrivacyMeterHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  
  h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  span {
    font-size: 24px;
    font-weight: 700;
    color: ${props => {
      if (props.$score >= 80) return '#10B981';
      if (props.$score >= 50) return '#F59E0B';
      return '#EF4444';
    }};
  }
`;

const PrivacyBar = styled.div`
  height: 8px;
  background: #252542;
  border-radius: 4px;
  overflow: hidden;
`;

const PrivacyFill = styled.div`
  height: 100%;
  width: ${props => props.$score}%;
  background: ${props => {
    if (props.$score >= 80) return 'linear-gradient(90deg, #10B981 0%, #059669 100%)';
    if (props.$score >= 50) return 'linear-gradient(90deg, #F59E0B 0%, #D97706 100%)';
    return 'linear-gradient(90deg, #EF4444 0%, #DC2626 100%)';
  }};
  border-radius: 4px;
  transition: width 0.5s ease;
`;

const PrivacyTip = styled.p`
  margin: 12px 0 0;
  font-size: 13px;
  color: #6b6b8a;
`;

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

  const calculatePrivacyScore = () => {
    let score = 100;
    
    // Deduct points for enabled data collection
    if (privacy.analytics !== false) score -= 10;
    if (privacy.errorReporting !== false) score -= 5;
    if (privacy.performanceMonitoring !== false) score -= 5;
    if (privacy.crashReports !== false) score -= 5;
    if (privacy.usageData) score -= 15;
    
    // Add points for good privacy practices
    if (privacy.keepLoginHistory === false) score += 5;
    if (privacy.loginHistoryDays && privacy.loginHistoryDays <= 30) score += 5;
    
    return Math.max(0, Math.min(100, score));
  };

  const privacyScore = calculatePrivacyScore();

  return (
    <>
      {saved && (
        <Alert type="success">
          <FaCheckCircle /> Privacy settings saved successfully!
        </Alert>
      )}
      
      <Section>
        <SectionHeader>
          <SectionIcon $color="#7B68EE">
            <FaChartBar />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Data Collection</h2>
            <p>Control what data we collect to improve your experience</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaChartBar style={{ color: '#3B82F6', marginRight: 8 }} />
              Analytics
            </h3>
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
            <h3>
              <FaBug style={{ color: '#EF4444', marginRight: 8 }} />
              Error Reporting
            </h3>
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
            <h3>
              <FaTachometerAlt style={{ color: '#10B981', marginRight: 8 }} />
              Performance Monitoring
            </h3>
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
            <h3>
              <FaExclamationTriangle style={{ color: '#F59E0B', marginRight: 8 }} />
              Crash Reports
            </h3>
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
            <h3>
              <FaDatabase style={{ color: '#EC4899', marginRight: 8 }} />
              Usage Data
              <Badge $variant="warning">Extended</Badge>
            </h3>
            <p>Collect detailed data about feature usage patterns</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.usageData || false}
              onChange={(value) => updatePrivacy('usageData', value)}
            />
          </SettingControl>
        </SettingItem>

        <PrivacyMeter>
          <PrivacyMeterHeader $score={privacyScore}>
            <h4>
              <FaLock /> Privacy Score
            </h4>
            <span>{privacyScore}%</span>
          </PrivacyMeterHeader>
          <PrivacyBar>
            <PrivacyFill $score={privacyScore} />
          </PrivacyBar>
          <PrivacyTip>
            {privacyScore >= 80 
              ? '✨ Excellent! Your privacy settings are well configured.'
              : privacyScore >= 50
              ? '⚠️ Moderate. Consider disabling some data collection for better privacy.'
              : '🔒 Consider reviewing your privacy settings to enhance protection.'}
          </PrivacyTip>
        </PrivacyMeter>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#F59E0B">
            <FaHistory />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>History & Logs</h2>
            <p>Manage how long we keep your activity history</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Keep Login History</h3>
            <p>Store record of your login attempts for security review</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.keepLoginHistory !== false}
              onChange={(value) => updatePrivacy('keepLoginHistory', value)}
            />
          </SettingControl>
        </SettingItem>

        {privacy.keepLoginHistory !== false && (
          <SettingItem $index={1}>
            <SettingInfo>
              <h3>
                Login History Retention
                <RetentionBadge $days={privacy.loginHistoryDays || 90}>
                  {privacy.loginHistoryDays || 90} days
                </RetentionBadge>
              </h3>
              <p>Delete login history older than this period</p>
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
            <h3>
              <FaClipboardList style={{ color: '#3B82F6', marginRight: 8 }} />
              Keep Audit Logs
            </h3>
            <p>Store record of vault item changes for compliance</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={privacy.keepAuditLogs !== false}
              onChange={(value) => updatePrivacy('keepAuditLogs', value)}
            />
          </SettingControl>
        </SettingItem>

        {privacy.keepAuditLogs !== false && (
          <SettingItem $index={1}>
            <SettingInfo>
              <h3>
                Audit Log Retention
                <RetentionBadge $days={privacy.auditLogDays || 365}>
                  {privacy.auditLogDays === -1 ? 'Forever' : `${privacy.auditLogDays || 365} days`}
                </RetentionBadge>
              </h3>
              <p>Delete audit logs older than this period</p>
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

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Privacy Tip:</strong> Shorter retention periods improve privacy, 
            but may limit your ability to review past activity if needed.
          </InfoText>
        </InfoBox>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#10B981">
            <FaUserShield />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Your Data Rights</h2>
            <p>Exercise your GDPR and privacy rights</p>
          </SectionHeaderContent>
        </SectionHeader>

        <DataRightsCard>
          <DataRightsIcon>
            <FaDatabase />
          </DataRightsIcon>
          <DataRightsContent>
            <h4>Your Personal Data</h4>
            <p>
              You have the right to access, export, or delete your personal data at any time. 
              We believe in complete data transparency and user control.
            </p>
          </DataRightsContent>
          <DataRightsActions>
            <Button>
              <FaDownload /> Export Data
            </Button>
            <Button variant="danger">
              <FaTrash /> Delete Account
            </Button>
          </DataRightsActions>
        </DataRightsCard>

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Data Deletion:</strong> Requesting account deletion will permanently remove 
            all your data including vault items, settings, and history. This action cannot be undone.
          </InfoText>
        </InfoBox>
      </Section>
    </>
  );
};

export default PrivacySettings;

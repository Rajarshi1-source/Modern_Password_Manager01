import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { FaBell, FaEnvelope, FaMobileAlt, FaDesktop, FaShieldAlt, FaClock, FaExclamationTriangle, FaSave, FaToggleOn, FaToggleOff } from 'react-icons/fa';

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
  50% { transform: scale(1.05); }
`;

const Container = styled.div`
  animation: ${fadeIn} 0.3s ease-out;
`;

const Header = styled.div`
  margin-bottom: 24px;
`;

const Title = styled.h3`
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  svg { color: ${props => props.theme.primary || '#7B68EE'}; }
`;

const Subtitle = styled.p`
  margin: 0;
  color: ${props => props.theme.textSecondary || '#666'};
  font-size: 14px;
`;

const InfoBanner = styled.div`
  background: linear-gradient(135deg, ${props => props.theme.primaryLight || '#f0edff'} 0%, #e8f4fd 100%);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border: 1px solid ${props => props.theme.primary || '#7B68EE'}20;
`;

const InfoIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: ${props => props.theme.primary || '#7B68EE'};
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  svg { color: white; font-size: 18px; }
`;

const InfoContent = styled.div`
  flex: 1;
`;

const InfoTitle = styled.h4`
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const InfoText = styled.p`
  margin: 0;
  font-size: 13px;
  color: ${props => props.theme.textSecondary || '#666'};
  line-height: 1.5;
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const Spinner = styled.div`
  width: 40px;
  height: 40px;
  border: 3px solid ${props => props.theme.backgroundSecondary || '#f0f0f0'};
  border-top-color: ${props => props.theme.primary || '#7B68EE'};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-bottom: 16px;
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 24px;
`;

const Section = styled.div`
  background: ${props => props.theme.cardBg || '#fff'};
  border-radius: 16px;
  padding: 24px;
  border: 1px solid ${props => props.theme.borderColor || '#e0e0e0'};
  animation: ${fadeIn} 0.3s ease-out;
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid ${props => props.theme.borderColor || '#e0e0e0'};
`;

const SectionIcon = styled.div`
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: ${props => props.$color || props.theme.primary || '#7B68EE'}15;
  display: flex;
  align-items: center;
  justify-content: center;
  svg { color: ${props => props.$color || props.theme.primary || '#7B68EE'}; font-size: 18px; }
`;

const SectionTitle = styled.h4`
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const ToggleGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const ToggleItem = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: ${props => props.$active 
    ? `linear-gradient(135deg, ${props.theme.primaryLight || '#f0edff'} 0%, ${props.theme.cardBg || '#fff'} 100%)`
    : props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 12px;
  border: 1px solid ${props => props.$active ? props.theme.primary || '#7B68EE' : 'transparent'};
  transition: all 0.2s ease;
  &:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
`;

const ToggleInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
`;

const ToggleIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: ${props => props.$active ? props.theme.primary || '#7B68EE' : props.theme.borderColor || '#e0e0e0'};
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  svg { color: ${props => props.$active ? 'white' : props.theme.textSecondary || '#666'}; font-size: 18px; }
`;

const ToggleContent = styled.div`
  flex: 1;
`;

const ToggleLabel = styled.label`
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  margin-bottom: 4px;
  cursor: pointer;
`;

const ToggleDescription = styled.p`
  margin: 0;
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#666'};
  line-height: 1.4;
`;

const ToggleSwitch = styled.button`
  width: 52px;
  height: 28px;
  border-radius: 14px;
  border: none;
  cursor: pointer;
  position: relative;
  transition: all 0.3s ease;
  background: ${props => props.$active 
    ? `linear-gradient(135deg, ${props.theme.primary || '#7B68EE'} 0%, ${props.theme.accent || '#9B8BFF'} 100%)`
    : props.theme.borderColor || '#d1d5db'};
  &::after {
    content: '';
    position: absolute;
    top: 3px;
    left: ${props => props.$active ? '26px' : '3px'};
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    transition: all 0.3s ease;
  }
  &:hover { transform: scale(1.05); }
`;

const PhoneInput = styled.div`
  margin-top: 16px;
  padding: 16px;
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 12px;
  animation: ${fadeIn} 0.3s ease-out;
`;

const InputLabel = styled.label`
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  margin-bottom: 8px;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 16px;
  border: 2px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 10px;
  font-size: 14px;
  background: ${props => props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  transition: all 0.2s ease;
  box-sizing: border-box;
  &:focus { outline: none; border-color: ${props => props.theme.primary || '#7B68EE'}; }
`;

const InputHint = styled.p`
  margin: 8px 0 0;
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const SelectGroup = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
`;

const SelectContainer = styled.div`
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 12px;
  padding: 16px;
`;

const Select = styled.select`
  width: 100%;
  padding: 12px 16px;
  border: 2px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 10px;
  font-size: 14px;
  background: ${props => props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  cursor: pointer;
  transition: all 0.2s ease;
  box-sizing: border-box;
  &:focus { outline: none; border-color: ${props => props.theme.primary || '#7B68EE'}; }
`;

const SubmitButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 16px 24px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  background: linear-gradient(135deg, ${props => props.theme.primary || '#7B68EE'} 0%, ${props => props.theme.accent || '#9B8BFF'} 100%);
  color: white;
  box-shadow: 0 4px 14px ${props => props.theme.primary || '#7B68EE'}40;
  &:hover:not(:disabled) { transform: translateY(-2px); }
  &:disabled { opacity: 0.7; cursor: not-allowed; animation: ${pulse} 1.5s ease-in-out infinite; }
`;

const NotificationSettings = () => {
  const [settings, setSettings] = useState({
    email_alerts: true,
    sms_alerts: false,
    push_alerts: true,
    auto_lock_accounts: true,
    suspicious_activity_threshold: 3,
    alert_cooldown_minutes: 15,
    phone_number: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/security/account-protection/notification-settings/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      setSettings(response.data);
    } catch (error) {
      toast.error('Failed to fetch notification settings');
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      await axios.put('/api/security/account-protection/notification-settings/', settings, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      
      toast.success('Settings saved successfully! 🎉');
    } catch (error) {
      toast.error('Failed to update notification settings');
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };
  
  const handleToggle = (name) => {
    setSettings(prev => ({
      ...prev,
      [name]: !prev[name]
    }));
  };
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  if (loading) {
    return (
      <LoadingContainer>
        <Spinner />
        <span>Loading settings...</span>
      </LoadingContainer>
    );
  }
  
  return (
    <Container>
      <Header>
        <Title>
          <FaBell /> Notification Settings
        </Title>
        <Subtitle>
          Configure how you want to be notified when suspicious login attempts are detected.
        </Subtitle>
      </Header>

      <InfoBanner>
        <InfoIcon>
          <FaShieldAlt />
        </InfoIcon>
        <InfoContent>
          <InfoTitle>Stay Protected</InfoTitle>
          <InfoText>
            Enable notifications to receive instant alerts when suspicious activity is detected. 
            We recommend keeping at least one notification method active for maximum security.
          </InfoText>
        </InfoContent>
      </InfoBanner>

      <Form onSubmit={handleSubmit}>
        <Section>
          <SectionHeader>
            <SectionIcon $color="#7B68EE">
              <FaBell />
            </SectionIcon>
            <SectionTitle>Alert Methods</SectionTitle>
          </SectionHeader>
          
          <ToggleGroup>
            <ToggleItem $active={settings.email_alerts}>
              <ToggleInfo>
                <ToggleIcon $active={settings.email_alerts}>
                  <FaEnvelope />
                </ToggleIcon>
                <ToggleContent>
                  <ToggleLabel htmlFor="email_alerts">Email Alerts</ToggleLabel>
                  <ToggleDescription>
                    Receive security alerts via email when suspicious activity is detected
                  </ToggleDescription>
                </ToggleContent>
              </ToggleInfo>
              <ToggleSwitch
                type="button"
                $active={settings.email_alerts}
                onClick={() => handleToggle('email_alerts')}
              />
            </ToggleItem>

            <ToggleItem $active={settings.sms_alerts}>
              <ToggleInfo>
                <ToggleIcon $active={settings.sms_alerts}>
                  <FaMobileAlt />
                </ToggleIcon>
                <ToggleContent>
                  <ToggleLabel htmlFor="sms_alerts">SMS Alerts</ToggleLabel>
                  <ToggleDescription>
                    Receive instant text messages for critical security alerts
                  </ToggleDescription>
                </ToggleContent>
              </ToggleInfo>
              <ToggleSwitch
                type="button"
                $active={settings.sms_alerts}
                onClick={() => handleToggle('sms_alerts')}
              />
            </ToggleItem>

            {settings.sms_alerts && (
              <PhoneInput>
                <InputLabel htmlFor="phone_number">Phone Number</InputLabel>
                <Input
                  type="tel"
                  id="phone_number"
                  name="phone_number"
                  value={settings.phone_number}
                  onChange={handleChange}
                  placeholder="+1 (555) 000-0000"
                  required={settings.sms_alerts}
                />
                <InputHint>Enter your phone number in international format</InputHint>
              </PhoneInput>
            )}

            <ToggleItem $active={settings.push_alerts}>
              <ToggleInfo>
                <ToggleIcon $active={settings.push_alerts}>
                  <FaDesktop />
                </ToggleIcon>
                <ToggleContent>
                  <ToggleLabel htmlFor="push_alerts">Push Notifications</ToggleLabel>
                  <ToggleDescription>
                    Receive push notifications directly in your browser
                  </ToggleDescription>
                </ToggleContent>
              </ToggleInfo>
              <ToggleSwitch
                type="button"
                $active={settings.push_alerts}
                onClick={() => handleToggle('push_alerts')}
              />
            </ToggleItem>
          </ToggleGroup>
        </Section>

        <Section>
          <SectionHeader>
            <SectionIcon $color="#10B981">
              <FaShieldAlt />
            </SectionIcon>
            <SectionTitle>Automatic Protection</SectionTitle>
          </SectionHeader>
          
          <ToggleItem $active={settings.auto_lock_accounts}>
            <ToggleInfo>
              <ToggleIcon $active={settings.auto_lock_accounts}>
                {settings.auto_lock_accounts ? <FaToggleOn /> : <FaToggleOff />}
              </ToggleIcon>
              <ToggleContent>
                <ToggleLabel>Auto-Lock Accounts</ToggleLabel>
                <ToggleDescription>
                  Automatically lock your social media accounts when suspicious activity is detected
                </ToggleDescription>
              </ToggleContent>
            </ToggleInfo>
            <ToggleSwitch
              type="button"
              $active={settings.auto_lock_accounts}
              onClick={() => handleToggle('auto_lock_accounts')}
            />
          </ToggleItem>
        </Section>

        <Section>
          <SectionHeader>
            <SectionIcon $color="#F59E0B">
              <FaClock />
            </SectionIcon>
            <SectionTitle>Alert Thresholds</SectionTitle>
          </SectionHeader>
          
          <SelectGroup>
            <SelectContainer>
              <InputLabel htmlFor="suspicious_activity_threshold">
                <FaExclamationTriangle style={{ marginRight: '8px', color: '#F59E0B' }} />
                Suspicious Activity Threshold
              </InputLabel>
              <Select
                id="suspicious_activity_threshold"
                name="suspicious_activity_threshold"
                value={settings.suspicious_activity_threshold}
                onChange={handleChange}
              >
                <option value={1}>1 failed attempt</option>
                <option value={3}>3 failed attempts</option>
                <option value={5}>5 failed attempts</option>
                <option value={10}>10 failed attempts</option>
              </Select>
              <InputHint>Number of failed attempts before triggering an alert</InputHint>
            </SelectContainer>

            <SelectContainer>
              <InputLabel htmlFor="alert_cooldown_minutes">
                <FaClock style={{ marginRight: '8px', color: '#7B68EE' }} />
                Alert Cooldown Period
              </InputLabel>
              <Select
                id="alert_cooldown_minutes"
                name="alert_cooldown_minutes"
                value={settings.alert_cooldown_minutes}
                onChange={handleChange}
              >
                <option value={5}>5 minutes</option>
                <option value={15}>15 minutes</option>
                <option value={30}>30 minutes</option>
                <option value={60}>1 hour</option>
              </Select>
              <InputHint>Minimum time between consecutive alerts</InputHint>
            </SelectContainer>
          </SelectGroup>
        </Section>

        <SubmitButton type="submit" disabled={saving}>
          <FaSave />
          {saving ? 'Saving Changes...' : 'Save Settings'}
        </SubmitButton>
      </Form>
    </Container>
  );
};

export default NotificationSettings; 
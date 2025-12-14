import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import preferencesService from '../../services/preferencesService';
import { FaPalette, FaSun, FaMoon, FaDesktop, FaFont, FaAdjust, FaMagic, FaEye, FaExpand, FaCheckCircle, FaInfoCircle } from 'react-icons/fa';
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
  ColorPicker,
  Slider,
  Alert,
  Badge,
  InfoBox,
  InfoText
} from './SettingsComponents';

const ThemeModeGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
`;

const ThemeModeCard = styled.button`
  background: ${props => props.$active 
    ? 'linear-gradient(135deg, #7B68EE 0%, #6B58DE 100%)'
    : '#252542'};
  border: 2px solid ${props => props.$active ? '#7B68EE' : '#2d2d4a'};
  border-radius: 16px;
  padding: 24px 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  
  &:hover {
    border-color: ${props => props.$active ? '#7B68EE' : '#7B68EE50'};
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(123, 104, 238, 0.2);
  }
  
  svg {
    font-size: 28px;
    color: ${props => props.$active ? '#fff' : '#a0a0b8'};
  }
  
  span {
    font-size: 14px;
    font-weight: 600;
    color: ${props => props.$active ? '#fff' : '#a0a0b8'};
  }
`;

const FontPreview = styled.div`
  background: #252542;
  border-radius: 12px;
  padding: 20px;
  margin-top: 16px;
  border: 1px solid #2d2d4a;
  
  p {
    margin: 0;
    font-family: ${props => props.$font};
    color: #ffffff;
    font-size: ${props => props.$size}px;
    line-height: 1.6;
  }
  
  span {
    display: block;
    margin-top: 8px;
    font-size: 12px;
    color: #6b6b8a;
  }
`;

const SliderValue = styled.span`
  min-width: 48px;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: #7B68EE;
  background: #7B68EE20;
  padding: 6px 12px;
  border-radius: 8px;
`;

const ColorPresets = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
`;

const ColorPreset = styled.button`
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 2px solid ${props => props.$selected ? '#fff' : 'transparent'};
  background: ${props => props.$color};
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: ${props => props.$selected ? `0 0 0 3px ${props.$color}50` : 'none'};
  
  &:hover {
    transform: scale(1.1);
  }
`;

const ThemeSettings = () => {
  const [theme, setTheme] = useState({});
  const [saved, setSaved] = useState(false);

  const presetColors = ['#7B68EE', '#10B981', '#F59E0B', '#EF4444', '#3B82F6', '#EC4899'];

  useEffect(() => {
    const loadTheme = () => {
      const themePrefs = preferencesService.get('theme') || {};
      setTheme(themePrefs);
    };
    
    loadTheme();
  }, []);

  const updateTheme = async (key, value) => {
    const newTheme = { ...theme, [key]: value };
    setTheme(newTheme);
    
    try {
      await preferencesService.set('theme', key, value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      
      // Apply theme changes immediately
      applyTheme(key, value);
    } catch (error) {
      console.error('Failed to save theme preference:', error);
    }
  };

  const applyTheme = (key, value) => {
    switch (key) {
      case 'mode':
        document.body.classList.remove('light-mode', 'dark-mode');
        if (value === 'light') {
          document.body.classList.add('light-mode');
        } else if (value === 'dark') {
          document.body.classList.add('dark-mode');
        } else {
          // Auto mode - use system preference
          const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          document.body.classList.add(prefersDark ? 'dark-mode' : 'light-mode');
        }
        break;
      case 'fontSize':
        document.documentElement.style.fontSize = `${value}px`;
        break;
      case 'fontFamily':
        document.body.style.fontFamily = value;
        break;
      case 'animations':
        document.body.classList.toggle('reduce-motion', !value);
        break;
      default:
        break;
    }
  };

  return (
    <>
      {saved && (
        <Alert type="success">
          <FaCheckCircle /> Theme settings saved successfully!
        </Alert>
      )}
      
      <Section>
        <SectionHeader>
          <SectionIcon $color="#7B68EE">
            <FaPalette />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Color Theme</h2>
            <p>Choose your preferred visual appearance</p>
          </SectionHeaderContent>
        </SectionHeader>

        <ThemeModeGrid>
          <ThemeModeCard 
            $active={theme.mode === 'light'}
            onClick={() => updateTheme('mode', 'light')}
          >
            <FaSun />
            <span>Light</span>
          </ThemeModeCard>
          <ThemeModeCard 
            $active={theme.mode === 'dark' || !theme.mode}
            onClick={() => updateTheme('mode', 'dark')}
          >
            <FaMoon />
            <span>Dark</span>
          </ThemeModeCard>
          <ThemeModeCard 
            $active={theme.mode === 'auto'}
            onClick={() => updateTheme('mode', 'auto')}
          >
            <FaDesktop />
            <span>Auto</span>
          </ThemeModeCard>
        </ThemeModeGrid>

        <SettingItem>
          <SettingInfo>
            <h3>
              Accent Color
              <Badge $variant="new">Customize</Badge>
            </h3>
            <p>Choose your primary accent color for highlights and buttons</p>
            <ColorPresets>
              {presetColors.map(color => (
                <ColorPreset
                  key={color}
                  $color={color}
                  $selected={theme.primaryColor === color}
                  onClick={() => updateTheme('primaryColor', color)}
                />
              ))}
            </ColorPresets>
          </SettingInfo>
          <SettingControl>
            <ColorPicker
              value={theme.primaryColor || '#7B68EE'}
              onChange={(value) => updateTheme('primaryColor', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#10B981">
            <FaFont />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Typography</h2>
            <p>Customize text appearance for better readability</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Font Size</h3>
            <p>Adjust the base text size across the application</p>
          </SettingInfo>
          <SettingControl>
            <Slider
              min="12"
              max="20"
              value={theme.fontSize || 16}
              onChange={(e) => updateTheme('fontSize', parseInt(e.target.value))}
            />
            <SliderValue>{theme.fontSize || 16}px</SliderValue>
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Font Family</h3>
            <p>Choose your preferred font style</p>
          </SettingInfo>
          <SettingControl>
            <Select
              value={theme.fontFamily || 'Inter'}
              onChange={(e) => updateTheme('fontFamily', e.target.value)}
            >
              <option value="Inter">Inter</option>
              <option value="'JetBrains Mono'">JetBrains Mono</option>
              <option value="Roboto">Roboto</option>
              <option value="system-ui">System Default</option>
              <option value="'Segoe UI'">Segoe UI</option>
            </Select>
          </SettingControl>
        </SettingItem>

        <FontPreview $font={theme.fontFamily || 'Inter'} $size={theme.fontSize || 16}>
          <p>The quick brown fox jumps over the lazy dog.</p>
          <span>Preview with current settings</span>
        </FontPreview>
      </Section>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#F59E0B">
            <FaMagic />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Visual Effects</h2>
            <p>Control animations and visual enhancements</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaMagic style={{ color: '#F59E0B', marginRight: 8 }} />
              Animations
            </h3>
            <p>Enable smooth transitions and micro-interactions</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={theme.animations !== false}
              onChange={(value) => updateTheme('animations', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaExpand style={{ color: '#3B82F6', marginRight: 8 }} />
              Compact Mode
            </h3>
            <p>Reduce spacing for a more dense layout</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={theme.compactMode || false}
              onChange={(value) => updateTheme('compactMode', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaAdjust style={{ color: '#EC4899', marginRight: 8 }} />
              High Contrast
            </h3>
            <p>Increase contrast for better accessibility</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={theme.highContrast || false}
              onChange={(value) => updateTheme('highContrast', value)}
            />
          </SettingControl>
        </SettingItem>

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>Accessibility Tip:</strong> Enabling High Contrast mode and disabling 
            animations can help users with visual impairments or motion sensitivity.
          </InfoText>
        </InfoBox>
      </Section>
    </>
  );
};

export default ThemeSettings;

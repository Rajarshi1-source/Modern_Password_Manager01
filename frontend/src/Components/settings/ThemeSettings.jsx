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
  ColorPicker,
  Slider,
  Alert
} from './SettingsComponents';

const ThemeSettings = () => {
  const [theme, setTheme] = useState({});
  const [saved, setSaved] = useState(false);

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
      {saved && <Alert type="success">Theme settings saved successfully!</Alert>}
      
      <Section>
        <SectionHeader>
          <h2>Appearance</h2>
          <p>Customize the look and feel of your password manager</p>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Theme Mode</h3>
            <p>Choose your preferred color scheme</p>
          </SettingInfo>
          <SettingControl>
            <Select
              value={theme.mode || 'auto'}
              onChange={(e) => updateTheme('mode', e.target.value)}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="auto">Auto (System)</option>
            </Select>
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Primary Color</h3>
            <p>Choose your accent color</p>
          </SettingInfo>
          <SettingControl>
            <ColorPicker
              value={theme.primaryColor || '#4A6CF7'}
              onChange={(value) => updateTheme('primaryColor', value)}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Font Size</h3>
            <p>Adjust text size for better readability ({theme.fontSize || 16}px)</p>
          </SettingInfo>
          <SettingControl>
            <Slider
              min="12"
              max="20"
              value={theme.fontSize || 16}
              onChange={(e) => updateTheme('fontSize', parseInt(e.target.value))}
            />
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Font Family</h3>
            <p>Choose your preferred font</p>
          </SettingInfo>
          <SettingControl>
            <Select
              value={theme.fontFamily || 'Inter'}
              onChange={(e) => updateTheme('fontFamily', e.target.value)}
            >
              <option value="Inter">Inter</option>
              <option value="Roboto">Roboto</option>
              <option value="system-ui">System Default</option>
              <option value="'Segoe UI'">Segoe UI</option>
              <option value="Arial">Arial</option>
            </Select>
          </SettingControl>
        </SettingItem>

        <SettingItem>
          <SettingInfo>
            <h3>Compact Mode</h3>
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
            <h3>Animations</h3>
            <p>Enable smooth transitions and animations</p>
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
            <h3>High Contrast</h3>
            <p>Increase contrast for better visibility</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={theme.highContrast || false}
              onChange={(value) => updateTheme('highContrast', value)}
            />
          </SettingControl>
        </SettingItem>
      </Section>
    </>
  );
};

export default ThemeSettings;


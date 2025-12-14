import React from 'react';
import styled, { keyframes } from 'styled-components';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const shimmer = keyframes`
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
`;

// Color Constants - Purple and Black Theme
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  accent: '#A78BFA',
  background: '#0f0f1a',
  backgroundSecondary: '#1a1a2e',
  backgroundTertiary: '#252542',
  cardBg: '#1e1e35',
  cardBgHover: '#262649',
  text: '#ffffff',
  textSecondary: '#a0a0b8',
  textMuted: '#6b6b8a',
  border: '#2d2d4a',
  borderLight: '#3d3d5a',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6'
};

// Full Page Wrapper - covers entire viewport
export const SettingsPageWrapper = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: ${colors.background};
  overflow-y: auto;
  overflow-x: hidden;
`;

// Main Container
export const SettingsContainer = styled.div`
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
  min-height: 100vh;
  background: linear-gradient(180deg, ${colors.background} 0%, ${colors.backgroundSecondary} 100%);
  animation: ${fadeIn} 0.4s ease-out;
`;

// Header Section
export const SettingsHeader = styled.div`
  margin-bottom: 40px;
  text-align: center;
  
  h1 {
    font-size: 36px;
    font-weight: 800;
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.accent} 50%, ${colors.primaryLight} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 12px 0;
    letter-spacing: -0.5px;
  }
  
  p {
    font-size: 16px;
    color: ${colors.textSecondary};
    margin: 0;
    font-weight: 400;
  }
`;

// Tab Container - Pill Style
export const TabContainer = styled.div`
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-bottom: 40px;
  background: ${colors.backgroundTertiary};
  padding: 6px;
  border-radius: 16px;
  flex-wrap: wrap;
`;

// Tab Button
export const Tab = styled.button`
  background: ${props => props.active 
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
    : 'transparent'};
  border: none;
  padding: 14px 24px;
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.active ? '#fff' : colors.textSecondary};
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: ${props => props.active ? `0 4px 20px ${colors.primary}50` : 'none'};
  
  &:hover {
    background: ${props => props.active 
      ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
      : colors.cardBg};
    color: ${props => props.active ? '#fff' : colors.text};
    transform: translateY(-1px);
  }
`;

// Section Container
export const Section = styled.div`
  background: ${colors.cardBg};
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 24px;
  border: 1px solid ${colors.border};
  animation: ${fadeIn} 0.3s ease-out;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: ${colors.borderLight};
    box-shadow: 0 8px 32px rgba(123, 104, 238, 0.1);
  }
  
  &:last-child {
    margin-bottom: 0;
  }
`;

// Section Header
export const SectionHeader = styled.div`
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${colors.border};
  display: flex;
  align-items: center;
  gap: 14px;
  
  h2 {
    font-size: 20px;
    font-weight: 700;
    color: ${colors.text};
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    
    svg {
      color: ${colors.primary};
      font-size: 22px;
    }
  }
  
  p {
    font-size: 14px;
    color: ${colors.textSecondary};
    margin: 4px 0 0 0;
    line-height: 1.5;
  }
`;

export const SectionHeaderContent = styled.div`
  flex: 1;
`;

export const SectionIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${props => props.$color || colors.primary}20 0%, ${props => props.$color || colors.primary}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 24px;
    color: ${props => props.$color || colors.primary};
  }
`;

// Setting Item
export const SettingItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: ${colors.backgroundSecondary};
  border-radius: 14px;
  margin-bottom: 12px;
  border: 1px solid transparent;
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index ? `${props.$index * 0.05}s` : '0s'};
  animation-fill-mode: backwards;
  
  &:hover {
    background: ${colors.cardBgHover};
    border-color: ${colors.border};
    transform: translateX(4px);
  }
  
  &:last-child {
    margin-bottom: 0;
  }
`;

// Setting Info
export const SettingInfo = styled.div`
  flex: 1;
  margin-right: 24px;
  
  h3 {
    font-size: 15px;
    font-weight: 600;
    color: ${colors.text};
    margin: 0 0 6px 0;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  p {
    font-size: 13px;
    color: ${colors.textSecondary};
    margin: 0;
    line-height: 1.5;
  }
`;

// Setting Control Container
export const SettingControl = styled.div`
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
`;

// Toggle Switch Component
export const ToggleSwitch = ({ checked, onChange, disabled = false }) => {
  return (
    <ToggleContainer onClick={() => !disabled && onChange(!checked)} disabled={disabled}>
      <ToggleTrack $checked={checked} $disabled={disabled}>
        <ToggleThumb $checked={checked} />
      </ToggleTrack>
    </ToggleContainer>
  );
};

const ToggleContainer = styled.div`
  cursor: ${props => props.disabled ? 'not-allowed' : 'pointer'};
  opacity: ${props => props.disabled ? 0.5 : 1};
`;

const ToggleTrack = styled.div`
  width: 52px;
  height: 28px;
  background: ${props => props.$checked 
    ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`
    : colors.backgroundTertiary};
  border: 2px solid ${props => props.$checked ? 'transparent' : colors.border};
  border-radius: 14px;
  position: relative;
  transition: all 0.3s ease;
  box-shadow: ${props => props.$checked ? `0 4px 12px ${colors.primary}40` : 'none'};
`;

const ToggleThumb = styled.div`
  width: 20px;
  height: 20px;
  background: ${props => props.$checked ? '#fff' : colors.textMuted};
  border-radius: 10px;
  position: absolute;
  top: 2px;
  left: ${props => props.$checked ? '26px' : '2px'};
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
`;

// Select Component
export const Select = styled.select`
  padding: 12px 16px;
  border: 2px solid ${colors.border};
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: ${colors.text};
  background: ${colors.backgroundTertiary};
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 160px;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%237B68EE' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
  
  &:focus {
    outline: none;
    border-color: ${colors.primary};
    box-shadow: 0 0 0 3px ${colors.primary}30;
  }
  
  &:hover {
    border-color: ${colors.borderLight};
  }
  
  option {
    background: ${colors.backgroundSecondary};
    color: ${colors.text};
    padding: 10px;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Input Component
export const Input = styled.input`
  padding: 12px 16px;
  border: 2px solid ${colors.border};
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: ${colors.text};
  background: ${colors.backgroundTertiary};
  transition: all 0.2s ease;
  min-width: 120px;
  
  &:focus {
    outline: none;
    border-color: ${colors.primary};
    box-shadow: 0 0 0 3px ${colors.primary}30;
  }
  
  &:hover {
    border-color: ${colors.borderLight};
  }
  
  &::placeholder {
    color: ${colors.textMuted};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Button Component
export const Button = styled.button`
  padding: 12px 24px;
  background: ${props => {
    if (props.variant === 'primary') return `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`;
    if (props.variant === 'danger') return `linear-gradient(135deg, ${colors.danger} 0%, #dc2626 100%)`;
    return colors.backgroundTertiary;
  }};
  color: ${props => props.variant ? '#fff' : colors.textSecondary};
  border: ${props => props.variant ? 'none' : `2px solid ${colors.border}`};
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: ${props => props.variant === 'primary' ? `0 4px 14px ${colors.primary}40` : 'none'};
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: ${props => {
      if (props.variant === 'primary') return `0 6px 20px ${colors.primary}50`;
      if (props.variant === 'danger') return `0 6px 20px ${colors.danger}40`;
      return `0 4px 12px rgba(0,0,0,0.2)`;
    }};
    background: ${props => {
      if (props.variant === 'primary') return `linear-gradient(135deg, ${colors.primaryDark} 0%, ${colors.primary} 100%)`;
      if (props.variant === 'danger') return `linear-gradient(135deg, #dc2626 0%, ${colors.danger} 100%)`;
      return colors.cardBgHover;
    }};
    color: ${props => props.variant ? '#fff' : colors.text};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
`;

// Color Picker Component
export const ColorPicker = ({ value, onChange, disabled = false }) => {
  return (
    <ColorPickerContainer>
      <ColorInput
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
      <ColorValue>{value}</ColorValue>
    </ColorPickerContainer>
  );
};

const ColorPickerContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  background: ${colors.backgroundTertiary};
  padding: 8px 12px;
  border-radius: 10px;
  border: 2px solid ${colors.border};
`;

const ColorInput = styled.input`
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background: none;
  
  &::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  
  &::-webkit-color-swatch {
    border: 2px solid ${colors.borderLight};
    border-radius: 6px;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ColorValue = styled.span`
  font-size: 13px;
  color: ${colors.textSecondary};
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
`;

// Slider Component
export const Slider = styled.input.attrs({ type: 'range' })`
  width: 200px;
  height: 6px;
  border-radius: 3px;
  background: ${colors.backgroundTertiary};
  outline: none;
  appearance: none;
  
  &::-webkit-slider-track {
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(to right, ${colors.primary} 0%, ${colors.primary} ${props => ((props.value - props.min) / (props.max - props.min)) * 100}%, ${colors.backgroundTertiary} ${props => ((props.value - props.min) / (props.max - props.min)) * 100}%, ${colors.backgroundTertiary} 100%);
  }
  
  &::-webkit-slider-thumb {
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
    cursor: pointer;
    border: 3px solid ${colors.cardBg};
    box-shadow: 0 2px 8px ${colors.primary}40;
    transition: transform 0.2s ease;
    
    &:hover {
      transform: scale(1.1);
    }
  }
  
  &::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
    cursor: pointer;
    border: 3px solid ${colors.cardBg};
    box-shadow: 0 2px 8px ${colors.primary}40;
  }
`;

// Time Picker Component
export const TimePicker = styled.input.attrs({ type: 'time' })`
  padding: 12px 16px;
  border: 2px solid ${colors.border};
  border-radius: 10px;
  font-size: 14px;
  color: ${colors.text};
  background: ${colors.backgroundTertiary};
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: ${colors.primary};
    box-shadow: 0 0 0 3px ${colors.primary}30;
  }
  
  &::-webkit-calendar-picker-indicator {
    filter: invert(1);
  }
`;

// Alert Component
export const Alert = styled.div`
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  animation: ${fadeIn} 0.3s ease-out;
  
  ${props => {
    if (props.type === 'success') return `
      background: linear-gradient(135deg, ${colors.success}20 0%, ${colors.success}10 100%);
      color: ${colors.success};
      border: 1px solid ${colors.success}40;
    `;
    if (props.type === 'warning') return `
      background: linear-gradient(135deg, ${colors.warning}20 0%, ${colors.warning}10 100%);
      color: ${colors.warning};
      border: 1px solid ${colors.warning}40;
    `;
    if (props.type === 'error') return `
      background: linear-gradient(135deg, ${colors.danger}20 0%, ${colors.danger}10 100%);
      color: ${colors.danger};
      border: 1px solid ${colors.danger}40;
    `;
    return `
      background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primary}10 100%);
      color: ${colors.primaryLight};
      border: 1px solid ${colors.primary}40;
    `;
  }}
`;

// Action Buttons Container
export const ActionButtons = styled.div`
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 32px;
  padding-top: 32px;
  border-top: 1px solid ${colors.border};
  flex-wrap: wrap;
`;

// Badge Component
export const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  ${props => {
    if (props.$variant === 'success') return `
      background: linear-gradient(135deg, ${colors.success}30 0%, ${colors.success}20 100%);
      color: ${colors.success};
    `;
    if (props.$variant === 'warning') return `
      background: linear-gradient(135deg, ${colors.warning}30 0%, ${colors.warning}20 100%);
      color: ${colors.warning};
    `;
    if (props.$variant === 'danger') return `
      background: linear-gradient(135deg, ${colors.danger}30 0%, ${colors.danger}20 100%);
      color: ${colors.danger};
    `;
    if (props.$variant === 'new') return `
      background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.accent} 100%);
      color: #fff;
    `;
    return `
      background: ${colors.backgroundTertiary};
      color: ${colors.textSecondary};
    `;
  }}
`;

// Info Box
export const InfoBox = styled.div`
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primary}05 100%);
  border-left: 4px solid ${colors.primary};
  padding: 18px 20px;
  border-radius: 0 12px 12px 0;
  margin-top: 16px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  
  svg {
    color: ${colors.primary};
    font-size: 20px;
    flex-shrink: 0;
    margin-top: 2px;
  }
`;

export const InfoText = styled.div`
  font-size: 14px;
  color: ${colors.textSecondary};
  line-height: 1.6;
  
  strong {
    color: ${colors.text};
    font-weight: 600;
  }
`;

// Feature Card
export const FeatureCard = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundTertiary} 0%, ${colors.cardBg} 100%);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid ${colors.border};
  transition: all 0.3s ease;
  
  &:hover {
    border-color: ${colors.primary}50;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px ${colors.primary}15;
  }
`;

// Shortcut Key Display
export const ShortcutKey = styled.kbd`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  background: ${colors.backgroundTertiary};
  border: 1px solid ${colors.border};
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: ${colors.text};
  box-shadow: 0 2px 0 ${colors.border};
`;

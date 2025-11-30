import React from 'react';
import styled from 'styled-components';

// Styled Components
export const SettingsContainer = styled.div`
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
`;

export const SettingsHeader = styled.div`
  margin-bottom: 32px;
  
  h1 {
    font-size: 28px;
    font-weight: 700;
    color: ${props => props.theme?.textPrimary || '#1a1a1a'};
    margin: 0 0 8px 0;
  }
  
  p {
    font-size: 14px;
    color: ${props => props.theme?.textSecondary || '#666'};
    margin: 0;
  }
`;

export const TabContainer = styled.div`
  border-bottom: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
  margin-bottom: 32px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
`;

export const Tab = styled.button`
  background: none;
  border: none;
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 500;
  color: ${props => props.active ? props.theme?.primary || '#4A6CF7' : props.theme?.textSecondary || '#666'};
  border-bottom: 3px solid ${props => props.active ? props.theme?.primary || '#4A6CF7' : 'transparent'};
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  
  &:hover {
    color: ${props => props.theme?.primary || '#4A6CF7'};
  }
`;

export const Section = styled.div`
  margin-bottom: 32px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

export const SectionHeader = styled.div`
  margin-bottom: 16px;
  
  h2 {
    font-size: 18px;
    font-weight: 600;
    color: ${props => props.theme?.textPrimary || '#1a1a1a'};
    margin: 0 0 4px 0;
  }
  
  p {
    font-size: 13px;
    color: ${props => props.theme?.textSecondary || '#666'};
    margin: 0;
  }
`;

export const SettingItem = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px;
  background: ${props => props.theme?.backgroundSecondary || '#f9f9f9'};
  border-radius: 8px;
  margin-bottom: 12px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

export const SettingInfo = styled.div`
  flex: 1;
  margin-right: 16px;
  
  h3 {
    font-size: 15px;
    font-weight: 600;
    color: ${props => props.theme?.textPrimary || '#1a1a1a'};
    margin: 0 0 4px 0;
  }
  
  p {
    font-size: 13px;
    color: ${props => props.theme?.textSecondary || '#666'};
    margin: 0;
    line-height: 1.5;
  }
`;

export const SettingControl = styled.div`
  flex-shrink: 0;
`;

// Toggle Switch Component
export const ToggleSwitch = ({ checked, onChange, disabled = false }) => {
  return (
    <ToggleContainer onClick={() => !disabled && onChange(!checked)} disabled={disabled}>
      <ToggleTrack checked={checked} disabled={disabled}>
        <ToggleThumb checked={checked} />
      </ToggleTrack>
    </ToggleContainer>
  );
};

const ToggleContainer = styled.div`
  cursor: ${props => props.disabled ? 'not-allowed' : 'pointer'};
  opacity: ${props => props.disabled ? 0.5 : 1};
`;

const ToggleTrack = styled.div`
  width: 48px;
  height: 26px;
  background: ${props => props.checked ? props.theme?.primary || '#4A6CF7' : '#ccc'};
  border-radius: 13px;
  position: relative;
  transition: background 0.3s;
`;

const ToggleThumb = styled.div`
  width: 22px;
  height: 22px;
  background: white;
  border-radius: 11px;
  position: absolute;
  top: 2px;
  left: ${props => props.checked ? '24px' : '2px'};
  transition: left 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
`;

// Select Component
export const Select = styled.select`
  padding: 8px 12px;
  border: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
  border-radius: 6px;
  font-size: 14px;
  color: ${props => props.theme?.textPrimary || '#1a1a1a'};
  background: white;
  cursor: pointer;
  transition: border-color 0.2s;
  min-width: 120px;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme?.primary || '#4A6CF7'};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Input Component
export const Input = styled.input`
  padding: 8px 12px;
  border: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
  border-radius: 6px;
  font-size: 14px;
  color: ${props => props.theme?.textPrimary || '#1a1a1a'};
  background: white;
  transition: border-color 0.2s;
  min-width: 120px;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme?.primary || '#4A6CF7'};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Button Component
export const Button = styled.button`
  padding: 10px 20px;
  background: ${props => props.variant === 'primary' ? props.theme?.primary || '#4A6CF7' : 'transparent'};
  color: ${props => props.variant === 'primary' ? 'white' : props.theme?.primary || '#4A6CF7'};
  border: 2px solid ${props => props.theme?.primary || '#4A6CF7'};
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => props.variant === 'primary' ? props.theme?.primaryDark || '#3A5CE7' : props.theme?.primaryLight || '#EEF2FF'};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
  gap: 8px;
`;

const ColorInput = styled.input`
  width: 48px;
  height: 32px;
  border: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
  border-radius: 6px;
  cursor: pointer;
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ColorValue = styled.span`
  font-size: 13px;
  color: ${props => props.theme?.textSecondary || '#666'};
  font-family: monospace;
`;

// Slider Component
export const Slider = styled.input.attrs({ type: 'range' })`
  width: 200px;
  height: 6px;
  border-radius: 3px;
  background: ${props => props.theme?.borderColor || '#e0e0e0'};
  outline: none;
  
  &::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: ${props => props.theme?.primary || '#4A6CF7'};
    cursor: pointer;
  }
  
  &::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: ${props => props.theme?.primary || '#4A6CF7'};
    cursor: pointer;
    border: none;
  }
`;

// Time Picker Component
export const TimePicker = styled.input.attrs({ type: 'time' })`
  padding: 8px 12px;
  border: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
  border-radius: 6px;
  font-size: 14px;
  color: ${props => props.theme?.textPrimary || '#1a1a1a'};
  background: white;
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme?.primary || '#4A6CF7'};
  }
`;

// Alert Component
export const Alert = styled.div`
  padding: 12px 16px;
  background: ${props => {
    if (props.type === 'success') return '#d4edda';
    if (props.type === 'warning') return '#fff3cd';
    if (props.type === 'error') return '#f8d7da';
    return '#d1ecf1';
  }};
  color: ${props => {
    if (props.type === 'success') return '#155724';
    if (props.type === 'warning') return '#856404';
    if (props.type === 'error') return '#721c24';
    return '#0c5460';
  }};
  border: 1px solid ${props => {
    if (props.type === 'success') return '#c3e6cb';
    if (props.type === 'warning') return '#ffeeba';
    if (props.type === 'error') return '#f5c6cb';
    return '#bee5eb';
  }};
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 14px;
  line-height: 1.5;
`;

// Action Buttons Container
export const ActionButtons = styled.div`
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 2px solid ${props => props.theme?.borderColor || '#e0e0e0'};
`;


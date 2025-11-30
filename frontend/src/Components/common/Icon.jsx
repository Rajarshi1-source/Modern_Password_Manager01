import React from 'react';
import styled from 'styled-components';
import * as FaIcons from 'react-icons/fa';
import * as IoIcons from 'react-icons/io5';
import * as MdIcons from 'react-icons/md';

const IconWrapper = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  
  ${({ size }) => {
    switch (size) {
      case 'tiny':
        return 'font-size: 12px;';
      case 'small':
        return 'font-size: 16px;';
      case 'large':
        return 'font-size: 24px;';
      case 'xl':
        return 'font-size: 32px;';
      default:
        return 'font-size: 20px;';
    }
  }}
  
  color: ${({ color, theme }) => {
    if (color === 'primary') return theme.primary;
    if (color === 'secondary') return theme.textSecondary;
    if (color === 'danger') return theme.danger;
    if (color === 'success') return theme.success;
    if (color === 'warning') return theme.warning;
    return color || 'inherit';
  }};
  
  ${({ clickable }) => clickable && `
    cursor: pointer;
    &:hover {
      opacity: 0.8;
    }
  `}
`;

/**
 * Icon component supporting multiple icon libraries
 * @param {Object} props - Component props
 * @param {string} props.name - Icon name (e.g., 'FaLock', 'IoAlertCircle')
 * @param {string} [props.size='medium'] - Icon size (tiny, small, medium, large, xl)
 * @param {string} [props.color] - Icon color (CSS color or theme key: primary, secondary, danger, etc.)
 * @param {Function} [props.onClick] - Click handler
 * @param {string} [props.title] - Title/tooltip for the icon
 * @param {boolean} [props.spin=false] - Whether the icon should spin
 */
const Icon = ({ 
  name, 
  size = 'medium', 
  color,
  onClick,
  title,
  spin = false,
  ...rest
}) => {
  let IconComponent;
  
  // Determine icon library and component based on name prefix
  if (name.startsWith('Fa')) {
    IconComponent = FaIcons[name];
  } else if (name.startsWith('Io')) {
    IconComponent = IoIcons[name];
  } else if (name.startsWith('Md')) {
    IconComponent = MdIcons[name];
  }
  
  if (!IconComponent) {
    console.warn(`Icon "${name}" not found`);
    return null;
  }
  
  return (
    <IconWrapper 
      size={size} 
      color={color} 
      onClick={onClick}
      clickable={!!onClick}
      title={title}
      {...rest}
    >
      <IconComponent style={spin ? { animation: 'spin 2s linear infinite' } : undefined} />
    </IconWrapper>
  );
};

export default Icon;

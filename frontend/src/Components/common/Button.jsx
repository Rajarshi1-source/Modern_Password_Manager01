import React, { forwardRef } from 'react';
import styled, { css } from 'styled-components';
import { useAccessibility } from '../../contexts/AccessibilityContext';

// Base button styles
const BaseButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  padding: ${props => props.size === 'large' ? '12px 20px' : 
               props.size === 'small' ? '6px 12px' : '8px 16px'};
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
  position: relative;
  overflow: hidden;
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  ${props => props.fullWidth && css`
    width: 100%;
  `}
`;

// Primary button style
const PrimaryButton = styled(BaseButton)`
  background: ${props => props.theme.primary};
  color: white;
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.primaryDark};
  }
  
  &:active:not(:disabled) {
    transform: scale(0.98);
  }
  
  &:focus-visible {
    box-shadow: 0 0 0 3px ${props => props.theme.primaryLight};
  }
`;

// Secondary button style
const SecondaryButton = styled(BaseButton)`
  background: transparent;
  color: ${props => props.theme.primary};
  border: 1px solid ${props => props.theme.primary};
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.primaryLight};
  }
  
  &:active:not(:disabled) {
    transform: scale(0.98);
  }
`;

// Danger button style
const DangerButton = styled(BaseButton)`
  background: ${props => props.theme.error};
  color: white;
  border: none;
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.errorDark};
  }
  
  &:active:not(:disabled) {
    transform: scale(0.98);
  }
  
  &:focus-visible {
    box-shadow: 0 0 0 3px ${props => props.theme.errorLight};
  }
`;

// Text button style
const TextButton = styled(BaseButton)`
  background: transparent;
  color: ${props => props.theme.primary};
  padding: ${props => props.size === 'large' ? '8px 16px' : 
               props.size === 'small' ? '4px 8px' : '6px 12px'};
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.backgroundHover};
  }
`;

/**
 * Button component with multiple variants
 * @param {Object} props - Component props
 * @param {string} [props.variant='primary'] - Button variant (primary, secondary, danger, text)
 * @param {string} [props.size='medium'] - Button size (small, medium, large)
 * @param {boolean} [props.fullWidth=false] - Whether button should take full width
 * @param {React.ReactNode} [props.children] - Button content
 * @param {React.ReactNode} [props.leftIcon] - Icon to display before text
 * @param {React.ReactNode} [props.rightIcon] - Icon to display after text
 * @param {string} [props.type='button'] - Button type attribute
 * @param {boolean} [props.disabled=false] - Whether button is disabled
 * @param {Function} [props.onClick] - Click handler
 */
const Button = forwardRef(({
  variant = 'primary',
  size = 'medium',
  fullWidth = false,
  children,
  leftIcon,
  rightIcon,
  type = 'button',
  disabled = false,
  onClick,
  ...props
}, ref) => {
  const { setFocusedElementId } = useAccessibility();
  
  const handleClick = (e) => {
    // Create ripple effect
    const button = e.currentTarget;
    const ripple = document.createElement('span');
    const rect = button.getBoundingClientRect();
    
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    ripple.className = 'ripple';
    
    button.appendChild(ripple);
    
    setTimeout(() => {
      ripple.remove();
    }, 600);
    
    if (onClick) onClick(e);
  };
  
  const handleFocus = () => {
    if (props.id) {
      setFocusedElementId(props.id);
    }
  };
  
  // Select button component based on variant
  const ButtonComponent = {
    primary: PrimaryButton,
    secondary: SecondaryButton,
    danger: DangerButton,
    text: TextButton
  }[variant] || PrimaryButton;
  
  return (
    <ButtonComponent
      ref={ref}
      type={type}
      size={size}
      fullWidth={fullWidth}
      disabled={disabled}
      onClick={handleClick}
      onFocus={handleFocus}
      aria-disabled={disabled}
      {...props}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </ButtonComponent>
  );
});

export default Button;

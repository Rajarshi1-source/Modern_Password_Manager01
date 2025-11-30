import React, { useState, useRef, useEffect } from 'react';
import styled, { keyframes, css } from 'styled-components';

const fadeIn = keyframes`
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
`;

const TooltipContainer = styled.div`
  position: relative;
  display: inline-flex;
  vertical-align: middle;
`;

const TooltipContent = styled.div`
  position: absolute;
  z-index: 1000;
  background-color: ${props => props.theme.tooltipBg || props.theme.textPrimary || '#333'};
  color: ${props => props.theme.tooltipText || 'white'};
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
  pointer-events: none;
  animation: ${fadeIn} 0.2s ease-out;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  max-width: ${props => props.maxWidth || '200px'};
  
  ${props => props.multiline && css`
    white-space: normal;
    text-align: center;
  `}
  
  /* Positioning based on placement */
  ${props => {
    switch (props.placement) {
      case 'top':
        return css`
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%) translateY(-6px);
          
          &::after {
            content: '';
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: ${props.theme.tooltipBg || props.theme.textPrimary || '#333'} transparent transparent transparent;
          }
        `;
      case 'bottom':
        return css`
          top: 100%;
          left: 50%;
          transform: translateX(-50%) translateY(6px);
          
          &::after {
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: transparent transparent ${props.theme.tooltipBg || props.theme.textPrimary || '#333'} transparent;
          }
        `;
      case 'left':
        return css`
          right: 100%;
          top: 50%;
          transform: translateY(-50%) translateX(-6px);
          
          &::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 100%;
            margin-top: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: transparent transparent transparent ${props.theme.tooltipBg || props.theme.textPrimary || '#333'};
          }
        `;
      case 'right':
        return css`
          left: 100%;
          top: 50%;
          transform: translateY(-50%) translateX(6px);
          
          &::after {
            content: '';
            position: absolute;
            top: 50%;
            right: 100%;
            margin-top: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: transparent ${props.theme.tooltipBg || props.theme.textPrimary || '#333'} transparent transparent;
          }
        `;
      default:
        return '';
    }
  }}
`;

/**
 * Tooltip component for displaying additional information
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Element that triggers the tooltip
 * @param {string} props.content - Content to display in the tooltip
 * @param {string} [props.placement='top'] - Tooltip placement (top, bottom, left, right)
 * @param {number} [props.showDelay=200] - Delay before showing tooltip (ms)
 * @param {number} [props.hideDelay=100] - Delay before hiding tooltip (ms)
 * @param {boolean} [props.multiline=false] - Whether tooltip should support multiline text
 * @param {string} [props.maxWidth='200px'] - Maximum tooltip width
 * @param {boolean} [props.visible] - Control tooltip visibility (makes tooltip controlled)
 * @param {Function} [props.onVisibilityChange] - Called when tooltip visibility changes
 */
const Tooltip = ({
  children,
  content,
  placement = 'top',
  showDelay = 200,
  hideDelay = 100,
  multiline = false,
  maxWidth,
  visible: controlledVisible,
  onVisibilityChange,
  ...rest
}) => {
  const [internalVisible, setInternalVisible] = useState(false);
  const showTimeoutRef = useRef(null);
  const hideTimeoutRef = useRef(null);
  
  // Determine if component is controlled or uncontrolled
  const isControlled = controlledVisible !== undefined;
  const visible = isControlled ? controlledVisible : internalVisible;
  
  // Clear timeouts on unmount
  useEffect(() => {
    return () => {
      if (showTimeoutRef.current) clearTimeout(showTimeoutRef.current);
      if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current);
    };
  }, []);
  
  const handleVisibility = (isVisible) => {
    // Clear any existing timeouts
    if (showTimeoutRef.current) clearTimeout(showTimeoutRef.current);
    if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current);
    
    if (isControlled) {
      // If controlled, call callback
      if (onVisibilityChange) onVisibilityChange(isVisible);
    } else {
      // If uncontrolled, manage internal state with delay
      if (isVisible) {
        showTimeoutRef.current = setTimeout(() => {
          setInternalVisible(true);
        }, showDelay);
      } else {
        hideTimeoutRef.current = setTimeout(() => {
          setInternalVisible(false);
        }, hideDelay);
      }
    }
  };
  
  return (
    <TooltipContainer
      onMouseEnter={() => handleVisibility(true)}
      onMouseLeave={() => handleVisibility(false)}
      onFocus={() => handleVisibility(true)}
      onBlur={() => handleVisibility(false)}
      {...rest}
    >
      {children}
      {visible && content && (
        <TooltipContent
          placement={placement}
          multiline={multiline}
          maxWidth={maxWidth}
          role="tooltip"
          aria-live="polite"
        >
          {content}
        </TooltipContent>
      )}
    </TooltipContainer>
  );
};

export default Tooltip;

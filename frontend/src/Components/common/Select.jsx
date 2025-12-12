import React, { useState } from 'react';
import styled, { css } from 'styled-components';
import { FaChevronDown } from 'react-icons/fa';

const SelectContainer = styled.div`
  display: flex;
  flex-direction: column;
  width: 100%;
  margin-bottom: ${props => props.marginBottom || '16px'};
`;

const SelectLabel = styled.label`
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
  color: ${props => props.theme.textPrimary};
  
  ${props => props.required && css`
    &::after {
      content: '*';
      color: ${props => props.theme.danger};
      margin-left: 4px;
    }
  `}
`;

const SelectWrapper = styled.div`
  position: relative;
  display: flex;
  width: 100%;
`;

const StyledSelect = styled.select`
  width: 100%;
  padding: 10px 36px 10px 12px;
  font-size: 14px;
  border: 1px solid ${props => 
    props.error 
      ? props.theme.danger 
      : props.focused 
        ? props.theme.primary 
        : props.theme.borderColor || '#ddd'};
  border-radius: 6px;
  background-color: ${props => props.theme.inputBg || props.theme.backgroundSecondary || '#fff'};
  color: ${props => props.theme.textPrimary};
  transition: all 0.2s ease;
  cursor: pointer;
  appearance: none;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.primary};
    box-shadow: 0 0 0 2px ${props => props.theme.primaryLight || props.theme.primary + '33'};
  }
  
  &:disabled {
    background-color: ${props => props.theme.disabledBg || '#f5f5f5'};
    cursor: not-allowed;
    opacity: 0.7;
  }
`;

const IconWrapper = styled.div`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: ${props => props.theme.textSecondary};
  display: flex;
  align-items: center;
  pointer-events: none;
`;

const ErrorMessage = styled.div`
  color: ${props => props.theme.danger};
  font-size: 12px;
  margin-top: 4px;
`;

const HelperText = styled.div`
  color: ${props => props.theme.textSecondary};
  font-size: 12px;
  margin-top: 4px;
`;

/**
 * Select dropdown component
 * @param {Object} props - Component props
 * @param {string} props.id - Select ID
 * @param {string} props.name - Select name
 * @param {string} [props.label] - Select label
 * @param {string} [props.value] - Selected value
 * @param {Function} [props.onChange] - Change handler
 * @param {Function} [props.onBlur] - Blur handler
 * @param {Function} [props.onFocus] - Focus handler
 * @param {boolean} [props.required=false] - Whether select is required
 * @param {boolean} [props.disabled=false] - Whether select is disabled
 * @param {boolean} [props.error=false] - Whether select has an error
 * @param {string} [props.errorMessage] - Error message to display
 * @param {string} [props.helperText] - Helper text to display
 * @param {string} [props.placeholder] - Placeholder text for empty option
 * @param {Array} [props.options] - Array of options: [{value, label}]
 * @param {string} [props.marginBottom] - Bottom margin (CSS value)
 */
const Select = ({
  id,
  name,
  label,
  value,
  onChange,
  onBlur,
  onFocus,
  required = false,
  disabled = false,
  error = false,
  errorMessage,
  helperText,
  placeholder,
  options = [],
  marginBottom,
  children,
  ...rest
}) => {
  const [focused, setFocused] = useState(false);
  
  const handleFocus = (e) => {
    setFocused(true);
    if (onFocus) onFocus(e);
  };
  
  const handleBlur = (e) => {
    setFocused(false);
    if (onBlur) onBlur(e);
  };
  
  return (
    <SelectContainer marginBottom={marginBottom} {...rest}>
      {label && (
        <SelectLabel htmlFor={id} required={required}>
          {label}
        </SelectLabel>
      )}
      
      <SelectWrapper>
        <StyledSelect
          id={id}
          name={name}
          value={value}
          onChange={onChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          required={required}
          disabled={disabled}
          error={error}
          focused={focused}
          aria-invalid={error ? 'true' : 'false'}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
          {children}
        </StyledSelect>
        
        <IconWrapper>
          <FaChevronDown size={12} />
        </IconWrapper>
      </SelectWrapper>
      
      {error && errorMessage && <ErrorMessage>{errorMessage}</ErrorMessage>}
      {helperText && !error && <HelperText>{helperText}</HelperText>}
    </SelectContainer>
  );
};

export default Select;


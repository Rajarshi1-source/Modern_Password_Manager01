import React, { useState } from 'react';
import styled, { css } from 'styled-components';
import { FaEye, FaEyeSlash } from 'react-icons/fa';

const InputContainer = styled.div`
  display: flex;
  flex-direction: column;
  width: 100%;
  margin-bottom: ${props => props.marginBottom || '16px'};
`;

const InputLabel = styled.label`
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

const InputWrapper = styled.div`
  position: relative;
  display: flex;
  width: 100%;
`;

const inputStyles = css`
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid ${props => 
    props.error 
      ? props.theme.danger 
      : props.focused 
        ? props.theme.primary 
        : props.theme.borderColor};
  border-radius: 6px;
  background-color: ${props => props.theme.inputBg || props.theme.backgroundSecondary || '#fff'};
  color: ${props => props.theme.textPrimary};
  transition: all 0.2s ease;
  
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
  
  ${props => props.leftIcon && css`
    padding-left: 36px;
  `}
  
  ${props => props.rightIcon && css`
    padding-right: 36px;
  `}
`;

const StyledInput = styled.input`
  ${inputStyles}
`;

const StyledTextarea = styled.textarea`
  ${inputStyles}
  resize: vertical;
  min-height: ${props => props.rows ? `${props.rows * 24}px` : '80px'};
  font-family: inherit;
`;

const LeftIconWrapper = styled.div`
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: ${props => props.theme.textSecondary};
  display: flex;
  align-items: center;
`;

const RightIconWrapper = styled.div`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: ${props => props.theme.textSecondary};
  display: flex;
  align-items: center;
  cursor: ${props => props.clickable ? 'pointer' : 'default'};
  
  &:hover {
    color: ${props => props.clickable ? props.theme.textPrimary : props.theme.textSecondary};
  }
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
 * Input component for form fields
 * @param {Object} props - Component props
 * @param {string} props.id - Input ID
 * @param {string} props.name - Input name
 * @param {string} [props.type='text'] - Input type (text, password, email, etc.)
 * @param {string} [props.label] - Input label
 * @param {string} [props.placeholder] - Input placeholder
 * @param {string} [props.value] - Input value
 * @param {Function} [props.onChange] - Change handler
 * @param {Function} [props.onBlur] - Blur handler
 * @param {Function} [props.onFocus] - Focus handler
 * @param {boolean} [props.required=false] - Whether input is required
 * @param {boolean} [props.disabled=false] - Whether input is disabled
 * @param {boolean} [props.error=false] - Whether input has an error
 * @param {string} [props.errorMessage] - Error message to display
 * @param {string} [props.helperText] - Helper text to display
 * @param {React.ReactNode} [props.leftIcon] - Icon to display on the left
 * @param {React.ReactNode} [props.rightIcon] - Icon to display on the right
 * @param {string} [props.marginBottom] - Bottom margin (CSS value)
 * @param {Object} [props.inputProps] - Additional props for the input element
 */
const Input = ({
  id,
  name,
  type = 'text',
  label,
  placeholder,
  value,
  onChange,
  onBlur,
  onFocus,
  required = false,
  disabled = false,
  error = false,
  errorMessage,
  helperText,
  leftIcon,
  rightIcon,
  marginBottom,
  inputProps = {},
  ...rest
}) => {
  const [focused, setFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  const handleFocus = (e) => {
    setFocused(true);
    if (onFocus) onFocus(e);
  };
  
  const handleBlur = (e) => {
    setFocused(false);
    if (onBlur) onBlur(e);
  };
  
  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };
  
  // Determine actual input type (for password toggle)
  const actualType = type === 'password' && showPassword ? 'text' : type;
  
  // Password toggle icon
  const passwordToggleIcon = type === 'password' ? (
    <RightIconWrapper 
      clickable 
      onClick={togglePasswordVisibility}
      data-testid="password-toggle"
    >
      {showPassword ? <FaEyeSlash /> : <FaEye />}
    </RightIconWrapper>
  ) : null;

  // Determine if we should render a textarea
  const isTextarea = type === 'textarea';
  const InputComponent = isTextarea ? StyledTextarea : StyledInput;
  
  return (
    <InputContainer marginBottom={marginBottom} {...rest}>
      {label && (
        <InputLabel htmlFor={id} required={required}>
          {label}
        </InputLabel>
      )}
      
      <InputWrapper>
        {leftIcon && !isTextarea && (
          <LeftIconWrapper>
            {leftIcon}
          </LeftIconWrapper>
        )}
        
        <InputComponent
          id={id}
          name={name}
          type={isTextarea ? undefined : actualType}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          required={required}
          disabled={disabled}
          error={error}
          focused={focused}
          leftIcon={!isTextarea ? leftIcon : undefined}
          rightIcon={!isTextarea ? (rightIcon || type === 'password') : undefined}
          aria-invalid={error ? 'true' : 'false'}
          rows={inputProps.rows}
          {...inputProps}
        />
        
        {rightIcon && !isTextarea && (
          <RightIconWrapper clickable={!!inputProps.onRightIconClick}>
            {rightIcon}
          </RightIconWrapper>
        )}
        
        {type === 'password' && passwordToggleIcon}
      </InputWrapper>
      
      {error && errorMessage && <ErrorMessage>{errorMessage}</ErrorMessage>}
      {helperText && !error && <HelperText>{helperText}</HelperText>}
    </InputContainer>
  );
};

export default Input;

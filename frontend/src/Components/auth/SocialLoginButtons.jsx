import React from 'react';
import { FaGoogle, FaApple, FaGithub } from 'react-icons/fa';
import styled from 'styled-components';

const SocialButtonsContainer = styled.div`
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
`;

const SocialButton = styled.button`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--button-border-radius, 12px);
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--primary-light);
    border-color: var(--primary-light);
  }
  
  &:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }
  
  svg {
    font-size: 1.1rem;
  }
`;

const Divider = styled.div`
  display: flex;
  align-items: center;
  margin: 1.5rem 0;
  color: var(--text-light);
  font-size: 0.9rem;
  
  &::before,
  &::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border-color);
  }
  
  &::before {
    margin-right: 1rem;
  }
  
  &::after {
    margin-left: 1rem;
  }
`;

const SocialLoginButtons = ({ onGoogleLogin, onAppleLogin, onGithubLogin }) => {
  return (
    <>
      <Divider>or continue with</Divider>
      <SocialButtonsContainer>
        <SocialButton 
          onClick={onGoogleLogin} 
          aria-label="Continue with Google"
          type="button"
        >
          <FaGoogle /> Google
        </SocialButton>
        <SocialButton 
          onClick={onAppleLogin} 
          aria-label="Continue with Apple"
          type="button"
        >
          <FaApple /> Apple
        </SocialButton>
        <SocialButton 
          onClick={onGithubLogin} 
          aria-label="Continue with GitHub"
          type="button"
        >
          <FaGithub /> GitHub
        </SocialButton>
      </SocialButtonsContainer>
    </>
  );
};

export default SocialLoginButtons;

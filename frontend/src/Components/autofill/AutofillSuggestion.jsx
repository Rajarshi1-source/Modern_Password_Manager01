import React from 'react';
import styled from 'styled-components';
import { FaKey, FaExternalLinkAlt, FaLock, FaTimes } from 'react-icons/fa';

const Container = styled.div`
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 320px;
  overflow: hidden;
  z-index: 10000;
  animation: slideIn 0.3s ease-out;
  
  @keyframes slideIn {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const Header = styled.div`
  background: ${props => props.theme.primary};
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h3`
  margin: 0;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 16px;
  padding: 4px;
`;

const Content = styled.div`
  padding: 16px;
`;

const AccountList = styled.div`
  max-height: 200px;
  overflow-y: auto;
`;

const AccountItem = styled.div`
  padding: 12px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  
  &:hover {
    background: ${props => props.theme.bgHover};
  }
`;

const AccountIcon = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 4px;
  background: ${props => props.theme.primaryLight};
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${props => props.theme.primary};
`;

const AccountInfo = styled.div`
  flex: 1;
`;

const Username = styled.div`
  font-weight: 500;
  margin-bottom: 2px;
`;

const Domain = styled.div`
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
`;

const ActionButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  margin-top: 12px;
  width: 100%;
  font-weight: 500;
  cursor: pointer;
  
  &:hover {
    background: ${props => props.theme.primaryDark};
  }
`;

const Message = styled.p`
  text-align: center;
  color: ${props => props.theme.textSecondary};
  font-size: 14px;
  margin: 12px 0;
`;

const AutofillSuggestion = ({ 
  accounts = [], 
  currentUrl = '', 
  onAutofill, 
  onClose,
  onOpenVault 
}) => {
  // Extract domain name from URL for display
  const getDomain = (url) => {
    try {
      const urlObj = new URL(url);
      return urlObj.hostname;
    } catch (e) {
      return url;
    }
  };
  
  const handleAutofill = (account) => {
    if (onAutofill) {
      onAutofill(account);
    }
    
    // Send message to browser extension to perform autofill
    if (window.chrome && chrome.runtime) {
      chrome.runtime.sendMessage({
        action: 'autofill',
        data: {
          username: account.username,
          password: account.password,
          url: currentUrl
        }
      });
    }
    
    // Close the suggestion popup
    if (onClose) {
      onClose();
    }
  };
  
  const domain = getDomain(currentUrl);
  
  return (
    <Container>
      <Header>
        <Title>
          <FaKey /> Passwords found for {domain}
        </Title>
        <CloseButton onClick={onClose}>
          <FaTimes />
        </CloseButton>
      </Header>
      
      <Content>
        {accounts.length > 0 ? (
          <>
            <AccountList>
              {accounts.map((account, index) => (
                <AccountItem 
                  key={index} 
                  onClick={() => handleAutofill(account)}
                >
                  <AccountIcon>
                    <FaLock />
                  </AccountIcon>
                  <AccountInfo>
                    <Username>{account.username}</Username>
                    <Domain>{account.name || getDomain(account.url)}</Domain>
                  </AccountInfo>
                </AccountItem>
              ))}
            </AccountList>
            
            <Message>
              Click an account to autofill your credentials
            </Message>
          </>
        ) : (
          <Message>
            No saved accounts found for this website.
          </Message>
        )}
        
        <ActionButton onClick={onOpenVault}>
          <FaExternalLinkAlt style={{ marginRight: '8px' }} /> 
          Open Password Manager
        </ActionButton>
      </Content>
    </Container>
  );
};

export default AutofillSuggestion;

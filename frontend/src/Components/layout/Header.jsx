import React, { useState } from 'react';
import styled from 'styled-components';
import { Link, useLocation } from 'react-router-dom';
import { FaLock, FaSearch, FaUser, FaBell, FaCog, FaSignOutAlt } from 'react-icons/fa';
import Button from '../common/Button';
import Tooltip from '../common/Tooltip';

const HeaderContainer = styled.header`
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: ${props => props.theme.primaryDark};
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const Logo = styled(Link)`
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: 700;
  color: white;
  text-decoration: none;
  
  svg {
    margin-right: 10px;
  }
`;

const SearchBar = styled.div`
  position: relative;
  width: 300px;
  
  @media (max-width: 768px) {
    display: none;
  }
`;

const SearchInput = styled.input`
  width: 100%;
  height: 36px;
  padding: 0 16px 0 36px;
  border-radius: 18px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: white;
  
  &::placeholder {
    color: rgba(255, 255, 255, 0.6);
  }
  
  &:focus {
    outline: none;
    background: rgba(255, 255, 255, 0.15);
  }
`;

const SearchIcon = styled.div`
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.6);
`;

const RightSection = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

const IconButton = styled.button`
  background: none;
  border: none;
  color: white;
  font-size: 16px;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  
  &:hover {
    background: rgba(255, 255, 255, 0.1);
  }
`;

const UserDropdown = styled.div`
  position: relative;
`;

const UserButton = styled.button`
  display: flex;
  align-items: center;
  background: none;
  border: none;
  color: white;
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 4px;
  
  &:hover {
    background: rgba(255, 255, 255, 0.1);
  }
  
  svg {
    margin-right: 8px;
  }
`;

const DropdownMenu = styled.div`
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: ${props => props.theme.background};
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 200px;
  z-index: 100;
  overflow: hidden;
  display: ${props => props.isOpen ? 'block' : 'none'};
`;

const DropdownItem = styled(Link)`
  display: flex;
  align-items: center;
  padding: 12px 16px;
  color: ${props => props.theme.textPrimary};
  text-decoration: none;
  font-size: 14px;
  
  svg {
    margin-right: 10px;
    color: ${props => props.theme.textSecondary};
  }
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
  }
`;

const Header = () => {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const location = useLocation();

  const handleSearch = (e) => {
    if (e.key === 'Enter') {
      // Handle search functionality
      console.log('Searching for:', e.target.value);
    }
  };

  const toggleUserMenu = () => {
    setIsUserMenuOpen(!isUserMenuOpen);
  };

  const handleLogout = () => {
    // Clear session state
    // Clear encryption keys from memory
    // Redirect to login page
    console.log('Logging out...');
  };

  return (
    <HeaderContainer>
      <Logo to="/dashboard">
        <FaLock /> SecureVault
      </Logo>
      
      <SearchBar>
        <SearchIcon>
          <FaSearch />
        </SearchIcon>
        <SearchInput 
          placeholder="Search vault..." 
          onKeyDown={handleSearch}
        />
      </SearchBar>
      
      <RightSection>
        <Tooltip content="Notifications">
          <IconButton>
            <FaBell />
          </IconButton>
        </Tooltip>
        
        <UserDropdown>
          <UserButton onClick={toggleUserMenu}>
            <FaUser />
            <span>John Doe</span>
          </UserButton>
          
          <DropdownMenu isOpen={isUserMenuOpen}>
            <DropdownItem to="/profile">
              <FaUser /> My Profile
            </DropdownItem>
            <DropdownItem to="/settings">
              <FaCog /> Account Settings
            </DropdownItem>
            <DropdownItem to="/login" onClick={handleLogout}>
              <FaSignOutAlt /> Logout
            </DropdownItem>
          </DropdownMenu>
        </UserDropdown>
        
        <Button
          variant="secondary"
          size="small"
          onClick={() => { /* Handle add new item */ }}
        >
          + New Item
        </Button>
      </RightSection>
    </HeaderContainer>
  );
};

export default Header;

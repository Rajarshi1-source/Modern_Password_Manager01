import React, { useState } from 'react';
import styled from 'styled-components';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  FaHome, 
  FaKey, 
  FaCreditCard, 
  FaIdCard, 
  FaStickyNote,
  FaShield, 
  FaClipboardList, 
  FaCog,
  FaChevronLeft,
  FaChevronRight,
  FaStar
} from 'react-icons/fa';

const SidebarContainer = styled.aside`
  width: ${props => props.collapsed ? '64px' : '240px'};
  height: 100%;
  background: ${props => props.theme.background};
  border-right: 1px solid ${props => props.theme.borderColor};
  transition: width 0.3s ease;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
`;

const SidebarHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: ${props => props.collapsed ? 'center' : 'flex-end'};
  padding: ${props => props.collapsed ? '16px 0' : '16px'};
  border-bottom: 1px solid ${props => props.theme.borderColor};
`;

const CollapseButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
    color: ${props => props.theme.textPrimary};
  }
`;

const SidebarContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
`;

const NavSection = styled.div`
  margin-bottom: 24px;
`;

const NavSectionTitle = styled.div`
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  color: ${props => props.theme.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: ${props => props.collapsed ? 'none' : 'block'};
`;

const NavItem = styled(NavLink)`
  display: flex;
  align-items: center;
  padding: ${props => props.collapsed ? '12px 0' : '12px 16px'};
  justify-content: ${props => props.collapsed ? 'center' : 'flex-start'};
  color: ${props => props.theme.textPrimary};
  text-decoration: none;
  font-size: 14px;
  border-left: 3px solid transparent;
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
  }
  
  &.active {
    border-left-color: ${props => props.theme.accent};
    background: ${props => props.theme.backgroundActive};
    color: ${props => props.theme.accent};
    
    svg {
      color: ${props => props.theme.accent};
    }
  }
  
  svg {
    font-size: 18px;
    margin-right: ${props => props.collapsed ? '0' : '12px'};
    color: ${props => props.theme.textSecondary};
  }
`;

const NavItemText = styled.span`
  display: ${props => props.collapsed ? 'none' : 'block'};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const CategorySection = styled.div`
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid ${props => props.theme.borderColor};
  display: ${props => props.collapsed ? 'none' : 'block'};
`;

const CategoryItem = styled.div`
  display: flex;
  align-items: center;
  padding: 8px 16px 8px 32px;
  color: ${props => props.theme.textSecondary};
  font-size: 13px;
  cursor: pointer;
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
    color: ${props => props.theme.textPrimary};
  }
  
  svg {
    margin-right: 8px;
    font-size: 12px;
  }
`;

const Sidebar = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  
  const toggleCollapse = () => {
    setCollapsed(!collapsed);
  };
  
  return (
    <SidebarContainer collapsed={collapsed}>
      <SidebarHeader collapsed={collapsed}>
        <CollapseButton onClick={toggleCollapse}>
          {collapsed ? <FaChevronRight /> : <FaChevronLeft />}
        </CollapseButton>
      </SidebarHeader>
      
      <SidebarContent>
        <NavSection>
          <NavSectionTitle collapsed={collapsed}>Main</NavSectionTitle>
          <NavItem to="/dashboard" collapsed={collapsed}>
            <FaHome />
            <NavItemText collapsed={collapsed}>Dashboard</NavItemText>
          </NavItem>
          <NavItem to="/vault" collapsed={collapsed}>
            <FaKey />
            <NavItemText collapsed={collapsed}>All Items</NavItemText>
          </NavItem>
          <NavItem to="/favorites" collapsed={collapsed}>
            <FaStar />
            <NavItemText collapsed={collapsed}>Favorites</NavItemText>
          </NavItem>
        </NavSection>
        
        <NavSection>
          <NavSectionTitle collapsed={collapsed}>Item Types</NavSectionTitle>
          <NavItem to="/vault/passwords" collapsed={collapsed}>
            <FaKey />
            <NavItemText collapsed={collapsed}>Passwords</NavItemText>
          </NavItem>
          <NavItem to="/vault/cards" collapsed={collapsed}>
            <FaCreditCard />
            <NavItemText collapsed={collapsed}>Payment Cards</NavItemText>
          </NavItem>
          <NavItem to="/vault/identities" collapsed={collapsed}>
            <FaIdCard />
            <NavItemText collapsed={collapsed}>Identities</NavItemText>
          </NavItem>
          <NavItem to="/vault/notes" collapsed={collapsed}>
            <FaStickyNote />
            <NavItemText collapsed={collapsed}>Secure Notes</NavItemText>
          </NavItem>
          
          {!collapsed && (
            <CategorySection collapsed={collapsed}>
              <CategoryItem>
                <FaStar /> Personal
              </CategoryItem>
              <CategoryItem>
                <FaStar /> Work
              </CategoryItem>
              <CategoryItem>
                <FaStar /> Finance
              </CategoryItem>
            </CategorySection>
          )}
        </NavSection>
        
        <NavSection>
          <NavSectionTitle collapsed={collapsed}>Tools</NavSectionTitle>
          <NavItem to="/security" collapsed={collapsed}>
            <FaShield />
            <NavItemText collapsed={collapsed}>Security Dashboard</NavItemText>
          </NavItem>
          <NavItem to="/generator" collapsed={collapsed}>
            <FaKey />
            <NavItemText collapsed={collapsed}>Password Generator</NavItemText>
          </NavItem>
          <NavItem to="/history" collapsed={collapsed}>
            <FaClipboardList />
            <NavItemText collapsed={collapsed}>History</NavItemText>
          </NavItem>
        </NavSection>
        
        <NavSection>
          <NavSectionTitle collapsed={collapsed}>Settings</NavSectionTitle>
          <NavItem to="/settings" collapsed={collapsed}>
            <FaCog />
            <NavItemText collapsed={collapsed}>Settings</NavItemText>
          </NavItem>
        </NavSection>
      </SidebarContent>
    </SidebarContainer>
  );
};

export default Sidebar;

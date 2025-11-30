import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import Header from './Header';
import Sidebar from './Sidebar';

const LayoutContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
`;

const MainContainer = styled.div`
  display: flex;
  flex: 1;
  overflow: hidden;
`;

const ContentContainer = styled.main`
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: ${props => props.theme.backgroundLight};
`;

const PageHeader = styled.div`
  margin-bottom: 24px;
`;

const PageTitle = styled.h1`
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: ${props => props.theme.textPrimary};
`;

const PageDescription = styled.p`
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
  margin: 0;
`;

/**
 * Main layout component for the application
 * Provides consistent structure with header, sidebar and content area
 */
const PageLayout = ({ 
  children, 
  title, 
  description,
  showHeader = true,
  showSidebar = true
}) => {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(isMobile);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      
      // Auto-collapse sidebar on mobile
      if (mobile && !sidebarCollapsed) {
        setSidebarCollapsed(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [sidebarCollapsed]);

  // Toggle sidebar collapsed state
  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  return (
    <LayoutContainer>
      {showHeader && <Header onMenuClick={toggleSidebar} />}
      
      <MainContainer>
        {showSidebar && <Sidebar collapsed={sidebarCollapsed} />}
        
        <ContentContainer>
          {(title || description) && (
            <PageHeader>
              {title && <PageTitle>{title}</PageTitle>}
              {description && <PageDescription>{description}</PageDescription>}
            </PageHeader>
          )}
          
          {children}
        </ContentContainer>
      </MainContainer>
    </LayoutContainer>
  );
};

export default PageLayout;

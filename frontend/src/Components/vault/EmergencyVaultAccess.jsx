import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import { FaExclamationTriangle, FaLock, FaClock, FaArrowLeft, FaShieldAlt } from 'react-icons/fa';
import api from '../../services/api';
import VaultItemCard from './VaultItemCard';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const Container = styled.div`
  padding: 32px 24px;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
  background: linear-gradient(180deg, ${colors.background} 0%, #f0f2ff 100%);
  animation: ${fadeIn} 0.4s ease-out;
`;

const EmergencyBanner = styled.div`
  background: linear-gradient(135deg, ${colors.warning}15 0%, ${colors.warning}08 100%);
  border: 1px solid ${colors.warning}40;
  border-radius: 20px;
  padding: 24px;
  margin-bottom: 32px;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: linear-gradient(180deg, ${colors.warning} 0%, #fbbf24 100%);
  }
`;

const BannerIcon = styled.div`
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.warning}25 0%, ${colors.warning}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 26px;
    color: ${colors.warning};
  }
`;

const BannerContent = styled.div`
  flex: 1;
`;

const BannerTitle = styled.h3`
  margin: 0 0 10px 0;
  font-size: 20px;
  font-weight: 700;
  color: ${colors.text};
`;

const BannerText = styled.p`
  margin: 0 0 14px 0;
  font-size: 14px;
  color: ${colors.textSecondary};
  line-height: 1.6;
`;

const ExpiryBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: ${colors.warning}20;
  border-radius: 30px;
  font-weight: 700;
  font-size: 14px;
  color: ${colors.warning};
  
  svg {
    font-size: 16px;
  }
`;

const VaultGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 80px 40px;
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 24px;
  border: 2px dashed ${colors.border};
  animation: ${fadeIn} 0.4s ease-out;
`;

const EmptyIcon = styled.div`
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
  
  svg {
    font-size: 36px;
    color: ${colors.primary};
  }
`;

const EmptyTitle = styled.h2`
  font-size: 24px;
  font-weight: 700;
  color: ${colors.text};
  margin: 0 0 12px 0;
`;

const EmptyText = styled.p`
  font-size: 15px;
  color: ${colors.textSecondary};
  margin: 0 0 28px 0;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.6;
`;

const BackButton = styled.button`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 14px 28px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 14px ${colors.primary}40;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

const LoadingIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  
  svg {
    font-size: 28px;
    color: ${colors.primary};
  }
`;

const LoadingText = styled.p`
  font-size: 16px;
  color: ${colors.textSecondary};
  font-weight: 500;
`;

const ErrorState = styled.div`
  text-align: center;
  padding: 80px 40px;
  background: linear-gradient(135deg, ${colors.danger}10 0%, ${colors.danger}05 100%);
  border: 1px solid ${colors.danger}30;
  border-radius: 24px;
`;

const ErrorIcon = styled.div`
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: ${colors.danger}15;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
  
  svg {
    font-size: 36px;
    color: ${colors.danger};
  }
`;

const ErrorTitle = styled.h2`
  font-size: 24px;
  font-weight: 700;
  color: ${colors.text};
  margin: 0 0 12px 0;
`;

const ErrorText = styled.p`
  font-size: 15px;
  color: ${colors.textSecondary};
  margin: 0 0 28px 0;
`;

const EmergencyVaultAccess = () => {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [vaultData, setVaultData] = useState(null);
  
  useEffect(() => {
    if (!requestId) {
      setError('Invalid request ID');
      setLoading(false);
      return;
    }
    
    const fetchVaultData = async () => {
      try {
        const response = await api.get(`/user/emergency-vault/${requestId}/`);
        setVaultData(response.data);
      } catch (err) {
        console.error('Error accessing emergency vault:', err);
        setError(err.response?.data?.error || 'Failed to access vault');
      } finally {
        setLoading(false);
      }
    };
    
    fetchVaultData();
  }, [requestId]);
  
  const formatExpiryTime = (expiryDate) => {
    if (!expiryDate) return 'Unknown';
    
    const expiry = new Date(expiryDate);
    const now = new Date();
    const diff = expiry - now;
    
    if (diff <= 0) return 'Expired';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    return `${hours}h ${minutes}m remaining`;
  };
  
  if (loading) {
    return (
      <Container>
        <LoadingContainer>
          <LoadingIcon>
            <FaShieldAlt />
          </LoadingIcon>
          <LoadingText>Loading emergency access...</LoadingText>
        </LoadingContainer>
      </Container>
    );
  }
  
  if (error) {
    return (
      <Container>
        <ErrorState>
          <ErrorIcon>
            <FaExclamationTriangle />
          </ErrorIcon>
          <ErrorTitle>Access Error</ErrorTitle>
          <ErrorText>{error}</ErrorText>
          <BackButton onClick={() => navigate('/dashboard')}>
            <FaArrowLeft /> Return to Dashboard
          </BackButton>
        </ErrorState>
      </Container>
    );
  }
  
  if (!vaultData || !vaultData.items || vaultData.items.length === 0) {
    return (
      <Container>
        <EmptyState>
          <EmptyIcon>
            <FaLock />
          </EmptyIcon>
          <EmptyTitle>No Items Available</EmptyTitle>
          <EmptyText>
            This vault is empty or you don't have permission to view any items.
          </EmptyText>
          <BackButton onClick={() => navigate('/dashboard')}>
            <FaArrowLeft /> Return to Dashboard
          </BackButton>
        </EmptyState>
      </Container>
    );
  }
  
  return (
    <Container>
      <EmergencyBanner>
        <BannerIcon>
          <FaExclamationTriangle />
        </BannerIcon>
        <BannerContent>
          <BannerTitle>🔐 Emergency Access to {vaultData.vault_owner}'s Vault</BannerTitle>
          <BannerText>
            You have {vaultData.access_type === 'view' ? 'view-only' : 'full'} access to this vault.
            Please respect the vault owner's privacy and only access necessary information.
          </BannerText>
          <ExpiryBadge>
            <FaClock /> {formatExpiryTime(vaultData.expires_at)}
          </ExpiryBadge>
        </BannerContent>
      </EmergencyBanner>
      
      <VaultGrid>
        {vaultData.items.map(item => (
          <VaultItemCard 
            key={item.id}
            item={item}
            readOnly={vaultData.access_type === 'view'}
            emergencyMode={true}
          />
        ))}
      </VaultGrid>
    </Container>
  );
};

export default EmergencyVaultAccess;

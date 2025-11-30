import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { FaExclamationTriangle, FaLock, FaEye, FaEyeSlash, FaCopy, FaClock } from 'react-icons/fa';
import api from '../../services/api';
import VaultItemCard from './VaultItemCard';

const Container = styled.div`
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
`;

const EmergencyBanner = styled.div`
  background: ${props => props.theme.warningLight};
  color: ${props => props.theme.warning};
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const BannerIcon = styled.div`
  font-size: 24px;
`;

const BannerContent = styled.div`
  flex: 1;
`;

const BannerTitle = styled.h3`
  margin: 0 0 8px 0;
`;

const ExpiryInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-top: 8px;
`;

const VaultList = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 24px;
  background: ${props => props.theme.backgroundSecondary};
  border-radius: 8px;
  margin-bottom: 24px;
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
    return <Container>Loading emergency access...</Container>;
  }
  
  if (error) {
    return (
      <Container>
        <EmptyState>
          <FaExclamationTriangle size={48} />
          <h2>Access Error</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/dashboard')}>Return to Dashboard</button>
        </EmptyState>
      </Container>
    );
  }
  
  if (!vaultData || !vaultData.items || vaultData.items.length === 0) {
    return (
      <Container>
        <EmptyState>
          <FaLock size={48} />
          <h2>No Items Available</h2>
          <p>This vault is empty or you don't have permission to view any items.</p>
          <button onClick={() => navigate('/dashboard')}>Return to Dashboard</button>
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
          <BannerTitle>Emergency Access to {vaultData.vault_owner}'s Vault</BannerTitle>
          <p>
            You have {vaultData.access_type === 'view' ? 'view-only' : 'full'} access to this vault.
            Please respect the vault owner's privacy and only access necessary information.
          </p>
          <ExpiryInfo>
            <FaClock /> {formatExpiryTime(vaultData.expires_at)}
          </ExpiryInfo>
        </BannerContent>
      </EmergencyBanner>
      
      <VaultList>
        {vaultData.items.map(item => (
          <VaultItemCard 
            key={item.id}
            item={item}
            readOnly={vaultData.access_type === 'view'}
            emergencyMode={true}
          />
        ))}
      </VaultList>
    </Container>
  );
};

export default EmergencyVaultAccess;
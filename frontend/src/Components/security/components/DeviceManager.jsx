import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { FaMobile, FaDesktop, FaTabletAlt, FaShieldAlt, FaTrash, FaEdit, FaSync, FaCheckCircle, FaTimesCircle, FaLaptop, FaClock, FaInfoCircle } from 'react-icons/fa';

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const Container = styled.div`
  animation: ${fadeIn} 0.3s ease-out;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
`;

const Title = styled.h3`
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  
  svg {
    color: ${props => props.theme.primary || '#7B68EE'};
  }
`;

const Subtitle = styled.p`
  margin: 0;
  color: ${props => props.theme.textSecondary || '#666'};
  font-size: 14px;
`;

const HeaderLeft = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const RefreshButton = styled.button`
  padding: 8px 12px;
  border: 1px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 8px;
  background: ${props => props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textSecondary || '#666'};
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: ${props => props.theme.primary || '#7B68EE'};
    color: ${props => props.theme.primary || '#7B68EE'};
  }
  
  svg {
    animation: ${props => props.$loading ? spin : 'none'} 1s linear infinite;
  }
`;

const InfoBanner = styled.div`
  background: linear-gradient(135deg, ${props => props.theme.primaryLight || '#f0edff'} 0%, #e8f4fd 100%);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border: 1px solid ${props => props.theme.primary || '#7B68EE'}20;
`;

const InfoIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: ${props => props.theme.primary || '#7B68EE'};
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  svg { color: white; font-size: 18px; }
`;

const InfoContent = styled.div`
  flex: 1;
`;

const InfoTitle = styled.h4`
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const InfoText = styled.p`
  margin: 0;
  font-size: 13px;
  color: ${props => props.theme.textSecondary || '#666'};
  line-height: 1.5;
`;

const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const Spinner = styled.div`
  width: 40px;
  height: 40px;
  border: 3px solid ${props => props.theme.backgroundSecondary || '#f0f0f0'};
  border-top-color: ${props => props.theme.primary || '#7B68EE'};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-bottom: 16px;
`;

const EmptyState = styled.div`
  background: linear-gradient(135deg, ${props => props.theme.primaryLight || '#f0edff'} 0%, ${props => props.theme.cardBg || '#fff'} 100%);
  border-radius: 16px;
  padding: 48px 24px;
  text-align: center;
  border: 1px dashed ${props => props.theme.borderColor || '#e0e0e0'};
`;

const EmptyIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: ${props => props.theme.primary || '#7B68EE'}20;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  
  svg {
    font-size: 28px;
    color: ${props => props.theme.primary || '#7B68EE'};
  }
`;

const EmptyTitle = styled.h4`
  margin: 0 0 8px;
  font-size: 18px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const EmptyText = styled.p`
  margin: 0;
  color: ${props => props.theme.textSecondary || '#666'};
  font-size: 14px;
`;

const DeviceList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const DeviceCard = styled.div`
  background: ${props => props.$current 
    ? `linear-gradient(135deg, ${props.theme.primaryLight || '#f0edff'} 0%, ${props.theme.cardBg || '#fff'} 100%)`
    : props.theme.cardBg || '#fff'};
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid ${props => props.$current 
    ? props.theme.primary || '#7B68EE' 
    : props.theme.borderColor || '#e0e0e0'};
  transition: all 0.2s ease;
  animation: ${fadeIn} 0.3s ease-out;
  animation-delay: ${props => props.$index * 0.05}s;
  animation-fill-mode: backwards;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    transform: translateY(-2px);
  }
`;

const CardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
`;

const DeviceInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const DeviceIconWrapper = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: ${props => props.$trusted 
    ? `linear-gradient(135deg, #10b981 0%, #059669 100%)`
    : `linear-gradient(135deg, ${props.theme.primary || '#7B68EE'} 0%, ${props.theme.accent || '#9B8BFF'} 100%)`};
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    color: white;
    font-size: 20px;
  }
`;

const DeviceDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const DeviceName = styled.span`
  font-size: 15px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const DeviceMeta = styled.span`
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  
  ${props => {
    if (props.$variant === 'trusted') {
      return `
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        color: #059669;
      `;
    }
    if (props.$variant === 'current') {
      return `
        background: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 100%);
        color: #7c3aed;
      `;
    }
    return `
      background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
      color: #64748b;
    `;
  }}
`;

const CardDetails = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
`;

const DetailItem = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 8px;
  
  svg {
    color: ${props => props.theme.primary || '#7B68EE'};
    font-size: 14px;
    flex-shrink: 0;
  }
`;

const DetailContent = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

const DetailLabel = styled.span`
  font-size: 11px;
  color: ${props => props.theme.textSecondary || '#666'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const DetailValue = styled.span`
  font-size: 13px;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  font-weight: 500;
  word-break: break-all;
`;

const CardActions = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

const ActionButton = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  ${props => {
    if (props.$variant === 'trust') {
      return `
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        &:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }
      `;
    }
    if (props.$variant === 'untrust') {
      return `
        background: ${props.theme.backgroundSecondary || '#f8f9fa'};
        color: ${props.theme.textSecondary || '#666'};
        border: 1px solid ${props.theme.borderColor || '#e0e0e0'};
        &:hover { border-color: ${props.theme.primary || '#7B68EE'}; color: ${props.theme.primary || '#7B68EE'}; }
      `;
    }
    if (props.$variant === 'edit') {
      return `
        background: ${props.theme.primary || '#7B68EE'}15;
        color: ${props.theme.primary || '#7B68EE'};
        &:hover { background: ${props.theme.primary || '#7B68EE'}25; }
      `;
    }
    if (props.$variant === 'delete') {
      return `
        background: #fee2e2;
        color: #dc2626;
        &:hover { background: #fecaca; }
      `;
    }
    return `
      background: ${props.theme.backgroundSecondary || '#f8f9fa'};
      color: ${props.theme.textPrimary || '#1a1a2e'};
    `;
  }}
`;

const Modal = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: ${fadeIn} 0.2s ease-out;
`;

const ModalContent = styled.div`
  background: ${props => props.theme.cardBg || '#fff'};
  padding: 28px;
  border-radius: 16px;
  width: 90%;
  max-width: 480px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  animation: ${fadeIn} 0.3s ease-out;
`;

const ModalHeader = styled.div`
  margin-bottom: 20px;
`;

const ModalTitle = styled.h3`
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
`;

const ModalSubtitle = styled.p`
  margin: 0;
  font-size: 14px;
  color: ${props => props.theme.textSecondary || '#666'};
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  margin-bottom: 8px;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 16px;
  border: 2px solid ${props => props.theme.borderColor || '#e0e0e0'};
  border-radius: 10px;
  font-size: 14px;
  background: ${props => props.theme.cardBg || '#fff'};
  color: ${props => props.theme.textPrimary || '#1a1a2e'};
  transition: all 0.2s ease;
  box-sizing: border-box;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.primary || '#7B68EE'};
  }
`;

const DeviceInfoBox = styled.div`
  background: ${props => props.theme.backgroundSecondary || '#f8f9fa'};
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 16px;
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#666'};
  line-height: 1.6;
`;

const ModalActions = styled.div`
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
`;

const ModalButton = styled.button`
  padding: 12px 20px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  ${props => props.$variant === 'primary' ? `
    background: linear-gradient(135deg, ${props.theme.primary || '#7B68EE'} 0%, ${props.theme.accent || '#9B8BFF'} 100%);
    color: white;
    box-shadow: 0 4px 14px ${props.theme.primary || '#7B68EE'}40;
    &:hover { transform: translateY(-2px); }
  ` : `
    background: ${props.theme.backgroundSecondary || '#f8f9fa'};
    color: ${props.theme.textPrimary || '#1a1a2e'};
    &:hover { background: ${props.theme.borderColor || '#e0e0e0'}; }
  `}
`;

const DeviceManager = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentDevice, setCurrentDevice] = useState(null);
  const [deviceName, setDeviceName] = useState('');

  const fetchDevices = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await axios.get('/api/security/devices/');
      setDevices(data.devices || []);
    } catch (error) {
      toast.error('Failed to load devices');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const handleEditDevice = (device) => {
    setCurrentDevice(device);
    setDeviceName(device.device_name || '');
    setShowEditModal(true);
  };

  const handleUpdateDevice = async () => {
    if (!currentDevice) return;
    try {
      await axios.patch(`/api/security/devices/${currentDevice.device_id}/`, {
        device_name: deviceName
      });
      
      toast.success('Device updated successfully');
      setShowEditModal(false);
      setCurrentDevice(null);
      fetchDevices();
    } catch (error) {
      toast.error('Failed to update device');
      console.error(error);
    }
  };

  const handleToggleTrusted = async (deviceId, isTrusted) => {
    try {
      if (isTrusted) {
        await axios.post(`/api/security/devices/${deviceId}/untrust/`);
        toast.success('Device unmarked as trusted');
      } else {
        await axios.post(`/api/security/devices/${deviceId}/trust/`);
        toast.success('Device marked as trusted');
      }
      
      fetchDevices();
    } catch (error) {
      toast.error('Failed to update device trust status');
      console.error(error);
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm('Are you sure you want to remove this device? This action cannot be undone.')) {
      return;
    }
    
    try {
      await axios.delete(`/api/security/devices/${deviceId}/`);
      toast.success('Device removed successfully');
      fetchDevices();
    } catch (error) {
      toast.error('Failed to remove device');
      console.error(error);
    }
  };

  const getDeviceIcon = (deviceType) => {
    switch (deviceType?.toLowerCase()) {
      case 'mobile':
        return <FaMobile />;
      case 'tablet':
        return <FaTabletAlt />;
      case 'laptop':
        return <FaLaptop />;
      default:
        return <FaDesktop />;
    }
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    const date = new Date(lastSeen);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) {
      return 'Just now';
    } else if (diffInMinutes < 60) {
      return `${diffInMinutes} min ago`;
    } else if (diffInMinutes < 1440) {
      return `${Math.floor(diffInMinutes / 60)} hours ago`;
    } else {
      return `${Math.floor(diffInMinutes / 1440)} days ago`;
    }
  };

  return (
    <Container>
      <Header>
        <HeaderLeft>
          <Title>
            <FaMobile /> Manage Devices
          </Title>
          <Subtitle>
            View and manage devices that have accessed your account
          </Subtitle>
        </HeaderLeft>
        <RefreshButton onClick={fetchDevices} $loading={loading}>
          <FaSync /> Refresh
        </RefreshButton>
      </Header>

      <InfoBanner>
        <InfoIcon>
          <FaShieldAlt />
        </InfoIcon>
        <InfoContent>
          <InfoTitle>Device Security</InfoTitle>
          <InfoText>
            Mark frequently used devices as trusted for a smoother login experience. 
            Remove any devices you don't recognize to protect your account.
          </InfoText>
        </InfoContent>
      </InfoBanner>

      {loading ? (
        <LoadingContainer>
          <Spinner />
          <span>Loading devices...</span>
        </LoadingContainer>
      ) : devices.length === 0 ? (
        <EmptyState>
          <EmptyIcon>
            <FaMobile />
          </EmptyIcon>
          <EmptyTitle>No Devices Found</EmptyTitle>
          <EmptyText>
            Devices will appear here after you log in from them.
          </EmptyText>
        </EmptyState>
      ) : (
        <DeviceList>
          {devices.map((device, index) => (
            <DeviceCard 
              key={device.device_id} 
              $current={device.is_current}
              $index={index}
            >
              <CardHeader>
                <DeviceInfo>
                  <DeviceIconWrapper $trusted={device.is_trusted}>
                    {getDeviceIcon(device.device_type)}
                  </DeviceIconWrapper>
                  <DeviceDetails>
                    <DeviceName>
                      {device.device_name || `Unknown Device`}
                    </DeviceName>
                    <DeviceMeta>
                      {device.browser || 'Unknown Browser'} • {device.os || 'Unknown OS'}
                    </DeviceMeta>
                  </DeviceDetails>
                </DeviceInfo>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {device.is_current && (
                    <StatusBadge $variant="current">
                      <FaCheckCircle /> Current Device
                    </StatusBadge>
                  )}
                  {device.is_trusted && (
                    <StatusBadge $variant="trusted">
                      <FaCheckCircle /> Trusted
                    </StatusBadge>
                  )}
                </div>
              </CardHeader>

              <CardDetails>
                <DetailItem>
                  <FaClock />
                  <DetailContent>
                    <DetailLabel>Last Active</DetailLabel>
                    <DetailValue>{formatLastSeen(device.last_seen)}</DetailValue>
                  </DetailContent>
                </DetailItem>
                
                <DetailItem>
                  <FaDesktop />
                  <DetailContent>
                    <DetailLabel>Device Type</DetailLabel>
                    <DetailValue style={{ textTransform: 'capitalize' }}>
                      {device.device_type || 'Unknown'}
                    </DetailValue>
                  </DetailContent>
                </DetailItem>
                
                {device.location && (
                  <DetailItem>
                    <FaInfoCircle />
                    <DetailContent>
                      <DetailLabel>Location</DetailLabel>
                      <DetailValue>{device.location}</DetailValue>
                    </DetailContent>
                  </DetailItem>
                )}
              </CardDetails>

              <CardActions>
                {device.is_trusted ? (
                  <ActionButton 
                    $variant="untrust"
                    onClick={() => handleToggleTrusted(device.device_id, true)}
                  >
                    <FaTimesCircle /> Remove Trust
                  </ActionButton>
                ) : (
                  <ActionButton 
                    $variant="trust"
                    onClick={() => handleToggleTrusted(device.device_id, false)}
                  >
                    <FaCheckCircle /> Mark as Trusted
                  </ActionButton>
                )}
                <ActionButton 
                  $variant="edit"
                  onClick={() => handleEditDevice(device)}
                >
                  <FaEdit /> Rename
                </ActionButton>
                {!device.is_current && (
                  <ActionButton 
                    $variant="delete"
                    onClick={() => handleDeleteDevice(device.device_id)}
                  >
                    <FaTrash /> Remove
                  </ActionButton>
                )}
              </CardActions>
            </DeviceCard>
          ))}
        </DeviceList>
      )}
      
      {/* Edit Device Modal */}
      {showEditModal && (
        <Modal onClick={() => { setShowEditModal(false); setCurrentDevice(null); }}>
          <ModalContent onClick={(e) => e.stopPropagation()}>
            <ModalHeader>
              <ModalTitle>Rename Device</ModalTitle>
              <ModalSubtitle>Give this device a friendly name to recognize it easily</ModalSubtitle>
            </ModalHeader>
            <form onSubmit={(e) => { e.preventDefault(); handleUpdateDevice(); }}>
              <FormGroup>
                <Label>Device Name</Label>
                <Input 
                  type="text" 
                  value={deviceName} 
                  onChange={(e) => setDeviceName(e.target.value)}
                  placeholder="E.g., John's Laptop, Work PC"
                  autoFocus
                />
              </FormGroup>
              {currentDevice && (
                <DeviceInfoBox>
                  <strong>Device ID:</strong> {currentDevice.fingerprint ? currentDevice.fingerprint.substring(0, 12) + '...' : 'N/A'}<br />
                  <strong>Last seen:</strong> {formatLastSeen(currentDevice.last_seen)}<br />
                  <strong>Type:</strong> {currentDevice.device_type || 'Unknown'}
                </DeviceInfoBox>
              )}
            </form>
            <ModalActions>
              <ModalButton 
                type="button"
                onClick={() => { setShowEditModal(false); setCurrentDevice(null); }}
              >
                Cancel
              </ModalButton>
              <ModalButton $variant="primary" onClick={handleUpdateDevice}>
                Save Changes
              </ModalButton>
            </ModalActions>
          </ModalContent>
        </Modal>
      )}
    </Container>
  );
};

export default DeviceManager;

import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { FaMobile, FaDesktop, FaTabletAlt } from 'react-icons/fa';

const Container = styled.div`
  padding: 20px;
`;

const Title = styled.h2`
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Description = styled.p`
  color: ${props => props.theme.textSecondary};
  margin-bottom: 24px;
`;

const LoadingMessage = styled.p`
  text-align: center;
  color: ${props => props.theme.textSecondary};
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 20px;
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  
  h3 {
    margin-bottom: 8px;
    color: ${props => props.theme.textPrimary};
  }
  
  p {
    color: ${props => props.theme.textSecondary};
  }
`;

const DeviceTable = styled.div`
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  overflow: hidden;
`;

const TableHeader = styled.div`
  display: grid;
  grid-template-columns: 2fr 1fr 2fr 1fr 1fr 1fr;
  gap: 16px;
  padding: 16px;
  background: ${props => props.theme.backgroundSecondary};
  font-weight: 600;
  font-size: 14px;
  color: ${props => props.theme.textSecondary};
`;

const DeviceRow = styled.div`
  display: grid;
  grid-template-columns: 2fr 1fr 2fr 1fr 1fr 1fr;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid ${props => props.theme.borderColor};
  align-items: center;
  
  &:last-child {
    border-bottom: none;
  }
`;

const DeviceName = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
`;

const DeviceType = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
`;

const TrustButton = styled.button`
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  
  ${props => props.trusted ? `
    background: ${props.theme.success};
    color: white;
  ` : `
    background: ${props.theme.backgroundSecondary};
    color: ${props.theme.textSecondary};
    border: 1px solid ${props.theme.borderColor};
  `}
  
  &:hover {
    opacity: 0.8;
  }
`;

const ActionButton = styled.button`
  padding: 6px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 4px;
  
  ${props => props.variant === 'edit' ? `
    background: ${props.theme.primary};
    color: white;
  ` : `
    background: ${props.theme.danger};
    color: white;
  `}
  
  &:hover {
    opacity: 0.8;
  }
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
`;

const ModalContent = styled.div`
  background: ${props => props.theme.cardBg};
  padding: 24px;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
`;

const ModalHeader = styled.h3`
  margin-top: 0;
  margin-bottom: 16px;
`;

const FormGroup = styled.div`
  margin-bottom: 16px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
`;

const Input = styled.input`
  width: 100%;
  padding: 8px 12px;
  border: 1px solid ${props => props.theme.borderColor};
  border-radius: 4px;
  background: ${props => props.theme.backgroundPrimary};
  color: ${props => props.theme.textPrimary};
`;

const DeviceInfo = styled.p`
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
  margin: 8px 0 0 0;
`;

const ModalActions = styled.div`
  display: flex;
  gap: 8px;
  justify-content: flex-end;
`;

const Button = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  
  ${props => props.variant === 'primary' ? `
    background: ${props.theme.primary};
    color: white;
  ` : `
    background: ${props.theme.backgroundSecondary};
    color: ${props.theme.textPrimary};
  `}
  
  &:hover {
    opacity: 0.8;
  }
`;

const DeviceManager = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentDevice, setCurrentDevice] = useState(null);
  const [deviceName, setDeviceName] = useState('');

  useEffect(() => {
    fetchDevices();
  }, []);

  const fetchDevices = async () => {
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
  };

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
      default:
        return <FaDesktop />;
    }
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    const date = new Date(lastSeen);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 60) {
      return `${diffInMinutes} minutes ago`;
    } else if (diffInMinutes < 1440) {
      return `${Math.floor(diffInMinutes / 60)} hours ago`;
    } else {
      return `${Math.floor(diffInMinutes / 1440)} days ago`;
    }
  };

  return (
    <Container>
      <Title>
        <FaMobile /> Manage Your Devices
      </Title>
      <Description>
        Devices that have accessed your account are listed here. You can mark devices as trusted for enhanced security or remove old/unrecognized devices.
      </Description>
      
      {loading ? (
        <LoadingMessage>Loading devices...</LoadingMessage>
      ) : devices.length === 0 ? (
        <EmptyState>
          <h3>No devices found</h3>
          <p>No devices have been registered with your account yet. Devices will appear here after you log in from them.</p>
        </EmptyState>
      ) : (
        <DeviceTable>
          <TableHeader>
            <div>Device Name</div>
            <div>Type</div>
            <div>Browser / OS</div>
            <div>Last Used</div>
            <div>Trusted</div>
            <div>Actions</div>
          </TableHeader>
          {devices.map(device => (
            <DeviceRow key={device.device_id}>
              <DeviceName>
                {getDeviceIcon(device.device_type)}
                {device.device_name || `Unknown Device (${device.fingerprint ? device.fingerprint.substring(0, 8) : 'N/A'})`}
              </DeviceName>
              <DeviceType>
                {device.device_type || 'Unknown'}
              </DeviceType>
              <div>
                {device.browser || 'Unknown'} / {device.os || 'Unknown'}
              </div>
              <div>{formatLastSeen(device.last_seen)}</div>
              <div>
                <TrustButton 
                  trusted={device.is_trusted}
                  onClick={() => handleToggleTrusted(device.device_id, device.is_trusted)}
                >
                  {device.is_trusted ? (
                    <>✓ Trusted</>
                  ) : (
                    <>✗ Not Trusted</>
                  )}
                </TrustButton>
              </div>
              <div>
                <ActionButton 
                  variant="edit"
                  onClick={() => handleEditDevice(device)}
                  title="Edit device name"
                >
                  ✏️
                </ActionButton>
                <ActionButton 
                  variant="delete"
                  onClick={() => handleDeleteDevice(device.device_id)}
                  title="Remove device"
                >
                  🗑️
                </ActionButton>
              </div>
            </DeviceRow>
          ))}
        </DeviceTable>
      )}
      
      {/* Edit Device Modal */}
      {showEditModal && (
        <Modal onClick={() => { setShowEditModal(false); setCurrentDevice(null); }}>
          <ModalContent onClick={(e) => e.stopPropagation()}>
            <ModalHeader>Edit Device Name</ModalHeader>
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
                <DeviceInfo>
                  Device ID: {currentDevice.fingerprint ? currentDevice.fingerprint.substring(0, 12) : 'N/A'}...<br />
                  Last seen: {formatLastSeen(currentDevice.last_seen)}<br />
                  Type: {currentDevice.device_type || 'Unknown'}
                </DeviceInfo>
              )}
            </form>
            <ModalActions>
              <Button 
                variant="secondary" 
                onClick={() => { setShowEditModal(false); setCurrentDevice(null); }}
              >
                Cancel
              </Button>
              <Button variant="primary" onClick={handleUpdateDevice}>
                Save Changes
              </Button>
            </ModalActions>
          </ModalContent>
        </Modal>
      )}
    </Container>
  );
};

export default DeviceManager; 
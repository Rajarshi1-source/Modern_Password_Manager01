import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { useVault } from '../../../contexts/VaultContext';
import Modal from '../../common/Modal';
import Button from '../../common/Button';
import { formatDate, formatFileSize } from '../../../utils/formatters';
import { FaCloudUploadAlt, FaCloudDownloadAlt, FaTrash, FaHistory } from 'react-icons/fa';

const Container = styled.div`
  padding: 20px;
`;

const Title = styled.h2`
  margin-bottom: 20px;
`;

const ActionsContainer = styled.div`
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
`;

const BackupList = styled.div`
  margin-top: 20px;
`;

const BackupCard = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-radius: 8px;
  background-color: ${props => props.theme.cardBg};
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
`;

const BackupInfo = styled.div`
  flex: 1;
`;

const BackupName = styled.h3`
  margin: 0;
  font-size: 16px;
`;

const BackupMeta = styled.div`
  color: ${props => props.theme.textSecondary};
  font-size: 14px;
  margin-top: 4px;
`;

const BackupActions = styled.div`
  display: flex;
  gap: 8px;
`;

const ActionButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  
  &:hover {
    color: ${props => props.theme.primary};
    background: ${props => props.theme.bgHover};
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 20px;
  color: ${props => props.theme.textSecondary};
`;

const BackupManager = () => {
  const { createBackup, getBackups, restoreBackup, loading } = useVault();
  const [backups, setBackups] = useState([]);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [selectedBackup, setSelectedBackup] = useState(null);
  const [restoreOptions, setRestoreOptions] = useState({ clearExisting: false });
  
  useEffect(() => {
    loadBackups();
  }, []);
  
  const loadBackups = async () => {
    try {
      const backupList = await getBackups();
      setBackups(backupList);
    } catch (error) {
      console.error('Failed to load backups:', error);
    }
  };
  
  const handleCreateBackup = async () => {
    try {
      await createBackup();
      await loadBackups();
    } catch (error) {
      console.error('Failed to create backup:', error);
    }
  };
  
  const handleRestoreClick = (backup) => {
    setSelectedBackup(backup);
    setShowRestoreModal(true);
  };
  
  const handleRestore = async () => {
    try {
      await restoreBackup(selectedBackup.id, restoreOptions);
      setShowRestoreModal(false);
      // Refresh page to reflect restored vault
      window.location.reload();
    } catch (error) {
      console.error('Failed to restore backup:', error);
    }
  };
  
  return (
    <Container>
      <Title>Vault Backups</Title>
      
      <ActionsContainer>
        <Button 
          primary 
          onClick={handleCreateBackup} 
          disabled={loading}
          icon={<FaCloudUploadAlt />}
        >
          Create Backup
        </Button>
      </ActionsContainer>
      
      <BackupList>
        {backups.length > 0 ? (
          backups.map(backup => (
            <BackupCard key={backup.id}>
              <BackupInfo>
                <BackupName>{backup.name}</BackupName>
                <BackupMeta>
                  {formatDate(backup.created_at)} • 
                  {backup.item_count} items • 
                  {formatFileSize(backup.size)} • 
                  {backup.cloud_sync_status === 'synced' ? 'Synced to cloud' : 'Local only'}
                </BackupMeta>
              </BackupInfo>
              
              <BackupActions>
                <ActionButton 
                  title="Restore from this backup"
                  onClick={() => handleRestoreClick(backup)}
                >
                  <FaHistory />
                </ActionButton>
                
                <ActionButton title="Download backup">
                  <FaCloudDownloadAlt />
                </ActionButton>
                
                <ActionButton title="Delete backup">
                  <FaTrash />
                </ActionButton>
              </BackupActions>
            </BackupCard>
          ))
        ) : (
          <EmptyState>
            <h3>No backups found</h3>
            <p>Create your first backup to protect your vault data.</p>
          </EmptyState>
        )}
      </BackupList>
      
      {showRestoreModal && (
        <Modal
          title="Restore Vault"
          onClose={() => setShowRestoreModal(false)}
          actions={[
            {
              label: 'Cancel',
              onClick: () => setShowRestoreModal(false)
            },
            {
              label: 'Restore',
              primary: true,
              onClick: handleRestore
            }
          ]}
        >
          <p>Are you sure you want to restore your vault from this backup?</p>
          <p><strong>{selectedBackup.name}</strong> created on {formatDate(selectedBackup.created_at)}</p>
          <p>This backup contains {selectedBackup.item_count} items.</p>
          
          <div>
            <label>
              <input
                type="checkbox"
                checked={restoreOptions.clearExisting}
                onChange={(e) => setRestoreOptions({
                  ...restoreOptions,
                  clearExisting: e.target.checked
                })}
              />
              Replace existing vault (remove all current items)
            </label>
            <p><small>If unchecked, backup items will be merged with your current vault.</small></p>
          </div>
        </Modal>
      )}
    </Container>
  );
};

export default BackupManager;

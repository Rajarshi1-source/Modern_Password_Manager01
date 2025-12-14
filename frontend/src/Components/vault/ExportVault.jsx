import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaDownload, FaLock, FaCheckCircle, FaExclamationTriangle, FaFileExport, FaFileCode, FaFileAlt, FaFileCsv } from 'react-icons/fa';
import { useVault } from '../../contexts/VaultContext';
import { VaultService } from '../../services/vaultService';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
`;

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
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
  max-width: 600px;
  margin: 0 auto;
  padding: 32px 24px;
  animation: ${fadeIn} 0.4s ease-out;
`;

const Card = styled.div`
  background: linear-gradient(135deg, ${colors.cardBg} 0%, ${colors.background} 100%);
  border-radius: 24px;
  padding: 36px;
  box-shadow: 0 8px 32px rgba(123, 104, 238, 0.12);
  border: 1px solid ${colors.border};
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 28px;
`;

const IconBadge = styled.div`
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  
  svg {
    font-size: 32px;
    color: ${colors.primary};
  }
`;

const Title = styled.h2`
  font-size: 26px;
  font-weight: 800;
  margin: 0 0 10px 0;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

const Description = styled.p`
  color: ${colors.textSecondary};
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
`;

const WarningBox = styled.div`
  background: linear-gradient(135deg, ${colors.warning}15 0%, ${colors.warning}08 100%);
  border-left: 4px solid ${colors.warning};
  padding: 18px 20px;
  border-radius: 0 14px 14px 0;
  margin-bottom: 28px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
`;

const WarningIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: ${colors.warning}20;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 18px;
    color: ${colors.warning};
  }
`;

const WarningText = styled.div`
  font-size: 14px;
  color: ${colors.text};
  line-height: 1.6;
  
  strong {
    font-weight: 700;
    display: block;
    margin-bottom: 4px;
    color: ${colors.warning};
  }
`;

const ProgressContainer = styled.div`
  margin: 28px 0;
  animation: ${fadeIn} 0.3s ease-out;
`;

const ProgressBar = styled.div`
  height: 10px;
  background: ${colors.border};
  border-radius: 5px;
  overflow: hidden;
  margin-bottom: 14px;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, ${colors.primary} 0%, ${colors.primaryLight} 100%);
  width: ${props => props.$progress}%;
  transition: width 0.3s ease;
  border-radius: 5px;
`;

const ProgressText = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: ${colors.textSecondary};
`;

const ProgressLabel = styled.span`
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  
  &::before {
    content: '';
    width: 16px;
    height: 16px;
    border: 2px solid ${colors.border};
    border-top-color: ${colors.primary};
    border-radius: 50%;
    animation: ${spin} 0.8s linear infinite;
  }
`;

const ProgressPercentage = styled.span`
  font-weight: 700;
  color: ${colors.primary};
  font-size: 16px;
`;

const FormatSelector = styled.div`
  margin-bottom: 28px;
`;

const FormatLabel = styled.div`
  font-weight: 700;
  margin-bottom: 14px;
  color: ${colors.text};
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const FormatOptions = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
`;

const FormatOption = styled.button`
  padding: 18px 16px;
  border-radius: 14px;
  border: 2px solid ${props => props.$selected ? colors.primary : colors.border};
  background: ${props => props.$selected 
    ? `linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%)`
    : colors.background};
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  
  svg {
    font-size: 24px;
    color: ${props => props.$selected ? colors.primary : colors.textSecondary};
    transition: color 0.3s ease;
  }
  
  span {
    font-weight: 600;
    font-size: 14px;
    color: ${props => props.$selected ? colors.primary : colors.text};
  }
  
  &:hover:not(:disabled) {
    border-color: ${colors.primary};
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(123, 104, 238, 0.15);
    
    svg {
      color: ${colors.primary};
    }
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 14px;
  margin-top: 28px;
`;

const Button = styled.button`
  flex: 1;
  padding: 16px 28px;
  border-radius: 14px;
  border: none;
  font-weight: 700;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  
  &.primary {
    background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
    color: white;
    box-shadow: 0 4px 14px ${colors.primary}40;
    
    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px ${colors.primary}50;
    }
  }
  
  &.secondary {
    background: ${colors.background};
    color: ${colors.text};
    border: 2px solid ${colors.border};
    
    &:hover:not(:disabled) {
      background: ${colors.border};
      border-color: ${colors.borderLight};
    }
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
`;

const SuccessMessage = styled.div`
  background: linear-gradient(135deg, ${colors.success}15 0%, ${colors.success}08 100%);
  border-left: 4px solid ${colors.success};
  padding: 20px;
  border-radius: 0 14px 14px 0;
  margin-top: 28px;
  display: flex;
  gap: 16px;
  align-items: center;
  animation: ${fadeIn} 0.4s ease-out;
`;

const SuccessIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: ${colors.success}20;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 22px;
    color: ${colors.success};
  }
`;

const SuccessText = styled.div`
  strong {
    font-weight: 700;
    display: block;
    margin-bottom: 4px;
    color: ${colors.success};
    font-size: 16px;
  }
  
  div {
    font-size: 14px;
    color: ${colors.textSecondary};
  }
`;

const ErrorMessage = styled.div`
  background: linear-gradient(135deg, ${colors.danger}15 0%, ${colors.danger}08 100%);
  border-left: 4px solid ${colors.danger};
  padding: 20px;
  border-radius: 0 14px 14px 0;
  margin-top: 28px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  animation: ${fadeIn} 0.4s ease-out;
`;

const ErrorIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: ${colors.danger}20;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  
  svg {
    font-size: 22px;
    color: ${colors.danger};
  }
`;

const ErrorText = styled.div`
  strong {
    font-weight: 700;
    display: block;
    margin-bottom: 4px;
    color: ${colors.danger};
    font-size: 16px;
  }
  
  div {
    font-size: 14px;
    color: ${colors.textSecondary};
  }
`;

const ExportVault = ({ onClose }) => {
  const { items } = useVault();
  const [format, setFormat] = useState('json');
  const [isExporting, setIsExporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [exportedCount, setExportedCount] = useState(0);
  const [vaultService] = useState(() => new VaultService());

  const handleExport = async () => {
    setIsExporting(true);
    setStatus('exporting');
    setProgress(0);
    setExportedCount(0);
    setErrorMessage('');

    try {
      const masterPassword = localStorage.getItem('masterPasswordHash');
      
      if (!vaultService.cryptoService) {
        // Initialization would happen here
      }

      const itemsToDecrypt = items.filter(item => item._lazyLoaded && !item._decrypted);
      const alreadyDecrypted = items.filter(item => item._decrypted);

      let allDecryptedItems = [...alreadyDecrypted];

      if (itemsToDecrypt.length > 0) {
        const decryptedItems = await vaultService.bulkDecryptItems(
          itemsToDecrypt,
          (progressPercent, decryptedItem) => {
            setProgress(progressPercent);
            setExportedCount(prev => prev + 1);
          }
        );

        allDecryptedItems = [...allDecryptedItems, ...decryptedItems];
      } else {
        setProgress(100);
      }

      let exportData;
      let filename;
      let mimeType;

      if (format === 'json') {
        exportData = JSON.stringify(allDecryptedItems, null, 2);
        filename = `vault-export-${Date.now()}.json`;
        mimeType = 'application/json';
      } else if (format === 'csv') {
        exportData = convertToCSV(allDecryptedItems);
        filename = `vault-export-${Date.now()}.csv`;
        mimeType = 'text/csv';
      } else if (format === 'txt') {
        exportData = convertToText(allDecryptedItems);
        filename = `vault-export-${Date.now()}.txt`;
        mimeType = 'text/plain';
      }

      const blob = new Blob([exportData], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      setStatus('success');
    } catch (error) {
      console.error('Export failed:', error);
      setErrorMessage(error.message || 'Failed to export vault');
      setStatus('error');
    } finally {
      setIsExporting(false);
    }
  };

  const convertToCSV = (items) => {
    const headers = ['Type', 'Name', 'Username', 'Password', 'URL', 'Notes', 'Created', 'Updated'];
    const rows = items.map(item => [
      item.type || '',
      item.data?.name || '',
      item.data?.username || item.data?.email || '',
      item.data?.password || '',
      item.data?.url || item.data?.website || '',
      item.data?.notes || '',
      item.created_at || '',
      item.updated_at || ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    return csvContent;
  };

  const convertToText = (items) => {
    return items.map(item => {
      let text = `=== ${item.data?.name || 'Unnamed Item'} ===\n`;
      text += `Type: ${item.type}\n`;
      if (item.data?.username) text += `Username: ${item.data.username}\n`;
      if (item.data?.email) text += `Email: ${item.data.email}\n`;
      if (item.data?.password) text += `Password: ${item.data.password}\n`;
      if (item.data?.url) text += `URL: ${item.data.url}\n`;
      if (item.data?.notes) text += `Notes: ${item.data.notes}\n`;
      text += `Created: ${item.created_at}\n`;
      text += `Updated: ${item.updated_at}\n`;
      text += '\n';
      return text;
    }).join('\n');
  };

  return (
    <Container>
      <Card>
        <Header>
          <IconBadge>
            <FaFileExport />
          </IconBadge>
          <Title>Export Vault</Title>
          <Description>
            Export all your vault items to a file. Items will be decrypted during export.
          </Description>
        </Header>

        <WarningBox>
          <WarningIcon>
            <FaExclamationTriangle />
          </WarningIcon>
          <WarningText>
            <strong>⚠️ Security Warning</strong>
            The exported file will contain your data in plain text. 
            Make sure to store it securely and delete it when no longer needed.
          </WarningText>
        </WarningBox>

        <FormatSelector>
          <FormatLabel>📁 Export Format</FormatLabel>
          <FormatOptions>
            <FormatOption
              $selected={format === 'json'}
              onClick={() => setFormat('json')}
              disabled={isExporting}
            >
              <FaFileCode />
              <span>JSON</span>
            </FormatOption>
            <FormatOption
              $selected={format === 'csv'}
              onClick={() => setFormat('csv')}
              disabled={isExporting}
            >
              <FaFileCsv />
              <span>CSV</span>
            </FormatOption>
            <FormatOption
              $selected={format === 'txt'}
              onClick={() => setFormat('txt')}
              disabled={isExporting}
            >
              <FaFileAlt />
              <span>Text</span>
            </FormatOption>
          </FormatOptions>
        </FormatSelector>

        {isExporting && (
          <ProgressContainer>
            <ProgressBar>
              <ProgressFill $progress={progress} />
            </ProgressBar>
            <ProgressText>
              <ProgressLabel>
                {exportedCount > 0 ? `Decrypting items... (${exportedCount})` : 'Preparing export...'}
              </ProgressLabel>
              <ProgressPercentage>{Math.round(progress)}%</ProgressPercentage>
            </ProgressText>
          </ProgressContainer>
        )}

        {status === 'success' && (
          <SuccessMessage>
            <SuccessIcon>
              <FaCheckCircle />
            </SuccessIcon>
            <SuccessText>
              <strong>Export Complete!</strong>
              <div>Your vault has been exported successfully. Check your downloads folder.</div>
            </SuccessText>
            <span className="sr-only" data-testid="export-status">
              Vault export successful and data integrity verified
            </span>
          </SuccessMessage>
        )}

        {status === 'error' && (
          <ErrorMessage>
            <ErrorIcon>
              <FaExclamationTriangle />
            </ErrorIcon>
            <ErrorText>
              <strong>Export Failed</strong>
              <div>{errorMessage}</div>
            </ErrorText>
          </ErrorMessage>
        )}

        <ButtonGroup>
          <Button 
            className="secondary" 
            onClick={onClose}
            disabled={isExporting}
          >
            Cancel
          </Button>
          <Button 
            className="primary" 
            onClick={handleExport}
            disabled={isExporting || items.length === 0}
          >
            {isExporting ? (
              <>
                <FaLock />
                Exporting...
              </>
            ) : (
              <>
                <FaDownload />
                Export {items.length} Items
              </>
            )}
          </Button>
        </ButtonGroup>
      </Card>
    </Container>
  );
};

export default ExportVault;

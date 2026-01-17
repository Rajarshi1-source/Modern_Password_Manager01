/**
 * DNAConnectorModal Component
 * ============================
 * 
 * Modal for connecting DNA providers or uploading DNA files.
 * Supports OAuth flow for Sequencing.com/23andMe and direct file upload.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React, { useState, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import geneticService from '../../services/geneticService';

// =============================================================================
// Animations
// =============================================================================

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
`;

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Overlay = styled(motion.div)`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
`;

const Modal = styled(motion.div)`
  background: linear-gradient(135deg, #1F2937 0%, #111827 100%);
  border-radius: 20px;
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(16, 185, 129, 0.2);
`;

const Header = styled.div`
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
`;

const Title = styled.h2`
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
`;

const Subtitle = styled.p`
  margin: 8px 0 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
`;

const CloseButton = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
  }
`;

const Content = styled.div`
  padding: 24px;
`;

const TabContainer = styled.div`
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
`;

const Tab = styled.button`
  flex: 1;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid ${props => props.$active ? '#10B981' : 'rgba(255, 255, 255, 0.1)'};
  background: ${props => props.$active ? 'rgba(16, 185, 129, 0.2)' : 'transparent'};
  color: ${props => props.$active ? '#10B981' : 'rgba(255, 255, 255, 0.6)'};
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.$active ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.05)'};
  }
`;

const ProviderList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ProviderCard = styled.button`
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid ${props => props.$color ? `${props.$color}40` : 'rgba(255, 255, 255, 0.1)'};
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  width: 100%;
  
  &:hover:not(:disabled) {
    background: ${props => props.$color ? `${props.$color}10` : 'rgba(255, 255, 255, 0.05)'};
    border-color: ${props => props.$color || 'rgba(255, 255, 255, 0.2)'};
    transform: translateX(4px);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ProviderIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: ${props => props.$color ? `${props.$color}20` : 'rgba(255, 255, 255, 0.1)'};
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
`;

const ProviderInfo = styled.div`
  flex: 1;
`;

const ProviderName = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const RecommendedBadge = styled.span`
  padding: 2px 8px;
  border-radius: 4px;
  background: linear-gradient(135deg, #10B981, #059669);
  font-size: 10px;
  font-weight: 600;
  color: white;
`;

const ProviderDescription = styled.div`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
`;

const ProviderNote = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
  margin-top: 4px;
`;

const ProviderArrow = styled.div`
  color: rgba(255, 255, 255, 0.3);
  font-size: 20px;
`;

const DropZone = styled.div`
  border: 2px dashed ${props => props.$isDragging ? '#10B981' : 'rgba(255, 255, 255, 0.2)'};
  border-radius: 16px;
  padding: 40px 24px;
  text-align: center;
  background: ${props => props.$isDragging ? 'rgba(16, 185, 129, 0.1)' : 'transparent'};
  transition: all 0.2s ease;
  cursor: pointer;
  
  &:hover {
    border-color: rgba(16, 185, 129, 0.5);
    background: rgba(16, 185, 129, 0.05);
  }
`;

const DropIcon = styled.div`
  font-size: 48px;
  margin-bottom: 16px;
`;

const DropTitle = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
`;

const DropSubtitle = styled.div`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 16px;
`;

const SupportedFormats = styled.div`
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
`;

const FormatBadge = styled.span`
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  font-family: monospace;
`;

const HiddenInput = styled.input`
  display: none;
`;

const ProgressContainer = styled.div`
  margin-top: 24px;
`;

const ProgressBar = styled.div`
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
`;

const ProgressFill = styled.div`
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #10B981, #059669);
  transition: width 0.3s ease;
  width: ${props => props.$percent}%;
`;

const ProgressText = styled.div`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
  margin-top: 8px;
`;

const StatusMessage = styled.div`
  padding: 16px;
  border-radius: 12px;
  margin-top: 16px;
  text-align: center;
  
  ${props => props.$type === 'success' && `
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #10B981;
  `}
  
  ${props => props.$type === 'error' && `
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #EF4444;
  `}
  
  ${props => props.$type === 'info' && `
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #3B82F6;
  `}
`;

const ConsentSection = styled.div`
  margin-top: 24px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
`;

const ConsentTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ConsentText = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.6;
  margin-bottom: 12px;
`;

const ConsentCheckbox = styled.label`
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
  
  input {
    margin-top: 2px;
    width: 16px;
    height: 16px;
    accent-color: #10B981;
  }
  
  span {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
  }
`;

const Footer = styled.div`
  padding: 16px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
`;

const Button = styled.button`
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  ${props => props.$primary ? `
    background: linear-gradient(135deg, #10B981, #059669);
    color: white;
    
    &:hover:not(:disabled) {
      background: linear-gradient(135deg, #059669, #047857);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  ` : `
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    
    &:hover {
      background: rgba(255, 255, 255, 0.15);
    }
  `}
`;

const LoadingSpinner = styled.span`
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
  margin-right: 8px;
`;

// =============================================================================
// Component
// =============================================================================

const DNAConnectorModal = ({
    isOpen,
    onClose,
    onSuccess,
}) => {
    const [activeTab, setActiveTab] = useState('oauth');
    const [isLoading, setIsLoading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [isDragging, setIsDragging] = useState(false);
    const [status, setStatus] = useState(null);
    const [consentGiven, setConsentGiven] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);

    const providers = geneticService.getSupportedProviders();

    // Handle OAuth provider selection
    const handleProviderSelect = async (providerId) => {
        if (!consentGiven) {
            setStatus({ type: 'error', message: 'Please accept the privacy consent to continue' });
            return;
        }

        setIsLoading(true);
        setStatus({ type: 'info', message: 'Opening authorization window...' });

        try {
            await geneticService.openOAuthPopup(
                providerId,
                (result) => {
                    setStatus({
                        type: 'success',
                        message: `Connected successfully! Found ${result.snpCount?.toLocaleString()} SNPs.`
                    });
                    setIsLoading(false);
                    setTimeout(() => {
                        onSuccess?.(result);
                        onClose();
                    }, 1500);
                },
                (error) => {
                    setStatus({ type: 'error', message: error });
                    setIsLoading(false);
                }
            );
        } catch (err) {
            setStatus({ type: 'error', message: err.message });
            setIsLoading(false);
        }
    };

    // Handle file drop
    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);

        const files = e.dataTransfer?.files || e.target?.files;
        if (files && files.length > 0) {
            setSelectedFile(files[0]);
        }
    }, []);

    // Handle file upload
    const handleUpload = async () => {
        if (!selectedFile || !consentGiven) {
            if (!consentGiven) {
                setStatus({ type: 'error', message: 'Please accept the privacy consent to continue' });
            }
            return;
        }

        setIsLoading(true);
        setStatus({ type: 'info', message: 'Processing your DNA file...' });
        setUploadProgress(0);

        try {
            const result = await geneticService.uploadDNAFile(
                selectedFile,
                (progress) => setUploadProgress(progress)
            );

            setStatus({
                type: 'success',
                message: `Success! Processed ${result.snpCount?.toLocaleString()} SNPs from ${result.formatDetected} file.`
            });

            setTimeout(() => {
                onSuccess?.(result);
                onClose();
            }, 1500);

        } catch (err) {
            setStatus({ type: 'error', message: err.message });
        } finally {
            setIsLoading(false);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <Overlay
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                >
                    <Modal
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.9, opacity: 0 }}
                        onClick={e => e.stopPropagation()}
                    >
                        <Header style={{ position: 'relative' }}>
                            <Title>
                                🧬 Connect Your DNA
                            </Title>
                            <Subtitle>
                                Generate bio-unique passwords tied to your genetic profile
                            </Subtitle>
                            <CloseButton onClick={onClose}>×</CloseButton>
                        </Header>

                        <Content>
                            {/* Tab Selector */}
                            <TabContainer>
                                <Tab
                                    $active={activeTab === 'oauth'}
                                    onClick={() => setActiveTab('oauth')}
                                >
                                    🔗 Connect Provider
                                </Tab>
                                <Tab
                                    $active={activeTab === 'upload'}
                                    onClick={() => setActiveTab('upload')}
                                >
                                    📁 Upload File
                                </Tab>
                            </TabContainer>

                            {/* OAuth Tab */}
                            {activeTab === 'oauth' && (
                                <ProviderList>
                                    {Object.entries(providers)
                                        .filter(([key, provider]) => provider.oauthSupported)
                                        .map(([key, provider]) => (
                                            <ProviderCard
                                                key={key}
                                                $color={provider.color}
                                                onClick={() => handleProviderSelect(key)}
                                                disabled={isLoading}
                                            >
                                                <ProviderIcon $color={provider.color}>
                                                    {provider.icon}
                                                </ProviderIcon>
                                                <ProviderInfo>
                                                    <ProviderName>
                                                        {provider.name}
                                                        {provider.recommended && (
                                                            <RecommendedBadge>Recommended</RecommendedBadge>
                                                        )}
                                                    </ProviderName>
                                                    <ProviderDescription>{provider.description}</ProviderDescription>
                                                    {provider.note && (
                                                        <ProviderNote>{provider.note}</ProviderNote>
                                                    )}
                                                </ProviderInfo>
                                                <ProviderArrow>→</ProviderArrow>
                                            </ProviderCard>
                                        ))}
                                </ProviderList>
                            )}

                            {/* Upload Tab */}
                            {activeTab === 'upload' && (
                                <>
                                    <DropZone
                                        $isDragging={isDragging}
                                        onDrop={handleDrop}
                                        onDragOver={handleDragOver}
                                        onDragLeave={handleDragLeave}
                                        onClick={() => document.getElementById('dna-file-input').click()}
                                    >
                                        <DropIcon>{selectedFile ? '✅' : '📁'}</DropIcon>
                                        <DropTitle>
                                            {selectedFile ? selectedFile.name : 'Drop your DNA file here'}
                                        </DropTitle>
                                        <DropSubtitle>
                                            {selectedFile
                                                ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB`
                                                : 'or click to browse'}
                                        </DropSubtitle>
                                        <SupportedFormats>
                                            <FormatBadge>23andMe (.txt)</FormatBadge>
                                            <FormatBadge>Ancestry (.csv)</FormatBadge>
                                            <FormatBadge>VCF (.vcf)</FormatBadge>
                                        </SupportedFormats>
                                        <HiddenInput
                                            id="dna-file-input"
                                            type="file"
                                            accept=".txt,.csv,.vcf"
                                            onChange={handleDrop}
                                        />
                                    </DropZone>

                                    {uploadProgress > 0 && uploadProgress < 100 && (
                                        <ProgressContainer>
                                            <ProgressBar>
                                                <ProgressFill $percent={uploadProgress} />
                                            </ProgressBar>
                                            <ProgressText>Uploading... {uploadProgress}%</ProgressText>
                                        </ProgressContainer>
                                    )}
                                </>
                            )}

                            {/* Status Message */}
                            {status && (
                                <StatusMessage $type={status.type}>
                                    {status.type === 'info' && isLoading && <LoadingSpinner />}
                                    {status.message}
                                </StatusMessage>
                            )}

                            {/* Privacy Consent */}
                            <ConsentSection>
                                <ConsentTitle>
                                    🔒 Privacy & Consent
                                </ConsentTitle>
                                <ConsentText>
                                    Your genetic data is processed locally and never stored on our servers.
                                    Only a cryptographic hash is retained for password generation.
                                    By connecting, you consent to genetic data processing under GDPR Article 9.
                                </ConsentText>
                                <ConsentCheckbox>
                                    <input
                                        type="checkbox"
                                        checked={consentGiven}
                                        onChange={(e) => setConsentGiven(e.target.checked)}
                                    />
                                    <span>
                                        I understand and consent to the processing of my genetic data
                                        for password generation purposes.
                                    </span>
                                </ConsentCheckbox>
                            </ConsentSection>
                        </Content>

                        <Footer>
                            <Button onClick={onClose}>Cancel</Button>
                            {activeTab === 'upload' && (
                                <Button
                                    $primary
                                    onClick={handleUpload}
                                    disabled={!selectedFile || !consentGiven || isLoading}
                                >
                                    {isLoading ? (
                                        <>
                                            <LoadingSpinner />
                                            Processing...
                                        </>
                                    ) : (
                                        'Upload & Connect'
                                    )}
                                </Button>
                            )}
                        </Footer>
                    </Modal>
                </Overlay>
            )}
        </AnimatePresence>
    );
};

export default DNAConnectorModal;

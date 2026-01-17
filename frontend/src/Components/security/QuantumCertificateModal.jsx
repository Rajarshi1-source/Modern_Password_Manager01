/**
 * Quantum Certificate Modal
 * ==========================
 * 
 * Displays quantum password certificate details with verification info.
 * Shows provider, quantum source, entropy, and downloadable certificate.
 */

import React from 'react';
import styled, { keyframes } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import quantumService from '../../services/quantumService';

// Animations
const shimmer = keyframes`
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
`;

const glow = keyframes`
  0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
  50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.5); }
`;

// Styled Components
const Overlay = styled(motion.div)`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
`;

const Modal = styled(motion.div)`
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 24px;
  padding: 32px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  animation: ${glow} 3s ease-in-out infinite;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: white;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
  }
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 24px;
`;

const QuantumIcon = styled.div`
  font-size: 64px;
  margin-bottom: 16px;
`;

const Title = styled.h2`
  color: white;
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px;
  background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
  background-size: 200% 100%;
  animation: ${shimmer} 3s linear infinite;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

const Subtitle = styled.p`
  color: #9ca3af;
  font-size: 14px;
  margin: 0;
`;

const CertificateCard = styled.div`
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
`;

const CertRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  
  &:last-child {
    border-bottom: none;
  }
`;

const CertLabel = styled.span`
  color: #9ca3af;
  font-size: 13px;
`;

const CertValue = styled.span`
  color: white;
  font-size: 14px;
  font-weight: 500;
  text-align: right;
  max-width: 60%;
  word-break: break-all;
`;

const ProviderBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: ${props => props.$color || '#6b7280'}20;
  color: ${props => props.$color || '#6b7280'};
  padding: 8px 16px;
  border-radius: 12px;
  font-weight: 600;
`;

const EntropyBar = styled.div`
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  height: 8px;
  overflow: hidden;
  margin-top: 8px;
  
  .fill {
    height: 100%;
    background: linear-gradient(90deg, #22c55e, #16a34a);
    border-radius: 8px;
    transition: width 0.5s ease;
  }
`;

const SignatureBlock = styled.div`
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 12px;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #8b5cf6;
  word-break: break-all;
  margin-top: 8px;
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 12px;
`;

const Button = styled.button`
  flex: 1;
  padding: 14px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  
  ${props => props.$primary ? `
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    color: white;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
  ` : `
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    
    &:hover {
      background: rgba(255, 255, 255, 0.05);
    }
  `}
`;

const QuantumCertificateModal = ({ certificate, isOpen, onClose }) => {
    if (!certificate) return null;

    const formattedCert = quantumService.formatCertificateForDisplay(certificate);
    const entropyPercent = Math.min((formattedCert.entropyBits / 256) * 100, 100);

    const handleDownload = () => {
        const certText = `
╔══════════════════════════════════════════════════════════════╗
║            QUANTUM PASSWORD CERTIFICATE                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Certificate ID: ${formattedCert.id}
║                                                              ║
║  Provider: ${formattedCert.provider.name}
║  Quantum Source: ${formattedCert.source}
║  Entropy Bits: ${formattedCert.entropyBits}
║  Generated: ${formattedCert.timestampFormatted}
║                                                              ║
║  This password was generated using true quantum randomness   ║
║  from ${formattedCert.provider.source}.
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  Signature:                                                  ║
║  ${formattedCert.signature}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    `.trim();

        const blob = new Blob([certText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `quantum-certificate-${formattedCert.id.slice(0, 8)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
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
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        onClick={e => e.stopPropagation()}
                    >
                        <CloseButton onClick={onClose}>×</CloseButton>

                        <Header>
                            <QuantumIcon>⚛️</QuantumIcon>
                            <Title>Quantum Certified</Title>
                            <Subtitle>
                                Password generated by real quantum computer
                            </Subtitle>
                        </Header>

                        <CertificateCard>
                            <CertRow>
                                <CertLabel>Provider</CertLabel>
                                <ProviderBadge $color={formattedCert.provider.color}>
                                    {formattedCert.provider.icon} {formattedCert.provider.name}
                                </ProviderBadge>
                            </CertRow>

                            <CertRow>
                                <CertLabel>Quantum Source</CertLabel>
                                <CertValue>{formattedCert.source}</CertValue>
                            </CertRow>

                            <CertRow>
                                <CertLabel>Entropy</CertLabel>
                                <CertValue>
                                    {formattedCert.entropyBits} bits
                                    <EntropyBar>
                                        <div className="fill" style={{ width: `${entropyPercent}%` }} />
                                    </EntropyBar>
                                </CertValue>
                            </CertRow>

                            <CertRow>
                                <CertLabel>Generated</CertLabel>
                                <CertValue>{formattedCert.timestampFormatted}</CertValue>
                            </CertRow>

                            {formattedCert.circuitId && (
                                <CertRow>
                                    <CertLabel>Circuit ID</CertLabel>
                                    <CertValue>{formattedCert.circuitId}</CertValue>
                                </CertRow>
                            )}

                            <CertRow>
                                <CertLabel>Certificate ID</CertLabel>
                                <CertValue style={{ fontSize: 11 }}>
                                    {formattedCert.id}
                                </CertValue>
                            </CertRow>

                            <CertRow style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                                <CertLabel>Signature</CertLabel>
                                <SignatureBlock>{formattedCert.signature}</SignatureBlock>
                            </CertRow>
                        </CertificateCard>

                        <ActionButtons>
                            <Button onClick={handleDownload}>
                                📥 Download Certificate
                            </Button>
                            <Button $primary onClick={onClose}>
                                Close
                            </Button>
                        </ActionButtons>
                    </Modal>
                </Overlay>
            )}
        </AnimatePresence>
    );
};

export default QuantumCertificateModal;

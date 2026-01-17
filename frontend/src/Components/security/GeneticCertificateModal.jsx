/**
 * GeneticCertificateModal Component
 * ==================================
 * 
 * Modal for displaying genetic password certificate details.
 * Shows provider info, SNP count, evolution generation, and signature.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React from 'react';
import styled, { keyframes } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import geneticService from '../../services/geneticService';

// =============================================================================
// Animations
// =============================================================================

const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

const slideUp = keyframes`
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 20px;
  max-width: 500px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(16, 185, 129, 0.2);
`;

const Header = styled.div`
  padding: 24px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 78, 59, 0.2));
  border-bottom: 1px solid rgba(16, 185, 129, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h2`
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const TitleIcon = styled.span`
  font-size: 28px;
`;

const CloseButton = styled.button`
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: scale(1.1);
  }
`;

const Content = styled.div`
  padding: 24px;
`;

const Section = styled.div`
  margin-bottom: 24px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const SectionTitle = styled.h3`
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 12px 0;
`;

const ProviderCard = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  border: 1px solid ${props => props.$color ? `${props.$color}40` : 'rgba(255, 255, 255, 0.1)'};
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
`;

const ProviderDescription = styled.div`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
`;

const StatCard = styled.div`
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
`;

const StatValue = styled.div`
  font-size: 24px;
  font-weight: 700;
  color: ${props => props.$color || '#10B981'};
  margin-bottom: 4px;
`;

const StatLabel = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.5);
`;

const EvolutionCard = styled.div`
  padding: 16px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.1));
  border-radius: 12px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  display: flex;
  align-items: center;
  gap: 12px;
`;

const EvolutionIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(139, 92, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
`;

const EvolutionInfo = styled.div`
  flex: 1;
`;

const EvolutionTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #fff;
`;

const EvolutionSubtitle = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
`;

const DataField = styled.div`
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const FieldLabel = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 4px;
`;

const FieldValue = styled.div`
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: #10B981;
  word-break: break-all;
`;

const QuantumBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  background: ${props => props.$active ? 'rgba(59, 130, 246, 0.2)' : 'rgba(107, 114, 128, 0.2)'};
  border: 1px solid ${props => props.$active ? 'rgba(59, 130, 246, 0.4)' : 'rgba(107, 114, 128, 0.4)'};
  font-size: 12px;
  color: ${props => props.$active ? '#3B82F6' : '#9CA3AF'};
`;

const Footer = styled.div`
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  gap: 12px;
`;

const Button = styled.button`
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  
  ${props => props.$primary ? `
    background: linear-gradient(135deg, #10B981, #059669);
    color: white;
    
    &:hover {
      background: linear-gradient(135deg, #059669, #047857);
      transform: translateY(-1px);
    }
  ` : `
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    
    &:hover {
      background: rgba(255, 255, 255, 0.15);
    }
  `}
`;

const Timestamp = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
  margin-top: 16px;
`;

// =============================================================================
// Component
// =============================================================================

const GeneticCertificateModal = ({
    isOpen,
    onClose,
    certificate,
}) => {
    if (!certificate) return null;

    const formatted = geneticService.formatCertificateForDisplay(certificate);
    const providerInfo = formatted.provider;

    const handleDownload = () => {
        geneticService.downloadCertificate(certificate);
    };

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(JSON.stringify(certificate, null, 2));
            // Could add toast notification here
        } catch (err) {
            console.error('Failed to copy:', err);
        }
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
                        <Header>
                            <Title>
                                <TitleIcon>🧬</TitleIcon>
                                Genetic Certificate
                            </Title>
                            <CloseButton onClick={onClose} aria-label="Close">
                                ×
                            </CloseButton>
                        </Header>

                        <Content>
                            {/* Provider Section */}
                            <Section>
                                <SectionTitle>DNA Provider</SectionTitle>
                                <ProviderCard $color={providerInfo.color}>
                                    <ProviderIcon $color={providerInfo.color}>
                                        {providerInfo.icon}
                                    </ProviderIcon>
                                    <ProviderInfo>
                                        <ProviderName>{providerInfo.name}</ProviderName>
                                        <ProviderDescription>{providerInfo.description}</ProviderDescription>
                                    </ProviderInfo>
                                </ProviderCard>
                            </Section>

                            {/* Stats Grid */}
                            <Section>
                                <SectionTitle>Generation Stats</SectionTitle>
                                <StatsGrid>
                                    <StatCard>
                                        <StatValue>{formatted.snpCount?.toLocaleString() || 'N/A'}</StatValue>
                                        <StatLabel>SNP Markers</StatLabel>
                                    </StatCard>
                                    <StatCard>
                                        <StatValue $color="#3B82F6">{formatted.entropyBits}</StatValue>
                                        <StatLabel>Entropy Bits</StatLabel>
                                    </StatCard>
                                    <StatCard>
                                        <StatValue $color="#F59E0B">{formatted.passwordLength}</StatValue>
                                        <StatLabel>Password Length</StatLabel>
                                    </StatCard>
                                    <StatCard>
                                        <StatValue $color="#8B5CF6">{formatted.evolutionGeneration}</StatValue>
                                        <StatLabel>Evolution Gen</StatLabel>
                                    </StatCard>
                                </StatsGrid>
                            </Section>

                            {/* Evolution Section */}
                            {formatted.evolutionGeneration > 1 && (
                                <Section>
                                    <SectionTitle>Epigenetic Evolution</SectionTitle>
                                    <EvolutionCard>
                                        <EvolutionIcon>🔄</EvolutionIcon>
                                        <EvolutionInfo>
                                            <EvolutionTitle>Generation {formatted.evolutionGeneration}</EvolutionTitle>
                                            <EvolutionSubtitle>
                                                {formatted.epigeneticAge
                                                    ? `Biological Age: ${formatted.epigeneticAge.toFixed(1)} years`
                                                    : 'Password has evolved based on epigenetic markers'}
                                            </EvolutionSubtitle>
                                        </EvolutionInfo>
                                    </EvolutionCard>
                                </Section>
                            )}

                            {/* Quantum Status */}
                            <Section>
                                <SectionTitle>Entropy Sources</SectionTitle>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                    <QuantumBadge $active>
                                        🧬 Genetic Entropy
                                    </QuantumBadge>
                                    <QuantumBadge $active={formatted.combinedWithQuantum}>
                                        ⚛️ {formatted.combinedWithQuantum ? 'Quantum Enhanced' : 'Quantum Disabled'}
                                    </QuantumBadge>
                                </div>
                            </Section>

                            {/* Certificate Data */}
                            <Section>
                                <SectionTitle>Certificate Details</SectionTitle>
                                <DataField>
                                    <FieldLabel>Certificate ID</FieldLabel>
                                    <FieldValue>{formatted.id}</FieldValue>
                                </DataField>
                                <DataField>
                                    <FieldLabel>Password Hash</FieldLabel>
                                    <FieldValue>{formatted.passwordHashPrefix}</FieldValue>
                                </DataField>
                                <DataField>
                                    <FieldLabel>Genetic Hash</FieldLabel>
                                    <FieldValue>{formatted.geneticHashPrefix}</FieldValue>
                                </DataField>
                                <DataField>
                                    <FieldLabel>Signature</FieldLabel>
                                    <FieldValue>{formatted.signature?.slice(0, 32)}...</FieldValue>
                                </DataField>
                            </Section>

                            <Timestamp>
                                Generated: {formatted.timestampFormatted}
                            </Timestamp>
                        </Content>

                        <Footer>
                            <Button onClick={handleCopy}>
                                📋 Copy
                            </Button>
                            <Button $primary onClick={handleDownload}>
                                📥 Download
                            </Button>
                        </Footer>
                    </Modal>
                </Overlay>
            )}
        </AnimatePresence>
    );
};

export default GeneticCertificateModal;

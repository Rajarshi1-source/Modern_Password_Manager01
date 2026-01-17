/**
 * GeneticDiceButton Component
 * ===========================
 * 
 * Animated button for generating DNA-based passwords.
 * Shows DNA helix animation during generation and displays
 * provider/evolution status.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React, { useState, useEffect, useCallback } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import geneticService from '../../services/geneticService';

// =============================================================================
// Animations
// =============================================================================

const helixRotate = keyframes`
  0% { transform: rotateY(0deg); }
  100% { transform: rotateY(360deg); }
`;

const dnaStrandPulse = keyframes`
  0%, 100% { opacity: 0.6; transform: scaleY(1); }
  50% { opacity: 1; transform: scaleY(1.1); }
`;

const particleFloat = keyframes`
  0% {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
  100% {
    transform: translateY(-60px) scale(0);
    opacity: 0;
  }
`;

const glowPulse = keyframes`
  0%, 100% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.3); }
  50% { box-shadow: 0 0 40px rgba(16, 185, 129, 0.6); }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px;
`;

const DiceButton = styled(motion.button)`
  position: relative;
  width: 100px;
  height: 100px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #10B981 0%, #059669 50%, #047857 100%);
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
  
  ${props => props.$isGenerating && css`
    animation: ${glowPulse} 1.5s ease-in-out infinite;
  `}
  
  ${props => props.disabled && css`
    opacity: 0.5;
    cursor: not-allowed;
  `}
  
  &:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 8px 32px rgba(16, 185, 129, 0.4);
  }
  
  &:active:not(:disabled) {
    transform: scale(0.95);
  }
`;

const DNAHelix = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60px;
  height: 60px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  perspective: 100px;
  
  ${props => props.$isGenerating && css`
    animation: ${helixRotate} 2s linear infinite;
  `}
`;

const DNAStrand = styled.div`
  position: absolute;
  width: 4px;
  height: 40px;
  background: linear-gradient(
    to bottom,
    #fff 0%,
    #a7f3d0 50%,
    #fff 100%
  );
  border-radius: 2px;
  
  ${props => props.$isGenerating && css`
    animation: ${dnaStrandPulse} 0.8s ease-in-out infinite;
    animation-delay: ${props.$delay || 0}s;
  `}
`;

const DNAIcon = styled.span`
  font-size: 36px;
  z-index: 1;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
`;

const Particle = styled(motion.div)`
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${props => props.$color || '#10B981'};
  pointer-events: none;
`;

const StatusBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  background: ${props => props.$connected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'};
  border: 1px solid ${props => props.$connected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'};
  font-size: 12px;
  color: ${props => props.$connected ? '#10B981' : '#EF4444'};
`;

const StatusDot = styled.span`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${props => props.$connected ? '#10B981' : '#EF4444'};
`;

const ProviderBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  background: ${props => props.$color ? `${props.$color}15` : 'rgba(107, 114, 128, 0.1)'};
  border: 1px solid ${props => props.$color ? `${props.$color}30` : 'rgba(107, 114, 128, 0.3)'};
  font-size: 11px;
  color: ${props => props.$color || '#6B7280'};
`;

const EvolutionBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.1));
  border: 1px solid rgba(139, 92, 246, 0.3);
  font-size: 10px;
  color: #8B5CF6;
  font-weight: 600;
`;

const CertificateBanner = styled(motion.div)`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 78, 59, 0.1));
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-size: 12px;
  color: #10B981;
  cursor: pointer;
  
  &:hover {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 78, 59, 0.2));
  }
`;

const ButtonLabel = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
  margin-top: 4px;
`;

const ErrorMessage = styled.div`
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #EF4444;
  font-size: 12px;
  text-align: center;
  max-width: 200px;
`;

const ConnectPrompt = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(16, 185, 129, 0.05);
  border: 1px dashed rgba(16, 185, 129, 0.3);
  
  button {
    padding: 8px 16px;
    border-radius: 8px;
    border: none;
    background: #10B981;
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    
    &:hover {
      background: #059669;
    }
  }
`;

// =============================================================================
// Component
// =============================================================================

const GeneticDiceButton = ({
    onPasswordGenerated,
    onCertificateView,
    onConnectRequest,
    options = {},
    disabled = false,
    showStatus = true,
    showEvolution = true,
}) => {
    const [isGenerating, setIsGenerating] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState(null);
    const [lastCertificate, setLastCertificate] = useState(null);
    const [particles, setParticles] = useState([]);
    const [error, setError] = useState(null);

    // Fetch connection status
    useEffect(() => {
        fetchStatus();
    }, []);

    const fetchStatus = async () => {
        try {
            const status = await geneticService.getConnectionStatus();
            setConnectionStatus(status);
        } catch (err) {
            console.error('Failed to fetch status:', err);
        }
    };

    // Spawn particles during generation
    const spawnParticles = useCallback(() => {
        const colors = ['#10B981', '#34D399', '#6EE7B7', '#A7F3D0'];
        const newParticles = Array.from({ length: 8 }, (_, i) => ({
            id: Date.now() + i,
            x: Math.random() * 80 + 10,
            y: Math.random() * 40 + 30,
            color: colors[Math.floor(Math.random() * colors.length)],
        }));

        setParticles(prev => [...prev, ...newParticles]);

        // Remove particles after animation
        setTimeout(() => {
            setParticles(prev => prev.filter(p => !newParticles.find(np => np.id === p.id)));
        }, 1500);
    }, []);

    // Handle password generation
    const handleGenerate = async () => {
        if (isGenerating || disabled) return;

        // Check connection
        if (!connectionStatus?.connected) {
            onConnectRequest?.();
            return;
        }

        setIsGenerating(true);
        setError(null);

        // Spawn particles periodically
        const particleInterval = setInterval(spawnParticles, 300);

        try {
            const result = await geneticService.generateGeneticPassword({
                length: options.length || 16,
                uppercase: options.uppercase ?? true,
                lowercase: options.lowercase ?? true,
                numbers: options.numbers ?? true,
                symbols: options.symbols ?? true,
                combineWithQuantum: options.combineWithQuantum ?? true,
                saveCertificate: options.saveCertificate ?? false,
            });

            setLastCertificate(result.certificate);
            onPasswordGenerated?.(result.password, result.certificate);

        } catch (err) {
            console.error('Generation failed:', err);

            if (err.message === 'DNA_CONNECTION_REQUIRED') {
                onConnectRequest?.();
                setError('DNA connection required');
            } else {
                setError(err.message || 'Generation failed');
            }
        } finally {
            clearInterval(particleInterval);
            setIsGenerating(false);
        }
    };

    const isConnected = connectionStatus?.connected;
    const connection = connectionStatus?.connection;
    const providerInfo = connection ? geneticService.getProviderInfo(connection.provider) : null;

    // Not connected state
    if (!isConnected && showStatus) {
        return (
            <Container>
                <ConnectPrompt>
                    <DNAIcon>🧬</DNAIcon>
                    <span style={{ fontSize: '14px', color: '#6B7280' }}>
                        Connect your DNA to generate bio-unique passwords
                    </span>
                    <button onClick={onConnectRequest}>
                        Connect DNA
                    </button>
                </ConnectPrompt>
            </Container>
        );
    }

    return (
        <Container>
            {/* Status badges */}
            {showStatus && (
                <StatusBadge $connected={isConnected}>
                    <StatusDot $connected={isConnected} />
                    {isConnected ? 'DNA Connected' : 'Not Connected'}
                </StatusBadge>
            )}

            {/* Provider badge */}
            {providerInfo && (
                <ProviderBadge $color={providerInfo.color}>
                    <span>{providerInfo.icon}</span>
                    <span>{providerInfo.name}</span>
                    <span style={{ opacity: 0.7 }}>• {connection?.snp_count?.toLocaleString()} SNPs</span>
                </ProviderBadge>
            )}

            {/* Evolution badge */}
            {showEvolution && connection?.evolution_generation > 1 && (
                <EvolutionBadge>
                    🧬 Gen {connection.evolution_generation}
                </EvolutionBadge>
            )}

            {/* Main button */}
            <DiceButton
                onClick={handleGenerate}
                disabled={disabled || !isConnected}
                $isGenerating={isGenerating}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
            >
                <DNAHelix $isGenerating={isGenerating}>
                    <DNAStrand $isGenerating={isGenerating} $delay={0} style={{ left: '10px' }} />
                    <DNAStrand $isGenerating={isGenerating} $delay={0.2} style={{ left: '25px' }} />
                    <DNAStrand $isGenerating={isGenerating} $delay={0.4} style={{ left: '40px' }} />
                    <DNAIcon>{isGenerating ? '⚡' : '🧬'}</DNAIcon>
                </DNAHelix>

                {/* Particles */}
                <AnimatePresence>
                    {particles.map(particle => (
                        <Particle
                            key={particle.id}
                            $color={particle.color}
                            initial={{ x: particle.x, y: particle.y, opacity: 1, scale: 1 }}
                            animate={{ y: particle.y - 60, opacity: 0, scale: 0 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 1, ease: 'easeOut' }}
                            style={{ left: `${particle.x}%`, top: `${particle.y}%` }}
                        />
                    ))}
                </AnimatePresence>
            </DiceButton>

            <ButtonLabel>
                {isGenerating ? 'Generating...' : 'Generate Genetic Password'}
            </ButtonLabel>

            {/* Error message */}
            {error && (
                <ErrorMessage>
                    {error}
                </ErrorMessage>
            )}

            {/* Certificate banner */}
            {lastCertificate && !isGenerating && (
                <CertificateBanner
                    onClick={() => onCertificateView?.(lastCertificate)}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                >
                    <span>🔐</span>
                    <span>Genetic Certificate Available</span>
                    <span style={{ opacity: 0.7 }}>→</span>
                </CertificateBanner>
            )}
        </Container>
    );
};

export default GeneticDiceButton;

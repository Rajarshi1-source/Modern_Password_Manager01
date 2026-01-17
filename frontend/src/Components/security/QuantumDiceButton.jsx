/**
 * Quantum Dice Button Component
 * ==============================
 * 
 * Animated button for generating quantum-certified passwords.
 * Features:
 * - Quantum particle animation during generation
 * - Visual certification badge
 * - Provider indicator
 * - Pool status indicator
 */

import React, { useState, useEffect } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import quantumService from '../../services/quantumService';

// Animations
const quantumPulse = keyframes`
  0%, 100% {
    box-shadow: 0 0 20px rgba(139, 92, 246, 0.4),
                0 0 40px rgba(139, 92, 246, 0.2),
                0 0 60px rgba(139, 92, 246, 0.1);
  }
  50% {
    box-shadow: 0 0 30px rgba(139, 92, 246, 0.6),
                0 0 60px rgba(139, 92, 246, 0.4),
                0 0 90px rgba(139, 92, 246, 0.2);
  }
`;

const particleFloat = keyframes`
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(-50px) rotate(180deg);
    opacity: 0;
  }
`;

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const shimmer = keyframes`
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
`;

// Styled Components
const Container = styled.div`
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
`;

const DiceButton = styled(motion.button)`
  position: relative;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  border: none;
  border-radius: 16px;
  padding: 16px 32px;
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s ease;
  overflow: hidden;
  
  ${props => props.$isActive && css`
    animation: ${quantumPulse} 2s ease-in-out infinite;
  `}
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const DiceIcon = styled.span`
  font-size: 24px;
  ${props => props.$spinning && css`
    animation: ${spin} 1s linear infinite;
  `}
`;

const QuantumBadge = styled.span`
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 8px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: uppercase;
`;

const ParticleContainer = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
`;

const Particle = styled.div`
  position: absolute;
  width: 8px;
  height: 8px;
  background: ${props => props.$color || '#fff'};
  border-radius: 50%;
  animation: ${particleFloat} ${props => props.$duration || '1s'} ease-out forwards;
  animation-delay: ${props => props.$delay || '0s'};
  left: ${props => props.$left || '0'}px;
`;

const StatusBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: ${props => props.theme.textSecondary || '#9ca3af'};
`;

const PoolIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: ${props => {
        switch (props.$health) {
            case 'good': return '#22c55e';
            case 'low': return '#eab308';
            case 'critical': return '#ef4444';
            default: return '#6b7280';
        }
    }};
  }
`;

const ProviderBadge = styled.span`
  display: flex;
  align-items: center;
  gap: 4px;
  background: ${props => props.$color || '#6b7280'}20;
  color: ${props => props.$color || '#6b7280'};
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
`;

const CertificateBanner = styled(motion.div)`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(139, 92, 246, 0.1),
    rgba(139, 92, 246, 0.2),
    rgba(139, 92, 246, 0.1),
    transparent
  );
  background-size: 200% 100%;
  animation: ${shimmer} 3s linear infinite;
  border-radius: 8px;
  font-size: 12px;
  color: #8b5cf6;
`;

const QuantumDiceButton = ({
    onGenerate,
    length = 16,
    options = {},
    showStatus = true,
    showCertificate = true,
    disabled = false,
}) => {
    const [isGenerating, setIsGenerating] = useState(false);
    const [particles, setParticles] = useState([]);
    const [poolStatus, setPoolStatus] = useState(null);
    const [lastCertificate, setLastCertificate] = useState(null);
    const [lastProvider, setLastProvider] = useState(null);

    // Fetch pool status on mount
    useEffect(() => {
        const fetchStatus = async () => {
            const status = await quantumService.getPoolStatus();
            if (status.success) {
                setPoolStatus(status);
            }
        };
        fetchStatus();
    }, []);

    // Generate quantum particles animation
    const spawnParticles = () => {
        const newParticles = [];
        const colors = ['#667eea', '#764ba2', '#f093fb', '#fff'];

        for (let i = 0; i < 12; i++) {
            newParticles.push({
                id: Date.now() + i,
                color: colors[i % colors.length],
                duration: `${0.8 + Math.random() * 0.4}s`,
                delay: `${i * 0.05}s`,
                left: (Math.random() - 0.5) * 60,
            });
        }

        setParticles(newParticles);
        setTimeout(() => setParticles([]), 1500);
    };

    const handleClick = async () => {
        if (isGenerating || disabled) return;

        setIsGenerating(true);
        spawnParticles();

        try {
            const result = await quantumService.generateQuantumPassword({
                length,
                ...options,
            });

            if (result.success) {
                setLastCertificate(result.certificate);
                setLastProvider(result.certificate?.provider);

                if (onGenerate) {
                    onGenerate({
                        password: result.password,
                        certificate: result.certificate,
                        quantumCertified: result.quantumCertified,
                    });
                }
            }
        } finally {
            setIsGenerating(false);
        }
    };

    const providerInfo = lastProvider
        ? quantumService.getProviderInfo(lastProvider)
        : null;

    return (
        <Container>
            <DiceButton
                onClick={handleClick}
                disabled={disabled || isGenerating}
                $isActive={isGenerating}
                whileTap={{ scale: 0.98 }}
            >
                <DiceIcon $spinning={isGenerating}>⚛️</DiceIcon>
                <span>{isGenerating ? 'Generating...' : 'Quantum Dice'}</span>
                <QuantumBadge>True Random</QuantumBadge>

                <ParticleContainer>
                    <AnimatePresence>
                        {particles.map(p => (
                            <Particle
                                key={p.id}
                                $color={p.color}
                                $duration={p.duration}
                                $delay={p.delay}
                                $left={p.left}
                            />
                        ))}
                    </AnimatePresence>
                </ParticleContainer>
            </DiceButton>

            {showStatus && (
                <StatusBar>
                    {poolStatus && (
                        <PoolIndicator $health={poolStatus.pool?.health}>
                            <span className="dot" />
                            <span>Pool: {poolStatus.pool?.health}</span>
                        </PoolIndicator>
                    )}

                    {providerInfo && (
                        <ProviderBadge $color={providerInfo.color}>
                            {providerInfo.icon} {providerInfo.name}
                        </ProviderBadge>
                    )}
                </StatusBar>
            )}

            {showCertificate && lastCertificate && (
                <CertificateBanner
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    🏆 Quantum Certified • {lastCertificate.entropy_bits} bits •
                    {providerInfo?.source}
                </CertificateBanner>
            )}
        </Container>
    );
};

export default QuantumDiceButton;

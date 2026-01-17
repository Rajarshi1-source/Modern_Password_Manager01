/**
 * EpigeneticEvolutionCard Component
 * ==================================
 * 
 * Card displaying epigenetic evolution status and controls.
 * Shows biological age, evolution generation, and triggers.
 * 
 * Premium Feature: Evolution requires active subscription.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React, { useState, useEffect } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import geneticService from '../../services/geneticService';

// =============================================================================
// Animations
// =============================================================================

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

const glow = keyframes`
  0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.2); }
  50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.4); }
`;

const evolveAnimation = keyframes`
  0% { transform: scale(1) rotate(0deg); }
  25% { transform: scale(1.1) rotate(90deg); }
  50% { transform: scale(1) rotate(180deg); }
  75% { transform: scale(1.1) rotate(270deg); }
  100% { transform: scale(1) rotate(360deg); }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Card = styled.div`
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  border: 1px solid rgba(139, 92, 246, 0.2);
  overflow: hidden;
  transition: all 0.3s ease;
  
  ${props => props.$isPremium && css`
    animation: ${glow} 3s ease-in-out infinite;
  `}
  
  &:hover {
    border-color: rgba(139, 92, 246, 0.4);
    transform: translateY(-2px);
  }
`;

const Header = styled.div`
  padding: 16px 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(16, 185, 129, 0.1));
  border-bottom: 1px solid rgba(139, 92, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h3`
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const TitleIcon = styled.span`
  font-size: 20px;
`;

const PremiumBadge = styled.span`
  padding: 4px 10px;
  border-radius: 20px;
  background: linear-gradient(135deg, #8B5CF6, #7C3AED);
  font-size: 10px;
  font-weight: 700;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const Content = styled.div`
  padding: 20px;
`;

const EvolutionTimeline = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
`;

const GenerationCircle = styled.div`
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8B5CF6, #10B981);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  
  ${props => props.$isEvolving && css`
    animation: ${evolveAnimation} 2s ease-in-out infinite;
  `}
`;

const GenerationNumber = styled.div`
  font-size: 20px;
  font-weight: 700;
  color: white;
`;

const GenerationLabel = styled.div`
  font-size: 9px;
  color: rgba(255, 255, 255, 0.8);
  text-transform: uppercase;
`;

const TimelineInfo = styled.div`
  flex: 1;
`;

const TimelineTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
`;

const TimelineSubtitle = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
`;

const StatsRow = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
`;

const StatCard = styled.div`
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
`;

const StatIcon = styled.div`
  font-size: 24px;
  margin-bottom: 8px;
`;

const StatValue = styled.div`
  font-size: 20px;
  font-weight: 700;
  color: ${props => props.$color || '#fff'};
`;

const StatLabel = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const NextEvolutionCard = styled.div`
  padding: 16px;
  background: linear-gradient(90deg, rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.1));
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  margin-bottom: 20px;
`;

const NextTitle = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: #8B5CF6;
  margin-bottom: 8px;
`;

const ProgressBar = styled.div`
  height: 6px;
  background: rgba(139, 92, 246, 0.2);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, #8B5CF6, #10B981);
  border-radius: 3px;
  width: ${props => props.$percent}%;
  transition: width 0.5s ease;
`;

const NextSubtitle = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
`;

const ManualAgeInput = styled.div`
  margin-bottom: 16px;
`;

const InputLabel = styled.label`
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 8px;
`;

const InputRow = styled.div`
  display: flex;
  gap: 12px;
`;

const NumberInput = styled.input`
  flex: 1;
  padding: 12px 16px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.3);
  color: #fff;
  font-size: 16px;
  
  &:focus {
    outline: none;
    border-color: #8B5CF6;
  }
  
  &::placeholder {
    color: rgba(255, 255, 255, 0.3);
  }
`;

const ActionButton = styled.button`
  padding: 12px 24px;
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
    background: linear-gradient(135deg, #8B5CF6, #7C3AED);
    color: white;
    
    &:hover:not(:disabled) {
      background: linear-gradient(135deg, #7C3AED, #6D28D9);
      transform: translateY(-1px);
    }
  ` : `
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid rgba(139, 92, 246, 0.3);
    color: #8B5CF6;
    
    &:hover:not(:disabled) {
      background: rgba(139, 92, 246, 0.2);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ButtonRow = styled.div`
  display: flex;
  gap: 12px;
`;

const LockedOverlay = styled.div`
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
`;

const LockedMessage = styled.div`
  padding: 24px;
  text-align: center;
`;

const LockedIcon = styled.div`
  font-size: 40px;
  margin-bottom: 12px;
`;

const LockedTitle = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
`;

const LockedSubtitle = styled.div`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 16px;
`;

const UpgradeButton = styled.button`
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #8B5CF6, #7C3AED);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  
  &:hover {
    background: linear-gradient(135deg, #7C3AED, #6D28D9);
  }
`;

const StatusMessage = styled.div`
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  margin-top: 12px;
  
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
`;

// =============================================================================
// Component
// =============================================================================

const EpigeneticEvolutionCard = ({
    onEvolutionTriggered,
    onUpgradeClick,
}) => {
    const [evolutionStatus, setEvolutionStatus] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isEvolving, setIsEvolving] = useState(false);
    const [manualAge, setManualAge] = useState('');
    const [status, setStatus] = useState(null);

    // Fetch evolution status on mount
    useEffect(() => {
        fetchEvolutionStatus();
    }, []);

    const fetchEvolutionStatus = async () => {
        try {
            const result = await geneticService.getEvolutionStatus();
            setEvolutionStatus(result.evolution);
        } catch (err) {
            console.error('Failed to fetch evolution status:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleTriggerEvolution = async (force = false) => {
        if (!evolutionStatus?.can_use_epigenetic) {
            onUpgradeClick?.();
            return;
        }

        setIsEvolving(true);
        setStatus(null);

        try {
            const options = { force };
            if (manualAge && parseFloat(manualAge) > 0) {
                options.newBiologicalAge = parseFloat(manualAge);
            }

            const result = await geneticService.triggerEvolution(options);

            if (result.evolved) {
                setStatus({ type: 'success', message: result.message });
                onEvolutionTriggered?.(result);
                // Refresh status
                await fetchEvolutionStatus();
            } else {
                setStatus({ type: 'info', message: result.message });
            }
        } catch (err) {
            if (err.message === 'PREMIUM_REQUIRED') {
                onUpgradeClick?.();
            } else {
                setStatus({ type: 'error', message: err.message });
            }
        } finally {
            setIsEvolving(false);
        }
    };

    const canUseEpigenetic = evolutionStatus?.can_use_epigenetic;
    const isPremium = evolutionStatus?.is_premium;
    const isTrial = evolutionStatus?.is_trial;
    const currentGeneration = evolutionStatus?.current_generation || 1;
    const biologicalAge = evolutionStatus?.last_biological_age;

    // Calculate progress to next evolution (mock data for demo)
    const progressPercent = biologicalAge ? Math.min((biologicalAge % 0.5) * 200, 100) : 0;

    if (isLoading) {
        return (
            <Card>
                <Content style={{ textAlign: 'center', padding: '40px' }}>
                    <div style={{ fontSize: '24px', marginBottom: '12px' }}>⏳</div>
                    <div style={{ color: 'rgba(255,255,255,0.5)' }}>Loading evolution status...</div>
                </Content>
            </Card>
        );
    }

    return (
        <Card $isPremium={isPremium || isTrial}>
            <Header>
                <Title>
                    <TitleIcon>🧬</TitleIcon>
                    Epigenetic Evolution
                </Title>
                {isPremium && <PremiumBadge>Premium</PremiumBadge>}
                {isTrial && <PremiumBadge>Trial</PremiumBadge>}
            </Header>

            <Content>
                {/* Evolution Timeline */}
                <EvolutionTimeline>
                    <GenerationCircle $isEvolving={isEvolving}>
                        <GenerationNumber>{currentGeneration}</GenerationNumber>
                        <GenerationLabel>Gen</GenerationLabel>
                    </GenerationCircle>
                    <TimelineInfo>
                        <TimelineTitle>Evolution Generation {currentGeneration}</TimelineTitle>
                        <TimelineSubtitle>
                            {biologicalAge
                                ? `Biological Age: ${biologicalAge.toFixed(1)} years`
                                : 'No biological age data yet'}
                        </TimelineSubtitle>
                    </TimelineInfo>
                </EvolutionTimeline>

                {/* Stats */}
                <StatsRow>
                    <StatCard>
                        <StatIcon>🔬</StatIcon>
                        <StatValue $color="#8B5CF6">
                            {biologicalAge ? `${biologicalAge.toFixed(1)}y` : '—'}
                        </StatValue>
                        <StatLabel>Biological Age</StatLabel>
                    </StatCard>
                    <StatCard>
                        <StatIcon>🔄</StatIcon>
                        <StatValue $color="#10B981">{currentGeneration}</StatValue>
                        <StatLabel>Evolutions</StatLabel>
                    </StatCard>
                </StatsRow>

                {/* Locked State for non-premium */}
                {!canUseEpigenetic && (
                    <LockedMessage>
                        <LockedIcon>🔒</LockedIcon>
                        <LockedTitle>Premium Feature</LockedTitle>
                        <LockedSubtitle>
                            Epigenetic evolution requires an active premium subscription.
                            Your passwords can evolve based on biological age changes.
                        </LockedSubtitle>
                        <UpgradeButton onClick={onUpgradeClick}>
                            Upgrade to Premium
                        </UpgradeButton>
                    </LockedMessage>
                )}

                {/* Active Evolution Controls */}
                {canUseEpigenetic && (
                    <>
                        {/* Next Evolution Progress */}
                        <NextEvolutionCard>
                            <NextTitle>Next Evolution Progress</NextTitle>
                            <ProgressBar>
                                <ProgressFill $percent={progressPercent} />
                            </ProgressBar>
                            <NextSubtitle>
                                {evolutionStatus?.next_check
                                    ? `Next check: ${new Date(evolutionStatus.next_check).toLocaleDateString()}`
                                    : 'Evolution triggered by significant biological age changes'}
                            </NextSubtitle>
                        </NextEvolutionCard>

                        {/* Manual Age Input */}
                        <ManualAgeInput>
                            <InputLabel>
                                Update Biological Age (from epigenetic test)
                            </InputLabel>
                            <InputRow>
                                <NumberInput
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="150"
                                    placeholder="e.g., 35.5"
                                    value={manualAge}
                                    onChange={(e) => setManualAge(e.target.value)}
                                />
                            </InputRow>
                        </ManualAgeInput>

                        {/* Action Buttons */}
                        <ButtonRow>
                            <ActionButton
                                onClick={() => handleTriggerEvolution(false)}
                                disabled={isEvolving}
                            >
                                {isEvolving ? '⏳ Evolving...' : '🧬 Check Evolution'}
                            </ActionButton>
                            <ActionButton
                                $primary
                                onClick={() => handleTriggerEvolution(true)}
                                disabled={isEvolving}
                            >
                                ⚡ Force Evolution
                            </ActionButton>
                        </ButtonRow>
                    </>
                )}

                {/* Status Message */}
                {status && (
                    <StatusMessage $type={status.type}>
                        {status.message}
                    </StatusMessage>
                )}
            </Content>
        </Card>
    );
};

export default EpigeneticEvolutionCard;

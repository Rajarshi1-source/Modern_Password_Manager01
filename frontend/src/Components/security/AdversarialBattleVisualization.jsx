/**
 * Adversarial Battle Visualization Component
 * 
 * Animated visualization showing attack vectors vs defense shields,
 * victory/defeat status, and learning insights.
 * 
 * Supports two modes:
 * 1. Controlled mode: Pass battleResult, attackVectors, etc. as props
 * 2. Self-contained mode: Pass password prop to auto-analyze
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import styled, { keyframes, css } from 'styled-components';
import mlSecurityService from '../../services/mlSecurityService';
import adversarialService from '../../services/adversarialService';

// Animations
const attackMove = keyframes`
  0% { transform: translateX(0) rotate(0deg); opacity: 1; }
  50% { transform: translateX(80px) rotate(10deg); opacity: 0.8; }
  100% { transform: translateX(0) rotate(0deg); opacity: 1; }
`;

const shieldPulse = keyframes`
  0%, 100% { transform: scale(1); filter: brightness(1); }
  50% { transform: scale(1.1); filter: brightness(1.3); }
`;

const blocked = keyframes`
  0% { transform: scale(1); }
  50% { transform: scale(0.8); opacity: 0.5; }
  100% { transform: scale(1); opacity: 1; }
`;

const victoryGlow = keyframes`
  0%, 100% { box-shadow: 0 0 20px rgba(34, 197, 94, 0.5); }
  50% { box-shadow: 0 0 40px rgba(34, 197, 94, 0.8); }
`;

const defeatGlow = keyframes`
  0%, 100% { box-shadow: 0 0 20px rgba(239, 68, 68, 0.5); }
  50% { box-shadow: 0 0 40px rgba(239, 68, 68, 0.8); }
`;

const floatIn = keyframes`
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
`;

// Styled Components
const Container = styled.div`
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
  border-radius: 16px;
  padding: 24px;
  position: relative;
  overflow: hidden;
`;

const LoadingOverlay = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #9ca3af;
  font-size: 14px;
`;

const MLBadge = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
`;

const CombinedScoreDisplay = styled.div`
  text-align: center;
  padding: 12px;
  margin-bottom: 16px;
  background: rgba(107, 114, 128, 0.1);
  border-radius: 8px;
`;

const CombinedScoreLabel = styled.div`
  font-size: 11px;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const CombinedScoreValue = styled.div`
  font-size: 24px;
  font-weight: 700;
  color: ${props => props.$color || '#fff'};
  margin-top: 4px;
`;

const BattleArena = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32px 24px;
  background: radial-gradient(ellipse at center, rgba(107, 114, 128, 0.1) 0%, transparent 70%);
  border-radius: 12px;
  margin-bottom: 24px;
  min-height: 200px;
  position: relative;
`;

const AttackerZone = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
`;

const DefenderZone = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
`;

const BattleCenter = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 32px;
`;

const AttackVector = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #f87171;
  transition: all 0.3s ease;
  
  ${props => props.$attacking && css`
    animation: ${attackMove} 1s ease-in-out;
  `}
  
  ${props => props.$blocked && css`
    animation: ${blocked} 0.5s ease-out;
    opacity: 0.5;
    text-decoration: line-through;
  `}
`;

const DefenseShield = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #4ade80;
  
  ${props => props.$active && css`
    animation: ${shieldPulse} 1s ease-in-out infinite;
  `}
`;

const CombatantIcon = styled.div`
  font-size: 48px;
  margin-bottom: 16px;
  
  ${props => props.$winner && css`
    animation: ${props.$type === 'attacker' ? defeatGlow : victoryGlow} 2s ease-in-out infinite;
    border-radius: 50%;
    padding: 16px;
  `}
`;

const CombatantLabel = styled.div`
  font-size: 14px;
  font-weight: 700;
  color: ${props => props.$color || '#fff'};
  text-transform: uppercase;
  letter-spacing: 1px;
`;

const ScoreValue = styled.div`
  font-size: 28px;
  font-weight: 700;
  color: ${props => props.$color || '#fff'};
  margin-top: 8px;
`;

const VSBadge = styled.div`
  font-size: 24px;
  font-weight: 900;
  color: #6b7280;
  padding: 12px 20px;
  background: #0f0f1a;
  border-radius: 50%;
  border: 2px solid #2d2d44;
`;

const StatusBanner = styled.div`
  text-align: center;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 24px;
  animation: ${floatIn} 0.5s ease-out;
  
  ${props => props.$outcome === 'defender_wins' && css`
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(22, 163, 74, 0.1) 100%);
    border: 1px solid rgba(34, 197, 94, 0.3);
  `}
  
  ${props => props.$outcome === 'attacker_wins' && css`
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(220, 38, 38, 0.1) 100%);
    border: 1px solid rgba(239, 68, 68, 0.3);
  `}
  
  ${props => props.$outcome === 'draw' && css`
    background: linear-gradient(135deg, rgba(234, 179, 8, 0.2) 0%, rgba(202, 138, 4, 0.1) 100%);
    border: 1px solid rgba(234, 179, 8, 0.3);
  `}
`;

const StatusIcon = styled.span`
  font-size: 32px;
  display: block;
  margin-bottom: 8px;
`;

const StatusText = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: #fff;
`;

const StatusSubtext = styled.div`
  font-size: 14px;
  color: #9ca3af;
  margin-top: 4px;
`;

const InsightsSection = styled.div`
  background: rgba(107, 114, 128, 0.1);
  border-radius: 12px;
  padding: 16px;
`;

const InsightTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const InsightCard = styled.div`
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  animation: ${floatIn} 0.5s ease-out;
  animation-delay: ${props => props.$delay || 0}ms;
  animation-fill-mode: both;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const InsightIcon = styled.span`
  font-size: 20px;
`;

const InsightText = styled.div`
  flex: 1;
`;

const InsightLabel = styled.div`
  font-size: 13px;
  color: #fff;
`;

const InsightValue = styled.div`
  font-size: 12px;
  color: #9ca3af;
`;

// Attack type icons
const ATTACK_ICONS = {
    dictionary: '📖',
    brute_force: '🔨',
    rule_based: '📐',
    pattern: '🔢',
    markov: '📊',
    hybrid: '🔀',
};

const AdversarialBattleVisualization = ({
    // Controlled mode props
    battleResult: externalBattleResult,
    attackVectors: externalAttackVectors = [],
    defenseStrategies: externalDefenseStrategies = [],
    isAnimating: externalIsAnimating = false,
    insights: externalInsights = [],

    // Self-contained mode props
    password = null,
    useCombinedAnalysis = false,
    showTrendingInsights = true,
    onAnalysisComplete,
}) => {
    // State for self-contained mode
    const [internalBattleResult, setInternalBattleResult] = useState(null);
    const [internalAttackVectors, setInternalAttackVectors] = useState([]);
    const [internalDefenseStrategies, setInternalDefenseStrategies] = useState([]);
    const [internalInsights, setInternalInsights] = useState([]);
    const [combinedScore, setCombinedScore] = useState(null);
    const [mlStrength, setMlStrength] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // Animation state
    const [activeAttackIndex, setActiveAttackIndex] = useState(-1);
    const [blockedAttacks, setBlockedAttacks] = useState(new Set());
    const [internalIsAnimating, setInternalIsAnimating] = useState(false);
    const animationRef = useRef(null);
    const debounceRef = useRef(null);

    // Use external or internal data
    const battleResult = externalBattleResult || internalBattleResult;
    const attackVectors = externalAttackVectors.length > 0 ? externalAttackVectors : internalAttackVectors;
    const defenseStrategies = externalDefenseStrategies.length > 0 ? externalDefenseStrategies : internalDefenseStrategies;
    const insights = externalInsights.length > 0 ? externalInsights : internalInsights;
    const isAnimating = externalIsAnimating || internalIsAnimating;

    // Self-contained analysis function
    const analyzePassword = useCallback(async (pwd) => {
        if (!pwd || pwd.length < 1) {
            setInternalBattleResult(null);
            setInternalAttackVectors([]);
            setInternalDefenseStrategies([]);
            setCombinedScore(null);
            setMlStrength(null);
            return;
        }

        setIsLoading(true);

        try {
            if (useCombinedAnalysis) {
                // Use mlSecurityService for combined ML + Adversarial analysis
                const result = await mlSecurityService.getComprehensivePasswordAnalysis(pwd);

                if (result.success) {
                    setCombinedScore(result.combined_score);
                    setMlStrength(result.ml_analysis?.prediction?.strength);

                    if (result.adversarial_analysis?.analysis) {
                        setInternalBattleResult({
                            defense_score: result.adversarial_analysis.analysis.defense_score,
                            outcome: result.adversarial_analysis.analysis.defense_score > 0.5
                                ? 'defender_wins' : 'attacker_wins'
                        });
                    }

                    if (onAnalysisComplete) {
                        onAnalysisComplete(result);
                    }
                }
            } else {
                // Direct adversarial analysis
                const features = adversarialService.extractFeatures(pwd);
                const result = await adversarialService.analyzePassword(features, true);

                if (result.success && result.battle) {
                    setInternalBattleResult(result.battle);
                    setInternalIsAnimating(true);

                    // Extract attack vectors and defenses from rounds
                    const attacks = (result.battle.rounds || []).map(r => ({
                        category: r.attack,
                        name: r.attack
                    }));
                    setInternalAttackVectors(attacks);

                    if (onAnalysisComplete) {
                        onAnalysisComplete(result.battle);
                    }

                    setTimeout(() => setInternalIsAnimating(false), attacks.length * 1000 + 500);
                }
            }

            // Fetch trending insights if enabled
            if (showTrendingInsights) {
                try {
                    const trends = await mlSecurityService.getTrendingAttacks(3);
                    if (trends?.trending) {
                        setInternalInsights(trends.trending.map(t => ({
                            icon: ATTACK_ICONS[t.attack_type] || '📊',
                            title: `${t.attack_type.replace('_', ' ')} attacks ${t.direction}`,
                            description: `Affecting ${t.affected_count} patterns`
                        })));
                    }
                } catch (e) {
                    console.warn('Could not fetch trending insights:', e);
                }
            }
        } catch (error) {
            console.error('Analysis error:', error);
        } finally {
            setIsLoading(false);
        }
    }, [useCombinedAnalysis, showTrendingInsights, onAnalysisComplete]);

    // Debounced password analysis
    useEffect(() => {
        if (password === null) return; // Only run in self-contained mode

        if (debounceRef.current) {
            clearTimeout(debounceRef.current);
        }

        debounceRef.current = setTimeout(() => {
            analyzePassword(password);
        }, 500);

        return () => {
            if (debounceRef.current) {
                clearTimeout(debounceRef.current);
            }
        };
    }, [password, analyzePassword]);

    // Animate attacks when isAnimating is true
    useEffect(() => {
        if (isAnimating && attackVectors.length > 0) {
            let index = 0;

            const animate = () => {
                setActiveAttackIndex(index);

                // Simulate blocking after attack
                setTimeout(() => {
                    if (Math.random() > 0.5) { // Random block simulation
                        setBlockedAttacks(prev => new Set([...prev, index]));
                    }
                }, 500);

                index++;
                if (index < attackVectors.length) {
                    animationRef.current = setTimeout(animate, 1000);
                } else {
                    setActiveAttackIndex(-1);
                }
            };

            animate();

            return () => {
                if (animationRef.current) {
                    clearTimeout(animationRef.current);
                }
            };
        }
    }, [isAnimating, attackVectors]);

    const getOutcomeDisplay = () => {
        if (!battleResult) return null;

        const { outcome } = battleResult;

        if (outcome === 'defender_wins') {
            return {
                icon: '🏆',
                text: 'DEFENDER WINS',
                subtext: 'Your password successfully defended against all attack vectors!',
            };
        } else if (outcome === 'attacker_wins') {
            return {
                icon: '⚠️',
                text: 'ATTACKER WINS',
                subtext: 'Your password is vulnerable. Consider strengthening it.',
            };
        } else {
            return {
                icon: '🤝',
                text: 'DRAW',
                subtext: 'Evenly matched. Room for improvement exists.',
            };
        }
    };

    const outcomeDisplay = getOutcomeDisplay();

    return (
        <Container>
            {/* Battle Arena */}
            <BattleArena>
                {/* Attacker Zone */}
                <AttackerZone>
                    <CombatantIcon
                        $winner={battleResult?.outcome === 'attacker_wins'}
                        $type="attacker"
                    >
                        ⚔️
                    </CombatantIcon>
                    <CombatantLabel $color="#ef4444">Attacker AI</CombatantLabel>
                    <ScoreValue $color="#ef4444">
                        {battleResult ? `${Math.round((1 - battleResult.defense_score) * 100)}%` : '--'}
                    </ScoreValue>

                    {/* Attack Vectors */}
                    <div style={{ marginTop: 16 }}>
                        {attackVectors.slice(0, 4).map((attack, index) => (
                            <AttackVector
                                key={index}
                                $attacking={activeAttackIndex === index}
                                $blocked={blockedAttacks.has(index)}
                            >
                                <span>{ATTACK_ICONS[attack.category] || '⚡'}</span>
                                <span>{attack.name || attack.category}</span>
                            </AttackVector>
                        ))}
                    </div>
                </AttackerZone>

                {/* Center */}
                <BattleCenter>
                    <VSBadge>VS</VSBadge>
                </BattleCenter>

                {/* Defender Zone */}
                <DefenderZone>
                    <CombatantIcon
                        $winner={battleResult?.outcome === 'defender_wins'}
                        $type="defender"
                    >
                        🛡️
                    </CombatantIcon>
                    <CombatantLabel $color="#22c55e">Defender AI</CombatantLabel>
                    <ScoreValue $color="#22c55e">
                        {battleResult ? `${Math.round(battleResult.defense_score * 100)}%` : '--'}
                    </ScoreValue>

                    {/* Defense Strategies */}
                    <div style={{ marginTop: 16 }}>
                        {defenseStrategies.slice(0, 4).map((defense, index) => (
                            <DefenseShield
                                key={index}
                                $active={activeAttackIndex === index}
                            >
                                <span>🛡️</span>
                                <span>{defense.name || defense}</span>
                            </DefenseShield>
                        ))}
                    </div>
                </DefenderZone>
            </BattleArena>

            {/* Status Banner */}
            {battleResult && outcomeDisplay && (
                <StatusBanner $outcome={battleResult.outcome}>
                    <StatusIcon>{outcomeDisplay.icon}</StatusIcon>
                    <StatusText>{outcomeDisplay.text}</StatusText>
                    <StatusSubtext>{outcomeDisplay.subtext}</StatusSubtext>
                </StatusBanner>
            )}

            {/* Learning Insights */}
            {insights.length > 0 && (
                <InsightsSection>
                    <InsightTitle>
                        <span>💡</span>
                        Insights from Aggregated Analysis
                    </InsightTitle>
                    {insights.map((insight, index) => (
                        <InsightCard key={index} $delay={index * 100}>
                            <InsightIcon>{insight.icon || '📊'}</InsightIcon>
                            <InsightText>
                                <InsightLabel>{insight.title}</InsightLabel>
                                <InsightValue>{insight.description}</InsightValue>
                            </InsightText>
                        </InsightCard>
                    ))}
                </InsightsSection>
            )}
        </Container>
    );
};

export default AdversarialBattleVisualization;

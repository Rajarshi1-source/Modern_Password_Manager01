/**
 * Adversarial Password Meter - Battle Visualization Component
 * 
 * Displays real-time adversarial AI analysis with animated battle visualization
 * showing attack vs defense interactions.
 * 
 * Integrates with both:
 * - adversarialService (for direct adversarial analysis)
 * - mlSecurityService (for combined ML + Adversarial analysis)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled, { keyframes, css } from 'styled-components';
import adversarialService from '../../services/adversarialService';
import mlSecurityService from '../../services/mlSecurityService';

// Animations
const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
`;

const shimmer = keyframes`
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
`;

const attackAnimation = keyframes`
  0% { transform: translateX(0) scale(1); opacity: 1; }
  50% { transform: translateX(30px) scale(1.1); opacity: 0.8; }
  100% { transform: translateX(0) scale(1); opacity: 1; }
`;

const defenseAnimation = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
  50% { transform: scale(1.05); box-shadow: 0 0 20px 5px rgba(34, 197, 94, 0.2); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
`;

// Styled Components
const Container = styled.div`
  background: ${props => props.theme?.backgroundSecondary || '#1a1a2e'};
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  border: 1px solid ${props => props.theme?.borderColor || '#2d2d44'};
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
`;

const Title = styled.h3`
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: ${props => props.theme?.textPrimary || '#fff'};
  display: flex;
  align-items: center;
  gap: 8px;
`;

const AIBadge = styled.span`
  font-size: 10px;
  padding: 3px 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  font-weight: 600;
`;

const BattleArena = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: linear-gradient(135deg, 
    rgba(239, 68, 68, 0.1) 0%, 
    rgba(107, 114, 128, 0.1) 50%, 
    rgba(34, 197, 94, 0.1) 100%
  );
  border-radius: 8px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
`;

const CombatantBox = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  border-radius: 8px;
  min-width: 120px;
  
  ${props => props.$isAttacker && css`
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    animation: ${props.$isActive ? attackAnimation : 'none'} 1s ease-in-out infinite;
  `}
  
  ${props => props.$isDefender && css`
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    animation: ${props.$isActive ? defenseAnimation : 'none'} 1s ease-in-out infinite;
  `}
`;

const CombatantIcon = styled.div`
  font-size: 32px;
  margin-bottom: 8px;
`;

const CombatantName = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const ScoreDisplay = styled.div`
  font-size: 24px;
  font-weight: 700;
  color: ${props => props.$color || props.theme?.textPrimary};
  margin-top: 4px;
`;

const VSBadge = styled.div`
  font-size: 20px;
  font-weight: 800;
  color: ${props => props.theme?.textSecondary || '#6b7280'};
  background: ${props => props.theme?.backgroundPrimary || '#0f0f1a'};
  padding: 8px 16px;
  border-radius: 20px;
`;

const StrengthBar = styled.div`
  height: 8px;
  background: ${props => props.theme?.backgroundTertiary || '#2d2d44'};
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
  position: relative;
`;

const StrengthFill = styled.div`
  height: 100%;
  width: ${props => props.$width}%;
  background: ${props => {
        if (props.$level === 'critical') return 'linear-gradient(90deg, #ef4444, #dc2626)';
        if (props.$level === 'weak') return 'linear-gradient(90deg, #f97316, #ea580c)';
        if (props.$level === 'moderate') return 'linear-gradient(90deg, #eab308, #ca8a04)';
        if (props.$level === 'strong') return 'linear-gradient(90deg, #22c55e, #16a34a)';
        if (props.$level === 'fortress') return 'linear-gradient(90deg, #06b6d4, #0891b2)';
        return 'linear-gradient(90deg, #6b7280, #4b5563)';
    }};
  transition: width 0.5s ease, background 0.3s ease;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    animation: ${shimmer} 2s infinite;
  }
`;

const StatusRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
`;

const StatusLabel = styled.span`
  font-size: 14px;
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
`;

const StatusValue = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: ${props => props.$color || props.theme?.textPrimary};
`;

const CrackTimeDisplay = styled.div`
  background: ${props => props.theme?.backgroundTertiary || '#2d2d44'};
  padding: 12px 16px;
  border-radius: 8px;
  text-align: center;
  margin-bottom: 16px;
`;

const CrackTimeLabel = styled.div`
  font-size: 11px;
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
`;

const CrackTimeValue = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: ${props => props.$color || props.theme?.textPrimary};
`;

const BattleLog = styled.div`
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid ${props => props.theme?.borderColor || '#2d2d44'};
  border-radius: 8px;
  padding: 8px;
  margin-bottom: 16px;
`;

const LogEntry = styled.div`
  font-size: 12px;
  padding: 6px 8px;
  margin-bottom: 4px;
  border-radius: 4px;
  background: ${props => {
        if (props.$type === 'attack') return 'rgba(239, 68, 68, 0.1)';
        if (props.$type === 'defense') return 'rgba(34, 197, 94, 0.1)';
        return 'transparent';
    }};
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const RecommendationCard = styled.div`
  background: ${props => props.theme?.backgroundTertiary || '#2d2d44'};
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  border-left: 3px solid ${props => {
        if (props.$priority === 'critical') return '#ef4444';
        if (props.$priority === 'high') return '#f97316';
        if (props.$priority === 'medium') return '#eab308';
        return '#22c55e';
    }};
`;

const RecommendationTitle = styled.div`
  font-size: 13px;
  font-weight: 600;
  color: ${props => props.theme?.textPrimary || '#fff'};
  margin-bottom: 4px;
`;

const RecommendationDescription = styled.div`
  font-size: 12px;
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
`;

const LoadingOverlay = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: ${props => props.theme?.textSecondary || '#9ca3af'};
  animation: ${pulse} 1.5s ease-in-out infinite;
`;

// Component
const AdversarialPasswordMeter = ({
    password,
    showBattleLog = true,
    showRecommendations = true,
    onAnalysisComplete,
    autoAnalyze = true,
    useCombinedAnalysis = false,  // Use mlSecurityService for combined ML + Adversarial
}) => {
    const [analysis, setAnalysis] = useState(null);
    const [battleResult, setBattleResult] = useState(null);
    const [battleLog, setBattleLog] = useState([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isAnimating, setIsAnimating] = useState(false);
    const [mlAnalysis, setMlAnalysis] = useState(null);  // For combined analysis
    const [combinedScore, setCombinedScore] = useState(null);
    const debounceTimer = useRef(null);

    // Extract features and analyze password
    const analyzePassword = useCallback(async (pwd) => {
        if (!pwd || pwd.length < 1) {
            setAnalysis(null);
            setBattleResult(null);
            setBattleLog([]);
            setMlAnalysis(null);
            setCombinedScore(null);
            return;
        }

        setIsAnalyzing(true);

        try {
            // Use combined analysis via mlSecurityService if enabled
            if (useCombinedAnalysis) {
                const combinedResult = await mlSecurityService.getComprehensivePasswordAnalysis(pwd);

                if (combinedResult.success) {
                    // Set ML analysis
                    setMlAnalysis(combinedResult.ml_analysis);
                    setCombinedScore(combinedResult.combined_score);

                    // Set adversarial analysis
                    if (combinedResult.adversarial_analysis?.analysis) {
                        setAnalysis(combinedResult.adversarial_analysis.analysis);
                    }

                    if (onAnalysisComplete) {
                        onAnalysisComplete({
                            ...combinedResult,
                            combined: true
                        });
                    }
                }
            } else {
                // Direct adversarial analysis
                const features = adversarialService.extractFeatures(pwd);

                // Quick analysis first
                const quickResult = await adversarialService.getQuickAssessment(features);

                if (quickResult.success) {
                    setAnalysis(quickResult.analysis);
                }

                // If password is long enough, run full battle
                if (pwd.length >= 4) {
                    const fullResult = await adversarialService.analyzePassword(features, true);

                    if (fullResult.success && fullResult.battle) {
                        setBattleResult(fullResult.battle);
                        setIsAnimating(true);

                        // Animate battle log
                        const rounds = fullResult.battle.rounds || [];
                        for (let i = 0; i < rounds.length; i++) {
                            await new Promise(resolve => setTimeout(resolve, 300));
                            setBattleLog(prev => [...prev, {
                                type: rounds[i].winner === 'attacker' ? 'attack' : 'defense',
                                message: `${rounds[i].attack} → ${rounds[i].winner === 'attacker' ? '⚔️ Hit!' : '🛡️ Blocked!'}`
                            }]);
                        }

                        setIsAnimating(false);

                        if (onAnalysisComplete) {
                            onAnalysisComplete(fullResult.battle);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error analyzing password:', error);
        } finally {
            setIsAnalyzing(false);
        }
    }, [onAnalysisComplete, useCombinedAnalysis]);

    // Debounced password analysis
    useEffect(() => {
        if (!autoAnalyze) return;

        if (debounceTimer.current) {
            clearTimeout(debounceTimer.current);
        }

        setBattleLog([]);

        debounceTimer.current = setTimeout(() => {
            analyzePassword(password);
        }, 500);

        return () => {
            if (debounceTimer.current) {
                clearTimeout(debounceTimer.current);
            }
        };
    }, [password, analyzePassword, autoAnalyze]);

    // Get color for defense score
    const getDefenseColor = (score) => {
        if (score >= 0.8) return '#06b6d4';
        if (score >= 0.6) return '#22c55e';
        if (score >= 0.4) return '#eab308';
        if (score >= 0.2) return '#f97316';
        return '#ef4444';
    };

    // Get level from score
    const getLevel = (score) => {
        if (score >= 0.9) return 'fortress';
        if (score >= 0.75) return 'strong';
        if (score >= 0.5) return 'moderate';
        if (score >= 0.25) return 'weak';
        return 'critical';
    };

    if (!password) {
        return null;
    }

    return (
        <Container>
            <Header>
                <Title>
                    🤖 Adversarial AI Analysis
                    <AIBadge>BETA</AIBadge>
                </Title>
            </Header>

            {isAnalyzing && !analysis && (
                <LoadingOverlay>
                    Analyzing password security...
                </LoadingOverlay>
            )}

            {analysis && (
                <>
                    {/* Battle Arena */}
                    <BattleArena>
                        <CombatantBox $isAttacker $isActive={isAnimating}>
                            <CombatantIcon>⚔️</CombatantIcon>
                            <CombatantName>Attacker</CombatantName>
                            <ScoreDisplay $color="#ef4444">
                                {battleResult ? Math.round(battleResult.attack_score * 100) : '--'}%
                            </ScoreDisplay>
                        </CombatantBox>

                        <VSBadge>VS</VSBadge>

                        <CombatantBox $isDefender $isActive={isAnimating}>
                            <CombatantIcon>🛡️</CombatantIcon>
                            <CombatantName>Defender</CombatantName>
                            <ScoreDisplay $color="#22c55e">
                                {battleResult ? Math.round(battleResult.defense_score * 100) : '--'}%
                            </ScoreDisplay>
                        </CombatantBox>
                    </BattleArena>

                    {/* Strength Bar */}
                    <StrengthBar>
                        <StrengthFill
                            $width={analysis.defense_score * 100}
                            $level={getLevel(analysis.defense_score)}
                        />
                    </StrengthBar>

                    <StatusRow>
                        <StatusLabel>Defense Level</StatusLabel>
                        <StatusValue $color={getDefenseColor(analysis.defense_score)}>
                            {analysis.status?.toUpperCase() || getLevel(analysis.defense_score).toUpperCase()}
                        </StatusValue>
                    </StatusRow>

                    {/* Estimated Crack Time */}
                    {battleResult && (
                        <CrackTimeDisplay>
                            <CrackTimeLabel>Estimated Time to Crack</CrackTimeLabel>
                            <CrackTimeValue $color={getDefenseColor(battleResult.defense_score)}>
                                {battleResult.crack_time_human || 'Unknown'}
                            </CrackTimeValue>
                        </CrackTimeDisplay>
                    )}

                    {/* Battle Log */}
                    {showBattleLog && battleLog.length > 0 && (
                        <BattleLog>
                            {battleLog.map((entry, index) => (
                                <LogEntry key={index} $type={entry.type}>
                                    {entry.message}
                                </LogEntry>
                            ))}
                        </BattleLog>
                    )}

                    {/* Recommendations */}
                    {showRecommendations && battleResult?.recommendations?.length > 0 && (
                        <>
                            <Title style={{ fontSize: '14px', marginBottom: '12px' }}>
                                💡 Recommendations
                            </Title>
                            {battleResult.recommendations.slice(0, 3).map((rec, index) => (
                                <RecommendationCard key={index} $priority={rec.priority}>
                                    <RecommendationTitle>{rec.title}</RecommendationTitle>
                                    <RecommendationDescription>{rec.description}</RecommendationDescription>
                                </RecommendationCard>
                            ))}
                        </>
                    )}

                    {/* Battle Outcome */}
                    {battleResult && (
                        <StatusRow style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #2d2d44' }}>
                            <StatusLabel>Battle Outcome</StatusLabel>
                            <StatusValue $color={
                                battleResult.outcome === 'defender_wins' ? '#22c55e' :
                                    battleResult.outcome === 'attacker_wins' ? '#ef4444' : '#eab308'
                            }>
                                {battleResult.outcome === 'defender_wins' ? '🏆 DEFENDER WINS' :
                                    battleResult.outcome === 'attacker_wins' ? '⚠️ ATTACKER WINS' : '🤝 DRAW'}
                            </StatusValue>
                        </StatusRow>
                    )}
                </>
            )}
        </Container>
    );
};

export default AdversarialPasswordMeter;

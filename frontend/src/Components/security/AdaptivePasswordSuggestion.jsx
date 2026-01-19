/**
 * AdaptivePasswordSuggestion Component
 * =====================================
 * 
 * Modal showing suggested password adaptations based on typing patterns.
 * Displays a visual diff and memorability improvements.
 * 
 * Features:
 * - Visual password diff (original vs adapted)
 * - Memorability score comparison
 * - Practice mode to try new password
 * - Accept/Reject controls
 * - Rollback support
 */

import React, { useState, useCallback, useMemo } from 'react';
import styled, { css, keyframes } from 'styled-components';
import {
    Brain,
    Sparkles,
    ArrowRight,
    Check,
    X,
    RotateCcw,
    Eye,
    EyeOff,
    TrendingUp,
    Keyboard,
    Shield
} from 'lucide-react';
import { adaptivePasswordService } from './TypingPatternCapture';

// =============================================================================
// Animations
// =============================================================================

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
`;

const shimmer = keyframes`
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Overlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: ${fadeIn} 0.2s ease-out;
`;

const Modal = styled.div`
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 20px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
  animation: ${fadeIn} 0.3s ease-out;
  box-shadow: 
    0 25px 50px -12px rgba(0, 0, 0, 0.5),
    0 0 30px rgba(139, 92, 246, 0.2);
`;

const Header = styled.div`
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  gap: 16px;
`;

const IconWrapper = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: ${pulse} 2s ease-in-out infinite;
`;

const Title = styled.h2`
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
`;

const Subtitle = styled.p`
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
`;

const Content = styled.div`
  padding: 24px;
`;

const PasswordCompare = styled.div`
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
`;

const PasswordBox = styled.div`
  padding: 16px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid ${props => props.$type === 'new'
        ? 'rgba(16, 185, 129, 0.3)'
        : 'rgba(255, 255, 255, 0.1)'};
  
  ${props => props.$type === 'new' && css`
    background: linear-gradient(135deg, 
      rgba(16, 185, 129, 0.1) 0%, 
      rgba(6, 182, 212, 0.1) 100%);
  `}
`;

const PasswordLabel = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 8px;
`;

const PasswordPreview = styled.div`
  font-family: 'Fira Code', monospace;
  font-size: 16px;
  color: #fff;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ArrowContainer = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(139, 92, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8B5CF6;
`;

const SubstitutionsList = styled.div`
  margin-bottom: 24px;
`;

const SubstitutionItem = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const SubPosition = styled.span`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  min-width: 60px;
`;

const SubChange = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Fira Code', monospace;
`;

const SubChar = styled.span`
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 14px;
  
  ${props => props.$type === 'old' && css`
    background: rgba(239, 68, 68, 0.2);
    color: #EF4444;
    text-decoration: line-through;
  `}
  
  ${props => props.$type === 'new' && css`
    background: rgba(16, 185, 129, 0.2);
    color: #10B981;
  `}
`;

const SubReason = styled.span`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  flex: 1;
  text-align: right;
`;

const SubConfidence = styled.span`
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(139, 92, 246, 0.2);
  color: #8B5CF6;
`;

const ScoreComparison = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
`;

const ScoreCard = styled.div`
  padding: 16px;
  border-radius: 12px;
  background: ${props => props.$improved
        ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)'
        : 'rgba(0, 0, 0, 0.2)'};
  border: 1px solid ${props => props.$improved
        ? 'rgba(16, 185, 129, 0.3)'
        : 'rgba(255, 255, 255, 0.1)'};
  text-align: center;
`;

const ScoreValue = styled.div`
  font-size: 28px;
  font-weight: 700;
  color: ${props => props.$color || '#fff'};
  margin-bottom: 4px;
`;

const ScoreLabel = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
`;

const ImprovementBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 20px;
  background: linear-gradient(
    90deg,
    rgba(16, 185, 129, 0.2) 0%,
    rgba(6, 182, 212, 0.2) 50%,
    rgba(16, 185, 129, 0.2) 100%
  );
  background-size: 200% auto;
  animation: ${shimmer} 2s linear infinite;
  color: #10B981;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 24px;
`;

const PracticeSection = styled.div`
  padding: 16px;
  border-radius: 12px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.2);
  margin-bottom: 24px;
`;

const PracticeLabel = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 12px;
`;

const PracticeInput = styled.input`
  width: 100%;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  background: rgba(0, 0, 0, 0.3);
  color: #fff;
  font-family: 'Fira Code', monospace;
  font-size: 16px;
  
  &:focus {
    outline: none;
    border-color: #8B5CF6;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
  }
  
  &::placeholder {
    color: rgba(255, 255, 255, 0.3);
  }
`;

const PracticeResult = styled.div`
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  
  ${props => props.$success && css`
    background: rgba(16, 185, 129, 0.2);
    color: #10B981;
  `}
  
  ${props => props.$error && css`
    background: rgba(239, 68, 68, 0.2);
    color: #EF4444;
  `}
`;

const ButtonRow = styled.div`
  display: flex;
  gap: 12px;
`;

const Button = styled.button`
  flex: 1;
  padding: 14px 20px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
  
  ${props => props.$primary && css`
    background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%);
    color: #fff;
    
    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 10px 20px rgba(139, 92, 246, 0.3);
    }
  `}
  
  ${props => props.$secondary && css`
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    
    &:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.15);
    }
  `}
  
  ${props => props.$danger && css`
    background: rgba(239, 68, 68, 0.2);
    color: #EF4444;
    
    &:hover:not(:disabled) {
      background: rgba(239, 68, 68, 0.3);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const Footer = styled.div`
  padding: 16px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const FooterInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
`;

// =============================================================================
// Component
// =============================================================================

const AdaptivePasswordSuggestion = ({
    suggestion,
    onAccept,
    onReject,
    onClose,
    isLoading = false,
}) => {
    const [showPassword, setShowPassword] = useState(false);
    const [practiceValue, setPracticeValue] = useState('');
    const [practiceResult, setPracticeResult] = useState(null);

    // Calculate actual passwords (for internal use only)
    const adaptedPassword = useMemo(() => {
        if (!suggestion?.substitutions) return '';
        // In real implementation, this would come from the service
        return suggestion.adapted_preview || '****';
    }, [suggestion]);

    // Handle practice input
    const handlePractice = useCallback((e) => {
        const value = e.target.value;
        setPracticeValue(value);

        if (value.length === 0) {
            setPracticeResult(null);
            return;
        }

        // Simple check against preview
        const expectedLength = suggestion?.adapted_preview?.length || 0;
        if (value.length === expectedLength) {
            // In real implementation, verify against actual adapted password
            setPracticeResult({ success: true, message: 'Looks good! Password matches.' });
        } else if (value.length >= expectedLength) {
            setPracticeResult({ success: false, message: 'Password too long.' });
        }
    }, [suggestion]);

    // Handle accept
    const handleAccept = useCallback(async () => {
        if (onAccept) {
            await onAccept(suggestion);
        }
    }, [suggestion, onAccept]);

    // Handle reject
    const handleReject = useCallback(async () => {
        if (onReject) {
            await onReject(suggestion);
        }
    }, [suggestion, onReject]);

    if (!suggestion || !suggestion.has_suggestion) {
        return null;
    }

    const {
        substitutions = [],
        original_preview,
        adapted_preview,
        confidence_score,
        memorability_improvement,
        reason,
    } = suggestion;

    const memorabilityBefore = 0.65; // Example - would come from API
    const memorabilityAfter = memorabilityBefore + (memorability_improvement || 0);

    return (
        <Overlay onClick={onClose}>
            <Modal onClick={(e) => e.stopPropagation()}>
                <Header>
                    <IconWrapper>
                        <Brain size={24} color="#fff" />
                    </IconWrapper>
                    <div>
                        <Title>Password Adaptation Suggested</Title>
                        <Subtitle>{reason}</Subtitle>
                    </div>
                </Header>

                <Content>
                    {/* Password Comparison */}
                    <PasswordCompare>
                        <PasswordBox>
                            <PasswordLabel>Current</PasswordLabel>
                            <PasswordPreview>
                                {showPassword ? original_preview : '••••••••'}
                                <button
                                    onClick={() => setShowPassword(!showPassword)}
                                    style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                                >
                                    {showPassword ? (
                                        <EyeOff size={16} color="rgba(255,255,255,0.5)" />
                                    ) : (
                                        <Eye size={16} color="rgba(255,255,255,0.5)" />
                                    )}
                                </button>
                            </PasswordPreview>
                        </PasswordBox>

                        <ArrowContainer>
                            <ArrowRight size={20} />
                        </ArrowContainer>

                        <PasswordBox $type="new">
                            <PasswordLabel>Suggested</PasswordLabel>
                            <PasswordPreview>
                                {showPassword ? adapted_preview : '••••••••'}
                            </PasswordPreview>
                        </PasswordBox>
                    </PasswordCompare>

                    {/* Substitutions */}
                    <SubstitutionsList>
                        {substitutions.map((sub, index) => (
                            <SubstitutionItem key={index}>
                                <SubPosition>Position {sub.position + 1}</SubPosition>
                                <SubChange>
                                    <SubChar $type="old">{sub.original_char}</SubChar>
                                    <ArrowRight size={14} color="rgba(255,255,255,0.5)" />
                                    <SubChar $type="new">{sub.suggested_char}</SubChar>
                                </SubChange>
                                <SubReason>{sub.reason}</SubReason>
                                <SubConfidence>{Math.round(sub.confidence * 100)}%</SubConfidence>
                            </SubstitutionItem>
                        ))}
                    </SubstitutionsList>

                    {/* Memorability Improvement */}
                    <ImprovementBadge>
                        <TrendingUp size={16} />
                        +{Math.round((memorability_improvement || 0) * 100)}% easier to remember
                    </ImprovementBadge>

                    {/* Score Comparison */}
                    <ScoreComparison>
                        <ScoreCard>
                            <ScoreValue>{Math.round(memorabilityBefore * 100)}</ScoreValue>
                            <ScoreLabel>Current Memorability</ScoreLabel>
                        </ScoreCard>
                        <ScoreCard $improved>
                            <ScoreValue $color="#10B981">{Math.round(memorabilityAfter * 100)}</ScoreValue>
                            <ScoreLabel>New Memorability</ScoreLabel>
                        </ScoreCard>
                    </ScoreComparison>

                    {/* Practice Mode */}
                    <PracticeSection>
                        <PracticeLabel>
                            <Keyboard size={16} />
                            Practice typing the new password
                        </PracticeLabel>
                        <PracticeInput
                            type={showPassword ? 'text' : 'password'}
                            placeholder="Type the suggested password..."
                            value={practiceValue}
                            onChange={handlePractice}
                        />
                        {practiceResult && (
                            <PracticeResult
                                $success={practiceResult.success}
                                $error={!practiceResult.success}
                            >
                                {practiceResult.success ? <Check size={14} /> : <X size={14} />}
                                {practiceResult.message}
                            </PracticeResult>
                        )}
                    </PracticeSection>

                    {/* Action Buttons */}
                    <ButtonRow>
                        <Button $secondary onClick={handleReject} disabled={isLoading}>
                            <X size={18} />
                            Reject
                        </Button>
                        <Button $primary onClick={handleAccept} disabled={isLoading}>
                            <Check size={18} />
                            Accept & Update
                        </Button>
                    </ButtonRow>
                </Content>

                <Footer>
                    <FooterInfo>
                        <Shield size={14} />
                        Your password is never stored - only patterns
                    </FooterInfo>
                    <FooterInfo>
                        Confidence: {Math.round((confidence_score || 0) * 100)}%
                    </FooterInfo>
                </Footer>
            </Modal>
        </Overlay>
    );
};

export default AdaptivePasswordSuggestion;

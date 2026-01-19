/**
 * TypingProfileCard Component
 * ============================
 * 
 * Dashboard card displaying user's typing profile and adaptation statistics.
 * Shows learned substitutions, error patterns, and evolution history.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styled, { css, keyframes } from 'styled-components';
import {
    Fingerprint,
    TrendingUp,
    Activity,
    Clock,
    Target,
    Zap,
    Settings,
    ChevronRight,
    ToggleLeft,
    ToggleRight,
    Trash2,
    Download,
    History,
    Sparkles
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
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Card = styled.div`
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  border: 1px solid rgba(139, 92, 246, 0.2);
  overflow: hidden;
  animation: ${fadeIn} 0.3s ease-out;
`;

const Header = styled.div`
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const IconWrapper = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%);
  display: flex;
  align-items: center;
  justify-content: center;
`;

const TitleSection = styled.div``;

const Title = styled.h3`
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
`;

const Subtitle = styled.p`
  margin: 4px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
`;

const ToggleButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: ${props => props.$enabled ? '#10B981' : 'rgba(255, 255, 255, 0.4)'};
  transition: all 0.2s ease;
  
  &:hover {
    transform: scale(1.1);
  }
`;

const Content = styled.div`
  padding: 20px;
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
`;

const StatCard = styled.div`
  padding: 14px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
  text-align: center;
`;

const StatIcon = styled.div`
  margin-bottom: 8px;
  color: ${props => props.$color || '#8B5CF6'};
`;

const StatValue = styled.div`
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
`;

const StatLabel = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const Section = styled.div`
  margin-bottom: 20px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const SectionTitle = styled.div`
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const SubstitutionGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
`;

const SubstitutionChip = styled.div`
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(139, 92, 246, 0.15);
  border: 1px solid rgba(139, 92, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const SubChange = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
`;

const SubChar = styled.span`
  color: ${props => props.$type === 'to' ? '#10B981' : '#fff'};
`;

const SubConfidence = styled.span`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
`;

const ErrorPositions = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
`;

const PositionDot = styled.div`
  width: ${props => 20 + (props.$intensity || 0) * 10}px;
  height: ${props => 20 + (props.$intensity || 0) * 10}px;
  border-radius: 50%;
  background: rgba(239, 68, 68, ${props => 0.2 + (props.$intensity || 0) * 0.6});
  border: 1px solid rgba(239, 68, 68, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #EF4444;
`;

const ProgressSection = styled.div`
  padding: 16px;
  border-radius: 12px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
`;

const ProgressHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
`;

const ProgressLabel = styled.span`
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
`;

const ProgressValue = styled.span`
  font-size: 13px;
  font-weight: 600;
  color: #10B981;
`;

const ProgressBar = styled.div`
  height: 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.3);
  overflow: hidden;
`;

const ProgressFill = styled.div`
  height: 100%;
  width: ${props => props.$value}%;
  background: linear-gradient(90deg, #10B981, #06B6D4);
  border-radius: 4px;
  transition: width 0.3s ease;
`;

const HistoryList = styled.div`
  max-height: 200px;
  overflow-y: auto;
`;

const HistoryItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const HistoryInfo = styled.div``;

const HistoryType = styled.div`
  font-size: 13px;
  color: #fff;
`;

const HistoryDate = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 2px;
`;

const HistoryStatus = styled.span`
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  
  ${props => props.$status === 'active' && css`
    background: rgba(16, 185, 129, 0.2);
    color: #10B981;
  `}
  
  ${props => props.$status === 'rolled_back' && css`
    background: rgba(239, 68, 68, 0.2);
    color: #EF4444;
  `}
  
  ${props => props.$status === 'suggested' && css`
    background: rgba(139, 92, 246, 0.2);
    color: #8B5CF6;
  `}
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
`;

const ActionButton = styled.button`
  flex: 1;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
  
  ${props => props.$danger && css`
    border-color: rgba(239, 68, 68, 0.2);
    color: #EF4444;
    
    &:hover {
      background: rgba(239, 68, 68, 0.1);
    }
  `}
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 20px;
  color: rgba(255, 255, 255, 0.5);
`;

const EmptyIcon = styled.div`
  margin-bottom: 16px;
  animation: ${pulse} 2s ease-in-out infinite;
`;

const EmptyText = styled.p`
  margin: 0 0 8px;
  font-size: 14px;
`;

const EmptySubtext = styled.p`
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
`;

// =============================================================================
// Component
// =============================================================================

const TypingProfileCard = ({ onSettingsClick }) => {
    const [config, setConfig] = useState(null);
    const [profile, setProfile] = useState(null);
    const [history, setHistory] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch data
    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            const [configRes, profileRes, historyRes, statsRes] = await Promise.all([
                adaptivePasswordService.getConfig(),
                adaptivePasswordService.getProfile(),
                adaptivePasswordService.getHistory(),
                adaptivePasswordService.getStats(),
            ]);

            setConfig(configRes);
            setProfile(profileRes);
            setHistory(historyRes.adaptations || []);
            setStats(statsRes);
        } catch (err) {
            console.error('Failed to fetch adaptive data:', err);
            setError(err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Toggle enable/disable
    const handleToggle = async () => {
        try {
            if (config?.enabled) {
                await adaptivePasswordService.disable();
            } else {
                await adaptivePasswordService.enable();
            }
            fetchData();
        } catch (err) {
            console.error('Failed to toggle adaptive passwords:', err);
        }
    };

    // Export data
    const handleExport = async () => {
        try {
            const data = await adaptivePasswordService.exportData();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'adaptive-password-data.json';
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Failed to export data:', err);
        }
    };

    // Delete data
    const handleDelete = async () => {
        if (!window.confirm('Delete all adaptive password data? This cannot be undone.')) {
            return;
        }
        try {
            await adaptivePasswordService.deleteAllData();
            fetchData();
        } catch (err) {
            console.error('Failed to delete data:', err);
        }
    };

    if (loading) {
        return (
            <Card>
                <Content>
                    <EmptyState>
                        <EmptyIcon>
                            <Activity size={40} color="rgba(255,255,255,0.3)" />
                        </EmptyIcon>
                        <EmptyText>Loading typing profile...</EmptyText>
                    </EmptyState>
                </Content>
            </Card>
        );
    }

    const isEnabled = config?.enabled;
    const hasProfile = profile?.has_profile;

    return (
        <Card>
            <Header>
                <HeaderLeft>
                    <IconWrapper>
                        <Fingerprint size={22} color="#fff" />
                    </IconWrapper>
                    <TitleSection>
                        <Title>Adaptive Password</Title>
                        <Subtitle>
                            {isEnabled
                                ? 'Learning from your typing patterns'
                                : 'Enable to learn your patterns'}
                        </Subtitle>
                    </TitleSection>
                </HeaderLeft>
                <ToggleButton onClick={handleToggle} $enabled={isEnabled}>
                    {isEnabled ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
                </ToggleButton>
            </Header>

            <Content>
                {!isEnabled ? (
                    <EmptyState>
                        <EmptyIcon>
                            <Fingerprint size={48} color="rgba(139,92,246,0.5)" />
                        </EmptyIcon>
                        <EmptyText>Adaptive Passwords Disabled</EmptyText>
                        <EmptySubtext>
                            Enable to start learning your typing patterns and get personalized suggestions
                        </EmptySubtext>
                    </EmptyState>
                ) : !hasProfile ? (
                    <EmptyState>
                        <EmptyIcon>
                            <Sparkles size={48} color="rgba(139,92,246,0.5)" />
                        </EmptyIcon>
                        <EmptyText>Building Your Profile</EmptyText>
                        <EmptySubtext>
                            Keep using the app - we'll learn your patterns over time
                        </EmptySubtext>
                    </EmptyState>
                ) : (
                    <>
                        {/* Statistics */}
                        <StatsGrid>
                            <StatCard>
                                <StatIcon $color="#8B5CF6">
                                    <Activity size={20} />
                                </StatIcon>
                                <StatValue>{profile?.total_sessions || 0}</StatValue>
                                <StatLabel>Sessions</StatLabel>
                            </StatCard>
                            <StatCard>
                                <StatIcon $color="#10B981">
                                    <Target size={20} />
                                </StatIcon>
                                <StatValue>{Math.round((profile?.success_rate || 0) * 100)}%</StatValue>
                                <StatLabel>Success Rate</StatLabel>
                            </StatCard>
                            <StatCard>
                                <StatIcon $color="#06B6D4">
                                    <Zap size={20} />
                                </StatIcon>
                                <StatValue>{Math.round(profile?.average_wpm || 0)}</StatValue>
                                <StatLabel>WPM</StatLabel>
                            </StatCard>
                        </StatsGrid>

                        {/* Profile Confidence */}
                        <Section>
                            <ProgressSection>
                                <ProgressHeader>
                                    <ProgressLabel>Profile Confidence</ProgressLabel>
                                    <ProgressValue>
                                        {Math.round((profile?.profile_confidence || 0) * 100)}%
                                    </ProgressValue>
                                </ProgressHeader>
                                <ProgressBar>
                                    <ProgressFill $value={(profile?.profile_confidence || 0) * 100} />
                                </ProgressBar>
                            </ProgressSection>
                        </Section>

                        {/* Learned Substitutions */}
                        {profile?.top_substitutions && Object.keys(profile.top_substitutions).length > 0 && (
                            <Section>
                                <SectionTitle>
                                    <Sparkles size={14} />
                                    Learned Preferences
                                </SectionTitle>
                                <SubstitutionGrid>
                                    {Object.entries(profile.top_substitutions).slice(0, 6).map(([key, conf]) => {
                                        const [from, to] = key.split('->');
                                        return (
                                            <SubstitutionChip key={key}>
                                                <SubChange>
                                                    <SubChar>{from}</SubChar>
                                                    <ChevronRight size={12} color="rgba(255,255,255,0.3)" />
                                                    <SubChar $type="to">{to}</SubChar>
                                                </SubChange>
                                                <SubConfidence>{Math.round(conf * 100)}%</SubConfidence>
                                            </SubstitutionChip>
                                        );
                                    })}
                                </SubstitutionGrid>
                            </Section>
                        )}

                        {/* Error Prone Positions */}
                        {profile?.error_prone_positions && Object.keys(profile.error_prone_positions).length > 0 && (
                            <Section>
                                <SectionTitle>
                                    <Target size={14} />
                                    Tricky Positions
                                </SectionTitle>
                                <ErrorPositions>
                                    {Object.entries(profile.error_prone_positions)
                                        .slice(0, 8)
                                        .map(([pos, intensity]) => (
                                            <PositionDot key={pos} $intensity={intensity}>
                                                {parseInt(pos) + 1}
                                            </PositionDot>
                                        ))}
                                </ErrorPositions>
                            </Section>
                        )}

                        {/* Adaptation History */}
                        {history.length > 0 && (
                            <Section>
                                <SectionTitle>
                                    <History size={14} />
                                    Recent Adaptations
                                </SectionTitle>
                                <HistoryList>
                                    {history.slice(0, 5).map((item) => (
                                        <HistoryItem key={item.id}>
                                            <HistoryInfo>
                                                <HistoryType>
                                                    Generation {item.generation} ({item.type})
                                                </HistoryType>
                                                <HistoryDate>
                                                    {new Date(item.suggested_at).toLocaleDateString()}
                                                </HistoryDate>
                                            </HistoryInfo>
                                            <HistoryStatus $status={item.status}>
                                                {item.status}
                                            </HistoryStatus>
                                        </HistoryItem>
                                    ))}
                                </HistoryList>
                            </Section>
                        )}

                        {/* Action Buttons */}
                        <ActionButtons>
                            <ActionButton onClick={handleExport}>
                                <Download size={14} />
                                Export
                            </ActionButton>
                            <ActionButton onClick={onSettingsClick}>
                                <Settings size={14} />
                                Settings
                            </ActionButton>
                            <ActionButton $danger onClick={handleDelete}>
                                <Trash2 size={14} />
                                Delete
                            </ActionButton>
                        </ActionButtons>
                    </>
                )}
            </Content>
        </Card>
    );
};

export default TypingProfileCard;

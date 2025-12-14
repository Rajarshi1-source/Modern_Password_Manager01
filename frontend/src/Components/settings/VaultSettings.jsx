import React from 'react';
import styled, { keyframes } from 'styled-components';
import { FaBolt, FaDatabase, FaClock, FaInfoCircle, FaRocket, FaMemory, FaLock, FaCheckCircle } from 'react-icons/fa';
import { useVault } from '../../contexts/VaultContext';
import {
  Section,
  SectionHeader,
  SectionHeaderContent,
  SectionIcon,
  SettingItem,
  SettingInfo,
  SettingControl,
  ToggleSwitch,
  Badge,
  InfoBox,
  InfoText
} from './SettingsComponents';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
`;

// Color Constants - matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  background: '#0f0f1a',
  backgroundSecondary: '#1a1a2e',
  cardBg: '#1e1e35',
  text: '#ffffff',
  textSecondary: '#a0a0b8',
  border: '#2d2d4a'
};

// Styled Components
const Container = styled.div`
  animation: ${fadeIn} 0.4s ease-out;
`;

const BenefitsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 20px;
`;

const BenefitCard = styled.div`
  background: linear-gradient(135deg, ${colors.backgroundSecondary} 0%, ${colors.cardBg} 100%);
  border-radius: 14px;
  padding: 20px;
  border: 1px solid ${colors.border};
  transition: all 0.3s ease;
  animation: ${fadeIn} 0.4s ease-out;
  animation-delay: ${props => props.$delay || '0s'};
  animation-fill-mode: backwards;
  
  &:hover {
    border-color: ${colors.success}50;
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(16, 185, 129, 0.15);
  }
`;

const BenefitIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, ${props => props.$color}30 0%, ${props => props.$color}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  
  svg {
    font-size: 20px;
    color: ${props => props.$color};
  }
`;

const BenefitTitle = styled.h4`
  font-size: 15px;
  font-weight: 600;
  color: ${colors.text};
  margin: 0 0 8px 0;
`;

const BenefitValue = styled.div`
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(135deg, ${props => props.$color} 0%, ${props => props.$colorEnd || props.$color} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 6px;
`;

const BenefitDescription = styled.p`
  font-size: 13px;
  color: ${colors.textSecondary};
  margin: 0;
  line-height: 1.5;
`;

const RecommendationCard = styled.div`
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryDark}10 100%);
  border: 1px solid ${colors.primary}40;
  border-radius: 16px;
  padding: 24px;
  margin-top: 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  animation: ${fadeIn} 0.5s ease-out;
`;

const RecommendationIcon = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  animation: ${pulse} 2s ease-in-out infinite;
  
  svg {
    font-size: 24px;
    color: #fff;
  }
`;

const RecommendationContent = styled.div`
  flex: 1;
`;

const RecommendationTitle = styled.h3`
  font-size: 18px;
  font-weight: 700;
  color: ${colors.text};
  margin: 0 0 8px 0;
`;

const RecommendationText = styled.p`
  font-size: 14px;
  color: ${colors.textSecondary};
  margin: 0;
  line-height: 1.6;
`;

const FeatureList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 20px 0 0 0;
`;

const FeatureItem = styled.li`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  font-size: 14px;
  
  &:last-child {
    border-bottom: none;
  }
  
  svg {
    color: ${colors.success};
    font-size: 16px;
    flex-shrink: 0;
  }
  
  strong {
    color: ${colors.text};
  }
`;

const StatusIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
`;

const VaultSettings = () => {
  const vaultContext = useVault();
  
  // Safely access vault context with fallbacks
  const lazyLoadEnabled = vaultContext?.lazyLoadEnabled ?? false;
  const setLazyLoadEnabled = vaultContext?.setLazyLoadEnabled;

  const handleToggleLazyLoad = () => {
    if (setLazyLoadEnabled) {
      setLazyLoadEnabled(!lazyLoadEnabled);
    }
  };

  return (
    <Container>
      {/* Performance Settings Section */}
      <Section>
        <SectionHeader>
          <SectionIcon $color={colors.primary}>
            <FaBolt />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Performance Settings</h2>
            <p>Optimize your vault's loading speed and memory usage</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>
              <FaLock style={{ color: colors.primary }} />
              Lazy Decryption
              <StatusIndicator>
                <Badge $variant={lazyLoadEnabled ? 'success' : 'warning'}>
                  {lazyLoadEnabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </StatusIndicator>
            </h3>
            <p>
              Load vault items faster by decrypting them only when accessed. 
              Dramatically improves performance for vaults with many items.
            </p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch
              checked={lazyLoadEnabled}
              onChange={handleToggleLazyLoad}
              disabled={!setLazyLoadEnabled}
            />
          </SettingControl>
        </SettingItem>

        <InfoBox>
          <FaInfoCircle />
          <InfoText>
            <strong>How it works:</strong> When enabled, vault items remain encrypted 
            until you click on them. This reduces initial load time from seconds to 
            milliseconds for large vaults.
          </InfoText>
        </InfoBox>

        {/* Performance Benefits */}
        {lazyLoadEnabled && (
          <BenefitsGrid>
            <BenefitCard $delay="0.1s">
              <BenefitIcon $color={colors.success}>
                <FaClock />
              </BenefitIcon>
              <BenefitTitle>Faster Unlock</BenefitTitle>
              <BenefitValue $color={colors.success} $colorEnd="#34d399">
                80%
              </BenefitValue>
              <BenefitDescription>
                Vault unlocks in under 500ms for 100+ items
              </BenefitDescription>
            </BenefitCard>

            <BenefitCard $delay="0.2s">
              <BenefitIcon $color={colors.primary}>
                <FaMemory />
              </BenefitIcon>
              <BenefitTitle>Less Memory</BenefitTitle>
              <BenefitValue $color={colors.primary} $colorEnd={colors.primaryLight}>
                70%
              </BenefitValue>
              <BenefitDescription>
                Uses ~15MB instead of ~50MB for large vaults
              </BenefitDescription>
            </BenefitCard>

            <BenefitCard $delay="0.3s">
              <BenefitIcon $color={colors.warning}>
                <FaBolt />
              </BenefitIcon>
              <BenefitTitle>Instant Access</BenefitTitle>
              <BenefitValue $color={colors.warning} $colorEnd="#fbbf24">
                &lt;20ms
              </BenefitValue>
              <BenefitDescription>
                Items decrypt instantly when clicked
              </BenefitDescription>
            </BenefitCard>
          </BenefitsGrid>
        )}

        {/* Show limitation note when enabled */}
        {lazyLoadEnabled && (
          <InfoBox style={{ marginTop: '20px' }}>
            <FaInfoCircle />
            <InfoText>
              <strong>Note:</strong> Search is limited to item titles for encrypted items. 
              Click an item to decrypt it for full-text search capabilities.
            </InfoText>
          </InfoBox>
        )}
      </Section>

      {/* Recommendation Section (when disabled) */}
      {!lazyLoadEnabled && (
        <Section>
          <SectionHeader>
            <SectionIcon $color={colors.success}>
              <FaRocket />
            </SectionIcon>
            <SectionHeaderContent>
              <h2>Why Enable Lazy Decryption?</h2>
              <p>Recommended for the best vault experience</p>
            </SectionHeaderContent>
          </SectionHeader>

          <RecommendationCard>
            <RecommendationIcon>
              <FaRocket />
            </RecommendationIcon>
            <RecommendationContent>
              <RecommendationTitle>Boost Your Vault Performance</RecommendationTitle>
              <RecommendationText>
                Enable lazy decryption for significant performance improvements, 
                especially if you have a large number of stored credentials.
              </RecommendationText>
            </RecommendationContent>
          </RecommendationCard>

          <FeatureList>
            <FeatureItem>
              <FaCheckCircle />
              <span><strong>Faster Login:</strong> Unlock your vault in milliseconds instead of seconds</span>
            </FeatureItem>
            <FeatureItem>
              <FaCheckCircle />
              <span><strong>Better Performance:</strong> Smoother scrolling and navigation</span>
            </FeatureItem>
            <FeatureItem>
              <FaCheckCircle />
              <span><strong>Lower Memory:</strong> Reduced RAM usage for better device performance</span>
            </FeatureItem>
            <FeatureItem>
              <FaCheckCircle />
              <span><strong>Longer Battery:</strong> Less CPU usage extends battery life on mobile</span>
            </FeatureItem>
            <FeatureItem>
              <FaCheckCircle />
              <span><strong>No Compromises:</strong> Items decrypt instantly when you need them</span>
            </FeatureItem>
          </FeatureList>

          <InfoBox>
            <FaInfoCircle />
            <InfoText>
              <strong>Recommended:</strong> We suggest enabling lazy decryption for the best experience. 
              You can always disable it if you prefer traditional full decryption on unlock.
            </InfoText>
          </InfoBox>
        </Section>
      )}
    </Container>
  );
};

export default VaultSettings;

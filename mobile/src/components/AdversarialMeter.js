/**
 * AdversarialMeter Component - React Native
 * 
 * Reusable mobile component for password strength visualization
 * using adversarial AI analysis.
 */

import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Dimensions,
} from 'react-native';

const { width } = Dimensions.get('window');

const AdversarialMeter = ({
  defenseScore = 0,
  attackScore = 0,
  outcome = null,
  crackTime = null,
  isLoading = false,
  compact = false,
}) => {
  const progressAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: defenseScore,
      duration: 800,
      useNativeDriver: false,
    }).start();
  }, [defenseScore]);

  const getColor = (score) => {
    if (score >= 0.8) return '#06b6d4';
    if (score >= 0.6) return '#22c55e';
    if (score >= 0.4) return '#eab308';
    if (score >= 0.2) return '#f97316';
    return '#ef4444';
  };

  const getLabel = (score) => {
    if (score >= 0.9) return 'Fortress';
    if (score >= 0.75) return 'Strong';
    if (score >= 0.5) return 'Moderate';
    if (score >= 0.25) return 'Weak';
    return 'Critical';
  };

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  const color = getColor(defenseScore);

  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <View style={styles.compactBar}>
          <Animated.View
            style={[
              styles.compactFill,
              { width: progressWidth, backgroundColor: color },
            ]}
          />
        </View>
        <Text style={[styles.compactLabel, { color }]}>
          {getLabel(defenseScore)}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Battle Score */}
      <View style={styles.scoreRow}>
        <View style={styles.scoreItem}>
          <Text style={styles.scoreIcon}>⚔️</Text>
          <Text style={[styles.scoreValue, { color: '#ef4444' }]}>
            {Math.round(attackScore * 100)}%
          </Text>
          <Text style={styles.scoreLabel}>Attack</Text>
        </View>
        
        <View style={styles.vsDivider}>
          <Text style={styles.vsText}>VS</Text>
        </View>
        
        <View style={styles.scoreItem}>
          <Text style={styles.scoreIcon}>🛡️</Text>
          <Text style={[styles.scoreValue, { color: '#22c55e' }]}>
            {Math.round(defenseScore * 100)}%
          </Text>
          <Text style={styles.scoreLabel}>Defense</Text>
        </View>
      </View>

      {/* Progress Bar */}
      <View style={styles.progressContainer}>
        <View style={styles.progressBackground}>
          <Animated.View
            style={[
              styles.progressFill,
              { width: progressWidth, backgroundColor: color },
            ]}
          />
        </View>
        <View style={styles.progressLabels}>
          <Text style={styles.progressLabelText}>
            {getLabel(defenseScore)}
          </Text>
          {crackTime && (
            <Text style={[styles.crackTimeText, { color }]}>
              {crackTime}
            </Text>
          )}
        </View>
      </View>

      {/* Outcome Badge */}
      {outcome && (
        <View
          style={[
            styles.outcomeBadge,
            {
              backgroundColor:
                outcome === 'defender_wins'
                  ? 'rgba(34, 197, 94, 0.15)'
                  : 'rgba(239, 68, 68, 0.15)',
              borderColor:
                outcome === 'defender_wins' ? '#22c55e' : '#ef4444',
            },
          ]}
        >
          <Text style={styles.outcomeText}>
            {outcome === 'defender_wins'
              ? '🏆 Defender Wins'
              : '⚠️ Attacker Wins'}
          </Text>
        </View>
      )}

      {isLoading && (
        <View style={styles.loadingOverlay}>
          <Text style={styles.loadingText}>Analyzing...</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    marginVertical: 8,
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  compactBar: {
    flex: 1,
    height: 6,
    backgroundColor: '#2d2d44',
    borderRadius: 3,
    overflow: 'hidden',
    marginRight: 12,
  },
  compactFill: {
    height: '100%',
    borderRadius: 3,
  },
  compactLabel: {
    fontSize: 12,
    fontWeight: '600',
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  scoreItem: {
    alignItems: 'center',
    flex: 1,
  },
  scoreIcon: {
    fontSize: 20,
    marginBottom: 4,
  },
  scoreValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  scoreLabel: {
    fontSize: 10,
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  vsDivider: {
    paddingHorizontal: 12,
  },
  vsText: {
    fontSize: 12,
    fontWeight: '800',
    color: '#6b7280',
  },
  progressContainer: {
    marginBottom: 12,
  },
  progressBackground: {
    height: 8,
    backgroundColor: '#2d2d44',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 8,
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  progressLabelText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  crackTimeText: {
    fontSize: 12,
    fontWeight: '500',
  },
  outcomeBadge: {
    borderRadius: 8,
    padding: 10,
    alignItems: 'center',
    borderWidth: 1,
    marginTop: 4,
  },
  outcomeText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
  },
  loadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#fff',
    fontSize: 14,
  },
});

export default AdversarialMeter;

/**
 * Adversarial Password Screen - React Native
 * 
 * Mobile screen for adversarial AI password analysis
 * with battle visualization optimized for mobile.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const { width } = Dimensions.get('window');

// API URL - adjust for your environment
const API_URL = 'http://localhost:8000/api/adversarial';

// Feature extraction (same logic as web)
const extractFeatures = (password) => {
  const calculateEntropy = (pwd) => {
    if (!pwd) return 0;
    let charsetSize = 0;
    if (/[a-z]/.test(pwd)) charsetSize += 26;
    if (/[A-Z]/.test(pwd)) charsetSize += 26;
    if (/\d/.test(pwd)) charsetSize += 10;
    if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd)) charsetSize += 32;
    return pwd.length * Math.log2(charsetSize || 1);
  };

  const calculateDiversity = (pwd) => {
    if (!pwd) return 0;
    const uniqueChars = new Set(pwd.toLowerCase()).size;
    return uniqueChars / pwd.length;
  };

  const checkCommonPatterns = (pwd) => {
    const patterns = [
      /^123/, /123$/, /^password/i, /password$/i,
      /qwerty/i, /asdf/i, /(.)\1{2,}/
    ];
    return patterns.some(p => p.test(pwd));
  };

  return {
    length: password.length,
    has_upper: /[A-Z]/.test(password),
    has_lower: /[a-z]/.test(password),
    has_digit: /\d/.test(password),
    has_special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
    character_diversity: calculateDiversity(password),
    entropy: calculateEntropy(password),
    has_common_patterns: checkCommonPatterns(password),
    guessability_score: 50,
    pattern_info: {
      keyboard_walk: /qwerty|asdf|zxcv/i.test(password),
      date_pattern: /\d{4}|19\d{2}|20\d{2}/.test(password),
      repeated_chars: /(.)\1{2,}/.test(password)
    }
  };
};

const AdversarialPasswordScreen = ({ navigation }) => {
  const [password, setPassword] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [battleResult, setBattleResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Animations
  const attackerAnim = useRef(new Animated.Value(0)).current;
  const defenderAnim = useRef(new Animated.Value(0)).current;
  const progressAnim = useRef(new Animated.Value(0)).current;
  
  const debounceRef = useRef(null);

  // Animate battle
  useEffect(() => {
    if (battleResult) {
      Animated.parallel([
        Animated.spring(attackerAnim, {
          toValue: 1,
          friction: 8,
          useNativeDriver: true
        }),
        Animated.spring(defenderAnim, {
          toValue: 1,
          friction: 8,
          useNativeDriver: true
        }),
        Animated.timing(progressAnim, {
          toValue: battleResult.defense_score,
          duration: 1000,
          useNativeDriver: false
        })
      ]).start();
    } else {
      attackerAnim.setValue(0);
      defenderAnim.setValue(0);
      progressAnim.setValue(0);
    }
  }, [battleResult]);

  // Analyze password
  const analyzePassword = useCallback(async (pwd) => {
    if (!pwd || pwd.length < 4) {
      setAnalysis(null);
      setBattleResult(null);
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const features = extractFeatures(pwd);
      
      const response = await fetch(`${API_URL}/analyze/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Add auth token here if needed
        },
        body: JSON.stringify({
          features,
          run_full_battle: true,
          save_result: false
        })
      });

      const data = await response.json();

      if (data.success) {
        setBattleResult(data.battle);
        setAnalysis(data.battle);
      } else {
        setError(data.message || 'Analysis failed');
      }
    } catch (err) {
      console.error('Error analyzing password:', err);
      setError('Failed to connect to server');
      
      // Fallback: Local analysis
      const features = extractFeatures(pwd);
      const localScore = calculateLocalScore(features);
      setAnalysis({
        defense_score: localScore,
        outcome: localScore > 0.6 ? 'defender_wins' : 'attacker_wins',
        crack_time_human: localScore > 0.7 ? 'Years' : localScore > 0.4 ? 'Days' : 'Minutes'
      });
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  // Local fallback scoring
  const calculateLocalScore = (features) => {
    let score = 0;
    if (features.length >= 12) score += 0.25;
    if (features.length >= 16) score += 0.15;
    if (features.has_upper) score += 0.1;
    if (features.has_digit) score += 0.1;
    if (features.has_special) score += 0.15;
    if (!features.has_common_patterns) score += 0.25;
    return Math.min(score, 1);
  };

  // Debounced analysis
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      analyzePassword(password);
    }, 600);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [password, analyzePassword]);

  // Get colors and text
  const getDefenseColor = (score) => {
    if (score >= 0.8) return '#06b6d4';
    if (score >= 0.6) return '#22c55e';
    if (score >= 0.4) return '#eab308';
    if (score >= 0.2) return '#f97316';
    return '#ef4444';
  };

  const getDefenseLabel = (score) => {
    if (score >= 0.9) return 'FORTRESS';
    if (score >= 0.75) return 'STRONG';
    if (score >= 0.5) return 'MODERATE';
    if (score >= 0.25) return 'WEAK';
    return 'CRITICAL';
  };

  const defenseScore = analysis?.defense_score || 0;
  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%']
  });

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>🤖 Adversarial AI</Text>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>BETA</Text>
          </View>
        </View>

        {/* Password Input */}
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            placeholder="Enter password to analyze..."
            placeholderTextColor="#6b7280"
            value={password}
            onChangeText={setPassword}
            secureTextEntry={false}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>

        {isAnalyzing && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color="#667eea" />
            <Text style={styles.loadingText}>Analyzing security...</Text>
          </View>
        )}

        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {analysis && (
          <>
            {/* Battle Arena */}
            <View style={styles.battleArena}>
              {/* Attacker */}
              <Animated.View style={[
                styles.combatantBox,
                styles.attackerBox,
                {
                  transform: [{
                    scale: attackerAnim.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0.8, 1]
                    })
                  }]
                }
              ]}>
                <Text style={styles.combatantIcon}>⚔️</Text>
                <Text style={styles.combatantName}>ATTACKER</Text>
                <Text style={[styles.scoreDisplay, { color: '#ef4444' }]}>
                  {Math.round((1 - defenseScore) * 100)}%
                </Text>
              </Animated.View>

              {/* VS */}
              <View style={styles.vsBadge}>
                <Text style={styles.vsText}>VS</Text>
              </View>

              {/* Defender */}
              <Animated.View style={[
                styles.combatantBox,
                styles.defenderBox,
                {
                  transform: [{
                    scale: defenderAnim.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0.8, 1]
                    })
                  }]
                }
              ]}>
                <Text style={styles.combatantIcon}>🛡️</Text>
                <Text style={styles.combatantName}>DEFENDER</Text>
                <Text style={[styles.scoreDisplay, { color: '#22c55e' }]}>
                  {Math.round(defenseScore * 100)}%
                </Text>
              </Animated.View>
            </View>

            {/* Progress Bar */}
            <View style={styles.progressContainer}>
              <View style={styles.progressBackground}>
                <Animated.View 
                  style={[
                    styles.progressFill,
                    { 
                      width: progressWidth,
                      backgroundColor: getDefenseColor(defenseScore)
                    }
                  ]}
                />
              </View>
              <View style={styles.progressLabels}>
                <Text style={styles.progressLabel}>Defense Level</Text>
                <Text style={[styles.progressValue, { color: getDefenseColor(defenseScore) }]}>
                  {getDefenseLabel(defenseScore)}
                </Text>
              </View>
            </View>

            {/* Crack Time */}
            <View style={styles.crackTimeContainer}>
              <Text style={styles.crackTimeLabel}>ESTIMATED TIME TO CRACK</Text>
              <Text style={[styles.crackTimeValue, { color: getDefenseColor(defenseScore) }]}>
                {analysis.crack_time_human || 'Unknown'}
              </Text>
            </View>

            {/* Outcome */}
            <View style={[
              styles.outcomeContainer,
              { 
                backgroundColor: analysis.outcome === 'defender_wins' 
                  ? 'rgba(34, 197, 94, 0.15)' 
                  : 'rgba(239, 68, 68, 0.15)',
                borderColor: analysis.outcome === 'defender_wins'
                  ? '#22c55e'
                  : '#ef4444'
              }
            ]}>
              <Text style={styles.outcomeText}>
                {analysis.outcome === 'defender_wins' 
                  ? '🏆 DEFENDER WINS' 
                  : '⚠️ ATTACKER WINS'}
              </Text>
            </View>

            {/* Recommendations */}
            {analysis.recommendations?.length > 0 && (
              <View style={styles.recommendationsContainer}>
                <Text style={styles.sectionTitle}>💡 Recommendations</Text>
                {analysis.recommendations.slice(0, 3).map((rec, index) => (
                  <View key={index} style={[
                    styles.recommendationCard,
                    { 
                      borderLeftColor: rec.priority === 'critical' ? '#ef4444' :
                        rec.priority === 'high' ? '#f97316' : '#eab308'
                    }
                  ]}>
                    <Text style={styles.recommendationTitle}>{rec.title}</Text>
                    <Text style={styles.recommendationDesc}>{rec.description}</Text>
                  </View>
                ))}
              </View>
            )}
          </>
        )}

        {!password && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateIcon}>🔐</Text>
            <Text style={styles.emptyStateText}>
              Enter a password to see how it holds up against AI-powered attacks
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  scrollContent: {
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#fff',
  },
  badge: {
    marginLeft: 10,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    backgroundColor: '#667eea',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#fff',
  },
  inputContainer: {
    marginBottom: 20,
  },
  input: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#2d2d44',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
  loadingText: {
    marginLeft: 8,
    color: '#9ca3af',
    fontSize: 14,
  },
  errorContainer: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 14,
  },
  battleArena: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    marginBottom: 16,
  },
  combatantBox: {
    alignItems: 'center',
    padding: 12,
    borderRadius: 8,
    minWidth: width * 0.3,
  },
  attackerBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  defenderBox: {
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(34, 197, 94, 0.3)',
  },
  combatantIcon: {
    fontSize: 28,
    marginBottom: 4,
  },
  combatantName: {
    fontSize: 10,
    fontWeight: '600',
    color: '#9ca3af',
    letterSpacing: 0.5,
  },
  scoreDisplay: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 4,
  },
  vsBadge: {
    backgroundColor: '#0f0f1a',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  vsText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#6b7280',
  },
  progressContainer: {
    marginBottom: 16,
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
  progressLabel: {
    fontSize: 14,
    color: '#9ca3af',
  },
  progressValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  crackTimeContainer: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
  },
  crackTimeLabel: {
    fontSize: 10,
    color: '#9ca3af',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  crackTimeValue: {
    fontSize: 22,
    fontWeight: '700',
  },
  outcomeContainer: {
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1,
  },
  outcomeText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
  },
  recommendationsContainer: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  recommendationCard: {
    backgroundColor: '#1a1a2e',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
  },
  recommendationTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 4,
  },
  recommendationDesc: {
    fontSize: 12,
    color: '#9ca3af',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyStateIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyStateText: {
    fontSize: 14,
    color: '#9ca3af',
    textAlign: 'center',
    lineHeight: 22,
    paddingHorizontal: 32,
  },
});

export default AdversarialPasswordScreen;

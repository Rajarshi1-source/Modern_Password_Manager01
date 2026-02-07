/**
 * Cognitive Verification Screen (Mobile)
 * ========================================
 * 
 * React Native screen for cognitive password verification.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  TextInput,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import CognitiveAuthService from '../services/CognitiveAuthService';

const { width } = Dimensions.get('window');

const CognitiveVerificationScreen = ({ route, navigation }) => {
  const { password, context = 'login', isCalibration = false } = route.params || {};

  // State
  const [isLoading, setIsLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [currentChallenge, setCurrentChallenge] = useState(null);
  const [completedCount, setCompletedCount] = useState(0);
  const [passedCount, setPassedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [sessionResult, setSessionResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [timeLeft, setTimeLeft] = useState(0);

  const timerRef = useRef(null);
  const countdownRef = useRef(null);

  // Initialize session
  useEffect(() => {
    initSession();
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      CognitiveAuthService.reset();
    };
  }, []);

  const initSession = async () => {
    try {
      setIsLoading(true);
      
      let response;
      if (isCalibration) {
        response = await CognitiveAuthService.startCalibration(password);
      } else {
        response = await CognitiveAuthService.startSession(password, { context });
      }

      setSession(response);
      setTotalCount(response.total_challenges);
      
      if (response.first_challenge) {
        setCurrentChallenge(response.first_challenge);
        startTimer(response.first_challenge.time_limit_ms);
      }

      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  // Start response timer
  const startTimer = (limitMs) => {
    timerRef.current = CognitiveAuthService.createTimer();
    timerRef.current.start();
    
    setTimeLeft(limitMs / 1000);
    
    countdownRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 0.1) {
          clearInterval(countdownRef.current);
          handleTimeout();
          return 0;
        }
        return prev - 0.1;
      });
    }, 100);
  };

  const handleTimeout = useCallback(() => {
    handleSubmit('');
  }, []);

  // Handle response submission
  const handleSubmit = async (response) => {
    if (!timerRef.current) return;

    clearInterval(countdownRef.current);
    const timing = timerRef.current.stop();
    timerRef.current = null;

    try {
      const result = await CognitiveAuthService.submitResponse(
        currentChallenge.id,
        response,
        timing
      );

      setCompletedCount(result.challenges_completed);
      setPassedCount(result.challenges_passed);
      setSelectedOption(null);
      setInputValue('');

      if (result.is_session_complete) {
        setSessionResult(result.session_result);
      } else if (result.next_challenge) {
        setCurrentChallenge(result.next_challenge);
        startTimer(result.next_challenge.time_limit_ms);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleOptionPress = (option) => {
    timerRef.current?.recordKeystroke();
    setSelectedOption(option);
    setTimeout(() => handleSubmit(option), 100);
  };

  // Render loading
  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#6366f1" />
          <Text style={styles.loadingText}>Preparing challenges...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Render error
  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={initSession}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Render results
  if (sessionResult) {
    const passed = sessionResult.status === 'passed';
    
    return (
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.resultsContainer}>
          <View style={[styles.resultIcon, passed ? styles.successIcon : styles.failedIcon]}>
            <Text style={styles.resultIconText}>{passed ? '✓' : '✗'}</Text>
          </View>

          <Text style={styles.resultTitle}>
            {passed ? 'Verification Successful' : 'Verification Failed'}
          </Text>

          <View style={styles.metricsContainer}>
            <View style={styles.metric}>
              <Text style={styles.metricValue}>
                {Math.round(sessionResult.overall_score * 100)}%
              </Text>
              <Text style={styles.metricLabel}>Accuracy</Text>
            </View>
            <View style={styles.metric}>
              <Text style={styles.metricValue}>
                {Math.round(sessionResult.confidence * 100)}%
              </Text>
              <Text style={styles.metricLabel}>Confidence</Text>
            </View>
            <View style={styles.metric}>
              <Text style={styles.metricValue}>
                {Math.round(sessionResult.creator_probability * 100)}%
              </Text>
              <Text style={styles.metricLabel}>Match</Text>
            </View>
          </View>

          <TouchableOpacity 
            style={styles.continueButton}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.continueButtonText}>Continue</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // Render challenge
  const challenge = currentChallenge;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {isCalibration ? 'Calibration' : 'Verification'}
        </Text>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.closeButton}>✕</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.progressBar}>
        <View 
          style={[
            styles.progressFill, 
            { width: `${(completedCount / totalCount) * 100}%` }
          ]} 
        />
      </View>
      <Text style={styles.progressText}>{completedCount} / {totalCount}</Text>

      <View style={styles.challengeContainer}>
        <View style={styles.timerContainer}>
          <Text style={[styles.timerText, timeLeft < 3 && styles.timerWarning]}>
            {timeLeft.toFixed(1)}s
          </Text>
        </View>

        {challenge?.type === 'scrambled' && (
          <View style={styles.scrambledContainer}>
            <Text style={styles.scrambledText}>{challenge.data.scrambled_text}</Text>
            <Text style={styles.instruction}>Select the correct pattern:</Text>
            <View style={styles.optionsGrid}>
              {challenge.data.options?.map((option, index) => (
                <TouchableOpacity
                  key={index}
                  style={[
                    styles.optionButton,
                    selectedOption === option && styles.selectedOption
                  ]}
                  onPress={() => handleOptionPress(option)}
                >
                  <Text style={styles.optionText}>{option}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {challenge?.type === 'partial' && (
          <View style={styles.partialContainer}>
            <Text style={styles.instruction}>{challenge.data.instruction}</Text>
            <Text style={styles.maskedPassword}>{challenge.data.masked_password}</Text>
            <TextInput
              style={styles.textInput}
              value={inputValue}
              onChangeText={(text) => {
                timerRef.current?.recordKeystroke();
                setInputValue(text);
              }}
              placeholder="Enter missing characters"
              placeholderTextColor="#6b7280"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity 
              style={styles.submitButton}
              onPress={() => handleSubmit(inputValue)}
            >
              <Text style={styles.submitButtonText}>Submit</Text>
            </TouchableOpacity>
          </View>
        )}

        {(challenge?.type === 'stroop' || challenge?.type === 'priming') && (
          <View style={styles.scrambledContainer}>
            <Text style={styles.instruction}>{challenge.data.instruction}</Text>
            <View style={styles.optionsGrid}>
              {challenge.data.options?.map((option, index) => (
                <TouchableOpacity
                  key={index}
                  style={[
                    styles.optionButton,
                    selectedOption === option && styles.selectedOption
                  ]}
                  onPress={() => handleOptionPress(option)}
                >
                  <Text style={styles.optionText}>{option}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0f12',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#8b949e',
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 24,
  },
  retryButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 32,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  headerTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  closeButton: {
    color: '#8b949e',
    fontSize: 24,
  },
  progressBar: {
    height: 6,
    backgroundColor: 'rgba(255,255,255,0.1)',
    marginHorizontal: 20,
    borderRadius: 3,
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#6366f1',
    borderRadius: 3,
  },
  progressText: {
    color: '#8b949e',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 8,
  },
  challengeContainer: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  timerContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  timerText: {
    color: '#22c55e',
    fontSize: 32,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  timerWarning: {
    color: '#ef4444',
  },
  scrambledContainer: {
    alignItems: 'center',
  },
  scrambledText: {
    color: '#6366f1',
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: 4,
    backgroundColor: 'rgba(99,102,241,0.1)',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderRadius: 12,
    marginBottom: 24,
  },
  instruction: {
    color: '#8b949e',
    fontSize: 14,
    marginBottom: 16,
    textAlign: 'center',
  },
  optionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 12,
  },
  optionButton: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 16,
    minWidth: (width - 80) / 2,
    alignItems: 'center',
  },
  selectedOption: {
    backgroundColor: 'rgba(99,102,241,0.2)',
    borderColor: '#6366f1',
  },
  optionText: {
    color: '#e1e4e8',
    fontSize: 18,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  partialContainer: {
    alignItems: 'center',
  },
  maskedPassword: {
    color: '#8b949e',
    fontSize: 24,
    fontFamily: 'monospace',
    marginBottom: 24,
  },
  textInput: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 18,
    width: '100%',
    marginBottom: 16,
  },
  submitButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 48,
    paddingVertical: 14,
    borderRadius: 8,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  resultsContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  resultIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  successIcon: {
    backgroundColor: 'rgba(34,197,94,0.2)',
    borderWidth: 2,
    borderColor: '#22c55e',
  },
  failedIcon: {
    backgroundColor: 'rgba(239,68,68,0.2)',
    borderWidth: 2,
    borderColor: '#ef4444',
  },
  resultIconText: {
    fontSize: 36,
    color: '#fff',
  },
  resultTitle: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 32,
  },
  metricsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    marginBottom: 40,
  },
  metric: {
    alignItems: 'center',
  },
  metricValue: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  metricLabel: {
    color: '#8b949e',
    fontSize: 12,
    marginTop: 4,
  },
  continueButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 48,
    paddingVertical: 14,
    borderRadius: 8,
  },
  continueButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default CognitiveVerificationScreen;

/**
 * LivenessVerificationScreen - React Native
 * 
 * Mobile screen for deepfake-resistant biometric liveness verification.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Camera } from 'expo-camera';
import BiometricLivenessService, { TimingUtils } from '../services/BiometricLivenessService';

const LivenessVerificationScreen = ({ navigation, route }) => {
  const context = route?.params?.context || 'login';
  
  const [status, setStatus] = useState('initializing');
  const [session, setSession] = useState(null);
  const [currentChallenge, setCurrentChallenge] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [frameCount, setFrameCount] = useState(0);
  const [hasPermission, setHasPermission] = useState(null);
  const [livenessIndicators, setLivenessIndicators] = useState({});

  const cameraRef = useRef(null);
  const captureIntervalRef = useRef(null);

  useEffect(() => {
    initSession();
    return () => cleanup();
  }, []);

  const initSession = async () => {
    try {
      setStatus('initializing');

      // Request camera permission
      const { status: cameraStatus } = await Camera.requestCameraPermissionsAsync();
      setHasPermission(cameraStatus === 'granted');

      if (cameraStatus !== 'granted') {
        setError('Camera permission denied');
        setStatus('error');
        return;
      }

      // Start liveness session
      const sessionData = await BiometricLivenessService.startSession(context);
      setSession(sessionData);

      // Connect WebSocket
      await BiometricLivenessService.connectWebSocket(
        sessionData.session_id,
        handleFrameResult,
        handleSessionComplete,
        handleError
      );

      if (sessionData.challenges?.length > 0) {
        setCurrentChallenge(sessionData.challenges[0]);
      }

      setStatus('capturing');
      startFrameCapture();
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const startFrameCapture = () => {
    if (captureIntervalRef.current) return;

    captureIntervalRef.current = setInterval(async () => {
      if (cameraRef.current && status === 'capturing') {
        try {
          const photo = await cameraRef.current.takePictureAsync({
            quality: 0.3,
            base64: true,
            skipProcessing: true,
          });

          BiometricLivenessService.sendFrame(
            photo.base64,
            photo.width,
            photo.height,
            TimingUtils.getHighResTime()
          );
          setFrameCount(prev => prev + 1);
        } catch (err) {
          console.error('Frame capture error:', err);
        }
      }
    }, 200); // 5 FPS for mobile
  };

  const stopFrameCapture = () => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
  };

  const handleFrameResult = useCallback((data) => {
    setLivenessIndicators(prev => ({ ...prev, ...data.results }));
  }, []);

  const handleSessionComplete = useCallback((data) => {
    stopFrameCapture();
    setResults(data);
    setStatus('complete');
  }, []);

  const handleError = useCallback((message) => {
    setError(message);
    setStatus('error');
  }, []);

  const handleComplete = () => {
    setStatus('processing');
    BiometricLivenessService.completeSession();
  };

  const cleanup = () => {
    stopFrameCapture();
    BiometricLivenessService.disconnect();
  };

  const handleCancel = () => {
    cleanup();
    navigation.goBack();
  };

  const renderContent = () => {
    switch (status) {
      case 'initializing':
        return (
          <View style={styles.centerContent}>
            <ActivityIndicator size="large" color="#00d4ff" />
            <Text style={styles.statusText}>Initializing camera...</Text>
          </View>
        );

      case 'capturing':
        return (
          <View style={styles.captureContainer}>
            <View style={styles.cameraContainer}>
              <Camera
                ref={cameraRef}
                style={styles.camera}
                type={Camera.Constants.Type.front}
              />
              <View style={styles.faceOverlay}>
                <View style={styles.faceGuide} />
              </View>
            </View>

            {currentChallenge && (
              <View style={styles.challengePanel}>
                <Text style={styles.challengeType}>{currentChallenge.type} Challenge</Text>
                <Text style={styles.challengeInstruction}>{currentChallenge.instruction}</Text>
              </View>
            )}

            <View style={styles.indicatorsRow}>
              <View style={styles.indicator}>
                <Text style={styles.indicatorValue}>{frameCount}</Text>
                <Text style={styles.indicatorLabel}>Frames</Text>
              </View>
              {livenessIndicators.pulse && (
                <View style={styles.indicator}>
                  <Text style={styles.indicatorValue}>
                    {livenessIndicators.pulse.heart_rate?.toFixed(0) || '--'}
                  </Text>
                  <Text style={styles.indicatorLabel}>BPM</Text>
                </View>
              )}
              {livenessIndicators.deepfake && (
                <View style={[styles.indicator, livenessIndicators.deepfake.is_fake ? styles.indicatorWarning : styles.indicatorSuccess]}>
                  <Text style={styles.indicatorValue}>
                    {livenessIndicators.deepfake.is_fake ? '⚠️' : '✓'}
                  </Text>
                  <Text style={styles.indicatorLabel}>Liveness</Text>
                </View>
              )}
            </View>

            <View style={styles.buttonRow}>
              <TouchableOpacity style={styles.btnComplete} onPress={handleComplete}>
                <Text style={styles.btnCompleteText}>Complete</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.btnCancel} onPress={handleCancel}>
                <Text style={styles.btnCancelText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        );

      case 'processing':
        return (
          <View style={styles.centerContent}>
            <ActivityIndicator size="large" color="#00d4ff" />
            <Text style={styles.statusText}>Analyzing biometric data...</Text>
          </View>
        );

      case 'complete':
        return (
          <View style={[styles.resultContainer, results?.is_verified ? styles.resultSuccess : styles.resultFailed]}>
            <Text style={styles.resultIcon}>{results?.is_verified ? '✓' : '✗'}</Text>
            <Text style={styles.resultTitle}>
              {results?.is_verified ? 'Verification Successful' : 'Verification Failed'}
            </Text>
            <View style={styles.resultDetails}>
              <View style={styles.scoreRow}>
                <Text style={styles.scoreLabel}>Liveness Score</Text>
                <Text style={styles.scoreValue}>{(results?.liveness_score * 100)?.toFixed(1)}%</Text>
              </View>
              <View style={styles.scoreRow}>
                <Text style={styles.scoreLabel}>Confidence</Text>
                <Text style={styles.scoreValue}>{(results?.confidence * 100)?.toFixed(1)}%</Text>
              </View>
              <Text style={styles.verdict}>Verdict: {results?.verdict}</Text>
            </View>
            <TouchableOpacity style={styles.btnPrimary} onPress={handleCancel}>
              <Text style={styles.btnPrimaryText}>Close</Text>
            </TouchableOpacity>
          </View>
        );

      case 'error':
        return (
          <View style={styles.errorContainer}>
            <Text style={styles.errorIcon}>⚠️</Text>
            <Text style={styles.errorTitle}>Verification Error</Text>
            <Text style={styles.errorMessage}>{error}</Text>
            <TouchableOpacity style={styles.btnPrimary} onPress={initSession}>
              <Text style={styles.btnPrimaryText}>Try Again</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.btnSecondary} onPress={handleCancel}>
              <Text style={styles.btnSecondaryText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        );

      default:
        return null;
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🎭 Biometric Liveness</Text>
        <Text style={styles.headerSubtitle}>Deepfake-resistant verification</Text>
      </View>
      {renderContent()}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  header: {
    padding: 20,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    color: 'rgba(255,255,255,0.7)',
    marginTop: 4,
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusText: {
    color: 'rgba(255,255,255,0.8)',
    marginTop: 16,
    fontSize: 16,
  },
  captureContainer: {
    flex: 1,
    padding: 16,
  },
  cameraContainer: {
    flex: 1,
    borderRadius: 16,
    overflow: 'hidden',
    position: 'relative',
  },
  camera: {
    flex: 1,
  },
  faceOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  faceGuide: {
    width: '60%',
    aspectRatio: 0.75,
    borderWidth: 2,
    borderColor: 'rgba(0,212,255,0.6)',
    borderStyle: 'dashed',
    borderRadius: 1000,
  },
  challengePanel: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    alignItems: 'center',
  },
  challengeType: {
    color: '#00d4ff',
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  challengeInstruction: {
    color: '#fff',
    fontSize: 16,
    marginTop: 8,
    textAlign: 'center',
  },
  indicatorsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 16,
  },
  indicator: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
    minWidth: 80,
  },
  indicatorSuccess: {
    backgroundColor: 'rgba(0,200,151,0.2)',
    borderWidth: 1,
    borderColor: 'rgba(0,200,151,0.5)',
  },
  indicatorWarning: {
    backgroundColor: 'rgba(255,193,7,0.2)',
    borderWidth: 1,
    borderColor: 'rgba(255,193,7,0.5)',
  },
  indicatorValue: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
  },
  indicatorLabel: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 12,
    textTransform: 'uppercase',
    marginTop: 4,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  btnComplete: {
    flex: 1,
    backgroundColor: '#00d4ff',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  btnCompleteText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  btnCancel: {
    flex: 1,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  btnCancelText: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 16,
  },
  resultContainer: {
    margin: 20,
    padding: 24,
    borderRadius: 16,
    alignItems: 'center',
  },
  resultSuccess: {
    backgroundColor: 'rgba(0,200,151,0.1)',
    borderWidth: 2,
    borderColor: 'rgba(0,200,151,0.5)',
  },
  resultFailed: {
    backgroundColor: 'rgba(255,107,107,0.1)',
    borderWidth: 2,
    borderColor: 'rgba(255,107,107,0.5)',
  },
  resultIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  resultTitle: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  resultDetails: {
    width: '100%',
    marginBottom: 24,
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  scoreLabel: {
    color: 'rgba(255,255,255,0.8)',
  },
  scoreValue: {
    color: '#fff',
    fontWeight: '600',
  },
  verdict: {
    color: '#00d4ff',
    textAlign: 'center',
    marginTop: 12,
  },
  btnPrimary: {
    backgroundColor: '#00d4ff',
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 10,
    width: '100%',
    alignItems: 'center',
    marginBottom: 8,
  },
  btnPrimaryText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  btnSecondary: {
    paddingVertical: 14,
    width: '100%',
    alignItems: 'center',
  },
  btnSecondaryText: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 16,
  },
  errorContainer: {
    margin: 20,
    padding: 24,
    backgroundColor: 'rgba(255,107,107,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255,107,107,0.3)',
    borderRadius: 16,
    alignItems: 'center',
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  errorTitle: {
    color: '#ff6b6b',
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  errorMessage: {
    color: 'rgba(255,255,255,0.7)',
    textAlign: 'center',
    marginBottom: 24,
  },
});

export default LivenessVerificationScreen;

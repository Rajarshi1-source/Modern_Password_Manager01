/**
 * GeneticPasswordScreen
 * ========================
 * 
 * React Native screen for DNA-based password generation.
 * Allows users to connect DNA providers, upload files,
 * and generate genetic passwords.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  TextInput,
  Clipboard,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import GeneticService from '../services/GeneticService';

const GeneticPasswordScreen = ({ navigation }) => {
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [password, setPassword] = useState('');
  const [certificate, setCertificate] = useState(null);
  const [evolutionStatus, setEvolutionStatus] = useState(null);
  
  // Password options
  const [passwordLength, setPasswordLength] = useState(16);
  const [options, setOptions] = useState({
    uppercase: true,
    lowercase: true,
    numbers: true,
    symbols: true,
    combineWithQuantum: true,
  });

  // Fetch connection status on mount
  useEffect(() => {
    fetchConnectionStatus();
  }, []);

  const fetchConnectionStatus = async () => {
    setIsLoading(true);
    try {
      const status = await GeneticService.getConnectionStatus();
      if (status.success) {
        setConnectionStatus(status);
      }
      
      // Also fetch evolution status if connected
      if (status.success && status.connected) {
        const evoStatus = await GeneticService.getEvolutionStatus();
        if (evoStatus.success) {
          setEvolutionStatus(evoStatus.evolution);
        }
      }
    } catch (error) {
      console.error('Failed to fetch status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle provider connection
  const handleConnect = async (provider) => {
    try {
      setIsLoading(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      
      const result = await GeneticService.initiateConnection(provider);
      
      if (result.success) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        Alert.alert(
          'Connected!',
          `Found ${result.snpCount?.toLocaleString()} genetic markers.`,
          [{ text: 'OK' }]
        );
        await fetchConnectionStatus();
      }
    } catch (error) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Connection Failed', error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle file upload
  const handleUpload = async () => {
    try {
      setIsLoading(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      
      const result = await GeneticService.uploadDNAFile();
      
      if (result.cancelled) {
        return;
      }
      
      if (result.success) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        Alert.alert(
          'Upload Complete',
          `Processed ${result.snpCount?.toLocaleString()} SNPs from ${result.formatDetected} file.`,
          [{ text: 'OK' }]
        );
        await fetchConnectionStatus();
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Upload Failed', error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Generate genetic password
  const handleGenerate = async () => {
    if (!connectionStatus?.connected) {
      Alert.alert('Not Connected', 'Please connect your DNA first.');
      return;
    }

    try {
      setIsGenerating(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      
      const result = await GeneticService.generateGeneticPassword({
        length: passwordLength,
        ...options,
        saveCertificate: true,
      });
      
      if (result.success) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        setPassword(result.password);
        setCertificate(result.certificate);
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Generation Failed', error.message);
    } finally {
      setIsGenerating(false);
    }
  };

  // Copy password
  const handleCopy = () => {
    if (password) {
      Clipboard.setString(password);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert('Copied!', 'Password copied to clipboard.');
    }
  };

  // Disconnect DNA
  const handleDisconnect = async () => {
    Alert.alert(
      'Disconnect DNA?',
      'This will remove your DNA connection. You can reconnect later.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            try {
              await GeneticService.disconnect();
              await fetchConnectionStatus();
            } catch (error) {
              Alert.alert('Error', error.message);
            }
          },
        },
      ]
    );
  };

  const isConnected = connectionStatus?.connected;
  const connection = connectionStatus?.connection;
  const providerInfo = connection 
    ? GeneticService.getProviderInfo(connection.provider) 
    : null;

  if (isLoading && !connectionStatus) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#10B981" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <LinearGradient
        colors={['#10B981', '#047857']}
        style={styles.header}
      >
        <Text style={styles.headerIcon}>🧬</Text>
        <Text style={styles.headerTitle}>Genetic Password</Text>
        <Text style={styles.headerSubtitle}>
          Generate bio-unique passwords tied to your DNA
        </Text>
      </LinearGradient>

      {/* Connection Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>DNA Connection</Text>
        
        {isConnected ? (
          <View style={styles.connectedCard}>
            <View style={styles.providerRow}>
              <Text style={styles.providerIcon}>{providerInfo?.icon}</Text>
              <View style={styles.providerInfo}>
                <Text style={styles.providerName}>{providerInfo?.name}</Text>
                <Text style={styles.providerMeta}>
                  {connection?.snp_count?.toLocaleString()} SNPs • Gen {connection?.evolution_generation}
                </Text>
              </View>
              <TouchableOpacity onPress={handleDisconnect}>
                <Text style={styles.disconnectBtn}>✕</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.providersGrid}>
            <TouchableOpacity
              style={[styles.providerCard, { borderColor: '#10B981' }]}
              onPress={() => handleConnect('sequencing')}
              disabled={isLoading}
            >
              <Text style={styles.providerCardIcon}>🧬</Text>
              <Text style={styles.providerCardName}>Sequencing.com</Text>
              <Text style={styles.providerCardBadge}>Recommended</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.providerCard, { borderColor: '#8B5CF6' }]}
              onPress={() => handleConnect('23andme')}
              disabled={isLoading}
            >
              <Text style={styles.providerCardIcon}>🔬</Text>
              <Text style={styles.providerCardName}>23andMe</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.providerCard, { borderColor: '#6B7280' }]}
              onPress={handleUpload}
              disabled={isLoading}
            >
              <Text style={styles.providerCardIcon}>📁</Text>
              <Text style={styles.providerCardName}>Upload File</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Password Generation */}
      {isConnected && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Generate Password</Text>
          
          {/* Generated Password Display */}
          {password ? (
            <TouchableOpacity style={styles.passwordDisplay} onPress={handleCopy}>
              <Text style={styles.passwordText}>{password}</Text>
              <Text style={styles.copyHint}>Tap to copy</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.passwordPlaceholder}>
              <Text style={styles.placeholderText}>
                Press the button below to generate
              </Text>
            </View>
          )}
          
          {/* Length Selector */}
          <View style={styles.lengthRow}>
            <Text style={styles.lengthLabel}>Length: {passwordLength}</Text>
            <View style={styles.lengthButtons}>
              <TouchableOpacity
                style={styles.lengthBtn}
                onPress={() => setPasswordLength(Math.max(8, passwordLength - 4))}
              >
                <Text style={styles.lengthBtnText}>−</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.lengthBtn}
                onPress={() => setPasswordLength(Math.min(64, passwordLength + 4))}
              >
                <Text style={styles.lengthBtnText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>
          
          {/* Options */}
          <View style={styles.optionsGrid}>
            {Object.entries({
              uppercase: 'A-Z',
              lowercase: 'a-z',
              numbers: '0-9',
              symbols: '!@#',
            }).map(([key, label]) => (
              <TouchableOpacity
                key={key}
                style={[
                  styles.optionChip,
                  options[key] && styles.optionChipActive,
                ]}
                onPress={() => setOptions(prev => ({ ...prev, [key]: !prev[key] }))}
              >
                <Text style={[
                  styles.optionChipText,
                  options[key] && styles.optionChipTextActive,
                ]}>
                  {label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          
          {/* Quantum Toggle */}
          <TouchableOpacity
            style={[
              styles.quantumToggle,
              options.combineWithQuantum && styles.quantumToggleActive,
            ]}
            onPress={() => setOptions(prev => ({
              ...prev,
              combineWithQuantum: !prev.combineWithQuantum,
            }))}
          >
            <Text style={styles.quantumIcon}>⚛️</Text>
            <Text style={[
              styles.quantumText,
              options.combineWithQuantum && styles.quantumTextActive,
            ]}>
              Combine with Quantum Entropy
            </Text>
          </TouchableOpacity>
          
          {/* Generate Button */}
          <TouchableOpacity
            style={styles.generateButton}
            onPress={handleGenerate}
            disabled={isGenerating}
          >
            <LinearGradient
              colors={['#10B981', '#059669']}
              style={styles.generateButtonInner}
            >
              {isGenerating ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Text style={styles.generateIcon}>🧬</Text>
                  <Text style={styles.generateText}>Generate Genetic Password</Text>
                </>
              )}
            </LinearGradient>
          </TouchableOpacity>
        </View>
      )}

      {/* Evolution Status (Premium) */}
      {isConnected && evolutionStatus && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Epigenetic Evolution</Text>
          <View style={styles.evolutionCard}>
            <View style={styles.evolutionRow}>
              <Text style={styles.evolutionIcon}>🔄</Text>
              <View>
                <Text style={styles.evolutionGen}>
                  Generation {evolutionStatus.current_generation}
                </Text>
                <Text style={styles.evolutionAge}>
                  {evolutionStatus.last_biological_age 
                    ? `Biological Age: ${evolutionStatus.last_biological_age.toFixed(1)}y`
                    : 'No epigenetic data yet'}
                </Text>
              </View>
            </View>
            {!evolutionStatus.can_use_epigenetic && (
              <View style={styles.premiumBanner}>
                <Text style={styles.premiumText}>
                  🔒 Upgrade to Premium for password evolution
                </Text>
              </View>
            )}
          </View>
        </View>
      )}

      {/* Certificate */}
      {certificate && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Certificate</Text>
          <View style={styles.certificateCard}>
            <Text style={styles.certLabel}>Certificate ID</Text>
            <Text style={styles.certValue}>
              {certificate.certificate_id?.slice(0, 16)}...
            </Text>
            <Text style={styles.certLabel}>SNP Markers Used</Text>
            <Text style={styles.certValue}>{certificate.snp_markers_used}</Text>
            <Text style={styles.certLabel}>Evolution Generation</Text>
            <Text style={styles.certValue}>{certificate.evolution_generation}</Text>
          </View>
        </View>
      )}

      {/* Privacy Notice */}
      <View style={styles.privacyNotice}>
        <Text style={styles.privacyIcon}>🔒</Text>
        <Text style={styles.privacyText}>
          Your DNA data is processed client-side and never stored. Only cryptographic hashes are retained.
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111827',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#111827',
  },
  loadingText: {
    color: '#9CA3AF',
    marginTop: 12,
  },
  header: {
    padding: 32,
    paddingTop: 60,
    alignItems: 'center',
  },
  headerIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 8,
    textAlign: 'center',
  },
  section: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  connectedCard: {
    backgroundColor: 'rgba(16,185,129,0.1)',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(16,185,129,0.3)',
  },
  providerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  providerIcon: {
    fontSize: 32,
    marginRight: 12,
  },
  providerInfo: {
    flex: 1,
  },
  providerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  providerMeta: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  disconnectBtn: {
    fontSize: 18,
    color: '#EF4444',
    padding: 8,
  },
  providersGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  providerCard: {
    flex: 1,
    minWidth: 100,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
  },
  providerCardIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  providerCardName: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
    textAlign: 'center',
  },
  providerCardBadge: {
    fontSize: 9,
    color: '#10B981',
    marginTop: 4,
    backgroundColor: 'rgba(16,185,129,0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  passwordDisplay: {
    backgroundColor: 'rgba(16,185,129,0.1)',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(16,185,129,0.3)',
  },
  passwordText: {
    fontSize: 18,
    fontFamily: 'Courier',
    color: '#10B981',
    letterSpacing: 1,
  },
  copyHint: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 8,
  },
  passwordPlaceholder: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    borderStyle: 'dashed',
  },
  placeholderText: {
    color: '#6B7280',
    fontSize: 14,
  },
  lengthRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  lengthLabel: {
    color: '#fff',
    fontSize: 14,
  },
  lengthButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  lengthBtn: {
    width: 40,
    height: 40,
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  lengthBtnText: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '600',
  },
  optionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 16,
  },
  optionChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  optionChipActive: {
    backgroundColor: 'rgba(16,185,129,0.2)',
    borderColor: '#10B981',
  },
  optionChipText: {
    color: '#9CA3AF',
    fontSize: 14,
  },
  optionChipTextActive: {
    color: '#10B981',
  },
  quantumToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    marginTop: 16,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  quantumToggleActive: {
    backgroundColor: 'rgba(59,130,246,0.1)',
    borderColor: 'rgba(59,130,246,0.3)',
  },
  quantumIcon: {
    fontSize: 20,
    marginRight: 12,
  },
  quantumText: {
    color: '#9CA3AF',
    fontSize: 14,
  },
  quantumTextActive: {
    color: '#3B82F6',
  },
  generateButton: {
    marginTop: 20,
    borderRadius: 12,
    overflow: 'hidden',
  },
  generateButtonInner: {
    flexDirection: 'row',
    padding: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  generateIcon: {
    fontSize: 20,
    marginRight: 8,
  },
  generateText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  evolutionCard: {
    backgroundColor: 'rgba(139,92,246,0.1)',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(139,92,246,0.3)',
  },
  evolutionRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  evolutionIcon: {
    fontSize: 32,
    marginRight: 12,
  },
  evolutionGen: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  evolutionAge: {
    color: '#9CA3AF',
    fontSize: 12,
    marginTop: 2,
  },
  premiumBanner: {
    marginTop: 12,
    padding: 12,
    borderRadius: 8,
    backgroundColor: 'rgba(139,92,246,0.2)',
  },
  premiumText: {
    color: '#8B5CF6',
    fontSize: 12,
    textAlign: 'center',
  },
  certificateCard: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 16,
  },
  certLabel: {
    color: '#6B7280',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 8,
  },
  certValue: {
    color: '#10B981',
    fontSize: 14,
    fontFamily: 'Courier',
    marginBottom: 4,
  },
  privacyNotice: {
    flexDirection: 'row',
    padding: 16,
    margin: 16,
    backgroundColor: 'rgba(59,130,246,0.1)',
    borderRadius: 12,
    alignItems: 'flex-start',
  },
  privacyIcon: {
    fontSize: 20,
    marginRight: 12,
  },
  privacyText: {
    flex: 1,
    color: '#93C5FD',
    fontSize: 12,
    lineHeight: 18,
  },
});

export default GeneticPasswordScreen;

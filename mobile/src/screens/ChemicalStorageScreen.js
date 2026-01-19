/**
 * Chemical Storage Screen (Mobile)
 * =================================
 * 
 * React Native screen for chemical password storage.
 * Provides DNA encoding, time-lock, and certificate viewing.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import ChemicalService from '../services/ChemicalService';

const TABS = [
  { id: 'encode', label: '🧬 Encode' },
  { id: 'timelock', label: '⏰ Time-Lock' },
  { id: 'certificates', label: '📜 Certificates' },
];

export default function ChemicalStorageScreen({ navigation }) {
  const [activeTab, setActiveTab] = useState('encode');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [subscription, setSubscription] = useState(null);
  
  // Encode state
  const [password, setPassword] = useState('');
  const [serviceName, setServiceName] = useState('');
  const [dnaResult, setDnaResult] = useState(null);
  
  // Time-lock state
  const [timeLockHours, setTimeLockHours] = useState('72');
  const [capsuleResult, setCapsuleResult] = useState(null);
  const [remainingTime, setRemainingTime] = useState('');
  
  // Certificates state
  const [certificates, setCertificates] = useState([]);

  useEffect(() => {
    loadSubscription();
  }, []);

  useEffect(() => {
    if (capsuleResult && capsuleResult.time_remaining_seconds > 0) {
      const timer = setInterval(() => {
        setRemainingTime(ChemicalService.formatTimeRemaining(capsuleResult.time_remaining_seconds));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [capsuleResult]);

  const loadSubscription = async () => {
    const result = await ChemicalService.getSubscription();
    if (result.success) {
      setSubscription(result.subscription);
    }
  };

  const loadCertificates = async () => {
    const result = await ChemicalService.listCertificates();
    if (result.success) {
      setCertificates(result.certificates || []);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadSubscription();
    if (activeTab === 'certificates') {
      await loadCertificates();
    }
    setRefreshing(false);
  }, [activeTab]);

  const handleEncode = async () => {
    if (!password) {
      Alert.alert('Error', 'Please enter a password');
      return;
    }

    setLoading(true);
    const result = await ChemicalService.encodePassword(password, {
      serviceName,
      saveToDb: true,
    });
    setLoading(false);

    if (result.success) {
      setDnaResult(result);
      Alert.alert('Success', `Password encoded to ${result.dna_sequence?.sequence?.length || 0} base pairs`);
    } else {
      Alert.alert('Error', result.error || 'Encoding failed');
    }
  };

  const handleCreateTimeLock = async () => {
    if (!password) {
      Alert.alert('Error', 'Please enter a password');
      return;
    }

    const hours = parseInt(timeLockHours) || 72;
    setLoading(true);
    const result = await ChemicalService.createTimeLock(password, hours);
    setLoading(false);

    if (result.success) {
      setCapsuleResult(result);
      Alert.alert('Success', `Time-lock created. Unlocks in ${hours} hours`);
    } else {
      Alert.alert('Error', result.error || 'Time-lock creation failed');
    }
  };

  const handleUnlock = async () => {
    if (!capsuleResult?.capsule_id) return;

    setLoading(true);
    const result = await ChemicalService.unlockCapsule(capsuleResult.capsule_id);
    setLoading(false);

    if (result.success) {
      Alert.alert('Unlocked!', `Password: ${result.password}`);
    } else {
      Alert.alert('Still Locked', result.error || 'Cannot unlock yet');
    }
  };

  const renderDNASequence = () => {
    if (!dnaResult?.dna_sequence?.sequence) return null;
    
    const sequence = dnaResult.dna_sequence.sequence;
    const preview = sequence.slice(0, 60);
    
    return (
      <View style={styles.sequenceCard}>
        <Text style={styles.sequenceTitle}>DNA Sequence</Text>
        <Text style={styles.sequenceLength}>{sequence.length} bp</Text>
        <View style={styles.sequencePreview}>
          {preview.split('').map((n, i) => (
            <Text
              key={i}
              style={[
                styles.nucleotide,
                n === 'A' && styles.nucleotideA,
                n === 'T' && styles.nucleotideT,
                n === 'C' && styles.nucleotideC,
                n === 'G' && styles.nucleotideG,
              ]}
            >
              {n}
            </Text>
          ))}
          {sequence.length > 60 && <Text style={styles.ellipsis}>...</Text>}
        </View>
        {dnaResult.cost_estimate && (
          <View style={styles.costBox}>
            <Text style={styles.costLabel}>Est. Cost</Text>
            <Text style={styles.costValue}>
              ${dnaResult.cost_estimate.total_cost_usd || dnaResult.cost_estimate.totalUsd}
            </Text>
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🧪 Chemical Storage</Text>
        <View style={styles.tierBadge}>
          <Text style={styles.tierText}>{subscription?.tier || 'Free'}</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {TABS.map(tab => (
          <TouchableOpacity
            key={tab.id}
            style={[styles.tab, activeTab === tab.id && styles.tabActive]}
            onPress={() => {
              setActiveTab(tab.id);
              if (tab.id === 'certificates') loadCertificates();
            }}
          >
            <Text style={[styles.tabText, activeTab === tab.id && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Encode Tab */}
        {activeTab === 'encode' && (
          <View style={styles.tabPanel}>
            <Text style={styles.inputLabel}>Service Name (optional)</Text>
            <TextInput
              style={styles.input}
              value={serviceName}
              onChangeText={setServiceName}
              placeholder="e.g., Gmail Account"
              placeholderTextColor="#6b7280"
            />

            <Text style={styles.inputLabel}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter password to encode"
              placeholderTextColor="#6b7280"
              secureTextEntry
            />

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleEncode}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>🧬 Encode to DNA</Text>
              )}
            </TouchableOpacity>

            {renderDNASequence()}
          </View>
        )}

        {/* Time-Lock Tab */}
        {activeTab === 'timelock' && (
          <View style={styles.tabPanel}>
            <Text style={styles.inputLabel}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter password to lock"
              placeholderTextColor="#6b7280"
              secureTextEntry
            />

            <Text style={styles.inputLabel}>Delay (hours)</Text>
            <TextInput
              style={styles.input}
              value={timeLockHours}
              onChangeText={setTimeLockHours}
              keyboardType="numeric"
              placeholder="72"
              placeholderTextColor="#6b7280"
            />

            <TouchableOpacity
              style={[styles.button, styles.buttonBlue, loading && styles.buttonDisabled]}
              onPress={handleCreateTimeLock}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>🔒 Create Time-Lock</Text>
              )}
            </TouchableOpacity>

            {capsuleResult && (
              <View style={styles.capsuleCard}>
                <Text style={styles.capsuleTitle}>
                  {capsuleResult.time_remaining_seconds > 0 ? '🔒 Locked' : '🔓 Ready'}
                </Text>
                <Text style={styles.capsuleId}>ID: {capsuleResult.capsule_id?.slice(0, 8)}...</Text>
                <Text style={styles.capsuleTime}>
                  {remainingTime || ChemicalService.formatTimeRemaining(capsuleResult.time_remaining_seconds)}
                </Text>
                <Text style={styles.unlockDate}>
                  Unlocks: {new Date(capsuleResult.unlock_at).toLocaleString()}
                </Text>

                <TouchableOpacity
                  style={[
                    styles.button,
                    capsuleResult.time_remaining_seconds > 0 ? styles.buttonLocked : styles.buttonGreen,
                  ]}
                  onPress={handleUnlock}
                  disabled={capsuleResult.time_remaining_seconds > 0}
                >
                  <Text style={styles.buttonText}>
                    {capsuleResult.time_remaining_seconds > 0 ? 'Locked' : 'Unlock Now'}
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}

        {/* Certificates Tab */}
        {activeTab === 'certificates' && (
          <View style={styles.tabPanel}>
            {certificates.length === 0 ? (
              <View style={styles.emptyState}>
                <Text style={styles.emptyIcon}>📜</Text>
                <Text style={styles.emptyText}>No certificates yet</Text>
                <Text style={styles.emptyHint}>
                  Certificates are generated when you store passwords chemically
                </Text>
              </View>
            ) : (
              certificates.map(cert => (
                <View key={cert.certificate_id} style={styles.certCard}>
                  <View style={styles.certHeader}>
                    <Text style={styles.certId}>#{cert.certificate_id?.slice(0, 8)}</Text>
                    <Text style={styles.certDate}>
                      {new Date(cert.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <Text style={styles.certMethod}>Method: {cert.encoding_method}</Text>
                  {cert.time_lock_enabled && (
                    <View style={styles.timeLockBadge}>
                      <Text style={styles.timeLockText}>⏰ Time-Locked</Text>
                    </View>
                  )}
                </View>
              ))
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  tierBadge: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  tierText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  tabs: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: '#6366f1',
  },
  tabText: {
    color: '#9ca3af',
    fontSize: 14,
  },
  tabTextActive: {
    color: '#fff',
  },
  content: {
    flex: 1,
  },
  tabPanel: {
    padding: 20,
  },
  inputLabel: {
    color: '#9ca3af',
    fontSize: 12,
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 16,
  },
  button: {
    backgroundColor: '#10b981',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonBlue: {
    backgroundColor: '#3b82f6',
  },
  buttonGreen: {
    backgroundColor: '#22c55e',
  },
  buttonLocked: {
    backgroundColor: '#6b7280',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  sequenceCard: {
    marginTop: 20,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.3)',
    borderRadius: 12,
    padding: 16,
  },
  sequenceTitle: {
    color: '#10b981',
    fontSize: 14,
    fontWeight: '600',
  },
  sequenceLength: {
    color: '#6b7280',
    fontSize: 12,
    marginTop: 4,
  },
  sequencePreview: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
  },
  nucleotide: {
    fontFamily: 'monospace',
    fontSize: 12,
  },
  nucleotideA: { color: '#22c55e' },
  nucleotideT: { color: '#ef4444' },
  nucleotideC: { color: '#3b82f6' },
  nucleotideG: { color: '#eab308' },
  ellipsis: {
    color: '#6b7280',
    marginLeft: 4,
  },
  costBox: {
    marginTop: 16,
    alignItems: 'center',
  },
  costLabel: {
    color: '#9ca3af',
    fontSize: 12,
  },
  costValue: {
    color: '#10b981',
    fontSize: 24,
    fontWeight: 'bold',
  },
  capsuleCard: {
    marginTop: 20,
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.3)',
    borderRadius: 12,
    padding: 16,
  },
  capsuleTitle: {
    color: '#3b82f6',
    fontSize: 18,
    fontWeight: '600',
    textAlign: 'center',
  },
  capsuleId: {
    color: '#6b7280',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 4,
  },
  capsuleTime: {
    color: '#fff',
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginTop: 16,
    fontFamily: 'monospace',
  },
  unlockDate: {
    color: '#9ca3af',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 16,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyIcon: {
    fontSize: 48,
    opacity: 0.5,
  },
  emptyText: {
    color: '#6b7280',
    fontSize: 16,
    marginTop: 12,
  },
  emptyHint: {
    color: '#4b5563',
    fontSize: 12,
    marginTop: 4,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  certCard: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  certHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  certId: {
    color: '#8b5cf6',
    fontFamily: 'monospace',
  },
  certDate: {
    color: '#6b7280',
    fontSize: 12,
  },
  certMethod: {
    color: '#9ca3af',
    fontSize: 12,
  },
  timeLockBadge: {
    marginTop: 8,
    backgroundColor: 'rgba(234, 179, 8, 0.2)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  timeLockText: {
    color: '#eab308',
    fontSize: 11,
  },
});

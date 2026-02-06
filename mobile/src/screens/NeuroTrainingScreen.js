/**
 * Neuro Training Screen for React Native Mobile
 * 
 * Main screen for EEG-based password memory training.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
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
  RefreshControl,
} from 'react-native';
import neuroFeedbackService from '../services/NeuroFeedbackService';

const NeuroTrainingScreen = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [programs, setPrograms] = useState([]);
  const [dueReviews, setDueReviews] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [devices, setDevices] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [programsRes, dueRes, statsRes, devicesRes] = await Promise.all([
        neuroFeedbackService.getPrograms(),
        neuroFeedbackService.getDueReviews(),
        neuroFeedbackService.getStatistics(),
        neuroFeedbackService.getDevices(),
      ]);
      
      setPrograms(programsRes.programs || []);
      setDueReviews(dueRes.programs || []);
      setStatistics(statsRes.statistics || null);
      setDevices(devicesRes.devices || []);
    } catch (error) {
      Alert.alert('Error', 'Failed to load training data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, []);

  const startTraining = async (program) => {
    // Check for paired device
    if (devices.length === 0) {
      Alert.alert(
        'No Device',
        'Please pair an EEG device before starting training.',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Pair Device', onPress: () => navigation.navigate('DeviceSetup') },
        ]
      );
      return;
    }

    try {
      const session = await neuroFeedbackService.startSession(program.program_id);
      navigation.navigate('TrainingSession', { 
        sessionId: session.session_id,
        programId: program.program_id,
        deviceName: session.device_name,
      });
    } catch (error) {
      Alert.alert('Error', 'Failed to start training session');
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.loadingText}>Loading Neuro Training...</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>🧠 Neuro Training</Text>
        <Text style={styles.subtitle}>Train your brain to memorize passwords</Text>
      </View>

      {/* Statistics Cards */}
      <View style={styles.statsRow}>
        <View style={[styles.statCard, styles.statPrimary]}>
          <Text style={styles.statValue}>{statistics?.active_programs || 0}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={[styles.statCard, styles.statSuccess]}>
          <Text style={styles.statValue}>{statistics?.passwords_memorized || 0}</Text>
          <Text style={styles.statLabel}>Memorized</Text>
        </View>
        <View style={[styles.statCard, styles.statInfo]}>
          <Text style={styles.statValue}>
            {Math.round((statistics?.average_memory_strength || 0) * 100)}%
          </Text>
          <Text style={styles.statLabel}>Strength</Text>
        </View>
      </View>

      {/* Due Reviews Alert */}
      {dueReviews.length > 0 && (
        <View style={styles.alertBox}>
          <Text style={styles.alertTitle}>📅 Reviews Due</Text>
          <Text style={styles.alertText}>
            {dueReviews.length} password(s) need practice
          </Text>
          <TouchableOpacity 
            style={styles.alertButton}
            onPress={() => startTraining(dueReviews[0])}
          >
            <Text style={styles.alertButtonText}>Practice Now</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Device Status */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>EEG Device</Text>
          <TouchableOpacity onPress={() => navigation.navigate('DeviceSetup')}>
            <Text style={styles.linkText}>Manage</Text>
          </TouchableOpacity>
        </View>
        
        {devices.length === 0 ? (
          <View style={styles.emptyDevice}>
            <Text style={styles.emptyText}>No device paired</Text>
            <TouchableOpacity 
              style={styles.pairButton}
              onPress={() => navigation.navigate('DeviceSetup')}
            >
              <Text style={styles.pairButtonText}>Pair Device</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.deviceCard}>
            <Text style={styles.deviceIcon}>🎧</Text>
            <View style={styles.deviceInfo}>
              <Text style={styles.deviceName}>{devices[0].device_name}</Text>
              <Text style={styles.deviceType}>{devices[0].device_type_display}</Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor(devices[0].status) }]}>
              <Text style={styles.statusText}>{devices[0].status}</Text>
            </View>
          </View>
        )}
      </View>

      {/* Training Programs */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Training Programs</Text>
        
        {programs.length === 0 ? (
          <View style={styles.emptyPrograms}>
            <Text style={styles.emptyIcon}>🎓</Text>
            <Text style={styles.emptyText}>No active programs</Text>
            <Text style={styles.emptyHint}>
              Start training a password from your vault
            </Text>
          </View>
        ) : (
          programs.map(program => (
            <View key={program.program_id} style={styles.programCard}>
              <View style={styles.programHeader}>
                <Text style={styles.programStatus}>{program.status}</Text>
                <Text style={styles.programChunks}>
                  {program.chunks_mastered}/{program.total_chunks} chunks
                </Text>
              </View>
              
              <View style={styles.progressBar}>
                <View 
                  style={[styles.progressFill, { width: `${program.completion_percentage}%` }]}
                />
              </View>
              
              <View style={styles.programStats}>
                <Text style={styles.programStatText}>
                  Strength: {Math.round(program.average_strength * 100)}%
                </Text>
                <Text style={styles.programStatText}>
                  {program.total_sessions} sessions
                </Text>
              </View>
              
              <TouchableOpacity 
                style={styles.trainButton}
                onPress={() => startTraining(program)}
              >
                <Text style={styles.trainButtonText}>Continue Training</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
};

const getStatusColor = (status) => {
  const colors = {
    ready: 'rgba(34, 197, 94, 0.3)',
    paired: 'rgba(59, 130, 246, 0.3)',
    calibrating: 'rgba(245, 158, 11, 0.3)',
    disconnected: 'rgba(107, 114, 128, 0.3)',
    error: 'rgba(239, 68, 68, 0.3)',
  };
  return colors[status] || colors.disconnected;
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a1a',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0a0a1a',
  },
  loadingText: {
    color: 'rgba(255, 255, 255, 0.6)',
    marginTop: 16,
  },
  header: {
    padding: 24,
    paddingTop: 48,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255, 255, 255, 0.6)',
    marginTop: 4,
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 12,
  },
  statCard: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  statPrimary: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
  },
  statSuccess: {
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
  },
  statInfo: {
    backgroundColor: 'rgba(59, 130, 246, 0.15)',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#fff',
  },
  statLabel: {
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.6)',
    marginTop: 4,
  },
  alertBox: {
    margin: 16,
    padding: 16,
    backgroundColor: 'rgba(234, 179, 8, 0.1)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(234, 179, 8, 0.3)',
  },
  alertTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fcd34d',
  },
  alertText: {
    color: 'rgba(255, 255, 255, 0.7)',
    marginTop: 4,
  },
  alertButton: {
    marginTop: 12,
    backgroundColor: '#eab308',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  alertButtonText: {
    color: '#000',
    fontWeight: '600',
  },
  section: {
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
  },
  linkText: {
    color: '#a78bfa',
  },
  emptyDevice: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 12,
  },
  emptyText: {
    color: 'rgba(255, 255, 255, 0.5)',
  },
  pairButton: {
    marginTop: 12,
    backgroundColor: '#6366f1',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  pairButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  deviceCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
  },
  deviceIcon: {
    fontSize: 32,
    marginRight: 12,
  },
  deviceInfo: {
    flex: 1,
  },
  deviceName: {
    color: '#fff',
    fontWeight: '500',
    fontSize: 16,
  },
  deviceType: {
    color: 'rgba(255, 255, 255, 0.5)',
    fontSize: 12,
  },
  statusBadge: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  statusText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  emptyPrograms: {
    alignItems: 'center',
    padding: 32,
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyHint: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 12,
    marginTop: 4,
  },
  programCard: {
    padding: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  programHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  programStatus: {
    color: '#a78bfa',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  programChunks: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 12,
  },
  progressBar: {
    height: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    marginBottom: 12,
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#6366f1',
    borderRadius: 4,
  },
  programStats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  programStatText: {
    color: 'rgba(255, 255, 255, 0.5)',
    fontSize: 12,
  },
  trainButton: {
    backgroundColor: '#6366f1',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  trainButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
});

export default NeuroTrainingScreen;

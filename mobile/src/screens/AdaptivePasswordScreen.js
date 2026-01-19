/**
 * AdaptivePasswordScreen
 * ======================
 * 
 * React Native screen for adaptive password management.
 * Displays typing profile, adaptations, and settings.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { 
  Ionicons, 
  MaterialCommunityIcons,
  Feather
} from '@expo/vector-icons';
import adaptivePasswordApi from '../services/AdaptivePasswordApi';

// =============================================================================
// Stat Card Component
// =============================================================================

const StatCard = ({ icon, value, label, color }) => (
  <View style={styles.statCard}>
    <Ionicons name={icon} size={20} color={color} />
    <Text style={styles.statValue}>{value}</Text>
    <Text style={styles.statLabel}>{label}</Text>
  </View>
);

// =============================================================================
// Substitution Chip Component
// =============================================================================

const SubstitutionChip = ({ from, to, confidence }) => (
  <View style={styles.substitutionChip}>
    <View style={styles.substitutionChange}>
      <Text style={styles.substitutionFrom}>{from}</Text>
      <Feather name="arrow-right" size={12} color="rgba(255,255,255,0.3)" />
      <Text style={styles.substitutionTo}>{to}</Text>
    </View>
    <Text style={styles.substitutionConfidence}>{Math.round(confidence * 100)}%</Text>
  </View>
);

// =============================================================================
// History Item Component
// =============================================================================

const HistoryItem = ({ item, onRollback }) => (
  <View style={styles.historyItem}>
    <View style={styles.historyInfo}>
      <Text style={styles.historyType}>
        Generation {item.generation} ({item.type})
      </Text>
      <Text style={styles.historyDate}>
        {new Date(item.suggested_at).toLocaleDateString()}
      </Text>
    </View>
    <View style={styles.historyActions}>
      <View style={[
        styles.historyStatus,
        item.status === 'active' && styles.statusActive,
        item.status === 'rolled_back' && styles.statusRolledBack,
        item.status === 'suggested' && styles.statusSuggested,
      ]}>
        <Text style={[
          styles.historyStatusText,
          item.status === 'active' && styles.statusActiveText,
          item.status === 'rolled_back' && styles.statusRolledBackText,
          item.status === 'suggested' && styles.statusSuggestedText,
        ]}>
          {item.status}
        </Text>
      </View>
      {item.can_rollback && (
        <TouchableOpacity 
          style={styles.rollbackButton}
          onPress={() => onRollback(item.id)}
        >
          <Feather name="rotate-ccw" size={14} color="#8B5CF6" />
        </TouchableOpacity>
      )}
    </View>
  </View>
);

// =============================================================================
// Main Screen Component
// =============================================================================

const AdaptivePasswordScreen = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [config, setConfig] = useState(null);
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      const [configRes, profileRes, historyRes, statsRes] = await Promise.all([
        adaptivePasswordApi.getConfig(),
        adaptivePasswordApi.getProfile(),
        adaptivePasswordApi.getHistory(),
        adaptivePasswordApi.getStats(),
      ]);
      
      setConfig(configRes);
      setProfile(profileRes);
      setHistory(historyRes.adaptations || []);
      setStats(statsRes);
    } catch (error) {
      console.error('Failed to fetch adaptive data:', error);
      Alert.alert('Error', 'Failed to load adaptive password data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Toggle enable/disable
  const handleToggle = async (value) => {
    try {
      if (value) {
        // Show consent dialog
        Alert.alert(
          'Enable Adaptive Passwords',
          'This feature learns from your typing patterns to suggest easier passwords. ' +
          'Only anonymized timing data is collected - never your actual keystrokes.\n\n' +
          'Do you consent to this?',
          [
            { text: 'Cancel', style: 'cancel' },
            { 
              text: 'I Consent', 
              onPress: async () => {
                await adaptivePasswordApi.enable({ consent: true });
                fetchData();
              }
            },
          ]
        );
      } else {
        await adaptivePasswordApi.disable();
        fetchData();
      }
    } catch (error) {
      console.error('Failed to toggle:', error);
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  // Rollback adaptation
  const handleRollback = async (adaptationId) => {
    Alert.alert(
      'Rollback Adaptation',
      'This will revert your password to the previous version. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rollback',
          style: 'destructive',
          onPress: async () => {
            try {
              await adaptivePasswordApi.rollback(adaptationId);
              fetchData();
              Alert.alert('Success', 'Password rolled back successfully');
            } catch (error) {
              Alert.alert('Error', 'Failed to rollback');
            }
          }
        }
      ]
    );
  };

  // Delete all data
  const handleDeleteData = () => {
    Alert.alert(
      'Delete All Data',
      'This will permanently delete all your typing pattern data. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await adaptivePasswordApi.deleteAllData();
              fetchData();
              Alert.alert('Deleted', 'All adaptive password data has been deleted');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete data');
            }
          }
        }
      ]
    );
  };

  // Export data
  const handleExportData = async () => {
    try {
      const data = await adaptivePasswordApi.exportData();
      // In a real app, you'd save this to a file or share it
      Alert.alert('Export Ready', 'Your data export is ready. Check your downloads.');
    } catch (error) {
      Alert.alert('Error', 'Failed to export data');
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#8B5CF6" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  const isEnabled = config?.enabled;
  const hasProfile = profile?.has_profile;

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            fetchData();
          }}
          tintColor="#8B5CF6"
        />
      }
    >
      {/* Header Card */}
      <LinearGradient
        colors={['#1a1a2e', '#16213e']}
        style={styles.headerCard}
      >
        <View style={styles.headerTop}>
          <View style={styles.headerIcon}>
            <MaterialCommunityIcons name="fingerprint" size={28} color="#fff" />
          </View>
          <View style={styles.headerInfo}>
            <Text style={styles.headerTitle}>Adaptive Passwords</Text>
            <Text style={styles.headerSubtitle}>
              {isEnabled ? 'Learning from your patterns' : 'Disabled'}
            </Text>
          </View>
          <Switch
            value={isEnabled}
            onValueChange={handleToggle}
            trackColor={{ false: '#3e3e4e', true: '#8B5CF6' }}
            thumbColor="#fff"
          />
        </View>
      </LinearGradient>

      {isEnabled && (
        <>
          {/* Stats Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Overview</Text>
            <View style={styles.statsGrid}>
              <StatCard 
                icon="analytics" 
                value={profile?.total_sessions || 0}
                label="Sessions"
                color="#8B5CF6"
              />
              <StatCard 
                icon="checkmark-circle" 
                value={`${Math.round((profile?.success_rate || 0) * 100)}%`}
                label="Success"
                color="#10B981"
              />
              <StatCard 
                icon="speedometer" 
                value={Math.round(profile?.average_wpm || 0)}
                label="WPM"
                color="#06B6D4"
              />
            </View>
          </View>

          {/* Profile Confidence */}
          <View style={styles.section}>
            <View style={styles.progressSection}>
              <View style={styles.progressHeader}>
                <Text style={styles.progressLabel}>Profile Confidence</Text>
                <Text style={styles.progressValue}>
                  {Math.round((profile?.profile_confidence || 0) * 100)}%
                </Text>
              </View>
              <View style={styles.progressBar}>
                <View 
                  style={[
                    styles.progressFill,
                    { width: `${(profile?.profile_confidence || 0) * 100}%` }
                  ]} 
                />
              </View>
              {!profile?.has_sufficient_data && (
                <Text style={styles.progressHint}>
                  📊 Need {10 - (profile?.total_sessions || 0)} more sessions for suggestions
                </Text>
              )}
            </View>
          </View>

          {/* Learned Substitutions */}
          {profile?.top_substitutions && Object.keys(profile.top_substitutions).length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                <Feather name="zap" size={14} color="#8B5CF6" /> Learned Preferences
              </Text>
              <View style={styles.substitutionsGrid}>
                {Object.entries(profile.top_substitutions).slice(0, 6).map(([key, conf]) => {
                  const [from, to] = key.split('->');
                  return (
                    <SubstitutionChip 
                      key={key} 
                      from={from} 
                      to={to} 
                      confidence={conf} 
                    />
                  );
                })}
              </View>
            </View>
          )}

          {/* Adaptation History */}
          {history.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                <Feather name="clock" size={14} color="#8B5CF6" /> Recent Adaptations
              </Text>
              {history.slice(0, 5).map((item) => (
                <HistoryItem 
                  key={item.id} 
                  item={item}
                  onRollback={handleRollback}
                />
              ))}
            </View>
          )}

          {/* Settings */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Settings</Text>
            
            <TouchableOpacity style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Suggestion Frequency</Text>
                <Text style={styles.settingValue}>
                  Every {config?.suggestion_frequency_days || 30} days
                </Text>
              </View>
              <Feather name="chevron-right" size={20} color="rgba(255,255,255,0.3)" />
            </TouchableOpacity>
            
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Centralized Training</Text>
                <Text style={styles.settingHint}>Improves suggestions for everyone</Text>
              </View>
              <Switch
                value={config?.allow_centralized_training ?? true}
                trackColor={{ false: '#3e3e4e', true: '#8B5CF6' }}
                thumbColor="#fff"
              />
            </View>
            
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Federated Learning</Text>
                <Text style={styles.settingHint}>On-device only, more private</Text>
              </View>
              <Switch
                value={config?.allow_federated_learning ?? false}
                trackColor={{ false: '#3e3e4e', true: '#8B5CF6' }}
                thumbColor="#fff"
              />
            </View>
          </View>

          {/* Data Management */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Data Management</Text>
            
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={handleExportData}
            >
              <Feather name="download" size={18} color="#8B5CF6" />
              <Text style={styles.actionButtonText}>Export My Data</Text>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={[styles.actionButton, styles.dangerButton]}
              onPress={handleDeleteData}
            >
              <Feather name="trash-2" size={18} color="#EF4444" />
              <Text style={[styles.actionButtonText, styles.dangerText]}>
                Delete All Data
              </Text>
            </TouchableOpacity>
          </View>
        </>
      )}

      {/* Privacy Notice */}
      <View style={styles.privacyNotice}>
        <Feather name="shield" size={16} color="rgba(255,255,255,0.3)" />
        <Text style={styles.privacyText}>
          Your keystrokes are never stored. Only anonymized timing patterns.
        </Text>
      </View>
    </ScrollView>
  );
};

// =============================================================================
// Styles
// =============================================================================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0f0f1a',
  },
  loadingText: {
    marginTop: 12,
    color: 'rgba(255,255,255,0.5)',
  },
  headerCard: {
    margin: 16,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.2)',
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#8B5CF6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerInfo: {
    flex: 1,
    marginLeft: 14,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
    marginTop: 2,
  },
  section: {
    marginHorizontal: 16,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.7)',
    marginBottom: 12,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 10,
  },
  statCard: {
    flex: 1,
    padding: 14,
    borderRadius: 12,
    backgroundColor: 'rgba(0,0,0,0.3)',
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#fff',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.5)',
    marginTop: 2,
    textTransform: 'uppercase',
  },
  progressSection: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.2)',
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  progressLabel: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.7)',
  },
  progressValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#10B981',
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(0,0,0,0.3)',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#10B981',
    borderRadius: 4,
  },
  progressHint: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.4)',
    marginTop: 8,
  },
  substitutionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  substitutionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: 'rgba(139, 92, 246, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.2)',
    minWidth: '30%',
  },
  substitutionChange: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  substitutionFrom: {
    fontFamily: 'monospace',
    fontSize: 14,
    color: '#fff',
  },
  substitutionTo: {
    fontFamily: 'monospace',
    fontSize: 14,
    color: '#10B981',
  },
  substitutionConfidence: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.4)',
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    borderRadius: 10,
    backgroundColor: 'rgba(0,0,0,0.2)',
    marginBottom: 8,
  },
  historyInfo: {},
  historyType: {
    fontSize: 13,
    color: '#fff',
  },
  historyDate: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.4)',
    marginTop: 2,
  },
  historyActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  historyStatus: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    backgroundColor: 'rgba(255,255,255,0.1)',
  },
  historyStatusText: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.5)',
  },
  statusActive: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  statusActiveText: {
    color: '#10B981',
  },
  statusRolledBack: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  statusRolledBackText: {
    color: '#EF4444',
  },
  statusSuggested: {
    backgroundColor: 'rgba(139, 92, 246, 0.2)',
  },
  statusSuggestedText: {
    color: '#8B5CF6',
  },
  rollbackButton: {
    padding: 6,
    borderRadius: 6,
    backgroundColor: 'rgba(139, 92, 246, 0.1)',
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    borderRadius: 10,
    backgroundColor: 'rgba(0,0,0,0.2)',
    marginBottom: 8,
  },
  settingInfo: {
    flex: 1,
  },
  settingLabel: {
    fontSize: 14,
    color: '#fff',
  },
  settingValue: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.4)',
    marginTop: 2,
  },
  settingHint: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.3)',
    marginTop: 2,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 14,
    borderRadius: 10,
    backgroundColor: 'rgba(139, 92, 246, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.2)',
    marginBottom: 8,
  },
  actionButtonText: {
    fontSize: 14,
    color: '#8B5CF6',
    fontWeight: '500',
  },
  dangerButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  dangerText: {
    color: '#EF4444',
  },
  privacyNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 20,
    marginBottom: 40,
  },
  privacyText: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.3)',
    textAlign: 'center',
  },
});

export default AdaptivePasswordScreen;

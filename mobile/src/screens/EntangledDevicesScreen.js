/**
 * EntangledDevicesScreen.js
 * 
 * Mobile screen for viewing and managing quantum entangled device pairs.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Feather';
import EntanglementService from '../services/EntanglementService';

const EntangledDevicesScreen = ({ navigation }) => {
  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [maxPairs, setMaxPairs] = useState(5);

  // Fetch pairs
  const fetchPairs = useCallback(async () => {
    try {
      const data = await EntanglementService.getUserPairs();
      setPairs(data.pairs || []);
      setMaxPairs(data.max_allowed || 5);
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchPairs();
  }, [fetchPairs]);

  // Handle refresh
  const onRefresh = () => {
    setRefreshing(true);
    fetchPairs();
  };

  // Handle rotate keys
  const handleRotate = async (pair) => {
    try {
      await EntanglementService.rotateKeys(pair.pair_id, pair.device_a_id);
      Alert.alert('Success', 'Keys rotated successfully');
      fetchPairs();
    } catch (error) {
      Alert.alert('Error', error.message);
    }
  };

  // Handle revoke
  const handleRevoke = (pair) => {
    Alert.alert(
      'Revoke Pairing',
      'This will immediately invalidate the cryptographic connection. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revoke',
          style: 'destructive',
          onPress: async () => {
            try {
              await EntanglementService.revokePair(pair.pair_id);
              Alert.alert('Success', 'Pairing revoked');
              fetchPairs();
            } catch (error) {
              Alert.alert('Error', error.message);
            }
          },
        },
      ]
    );
  };

  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#10b981';
      case 'pending': return '#f59e0b';
      case 'revoked': return '#ef4444';
      default: return '#6b7280';
    }
  };

  // Get entropy color
  const getEntropyColor = (health) => {
    switch (health) {
      case 'healthy': return '#10b981';
      case 'degraded': return '#f59e0b';
      case 'critical': return '#ef4444';
      default: return '#6b7280';
    }
  };

  // Render pair card
  const renderPairCard = (pair) => (
    <View key={pair.pair_id} style={[styles.pairCard, { borderLeftColor: getStatusColor(pair.status) }]}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.deviceNames}>
          <Text style={styles.deviceName}>{pair.device_a_name || 'Device A'}</Text>
          <Icon name="link" size={16} color="#3b82f6" />
          <Text style={styles.deviceName}>{pair.device_b_name || 'Device B'}</Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(pair.status) + '20' }]}>
          <Text style={[styles.statusText, { color: getStatusColor(pair.status) }]}>
            {pair.status.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* Entropy Bar */}
      <View style={styles.entropySection}>
        <View style={styles.entropyBar}>
          <View 
            style={[
              styles.entropyFill, 
              { 
                width: `${(pair.entropy_score / 8) * 100}%`,
                backgroundColor: getEntropyColor(pair.entropy_health),
              }
            ]} 
          />
        </View>
        <View style={styles.entropyInfo}>
          <Text style={styles.entropyLabel}>Entropy</Text>
          <Text style={[styles.entropyValue, { color: getEntropyColor(pair.entropy_health) }]}>
            {pair.entropy_score?.toFixed(2)} bits/byte
          </Text>
        </View>
      </View>

      {/* Info */}
      <View style={styles.infoSection}>
        <View style={styles.infoRow}>
          <Icon name="clock" size={14} color="#6b7280" />
          <Text style={styles.infoText}>
            Last sync: {pair.last_sync_at 
              ? new Date(pair.last_sync_at).toLocaleDateString()
              : 'Never'}
          </Text>
        </View>
        <View style={styles.infoRow}>
          <Icon name="refresh-cw" size={14} color="#6b7280" />
          <Text style={styles.infoText}>Generation: {pair.current_generation}</Text>
        </View>
      </View>

      {/* Actions */}
      {pair.status === 'active' && (
        <View style={styles.actions}>
          <TouchableOpacity 
            style={styles.actionButton} 
            onPress={() => handleRotate(pair)}
          >
            <Icon name="refresh-cw" size={16} color="#3b82f6" />
            <Text style={styles.actionText}>Rotate</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.actionButton, styles.dangerButton]} 
            onPress={() => handleRevoke(pair)}
          >
            <Icon name="x-circle" size={16} color="#ef4444" />
            <Text style={[styles.actionText, styles.dangerText]}>Revoke</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={styles.loadingText}>Loading entangled devices...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Entangled Devices</Text>
          <Text style={styles.subtitle}>Quantum-inspired synchronized keys</Text>
        </View>
        <TouchableOpacity 
          style={styles.addButton}
          onPress={() => navigation.navigate('DevicePairing')}
        >
          <Icon name="plus" size={24} color="#fff" />
        </TouchableOpacity>
      </View>

      {/* Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Icon name="link" size={24} color="#3b82f6" />
          <Text style={styles.statValue}>
            {pairs.filter(p => p.status === 'active').length}
          </Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={styles.statCard}>
          <Icon name="shield" size={24} color="#10b981" />
          <Text style={styles.statValue}>{maxPairs}</Text>
          <Text style={styles.statLabel}>Max</Text>
        </View>
        <View style={styles.statCard}>
          <Icon name="activity" size={24} color="#8b5cf6" />
          <Text style={styles.statValue}>
            {pairs.filter(p => p.entropy_health === 'healthy').length}
          </Text>
          <Text style={styles.statLabel}>Healthy</Text>
        </View>
      </View>

      {/* Pairs List */}
      <ScrollView 
        style={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {pairs.length === 0 ? (
          <View style={styles.emptyState}>
            <Icon name="zap" size={64} color="#d1d5db" />
            <Text style={styles.emptyTitle}>No Entangled Devices</Text>
            <Text style={styles.emptyText}>
              Pair two devices to create quantum-inspired synchronized keys
            </Text>
            <TouchableOpacity 
              style={styles.primaryButton}
              onPress={() => navigation.navigate('DevicePairing')}
            >
              <Icon name="plus" size={20} color="#fff" />
              <Text style={styles.primaryButtonText}>Start Pairing</Text>
            </TouchableOpacity>
          </View>
        ) : (
          pairs.map(renderPairCard)
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f9fafb',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    color: '#6b7280',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 4,
  },
  addButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#3b82f6',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  statsRow: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    marginTop: 8,
    color: '#111827',
  },
  statLabel: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  list: {
    flex: 1,
    padding: 16,
  },
  pairCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  deviceNames: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  deviceName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  entropySection: {
    marginBottom: 12,
  },
  entropyBar: {
    height: 6,
    backgroundColor: '#e5e7eb',
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 8,
  },
  entropyFill: {
    height: '100%',
    borderRadius: 3,
  },
  entropyInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  entropyLabel: {
    fontSize: 12,
    color: '#6b7280',
  },
  entropyValue: {
    fontSize: 12,
    fontWeight: '600',
  },
  infoSection: {
    backgroundColor: '#f3f4f6',
    borderRadius: 8,
    padding: 12,
    gap: 8,
    marginBottom: 12,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  infoText: {
    fontSize: 13,
    color: '#6b7280',
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 12,
    backgroundColor: '#eff6ff',
    borderRadius: 8,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#3b82f6',
  },
  dangerButton: {
    backgroundColor: '#fef2f2',
  },
  dangerText: {
    color: '#ef4444',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#3b82f6',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 24,
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default EntangledDevicesScreen;

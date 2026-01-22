/**
 * TimeLockScreen - Mobile
 * 
 * Main screen for managing time-lock capsules on mobile.
 * Shows countdown timers and unlock actions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
  ActivityIndicator
} from 'react-native';
import timeLockService from '../services/TimeLockService';

const TimeLockScreen = ({ navigation }) => {
  const [capsules, setCapsules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState({ locked: 0, unlocked: 0, total: 0 });

  const fetchCapsules = useCallback(async () => {
    try {
      const data = await timeLockService.getCapsules();
      setCapsules(data.capsules || []);
      setStats({
        locked: data.locked_count || 0,
        unlocked: data.unlocked_count || 0,
        total: (data.capsules || []).length
      });
    } catch (error) {
      Alert.alert('Error', 'Failed to fetch capsules');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchCapsules();
    
    // Update countdowns every second
    const interval = setInterval(() => {
      setCapsules(prev => prev.map(cap => ({
        ...cap,
        time_remaining_seconds: Math.max(0, cap.time_remaining_seconds - 1)
      })));
    }, 1000);

    return () => clearInterval(interval);
  }, [fetchCapsules]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchCapsules();
  };

  const handleUnlock = async (capsuleId) => {
    try {
      await timeLockService.unlockCapsule(capsuleId);
      Alert.alert('Success', 'Capsule unlocked!');
      fetchCapsules();
    } catch (error) {
      Alert.alert('Error', error.message);
    }
  };

  const handleCancel = (capsuleId) => {
    Alert.alert(
      'Cancel Capsule',
      'Are you sure? This cannot be undone.',
      [
        { text: 'No', style: 'cancel' },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: async () => {
            try {
              await timeLockService.cancelCapsule(capsuleId);
              fetchCapsules();
            } catch (error) {
              Alert.alert('Error', error.message);
            }
          }
        }
      ]
    );
  };

  const getTypeIcon = (type) => {
    const icons = {
      general: '🔐',
      will: '📜',
      escrow: '🤝',
      time_capsule: '⏳',
      emergency: '🚨'
    };
    return icons[type] || '🔒';
  };

  const getStatusColor = (status) => {
    const colors = {
      locked: '#ff6b6b',
      solving: '#ffa500',
      unlocked: '#00e676',
      expired: '#808080',
      cancelled: '#444'
    };
    return colors[status] || '#fff';
  };

  const renderCapsule = ({ item }) => (
    <TouchableOpacity 
      style={[styles.capsuleCard, item.status === 'unlocked' && styles.unlockedCard]}
      onPress={() => navigation.navigate('CapsuleDetail', { capsuleId: item.id })}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.typeIcon}>{getTypeIcon(item.capsule_type)}</Text>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
          <Text style={styles.statusText}>{item.status.toUpperCase()}</Text>
        </View>
      </View>

      <Text style={styles.title}>{item.title}</Text>
      
      {item.description && (
        <Text style={styles.description} numberOfLines={2}>
          {item.description}
        </Text>
      )}

      {item.status === 'locked' && (
        <View style={styles.countdown}>
          <Text style={styles.timeDisplay}>
            {timeLockService.formatTimeRemaining(item.time_remaining_seconds)}
          </Text>
          <View style={styles.progressBar}>
            <View 
              style={[
                styles.progress, 
                { width: `${Math.max(0, (1 - item.time_remaining_seconds / item.delay_seconds) * 100)}%` }
              ]} 
            />
          </View>
        </View>
      )}

      {item.beneficiary_count > 0 && (
        <View style={styles.beneficiaryBadge}>
          <Text style={styles.beneficiaryText}>
            👥 {item.beneficiary_count} beneficiaries
          </Text>
        </View>
      )}

      <View style={styles.actions}>
        {item.is_ready_to_unlock && item.status === 'locked' && (
          <TouchableOpacity 
            style={[styles.actionBtn, styles.unlockBtn]}
            onPress={() => handleUnlock(item.id)}
          >
            <Text style={styles.actionText}>🔓 Unlock</Text>
          </TouchableOpacity>
        )}
        {item.status === 'locked' && !item.is_ready_to_unlock && (
          <TouchableOpacity 
            style={[styles.actionBtn, styles.cancelBtn]}
            onPress={() => handleCancel(item.id)}
          >
            <Text style={[styles.actionText, { color: '#f44336' }]}>❌ Cancel</Text>
          </TouchableOpacity>
        )}
        {item.status === 'unlocked' && (
          <TouchableOpacity style={[styles.actionBtn, styles.viewBtn]}>
            <Text style={[styles.actionText, { color: '#4facfe' }]}>👁️ View</Text>
          </TouchableOpacity>
        )}
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4facfe" />
        <Text style={styles.loadingText}>Loading capsules...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🔐 Time-Lock Vault</Text>
        <Text style={styles.headerSubtitle}>Secrets locked in time</Text>
      </View>

      <View style={styles.statsBar}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{stats.locked}</Text>
          <Text style={styles.statLabel}>Locked</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{stats.unlocked}</Text>
          <Text style={styles.statLabel}>Unlocked</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{stats.total}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
      </View>

      <FlatList
        data={capsules}
        renderItem={renderCapsule}
        keyExtractor={item => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>🔐</Text>
            <Text style={styles.emptyText}>No capsules yet</Text>
            <TouchableOpacity 
              style={styles.createBtn}
              onPress={() => navigation.navigate('CreateCapsule')}
            >
              <Text style={styles.createBtnText}>Create Capsule</Text>
            </TouchableOpacity>
          </View>
        }
      />

      <TouchableOpacity 
        style={styles.fab}
        onPress={() => navigation.navigate('CreateCapsule')}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#1a1a2e',
  },
  loadingText: {
    color: '#a0a0a0',
    marginTop: 16,
  },
  header: {
    padding: 20,
    paddingTop: 50,
    backgroundColor: 'rgba(22, 33, 62, 0.95)',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    color: '#808080',
    marginTop: 4,
  },
  statsBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    padding: 16,
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#4facfe',
  },
  statLabel: {
    fontSize: 12,
    color: '#808080',
    textTransform: 'uppercase',
  },
  listContent: {
    padding: 16,
    paddingBottom: 80,
  },
  capsuleCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  unlockedCard: {
    borderColor: 'rgba(0, 230, 118, 0.3)',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  typeIcon: {
    fontSize: 24,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#1a1a2e',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 8,
  },
  description: {
    color: '#808080',
    fontSize: 14,
    marginBottom: 16,
  },
  countdown: {
    marginBottom: 16,
  },
  timeDisplay: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#ff6b6b',
    textAlign: 'center',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  progressBar: {
    height: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progress: {
    height: '100%',
    backgroundColor: '#667eea',
  },
  beneficiaryBadge: {
    backgroundColor: 'rgba(79, 172, 254, 0.1)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
    alignSelf: 'flex-start',
    marginBottom: 12,
  },
  beneficiaryText: {
    fontSize: 12,
    color: '#4facfe',
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  unlockBtn: {
    backgroundColor: 'rgba(0, 230, 118, 0.2)',
  },
  cancelBtn: {
    backgroundColor: 'rgba(244, 67, 54, 0.1)',
  },
  viewBtn: {
    backgroundColor: 'rgba(79, 172, 254, 0.1)',
  },
  actionText: {
    fontWeight: '600',
    color: '#00e676',
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyIcon: {
    fontSize: 60,
    opacity: 0.5,
  },
  emptyText: {
    color: '#808080',
    marginTop: 16,
    marginBottom: 24,
  },
  createBtn: {
    backgroundColor: '#667eea',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 8,
  },
  createBtnText: {
    color: '#fff',
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#667eea',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#667eea',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
  },
  fabText: {
    fontSize: 28,
    color: '#fff',
    fontWeight: '300',
  },
});

export default TimeLockScreen;

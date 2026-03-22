/**
 * SmartContractScreen (Mobile)
 * 
 * Mobile screen for managing smart contract vaults.
 * Shows vault list, check-in, unlock, and condition status.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import SmartContractService from '../services/SmartContractService';

const CONDITION_ICONS = {
  time_lock: '⏰',
  dead_mans_switch: '💀',
  multi_sig: '🔑',
  dao_vote: '🗳️',
  price_oracle: '📈',
  escrow: '🤝',
};

const CONDITION_LABELS = {
  time_lock: 'Time Lock',
  dead_mans_switch: "Dead Man's Switch",
  multi_sig: 'Multi-Sig',
  dao_vote: 'DAO Vote',
  price_oracle: 'Price Oracle',
  escrow: 'Escrow',
};

const STATUS_COLORS = {
  active: '#34d399',
  unlocked: '#60a5fa',
  cancelled: '#9ca3af',
  expired: '#f87171',
};

const SmartContractScreen = ({ navigation }) => {
  const [vaults, setVaults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchVaults = useCallback(async () => {
    try {
      const data = await SmartContractService.listVaults();
      setVaults(data || []);
    } catch (err) {
      Alert.alert('Error', err.message || 'Failed to load vaults');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchVaults();
  }, [fetchVaults]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchVaults();
  };

  const handleCheckIn = async (vaultId) => {
    try {
      await SmartContractService.checkIn(vaultId);
      Alert.alert('Success', 'Check-in recorded successfully');
      fetchVaults();
    } catch (err) {
      Alert.alert('Error', err.message);
    }
  };

  const handleUnlock = async (vaultId) => {
    try {
      const result = await SmartContractService.unlockVault(vaultId);
      if (result.unlocked) {
        Alert.alert('🔓 Unlocked', 'Vault conditions met. Password released.');
      } else {
        Alert.alert('Locked', `Conditions not met: ${result.reason}`);
      }
      fetchVaults();
    } catch (err) {
      Alert.alert('Error', err.message);
    }
  };

  const handleCancel = (vaultId) => {
    Alert.alert(
      'Cancel Vault',
      'Are you sure you want to cancel this vault?',
      [
        { text: 'No', style: 'cancel' },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: async () => {
            try {
              await SmartContractService.deleteVault(vaultId);
              fetchVaults();
            } catch (err) {
              Alert.alert('Error', err.message);
            }
          },
        },
      ]
    );
  };

  const renderVaultCard = ({ item: vault }) => (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleRow}>
          <Text style={styles.cardIcon}>{CONDITION_ICONS[vault.condition_type]}</Text>
          <Text style={styles.cardTitle} numberOfLines={1}>{vault.title}</Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: STATUS_COLORS[vault.status] + '22' }]}>
          <Text style={[styles.statusText, { color: STATUS_COLORS[vault.status] }]}>
            {vault.status_display}
          </Text>
        </View>
      </View>

      {/* Type */}
      <Text style={styles.typeLabel}>
        {CONDITION_LABELS[vault.condition_type]}
      </Text>

      {/* Condition Info */}
      {vault.condition_type === 'time_lock' && vault.unlock_at && (
        <View style={styles.conditionBox}>
          <Text style={styles.conditionLabel}>Unlock Date</Text>
          <Text style={styles.conditionValue}>
            {new Date(vault.unlock_at).toLocaleDateString()}
          </Text>
        </View>
      )}

      {vault.condition_type === 'dead_mans_switch' && (
        <View style={styles.conditionBox}>
          <Text style={styles.conditionLabel}>Check-In Interval</Text>
          <Text style={styles.conditionValue}>
            Every {vault.check_in_interval_days} days
          </Text>
        </View>
      )}

      {vault.condition_type === 'price_oracle' && vault.price_threshold && (
        <View style={styles.conditionBox}>
          <Text style={styles.conditionLabel}>
            Price {vault.price_above ? 'Above' : 'Below'}
          </Text>
          <Text style={styles.conditionValue}>
            ${Number(vault.price_threshold).toLocaleString()}
          </Text>
        </View>
      )}

      {/* Actions */}
      {vault.status === 'active' && (
        <View style={styles.actions}>
          {vault.condition_type === 'dead_mans_switch' && (
            <TouchableOpacity
              style={[styles.actionBtn, styles.primaryBtn]}
              onPress={() => handleCheckIn(vault.id)}
            >
              <Text style={styles.primaryBtnText}>✓ Check In</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => handleUnlock(vault.id)}
          >
            <Text style={styles.actionBtnText}>🔓 Unlock</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, styles.dangerBtn]}
            onPress={() => handleCancel(vault.id)}
          >
            <Text style={styles.dangerBtnText}>✕</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.loadingText}>Loading vaults...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerIcon}>⛓️</Text>
        <Text style={styles.headerTitle}>Smart Contract Vaults</Text>
      </View>

      {/* Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{vaults.length}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>
            {vaults.filter(v => v.status === 'active').length}
          </Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>
            {vaults.filter(v => v.status === 'unlocked').length}
          </Text>
          <Text style={styles.statLabel}>Unlocked</Text>
        </View>
      </View>

      {/* Vault List */}
      <FlatList
        data={vaults}
        keyExtractor={item => item.id}
        renderItem={renderVaultCard}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#6366f1" />
        }
        contentContainerStyle={vaults.length === 0 ? styles.emptyContainer : styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>⛓️</Text>
            <Text style={styles.emptyTitle}>No Vaults Yet</Text>
            <Text style={styles.emptyText}>
              Create blockchain-powered conditional password vaults
            </Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f1a' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f0f1a' },
  loadingText: { color: '#94a3b8', marginTop: 12, fontSize: 14 },

  header: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 20, paddingTop: 60, paddingBottom: 16,
  },
  headerIcon: { fontSize: 24 },
  headerTitle: { fontSize: 22, fontWeight: '700', color: '#e2e8f0' },

  statsRow: {
    flexDirection: 'row', paddingHorizontal: 16, gap: 10, marginBottom: 16,
  },
  statCard: {
    flex: 1, backgroundColor: 'rgba(30,30,46,0.8)', borderRadius: 12,
    padding: 12, alignItems: 'center',
    borderWidth: 1, borderColor: 'rgba(99,102,241,0.12)',
  },
  statValue: { fontSize: 22, fontWeight: '700', color: '#e2e8f0' },
  statLabel: { fontSize: 11, color: '#94a3b8', marginTop: 2, textTransform: 'uppercase' },

  listContent: { padding: 16, paddingBottom: 100 },
  card: {
    backgroundColor: 'rgba(30,30,46,0.85)', borderRadius: 16,
    padding: 16, marginBottom: 14,
    borderWidth: 1, borderColor: 'rgba(99,102,241,0.12)',
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  cardTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  cardIcon: { fontSize: 18 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: '#e2e8f0', flex: 1 },
  statusBadge: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  statusText: { fontSize: 11, fontWeight: '600', textTransform: 'uppercase' },
  typeLabel: { fontSize: 12, color: '#94a3b8', marginBottom: 10 },

  conditionBox: {
    backgroundColor: 'rgba(99,102,241,0.06)',
    borderWidth: 1, borderColor: 'rgba(99,102,241,0.1)',
    borderRadius: 10, padding: 10, marginBottom: 12,
  },
  conditionLabel: { fontSize: 10, color: '#64748b', textTransform: 'uppercase', marginBottom: 3 },
  conditionValue: { fontSize: 14, color: '#e2e8f0', fontWeight: '500' },

  actions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  actionBtn: {
    flex: 1, paddingVertical: 9, borderRadius: 8,
    borderWidth: 1, borderColor: 'rgba(99,102,241,0.2)',
    alignItems: 'center',
  },
  actionBtnText: { color: '#a78bfa', fontSize: 13, fontWeight: '500' },
  primaryBtn: { backgroundColor: '#6366f1', borderColor: '#6366f1' },
  primaryBtnText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  dangerBtn: { borderColor: 'rgba(239,68,68,0.2)', flex: 0, paddingHorizontal: 14 },
  dangerBtnText: { color: '#f87171', fontSize: 14 },

  emptyContainer: { flex: 1, justifyContent: 'center' },
  emptyState: { alignItems: 'center', padding: 40 },
  emptyIcon: { fontSize: 48, opacity: 0.4, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#e2e8f0', marginBottom: 6 },
  emptyText: { fontSize: 14, color: '#94a3b8', textAlign: 'center' },
});

export default SmartContractScreen;

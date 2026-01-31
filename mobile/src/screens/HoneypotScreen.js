/**
 * Honeypot Screen for Mobile
 * 
 * Main screen for managing honeypot email addresses for breach detection.
 * React Native implementation with mobile-optimized UI.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
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
  FlatList,
} from 'react-native';
import Icon from 'react-native-vector-icons/Feather';
import HoneypotService from '../services/HoneypotService';

const COLORS = {
  primary: '#6366f1',
  secondary: '#8b5cf6',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#0f172a',
  card: '#1e293b',
  border: '#334155',
  text: '#f1f5f9',
  textMuted: '#94a3b8',
};

const HoneypotScreen = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState('honeypots');

  const loadData = useCallback(async () => {
    try {
      const data = await HoneypotService.getDashboardStats();
      setStats(data);
    } catch (error) {
      Alert.alert('Error', 'Failed to load honeypot data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await HoneypotService.checkAllHoneypots();
      await loadData();
    } catch (error) {
      Alert.alert('Error', 'Failed to refresh');
    }
    setRefreshing(false);
  }, [loadData]);

  const handleCreateHoneypot = () => {
    Alert.prompt(
      'Create Honeypot',
      'Enter the service name (e.g., Netflix, Amazon):',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Create',
          onPress: async (serviceName) => {
            if (serviceName?.trim()) {
              try {
                await HoneypotService.createHoneypot({ service_name: serviceName.trim() });
                loadData();
                Alert.alert('Success', 'Honeypot created!');
              } catch (error) {
                Alert.alert('Error', error.response?.data?.error || 'Failed to create honeypot');
              }
            }
          },
        },
      ],
      'plain-text'
    );
  };

  const handleDeleteHoneypot = (honeypot) => {
    Alert.alert(
      'Delete Honeypot',
      `Are you sure you want to delete the honeypot for ${honeypot.service_name}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await HoneypotService.deleteHoneypot(honeypot.id);
              loadData();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete honeypot');
            }
          },
        },
      ]
    );
  };

  const handleAcknowledgeBreach = async (breach) => {
    try {
      await HoneypotService.updateBreach(breach.id, { acknowledge: true });
      loadData();
    } catch (error) {
      Alert.alert('Error', 'Failed to acknowledge breach');
    }
  };

  const handleRotateCredentials = async (breach) => {
    Alert.alert(
      'Rotate Credentials',
      `This will mark ${breach.service_name} for credential rotation. Proceed?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rotate',
          onPress: async () => {
            try {
              await HoneypotService.initiateRotation(breach.id);
              loadData();
              Alert.alert('Success', 'Credential rotation initiated');
            } catch (error) {
              Alert.alert('Error', 'Failed to initiate rotation');
            }
          },
        },
      ]
    );
  };

  const getStatusColor = (status) => {
    const colors = {
      active: COLORS.success,
      triggered: COLORS.warning,
      breached: COLORS.danger,
      disabled: COLORS.textMuted,
    };
    return colors[status] || COLORS.textMuted;
  };

  const getSeverityIcon = (severity) => {
    const icons = { critical: '🔴', high: '🟠', medium: '🟡', low: '🟢' };
    return icons[severity] || '⚪';
  };

  const renderStatCard = (icon, value, label, color) => (
    <View style={[styles.statCard, { borderLeftColor: color }]}>
      <Icon name={icon} size={24} color={color} />
      <View style={styles.statContent}>
        <Text style={styles.statValue}>{value}</Text>
        <Text style={styles.statLabel}>{label}</Text>
      </View>
    </View>
  );

  const renderHoneypotItem = ({ item }) => (
    <TouchableOpacity 
      style={[styles.honeypotCard, item.breach_detected && styles.breachedCard]}
      activeOpacity={0.7}
    >
      <View style={styles.honeypotHeader}>
        <Text style={styles.honeypotName}>{item.service_name}</Text>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '30' }]}>
          <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
            {item.status.toUpperCase()}
          </Text>
        </View>
      </View>
      
      <Text style={styles.honeypotEmail}>
        <Icon name="mail" size={12} /> {item.honeypot_address}
      </Text>
      
      <View style={styles.honeypotMeta}>
        <Text style={styles.metaText}>
          <Icon name="clock" size={12} /> {item.days_active} days
        </Text>
        {item.total_emails_received > 0 && (
          <Text style={styles.metaText}>📧 {item.total_emails_received}</Text>
        )}
      </View>
      
      {item.breach_detected && (
        <View style={styles.breachWarning}>
          <Icon name="alert-triangle" size={14} color={COLORS.danger} />
          <Text style={styles.breachWarningText}>
            Breach detected ({(item.breach_confidence * 100).toFixed(0)}%)
          </Text>
        </View>
      )}
      
      <TouchableOpacity 
        style={styles.deleteButton}
        onPress={() => handleDeleteHoneypot(item)}
      >
        <Icon name="trash-2" size={16} color={COLORS.danger} />
      </TouchableOpacity>
    </TouchableOpacity>
  );

  const renderBreachItem = ({ item }) => (
    <View style={[styles.breachCard, styles[`severity${item.severity}`]]}>
      <View style={styles.breachHeader}>
        <Text style={styles.severityIcon}>{getSeverityIcon(item.severity)}</Text>
        <Text style={styles.breachName}>{item.service_name}</Text>
      </View>
      
      <Text style={styles.breachDetail}>
        Detected: {new Date(item.detected_at).toLocaleDateString()}
      </Text>
      <Text style={styles.breachDetail}>
        Confidence: {(item.confidence_score * 100).toFixed(0)}%
      </Text>
      
      {item.days_before_public && (
        <Text style={styles.earlyDetection}>
          🎯 {item.days_before_public} days before public disclosure
        </Text>
      )}
      
      <View style={styles.breachActions}>
        {!item.user_acknowledged && (
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => handleAcknowledgeBreach(item)}
          >
            <Icon name="check" size={14} color={COLORS.text} />
            <Text style={styles.actionText}>Acknowledge</Text>
          </TouchableOpacity>
        )}
        {!item.credentials_rotated && (
          <TouchableOpacity 
            style={[styles.actionButton, styles.primaryAction]}
            onPress={() => handleRotateCredentials(item)}
          >
            <Icon name="refresh-cw" size={14} color={COLORS.text} />
            <Text style={styles.actionText}>Rotate</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Loading Honeypots...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Honeypot Protection</Text>
          <Text style={styles.subtitle}>Detect breaches early</Text>
        </View>
        <TouchableOpacity style={styles.addButton} onPress={handleCreateHoneypot}>
          <Icon name="plus" size={20} color={COLORS.text} />
        </TouchableOpacity>
      </View>

      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={COLORS.primary}
          />
        }
      >
        {/* Stats */}
        <View style={styles.statsGrid}>
          {renderStatCard('shield', stats?.activeHoneypots || 0, 'Active', COLORS.success)}
          {renderStatCard('activity', stats?.triggeredHoneypots || 0, 'Triggered', COLORS.warning)}
          {renderStatCard('alert-triangle', stats?.unresolvedBreaches || 0, 'Breaches', COLORS.danger)}
          {renderStatCard('mail', stats?.totalHoneypots || 0, 'Total', COLORS.primary)}
        </View>

        {/* Tabs */}
        <View style={styles.tabs}>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'honeypots' && styles.activeTab]}
            onPress={() => setActiveTab('honeypots')}
          >
            <Icon name="mail" size={16} color={activeTab === 'honeypots' ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'honeypots' && styles.activeTabText]}>
              Honeypots
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'breaches' && styles.activeTab]}
            onPress={() => setActiveTab('breaches')}
          >
            <Icon name="alert-triangle" size={16} color={activeTab === 'breaches' ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'breaches' && styles.activeTabText]}>
              Breaches ({stats?.unresolvedBreaches || 0})
            </Text>
          </TouchableOpacity>
        </View>

        {/* Content */}
        {activeTab === 'honeypots' && (
          <View style={styles.content}>
            {stats?.honeypots?.length === 0 ? (
              <View style={styles.emptyState}>
                <Icon name="mail" size={48} color={COLORS.textMuted} />
                <Text style={styles.emptyTitle}>No Honeypots Yet</Text>
                <Text style={styles.emptyText}>
                  Create honeypot emails to detect breaches early.
                </Text>
                <TouchableOpacity style={styles.createButton} onPress={handleCreateHoneypot}>
                  <Icon name="plus" size={18} color={COLORS.text} />
                  <Text style={styles.createButtonText}>Create Honeypot</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <FlatList
                data={stats.honeypots}
                renderItem={renderHoneypotItem}
                keyExtractor={(item) => item.id}
                scrollEnabled={false}
              />
            )}
          </View>
        )}

        {activeTab === 'breaches' && (
          <View style={styles.content}>
            {stats?.breaches?.length === 0 ? (
              <View style={styles.emptyState}>
                <Icon name="shield" size={48} color={COLORS.success} />
                <Text style={styles.emptyTitle}>No Breaches Detected</Text>
                <Text style={styles.emptyText}>
                  Your honeypots are monitoring for suspicious activity.
                </Text>
              </View>
            ) : (
              <FlatList
                data={stats.breaches}
                renderItem={renderBreachItem}
                keyExtractor={(item) => item.id}
                scrollEnabled={false}
              />
            )}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.background,
  },
  loadingText: {
    color: COLORS.textMuted,
    marginTop: 12,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.text,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textMuted,
  },
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 10,
    gap: 10,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    borderLeftWidth: 4,
  },
  statContent: {
    marginLeft: 12,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.text,
  },
  statLabel: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  tabs: {
    flexDirection: 'row',
    marginHorizontal: 20,
    marginTop: 10,
    borderRadius: 12,
    backgroundColor: COLORS.card,
    overflow: 'hidden',
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    gap: 6,
  },
  activeTab: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderBottomWidth: 2,
    borderBottomColor: COLORS.primary,
  },
  tabText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: '500',
  },
  activeTabText: {
    color: COLORS.primary,
  },
  content: {
    padding: 20,
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.text,
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: COLORS.textMuted,
    textAlign: 'center',
    marginTop: 8,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 20,
    gap: 8,
  },
  createButtonText: {
    color: COLORS.text,
    fontWeight: '600',
  },
  honeypotCard: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  breachedCard: {
    borderColor: COLORS.danger,
    backgroundColor: 'rgba(239, 68, 68, 0.05)',
  },
  honeypotHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  honeypotName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  honeypotEmail: {
    fontSize: 12,
    color: COLORS.textMuted,
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  honeypotMeta: {
    flexDirection: 'row',
    gap: 12,
  },
  metaText: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  breachWarning: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    padding: 8,
    borderRadius: 6,
    marginTop: 10,
    gap: 6,
  },
  breachWarningText: {
    color: COLORS.danger,
    fontSize: 12,
  },
  deleteButton: {
    position: 'absolute',
    top: 16,
    right: 16,
  },
  breachCard: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  severitycritical: { borderLeftColor: '#dc2626' },
  severityhigh: { borderLeftColor: '#f97316' },
  severitymedium: { borderLeftColor: '#eab308' },
  severitylow: { borderLeftColor: '#22c55e' },
  breachHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  severityIcon: {
    fontSize: 16,
  },
  breachName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },
  breachDetail: {
    fontSize: 13,
    color: COLORS.textMuted,
    marginBottom: 4,
  },
  earlyDetection: {
    fontSize: 13,
    color: COLORS.success,
    fontWeight: '500',
    marginTop: 6,
  },
  breachActions: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(148, 163, 184, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    gap: 6,
  },
  primaryAction: {
    backgroundColor: COLORS.primary,
  },
  actionText: {
    fontSize: 12,
    color: COLORS.text,
    fontWeight: '500',
  },
});

export default HoneypotScreen;

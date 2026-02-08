/**
 * Predictive Password Expiration Screen (Mobile)
 * ================================================
 * 
 * React Native screen for predictive password expiration feature.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Alert,
  Switch,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import PredictiveExpirationService from '../services/PredictiveExpirationService';

// Color constants
const COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  minimal: '#6b7280',
  primary: '#6366f1',
  background: '#0f172a',
  card: '#1e293b',
  surface: '#334155',
  text: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#475569',
};

// Risk Badge Component
const RiskBadge = ({ level, score }) => {
  const getColor = () => {
    switch (level) {
      case 'critical': return COLORS.critical;
      case 'high': return COLORS.high;
      case 'medium': return COLORS.medium;
      case 'low': return COLORS.low;
      default: return COLORS.minimal;
    }
  };

  return (
    <View style={[styles.badge, { backgroundColor: getColor() + '33' }]}>
      <Text style={[styles.badgeText, { color: getColor() }]}>
        {level?.toUpperCase()} {score && `(${Math.round(score * 100)}%)`}
      </Text>
    </View>
  );
};

// Credential Risk Card Component
const CredentialRiskCard = ({ credential, onRotate, onAcknowledge }) => {
  const getRiskColor = () => {
    switch (credential.risk_level) {
      case 'critical': return COLORS.critical;
      case 'high': return COLORS.high;
      case 'medium': return COLORS.medium;
      case 'low': return COLORS.low;
      default: return COLORS.minimal;
    }
  };

  const getDaysUntil = () => {
    if (!credential.predicted_compromise_date) return null;
    const now = new Date();
    const target = new Date(credential.predicted_compromise_date);
    const diffTime = target - now;
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  };

  const daysUntil = getDaysUntil();

  return (
    <View style={[styles.credentialCard, { borderLeftColor: getRiskColor() }]}>
      <View style={styles.credentialHeader}>
        <Icon name="lock" size={20} color={COLORS.text} />
        <Text style={styles.credentialDomain} numberOfLines={1}>
          {credential.credential_domain}
        </Text>
        <RiskBadge level={credential.risk_level} score={credential.risk_score} />
      </View>

      <View style={styles.credentialBody}>
        {daysUntil !== null && (
          <View style={styles.infoRow}>
            <Icon name="clock-outline" size={14} color={COLORS.textSecondary} />
            <Text style={styles.infoText}>
              {daysUntil > 0 
                ? `${daysUntil} days until predicted compromise`
                : 'Immediate action required'}
            </Text>
          </View>
        )}

        <View style={styles.infoRow}>
          <Icon name="alert-circle-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.infoText}>
            {credential.recommended_action?.replace(/_/g, ' ') || 'Monitor'}
          </Text>
        </View>
      </View>

      <View style={styles.credentialActions}>
        {!credential.user_acknowledged && (
          <TouchableOpacity 
            style={styles.btnAcknowledge}
            onPress={() => onAcknowledge(credential.credential_id)}
          >
            <Icon name="check-circle" size={16} color={COLORS.low} />
            <Text style={[styles.btnText, { color: COLORS.low }]}>Acknowledge</Text>
          </TouchableOpacity>
        )}

        {['rotate_immediately', 'rotate_soon'].includes(credential.recommended_action) && (
          <TouchableOpacity 
            style={styles.btnRotate}
            onPress={() => onRotate(credential.credential_id)}
          >
            <Icon name="refresh" size={16} color="#fff" />
            <Text style={styles.btnRotateText}>Rotate</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

// Threat Actor Card Component
const ThreatActorCard = ({ threat }) => {
  const getThreatColor = () => {
    switch (threat.threat_level) {
      case 'critical': return COLORS.critical;
      case 'high': return COLORS.high;
      default: return COLORS.medium;
    }
  };

  return (
    <View style={[styles.threatCard, { borderLeftColor: getThreatColor() }]}>
      <View style={styles.threatHeader}>
        <Icon name="target" size={20} color={COLORS.text} />
        <Text style={styles.threatName} numberOfLines={1}>{threat.name}</Text>
        <RiskBadge level={threat.threat_level} />
      </View>

      <View style={styles.threatBody}>
        <Text style={styles.threatType}>{threat.actor_type}</Text>
        {threat.is_currently_active && (
          <View style={styles.activeIndicator}>
            <Icon name="pulse" size={12} color={COLORS.low} />
            <Text style={styles.activeText}>Active</Text>
          </View>
        )}
      </View>
    </View>
  );
};

// Stat Card Component
const StatCard = ({ icon, value, label, color }) => (
  <View style={styles.statCard}>
    <View style={[styles.statIcon, { backgroundColor: color + '33' }]}>
      <Icon name={icon} size={24} color={color} />
    </View>
    <View style={styles.statContent}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  </View>
);

// Main Screen Component
const PredictiveExpirationScreen = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [threatSummary, setThreatSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [dashData, threatData, settingsData] = await Promise.all([
        PredictiveExpirationService.getDashboard(),
        PredictiveExpirationService.getThreatSummary(),
        PredictiveExpirationService.getSettings(),
      ]);

      setDashboard(dashData);
      setThreatSummary(threatData);
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleRotate = async (credentialId) => {
    Alert.alert(
      'Rotate Password',
      'Are you sure you want to rotate this password?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rotate',
          style: 'destructive',
          onPress: async () => {
            try {
              await PredictiveExpirationService.forceRotation(credentialId);
              fetchData();
            } catch (err) {
              Alert.alert('Error', 'Failed to rotate password');
            }
          },
        },
      ]
    );
  };

  const handleAcknowledge = async (credentialId) => {
    try {
      await PredictiveExpirationService.acknowledgeRisk(credentialId);
      fetchData();
    } catch (err) {
      Alert.alert('Error', 'Failed to acknowledge risk');
    }
  };

  const handleToggleFeature = async (value) => {
    try {
      const updated = await PredictiveExpirationService.updateSettings({
        is_enabled: value,
      });
      setSettings(updated);
    } catch (err) {
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const getRiskLevel = (score) => {
    if (score >= 0.8) return 'Critical';
    if (score >= 0.6) return 'High';
    if (score >= 0.4) return 'Medium';
    if (score >= 0.2) return 'Low';
    return 'Minimal';
  };

  const getRiskColor = (score) => {
    if (score >= 0.8) return COLORS.critical;
    if (score >= 0.6) return COLORS.high;
    if (score >= 0.4) return COLORS.medium;
    if (score >= 0.2) return COLORS.low;
    return COLORS.minimal;
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Loading predictive analysis...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Icon name="alert-outline" size={48} color={COLORS.critical} />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={fetchData}>
          <Icon name="refresh" size={16} color="#fff" />
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const overallScore = dashboard?.overall_risk_score || 0;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={COLORS.primary}
        />
      }
    >
      {/* Header Section */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Icon name="shield-check" size={32} color={COLORS.primary} />
          <View>
            <Text style={styles.headerTitle}>Predictive Expiration</Text>
            <Text style={styles.headerSubtitle}>AI-powered password security</Text>
          </View>
        </View>
        <Switch
          value={settings?.is_enabled || false}
          onValueChange={handleToggleFeature}
          trackColor={{ false: COLORS.surface, true: COLORS.primary + '66' }}
          thumbColor={settings?.is_enabled ? COLORS.primary : COLORS.textSecondary}
        />
      </View>

      {/* Overall Risk Score */}
      <View style={styles.riskOverview}>
        <View style={[styles.riskCircle, { borderColor: getRiskColor(overallScore) }]}>
          <Text style={styles.riskValue}>{Math.round(overallScore * 100)}%</Text>
          <Text style={styles.riskLabel}>{getRiskLevel(overallScore)}</Text>
        </View>
        <Text style={styles.riskTitle}>Overall Risk Score</Text>
      </View>

      {/* Quick Stats */}
      <View style={styles.statsGrid}>
        <StatCard 
          icon="close-circle" 
          value={dashboard?.critical_count || 0} 
          label="Critical" 
          color={COLORS.critical} 
        />
        <StatCard 
          icon="alert" 
          value={dashboard?.high_count || 0} 
          label="High Risk" 
          color={COLORS.high} 
        />
        <StatCard 
          icon="alert-circle" 
          value={dashboard?.medium_count || 0} 
          label="Medium" 
          color={COLORS.medium} 
        />
        <StatCard 
          icon="clock" 
          value={dashboard?.pending_rotations || 0} 
          label="Pending" 
          color={COLORS.primary} 
        />
      </View>

      {/* At-Risk Credentials */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Icon name="lock" size={20} color={COLORS.text} />
          <Text style={styles.sectionTitle}>At-Risk Credentials</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countBadgeText}>{dashboard?.at_risk_count || 0}</Text>
          </View>
        </View>

        {dashboard?.credentials_at_risk?.length > 0 ? (
          dashboard.credentials_at_risk.map((cred) => (
            <CredentialRiskCard
              key={cred.credential_id}
              credential={cred}
              onRotate={handleRotate}
              onAcknowledge={handleAcknowledge}
            />
          ))
        ) : (
          <View style={styles.emptyState}>
            <Icon name="check-circle" size={48} color={COLORS.low} />
            <Text style={styles.emptyStateText}>No credentials at risk!</Text>
          </View>
        )}
      </View>

      {/* Active Threats */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Icon name="target" size={20} color={COLORS.text} />
          <Text style={styles.sectionTitle}>Active Threats</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countBadgeText}>{threatSummary?.total_active_actors || 0}</Text>
          </View>
        </View>

        <View style={styles.threatSummary}>
          <View style={styles.threatStat}>
            <Icon name="flash" size={14} color={COLORS.critical} />
            <Text style={styles.threatStatText}>{threatSummary?.critical_threats || 0} Critical</Text>
          </View>
          <View style={styles.threatStat}>
            <Icon name="alert" size={14} color={COLORS.high} />
            <Text style={styles.threatStatText}>{threatSummary?.high_threats || 0} High</Text>
          </View>
        </View>

        {dashboard?.active_threats?.length > 0 ? (
          dashboard.active_threats.map((threat) => (
            <ThreatActorCard key={threat.actor_id} threat={threat} />
          ))
        ) : (
          <View style={styles.emptyState}>
            <Icon name="shield" size={48} color={COLORS.low} />
            <Text style={styles.emptyStateText}>No high-priority threats</Text>
          </View>
        )}
      </View>

      {/* View All Button */}
      <TouchableOpacity 
        style={styles.viewAllButton}
        onPress={() => navigation.navigate('PredictiveExpirationDetails')}
      >
        <Text style={styles.viewAllText}>View All Details</Text>
        <Icon name="chevron-right" size={20} color={COLORS.primary} />
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.background,
  },
  loadingText: {
    marginTop: 12,
    color: COLORS.textSecondary,
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    padding: 24,
  },
  errorText: {
    marginTop: 12,
    color: COLORS.textSecondary,
    fontSize: 16,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 16,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryText: {
    marginLeft: 8,
    color: '#fff',
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.text,
  },
  headerSubtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  riskOverview: {
    alignItems: 'center',
    marginBottom: 24,
    padding: 24,
    backgroundColor: COLORS.card,
    borderRadius: 16,
  },
  riskCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  riskValue: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.text,
  },
  riskLabel: {
    fontSize: 12,
    color: COLORS.textSecondary,
    textTransform: 'uppercase',
  },
  riskTitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: COLORS.card,
    borderRadius: 12,
    gap: 12,
  },
  statIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statContent: {
    flex: 1,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.text,
  },
  statLabel: {
    fontSize: 10,
    color: COLORS.textSecondary,
    textTransform: 'uppercase',
  },
  section: {
    marginBottom: 24,
    padding: 16,
    backgroundColor: COLORS.card,
    borderRadius: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 8,
  },
  sectionTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },
  countBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: COLORS.primary,
    borderRadius: 12,
  },
  countBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  credentialCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 4,
  },
  credentialHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  credentialDomain: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },
  credentialBody: {
    marginBottom: 8,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  infoText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  credentialActions: {
    flexDirection: 'row',
    gap: 8,
  },
  btnAcknowledge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: COLORS.low + '22',
  },
  btnRotate: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: COLORS.primary,
  },
  btnText: {
    fontSize: 12,
    fontWeight: '600',
  },
  btnRotateText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  threatCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 4,
  },
  threatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  threatName: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },
  threatBody: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  threatType: {
    fontSize: 12,
    color: COLORS.textSecondary,
    textTransform: 'capitalize',
  },
  activeIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  activeText: {
    fontSize: 10,
    color: COLORS.low,
  },
  threatSummary: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
    padding: 12,
    backgroundColor: COLORS.surface,
    borderRadius: 8,
  },
  threatStat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  threatStatText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  emptyStateText: {
    marginTop: 12,
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  viewAllButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
    backgroundColor: COLORS.card,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: COLORS.border,
  },
  viewAllText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
});

export default PredictiveExpirationScreen;

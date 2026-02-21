/**
 * Password Archaeology Screen
 * ==============================
 * React Native screen for Password Archaeology & Time Travel.
 * Shows timeline, strength metrics, achievements, and time machine.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Dimensions, RefreshControl, ActivityIndicator, FlatList,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const API_BASE = '/api/archaeology';

// ===================================================================
// API Functions (simplified for mobile)
// ===================================================================

async function fetchAPI(endpoint, token) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

// ===================================================================
// Helpers
// ===================================================================

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getStrengthColor(score) {
  if (score >= 80) return '#10b981';
  if (score >= 60) return '#3b82f6';
  if (score >= 40) return '#f59e0b';
  return '#ef4444';
}

function getScoreGrade(score) {
  if (score >= 90) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C';
  if (score >= 50) return 'D';
  return 'F';
}

// ===================================================================
// Sub-components
// ===================================================================

function ScoreRing({ score, size = 80 }) {
  const color = getStrengthColor(score);
  return (
    <View style={[styles.scoreRing, { width: size, height: size, borderRadius: size / 2 }]}>
      <View style={[styles.scoreRingInner, {
        width: size - 8,
        height: size - 8,
        borderRadius: (size - 8) / 2,
      }]}>
        <Text style={[styles.scoreRingValue, { color, fontSize: size * 0.28 }]}>
          {score}
        </Text>
      </View>
    </View>
  );
}

function StatCard({ icon, value, label, color = '#6366f1' }) {
  return (
    <View style={styles.statCard}>
      <Text style={{ fontSize: 20, marginBottom: 4 }}>{icon}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function TimelineItem({ event }) {
  const isPasswordChange = event.type === 'password_change';
  const icon = isPasswordChange ? '🔑' : '🛡️';
  const dotColor = isPasswordChange ? '#10b981' : event.severity === 'critical' ? '#ef4444' : '#f59e0b';

  return (
    <View style={styles.timelineItem}>
      <View style={styles.timelineLeft}>
        <View style={[styles.timelineDot, { backgroundColor: dotColor }]} />
        <View style={styles.timelineLine} />
      </View>
      <View style={styles.timelineCard}>
        <View style={styles.timelineCardHeader}>
          <Text style={styles.timelineIcon}>{icon}</Text>
          <Text style={styles.timelineTitle} numberOfLines={1}>
            {isPasswordChange
              ? `Password changed: ${event.credential_domain || 'Unknown'}`
              : event.title || event.event_type_display
            }
          </Text>
        </View>
        <Text style={styles.timelineTimestamp}>{formatDate(event.timestamp)}</Text>

        {isPasswordChange && (
          <View style={styles.strengthBars}>
            <View style={styles.strengthRow}>
              <Text style={styles.strengthLabel}>Before</Text>
              <View style={styles.strengthTrack}>
                <View style={[styles.strengthFill, {
                  width: `${event.strength_before || 0}%`,
                  backgroundColor: getStrengthColor(event.strength_before || 0),
                }]} />
              </View>
              <Text style={[styles.strengthValue, { color: getStrengthColor(event.strength_before || 0) }]}>
                {event.strength_before || 0}
              </Text>
            </View>
            <View style={styles.strengthRow}>
              <Text style={styles.strengthLabel}>After</Text>
              <View style={styles.strengthTrack}>
                <View style={[styles.strengthFill, {
                  width: `${event.strength_after || 0}%`,
                  backgroundColor: getStrengthColor(event.strength_after || 0),
                }]} />
              </View>
              <Text style={[styles.strengthValue, { color: getStrengthColor(event.strength_after || 0) }]}>
                {event.strength_after || 0}
              </Text>
            </View>
          </View>
        )}

        {!isPasswordChange && event.description && (
          <Text style={styles.timelineDesc} numberOfLines={2}>{event.description}</Text>
        )}

        {!isPasswordChange && event.severity && (
          <View style={styles.severityRow}>
            <View style={[styles.severityBadge, {
              backgroundColor: event.severity === 'critical' ? 'rgba(239,68,68,0.15)'
                : event.severity === 'high' ? 'rgba(239,68,68,0.1)'
                : event.severity === 'medium' ? 'rgba(245,158,11,0.15)'
                : 'rgba(59,130,246,0.15)',
            }]}>
              <Text style={[styles.severityText, {
                color: event.severity === 'critical' ? '#ef4444'
                  : event.severity === 'high' ? '#f87171'
                  : event.severity === 'medium' ? '#fbbf24'
                  : '#60a5fa',
              }]}>
                {event.severity.toUpperCase()}
              </Text>
            </View>
            {event.resolved && (
              <View style={[styles.severityBadge, { backgroundColor: 'rgba(16,185,129,0.15)' }]}>
                <Text style={[styles.severityText, { color: '#34d399' }]}>RESOLVED</Text>
              </View>
            )}
          </View>
        )}

        {isPasswordChange && event.has_blockchain_proof && (
          <View style={styles.blockchainBadge}>
            <Text style={styles.blockchainText}>🔗 Blockchain Verified</Text>
          </View>
        )}
      </View>
    </View>
  );
}

function AchievementCard({ achievement }) {
  const tierColors = {
    bronze: ['#b87855', '#cd8c5e'],
    silver: ['#a8b3c0', '#c0cad5'],
    gold: ['#d4a846', '#f0c75e'],
    platinum: ['#7cb7d0', '#a0d2e7'],
    diamond: ['#8b5cf6', '#a78bfa'],
  };
  const colors = tierColors[achievement.badge_tier] || tierColors.bronze;

  return (
    <View style={[styles.achievementCard, !achievement.acknowledged && styles.achievementNew]}>
      <LinearGradient
        colors={colors}
        style={styles.achievementIcon}
      >
        <Text style={{ fontSize: 20 }}>🏆</Text>
      </LinearGradient>
      <View style={styles.achievementInfo}>
        <Text style={styles.achievementTitle}>{achievement.title}</Text>
        <Text style={styles.achievementDesc} numberOfLines={2}>
          {achievement.description}
        </Text>
        <View style={styles.achievementMeta}>
          <Text style={styles.achievementPoints}>⭐ {achievement.score_points} pts</Text>
          <Text style={styles.achievementDate}>{formatDate(achievement.earned_at)}</Text>
          {!achievement.acknowledged && (
            <Text style={styles.achievementNewBadge}>✨ New!</Text>
          )}
        </View>
      </View>
    </View>
  );
}

// ===================================================================
// Main Screen
// ===================================================================

export default function PasswordArchaeologyScreen({ navigation, route }) {
  const [activeTab, setActiveTab] = useState('timeline');
  const [dashboard, setDashboard] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const token = route?.params?.token || '';

  const fetchData = useCallback(async () => {
    try {
      const [dashData, timelineData, achData] = await Promise.all([
        fetchAPI('/dashboard/', token),
        fetchAPI('/timeline/?limit=30', token),
        fetchAPI('/achievements/', token),
      ]);
      setDashboard(dashData);
      setTimeline(timelineData.timeline || []);
      setAchievements(achData.achievements || []);
      setError(null);
    } catch (err) {
      console.error('Archaeology fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const tabs = [
    { id: 'timeline', label: '📜 Timeline' },
    { id: 'achievements', label: '🏆 Achievements' },
  ];

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.loadingText}>Loading archaeology data...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorIcon}>⚠️</Text>
        <Text style={styles.loadingText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={fetchData}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#6366f1" />
      }
    >
      {/* Header */}
      <LinearGradient
        colors={['#6366f1', '#8b5cf6']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.headerTitle}>Password Archaeology</Text>
            <Text style={styles.headerSubtitle}>Time Travel · History · Insights</Text>
          </View>
          {dashboard && (
            <View style={styles.headerScore}>
              <Text style={styles.headerScoreValue}>
                {getScoreGrade(dashboard.overall_score || 0)}
              </Text>
              <Text style={styles.headerScoreLabel}>
                {dashboard.overall_score || 0}/100
              </Text>
            </View>
          )}
        </View>
      </LinearGradient>

      {/* Stats */}
      {dashboard && (
        <View style={styles.statsGrid}>
          <StatCard icon="🔑" value={dashboard.total_changes || 0} label="Changes" color="#8b5cf6" />
          <StatCard icon="🛡️" value={dashboard.total_credentials || 0} label="Credentials" color="#3b82f6" />
          <StatCard icon="📈" value={dashboard.avg_strength?.toFixed(0) || '—'} label="Avg Strength" color="#10b981" />
          <StatCard icon="⚠️" value={dashboard.total_breaches || 0} label="Breaches" color="#ef4444" />
        </View>
      )}

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        {tabs.map(tab => (
          <TouchableOpacity
            key={tab.id}
            style={[styles.tab, activeTab === tab.id && styles.tabActive]}
            onPress={() => setActiveTab(tab.id)}
          >
            <Text style={[styles.tabText, activeTab === tab.id && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      {activeTab === 'timeline' && (
        <View style={styles.section}>
          {timeline.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>🕰️</Text>
              <Text style={styles.emptyText}>No history yet</Text>
              <Text style={styles.emptySub}>
                Password changes and events will appear here.
              </Text>
            </View>
          ) : (
            timeline.map((event, i) => (
              <TimelineItem key={event.id || i} event={event} />
            ))
          )}
        </View>
      )}

      {activeTab === 'achievements' && (
        <View style={styles.section}>
          {achievements.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>🏆</Text>
              <Text style={styles.emptyText}>No achievements yet</Text>
              <Text style={styles.emptySub}>
                Keep improving your security to earn badges!
              </Text>
            </View>
          ) : (
            achievements.map((ach, i) => (
              <AchievementCard key={ach.id || i} achievement={ach} />
            ))
          )}
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ===================================================================
// Styles
// ===================================================================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0a0e1a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  loadingText: {
    color: '#94a3b8',
    fontSize: 15,
    marginTop: 16,
    textAlign: 'center',
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 8,
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 10,
    backgroundColor: '#6366f1',
    borderRadius: 8,
  },
  retryText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },

  // Header
  header: {
    padding: 24,
    paddingTop: 60,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  headerSubtitle: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 13,
    marginTop: 4,
  },
  headerScore: {
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 16,
  },
  headerScoreValue: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  headerScoreLabel: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 11,
    marginTop: 2,
  },

  // Score Ring
  scoreRing: {
    borderWidth: 3,
    borderColor: 'rgba(99,102,241,0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scoreRingInner: {
    backgroundColor: '#111827',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scoreRingValue: {
    fontWeight: '700',
  },

  // Stats
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 16,
    gap: 10,
  },
  statCard: {
    backgroundColor: 'rgba(17,24,39,0.85)',
    borderRadius: 12,
    padding: 14,
    width: (SCREEN_WIDTH - 42) / 2,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#f1f5f9',
  },
  statLabel: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 2,
  },

  // Tabs
  tabsContainer: {
    flexDirection: 'row',
    marginHorizontal: 16,
    backgroundColor: 'rgba(17,24,39,0.85)',
    borderRadius: 12,
    padding: 4,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 10,
  },
  tabActive: {
    backgroundColor: '#6366f1',
  },
  tabText: {
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#fff',
    fontWeight: '600',
  },

  // Section
  section: {
    padding: 16,
  },

  // Timeline
  timelineItem: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  timelineLeft: {
    width: 24,
    alignItems: 'center',
  },
  timelineDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginTop: 14,
  },
  timelineLine: {
    width: 2,
    flex: 1,
    backgroundColor: 'rgba(99,102,241,0.2)',
    marginTop: 4,
  },
  timelineCard: {
    flex: 1,
    marginLeft: 12,
    backgroundColor: 'rgba(17,24,39,0.85)',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  timelineCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  timelineIcon: {
    fontSize: 16,
  },
  timelineTitle: {
    color: '#f1f5f9',
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  timelineTimestamp: {
    color: '#64748b',
    fontSize: 11,
    marginBottom: 8,
  },
  timelineDesc: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8,
  },

  // Strength
  strengthBars: {
    marginTop: 8,
    gap: 6,
  },
  strengthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  strengthLabel: {
    color: '#64748b',
    fontSize: 11,
    width: 40,
  },
  strengthTrack: {
    flex: 1,
    height: 6,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 3,
    overflow: 'hidden',
  },
  strengthFill: {
    height: '100%',
    borderRadius: 3,
  },
  strengthValue: {
    fontSize: 12,
    fontWeight: '600',
    width: 24,
    textAlign: 'right',
  },

  // Severity
  severityRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  severityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 100,
  },
  severityText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },

  // Blockchain
  blockchainBadge: {
    marginTop: 8,
    backgroundColor: 'rgba(99,102,241,0.1)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 100,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.2)',
  },
  blockchainText: {
    color: '#6366f1',
    fontSize: 11,
  },

  // Achievements
  achievementCard: {
    flexDirection: 'row',
    backgroundColor: 'rgba(17,24,39,0.85)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    gap: 14,
  },
  achievementNew: {
    borderColor: 'rgba(99,102,241,0.3)',
  },
  achievementIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  achievementInfo: {
    flex: 1,
  },
  achievementTitle: {
    color: '#f1f5f9',
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 4,
  },
  achievementDesc: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 18,
  },
  achievementMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 8,
  },
  achievementPoints: {
    color: '#f59e0b',
    fontWeight: '600',
    fontSize: 12,
  },
  achievementDate: {
    color: '#64748b',
    fontSize: 12,
  },
  achievementNewBadge: {
    color: '#6366f1',
    fontWeight: '600',
    fontSize: 12,
  },

  // Empty
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16,
    opacity: 0.3,
  },
  emptyText: {
    color: '#94a3b8',
    fontSize: 16,
    marginBottom: 6,
  },
  emptySub: {
    color: '#64748b',
    fontSize: 13,
    textAlign: 'center',
  },
});

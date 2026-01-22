/**
 * CapsuleCard Component - Mobile
 * 
 * Reusable card component for displaying time-lock capsules.
 * Supports all capsule types and statuses.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated
} from 'react-native';

const CapsuleCard = ({
  capsule,
  onPress,
  onUnlock,
  onCancel,
  compact = false
}) => {
  const [timeRemaining, setTimeRemaining] = useState(capsule.time_remaining_seconds || 0);
  const pulseAnim = new Animated.Value(1);

  useEffect(() => {
    // Update countdown every second
    const interval = setInterval(() => {
      setTimeRemaining(prev => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Pulse animation when ready to unlock
    if (timeRemaining === 0 && capsule.status === 'locked') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.05,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 500,
            useNativeDriver: true,
          }),
        ])
      ).start();
    }
  }, [timeRemaining, capsule.status]);

  const formatTime = (seconds) => {
    if (seconds <= 0) return 'Ready';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  const getTypeIcon = () => {
    const icons = {
      general: '🔐',
      will: '📜',
      escrow: '🤝',
      time_capsule: '⏳',
      emergency: '🚨'
    };
    return icons[capsule.capsule_type] || '🔒';
  };

  const getStatusColor = () => {
    const colors = {
      locked: '#ff6b6b',
      solving: '#ffa500',
      unlocked: '#00e676',
      expired: '#808080',
      cancelled: '#444'
    };
    return colors[capsule.status] || '#fff';
  };

  const getProgress = () => {
    if (!capsule.delay_seconds || capsule.status !== 'locked') return 100;
    return Math.max(0, (1 - timeRemaining / capsule.delay_seconds) * 100);
  };

  const isReady = timeRemaining === 0 && capsule.status === 'locked';

  if (compact) {
    return (
      <TouchableOpacity 
        style={styles.compactCard}
        onPress={onPress}
      >
        <Text style={styles.compactIcon}>{getTypeIcon()}</Text>
        <View style={styles.compactInfo}>
          <Text style={styles.compactTitle} numberOfLines={1}>
            {capsule.title}
          </Text>
          <Text style={[styles.compactTime, { color: getStatusColor() }]}>
            {capsule.status === 'locked' ? formatTime(timeRemaining) : capsule.status}
          </Text>
        </View>
        <View style={[styles.compactStatus, { backgroundColor: getStatusColor() }]} />
      </TouchableOpacity>
    );
  }

  return (
    <Animated.View style={[
      styles.card,
      { transform: [{ scale: pulseAnim }] },
      capsule.status === 'unlocked' && styles.unlockedCard
    ]}>
      <TouchableOpacity onPress={onPress} activeOpacity={0.8}>
        <View style={styles.cardHeader}>
          <Text style={styles.typeIcon}>{getTypeIcon()}</Text>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor() }]}>
            <Text style={styles.statusText}>{capsule.status.toUpperCase()}</Text>
          </View>
        </View>

        <Text style={styles.title}>{capsule.title}</Text>
        
        {capsule.description && (
          <Text style={styles.description} numberOfLines={2}>
            {capsule.description}
          </Text>
        )}

        {capsule.status === 'locked' && (
          <View style={styles.countdown}>
            <Text style={[styles.timeDisplay, isReady && styles.readyTime]}>
              {formatTime(timeRemaining)}
            </Text>
            <View style={styles.progressBar}>
              <View 
                style={[styles.progress, { width: `${getProgress()}%` }]} 
              />
            </View>
          </View>
        )}

        {capsule.beneficiary_count > 0 && (
          <View style={styles.beneficiaryBadge}>
            <Text style={styles.beneficiaryText}>
              👥 {capsule.beneficiary_count} beneficiaries
            </Text>
          </View>
        )}

        {capsule.mode && (
          <View style={styles.modeBadge}>
            <Text style={styles.modeText}>
              {capsule.mode === 'server' && '🖥️ Server'}
              {capsule.mode === 'client' && '💻 Client VDF'}
              {capsule.mode === 'hybrid' && '🔄 Hybrid'}
            </Text>
          </View>
        )}
      </TouchableOpacity>

      <View style={styles.actions}>
        {isReady && onUnlock && (
          <TouchableOpacity 
            style={[styles.actionBtn, styles.unlockBtn]}
            onPress={() => onUnlock(capsule.id)}
          >
            <Text style={styles.unlockText}>🔓 Unlock</Text>
          </TouchableOpacity>
        )}
        
        {capsule.status === 'locked' && !isReady && onCancel && (
          <TouchableOpacity 
            style={[styles.actionBtn, styles.cancelBtn]}
            onPress={() => onCancel(capsule.id)}
          >
            <Text style={styles.cancelText}>❌ Cancel</Text>
          </TouchableOpacity>
        )}
        
        {capsule.status === 'unlocked' && (
          <TouchableOpacity style={[styles.actionBtn, styles.viewBtn]}>
            <Text style={styles.viewText}>👁️ View Secret</Text>
          </TouchableOpacity>
        )}
      </View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  card: {
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
    fontSize: 28,
  },
  statusBadge: {
    paddingHorizontal: 12,
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
    fontSize: 28,
    fontWeight: 'bold',
    color: '#ff6b6b',
    textAlign: 'center',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  readyTime: {
    color: '#00e676',
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
    marginBottom: 8,
  },
  beneficiaryText: {
    fontSize: 12,
    color: '#4facfe',
  },
  modeBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  modeText: {
    fontSize: 11,
    color: '#a0a0a0',
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
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
  unlockText: {
    fontWeight: '600',
    color: '#00e676',
  },
  cancelText: {
    fontWeight: '600',
    color: '#f44336',
  },
  viewText: {
    fontWeight: '600',
    color: '#4facfe',
  },
  // Compact card styles
  compactCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  compactIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  compactInfo: {
    flex: 1,
  },
  compactTitle: {
    color: '#fff',
    fontWeight: '500',
    fontSize: 14,
  },
  compactTime: {
    fontSize: 12,
    marginTop: 2,
    fontFamily: 'monospace',
  },
  compactStatus: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginLeft: 8,
  },
});

export default CapsuleCard;

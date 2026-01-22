/**
 * PasswordWillScreen - Mobile
 * 
 * Screen for managing password wills (digital inheritance).
 * Supports creating wills, check-ins, and viewing beneficiaries.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  RefreshControl,
  Alert,
  ActivityIndicator,
  Modal
} from 'react-native';
import timeLockService from '../services/TimeLockService';

const PasswordWillScreen = ({ navigation }) => {
  const [wills, setWills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchWills = useCallback(async () => {
    try {
      const data = await timeLockService.getWills();
      setWills(data.wills || []);
    } catch (error) {
      Alert.alert('Error', 'Failed to fetch password wills');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchWills();
  }, [fetchWills]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchWills();
  };

  const handleCheckIn = async (willId) => {
    try {
      await timeLockService.checkIn(willId);
      Alert.alert('Success', 'Check-in successful! Timer reset.');
      fetchWills();
    } catch (error) {
      Alert.alert('Error', error.message);
    }
  };

  const getDaysColor = (days) => {
    if (days <= 7) return '#f44336';
    if (days <= 14) return '#ff9800';
    return '#4caf50';
  };

  const renderWillCard = (will) => (
    <View 
      key={will.id} 
      style={[
        styles.willCard,
        will.is_triggered && styles.triggeredCard
      ]}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.cardIcon}>📜</Text>
        <View style={styles.statusBadges}>
          {will.is_triggered ? (
            <View style={[styles.badge, styles.triggeredBadge]}>
              <Text style={styles.badgeText}>TRIGGERED</Text>
            </View>
          ) : (
            <View style={[styles.badge, styles.activeBadge]}>
              <Text style={styles.badgeText}>ACTIVE</Text>
            </View>
          )}
        </View>
      </View>

      <Text style={styles.cardTitle}>{will.capsule_title}</Text>

      {!will.is_triggered && (
        <View style={styles.timerSection}>
          <Text style={[styles.daysCount, { color: getDaysColor(will.days_until_trigger) }]}>
            {will.days_until_trigger}
          </Text>
          <Text style={styles.daysLabel}>days until trigger</Text>
        </View>
      )}

      <View style={styles.infoRow}>
        <Text style={styles.infoLabel}>Trigger:</Text>
        <Text style={styles.infoValue}>
          {will.trigger_type === 'inactivity' 
            ? `${will.inactivity_days} days inactivity`
            : new Date(will.target_date).toLocaleDateString()}
        </Text>
      </View>

      <View style={styles.infoRow}>
        <Text style={styles.infoLabel}>Last Check-in:</Text>
        <Text style={styles.infoValue}>
          {new Date(will.last_check_in).toLocaleDateString()}
        </Text>
      </View>

      <View style={styles.infoRow}>
        <Text style={styles.infoLabel}>Beneficiaries:</Text>
        <Text style={styles.infoValue}>{will.beneficiary_count || 0}</Text>
      </View>

      {!will.is_triggered && (
        <TouchableOpacity
          style={styles.checkInBtn}
          onPress={() => handleCheckIn(will.id)}
        >
          <Text style={styles.checkInText}>✓ Check In Now</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#fbbf24" />
        <Text style={styles.loadingText}>Loading password wills...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📜 Password Wills</Text>
        <Text style={styles.headerSubtitle}>Digital inheritance</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {wills.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📜</Text>
            <Text style={styles.emptyText}>No password wills yet</Text>
            <Text style={styles.emptyHint}>
              Create a will to pass on your passwords to loved ones
            </Text>
          </View>
        ) : (
          wills.map(renderWillCard)
        )}

        <View style={styles.infoBox}>
          <Text style={styles.infoBoxTitle}>💡 How It Works</Text>
          <View style={styles.infoStep}>
            <Text style={styles.stepNumber}>1</Text>
            <Text style={styles.stepText}>Create a will with your secrets and beneficiaries</Text>
          </View>
          <View style={styles.infoStep}>
            <Text style={styles.stepNumber}>2</Text>
            <Text style={styles.stepText}>Check in regularly to reset the timer</Text>
          </View>
          <View style={styles.infoStep}>
            <Text style={styles.stepNumber}>3</Text>
            <Text style={styles.stepText}>If inactive too long, beneficiaries get notified</Text>
          </View>
        </View>
      </ScrollView>

      <TouchableOpacity
        style={styles.fab}
        onPress={() => setShowCreateModal(true)}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>

      <CreateWillModal
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={() => {
          setShowCreateModal(false);
          fetchWills();
        }}
      />
    </View>
  );
};

// Create Will Modal
const CreateWillModal = ({ visible, onClose, onCreated }) => {
  const [step, setStep] = useState(1);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    secret_data: '',
    trigger_type: 'inactivity',
    inactivity_days: 30,
    beneficiaryName: '',
    beneficiaryEmail: ''
  });

  const handleSubmit = async () => {
    if (!formData.title || !formData.secret_data) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }
    if (!formData.beneficiaryEmail) {
      Alert.alert('Error', 'Please add at least one beneficiary');
      return;
    }

    setCreating(true);

    try {
      await timeLockService.createWill({
        ...formData,
        beneficiaries: [{
          name: formData.beneficiaryName,
          email: formData.beneficiaryEmail,
          access_level: 'full'
        }]
      });
      Alert.alert('Success', 'Password will created!');
      onCreated();
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>📜 Create Password Will</Text>

          {step === 1 && (
            <>
              <Text style={styles.inputLabel}>Will Title</Text>
              <TextInput
                style={styles.input}
                value={formData.title}
                onChangeText={text => setFormData({ ...formData, title: text })}
                placeholder="e.g., My Digital Estate"
                placeholderTextColor="#666"
              />

              <Text style={styles.inputLabel}>Secrets to Pass On</Text>
              <TextInput
                style={[styles.input, styles.textArea]}
                value={formData.secret_data}
                onChangeText={text => setFormData({ ...formData, secret_data: text })}
                placeholder="Enter passwords and accounts..."
                placeholderTextColor="#666"
                multiline
                numberOfLines={6}
              />

              <Text style={styles.inputLabel}>Inactivity Period</Text>
              <View style={styles.daysSelector}>
                {[7, 14, 30, 60, 90].map(days => (
                  <TouchableOpacity
                    key={days}
                    style={[
                      styles.dayOption,
                      formData.inactivity_days === days && styles.dayOptionActive
                    ]}
                    onPress={() => setFormData({ ...formData, inactivity_days: days })}
                  >
                    <Text style={[
                      styles.dayOptionText,
                      formData.inactivity_days === days && styles.dayOptionTextActive
                    ]}>{days}d</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </>
          )}

          {step === 2 && (
            <>
              <Text style={styles.inputLabel}>Beneficiary Name</Text>
              <TextInput
                style={styles.input}
                value={formData.beneficiaryName}
                onChangeText={text => setFormData({ ...formData, beneficiaryName: text })}
                placeholder="Full name"
                placeholderTextColor="#666"
              />

              <Text style={styles.inputLabel}>Beneficiary Email</Text>
              <TextInput
                style={styles.input}
                value={formData.beneficiaryEmail}
                onChangeText={text => setFormData({ ...formData, beneficiaryEmail: text })}
                placeholder="email@example.com"
                placeholderTextColor="#666"
                keyboardType="email-address"
              />
            </>
          )}

          <View style={styles.modalActions}>
            {step > 1 && (
              <TouchableOpacity
                style={[styles.modalBtn, styles.secondaryBtn]}
                onPress={() => setStep(s => s - 1)}
              >
                <Text style={styles.secondaryBtnText}>Back</Text>
              </TouchableOpacity>
            )}
            
            {step < 2 ? (
              <TouchableOpacity
                style={[styles.modalBtn, styles.primaryBtn]}
                onPress={() => setStep(s => s + 1)}
              >
                <Text style={styles.primaryBtnText}>Next</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={[styles.modalBtn, styles.primaryBtn]}
                onPress={handleSubmit}
                disabled={creating}
              >
                <Text style={styles.primaryBtnText}>
                  {creating ? 'Creating...' : 'Create Will'}
                </Text>
              </TouchableOpacity>
            )}
          </View>

          <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
            <Text style={styles.closeBtnText}>×</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
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
  scrollContent: {
    padding: 16,
    paddingBottom: 100,
  },
  willCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(251, 191, 36, 0.3)',
  },
  triggeredCard: {
    borderColor: 'rgba(244, 67, 54, 0.3)',
    opacity: 0.7,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardIcon: {
    fontSize: 32,
  },
  statusBadges: {
    flexDirection: 'row',
    gap: 8,
  },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  activeBadge: {
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
  },
  triggeredBadge: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 16,
  },
  timerSection: {
    alignItems: 'center',
    marginBottom: 20,
    padding: 16,
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: 12,
  },
  daysCount: {
    fontSize: 48,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  daysLabel: {
    color: '#808080',
    fontSize: 14,
    marginTop: 4,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.05)',
  },
  infoLabel: {
    color: '#808080',
    fontSize: 14,
  },
  infoValue: {
    color: '#e0e0e0',
    fontSize: 14,
  },
  checkInBtn: {
    marginTop: 16,
    padding: 14,
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    borderRadius: 8,
    alignItems: 'center',
  },
  checkInText: {
    color: '#4caf50',
    fontWeight: '600',
    fontSize: 16,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyIcon: {
    fontSize: 64,
    opacity: 0.5,
  },
  emptyText: {
    color: '#a0a0a0',
    fontSize: 18,
    marginTop: 16,
  },
  emptyHint: {
    color: '#606060',
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 32,
  },
  infoBox: {
    backgroundColor: 'rgba(251, 191, 36, 0.1)',
    borderRadius: 12,
    padding: 20,
    marginTop: 16,
  },
  infoBoxTitle: {
    color: '#fbbf24',
    fontWeight: '600',
    marginBottom: 16,
  },
  infoStep: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  stepNumber: {
    width: 24,
    height: 24,
    backgroundColor: 'rgba(251, 191, 36, 0.3)',
    borderRadius: 12,
    textAlign: 'center',
    lineHeight: 24,
    color: '#fbbf24',
    fontWeight: '600',
    marginRight: 12,
  },
  stepText: {
    flex: 1,
    color: '#a0a0a0',
    fontSize: 13,
  },
  fab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#fbbf24',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#fbbf24',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
  },
  fabText: {
    fontSize: 28,
    color: '#1a1a2e',
    fontWeight: '300',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    borderRadius: 16,
    padding: 24,
    width: '90%',
    maxHeight: '80%',
    borderWidth: 1,
    borderColor: 'rgba(251, 191, 36, 0.3)',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 24,
    textAlign: 'center',
  },
  inputLabel: {
    color: '#a0a0a0',
    fontSize: 14,
    marginBottom: 8,
  },
  input: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    marginBottom: 16,
  },
  textArea: {
    height: 120,
    textAlignVertical: 'top',
  },
  daysSelector: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  dayOption: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  dayOptionActive: {
    backgroundColor: 'rgba(251, 191, 36, 0.2)',
    borderColor: '#fbbf24',
  },
  dayOptionText: {
    color: '#a0a0a0',
  },
  dayOptionTextActive: {
    color: '#fbbf24',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  modalBtn: {
    flex: 1,
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  primaryBtn: {
    backgroundColor: '#fbbf24',
  },
  secondaryBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  primaryBtnText: {
    color: '#1a1a2e',
    fontWeight: '600',
  },
  secondaryBtnText: {
    color: '#e0e0e0',
    fontWeight: '600',
  },
  closeBtn: {
    position: 'absolute',
    top: 16,
    right: 16,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeBtnText: {
    color: '#fff',
    fontSize: 20,
  },
});

export default PasswordWillScreen;

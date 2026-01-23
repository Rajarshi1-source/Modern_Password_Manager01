/**
 * Dead Drop Screen - Mobile
 * ==========================
 * 
 * React Native screen for managing mesh dead drops.
 * Supports creating, viewing, and collecting dead drops.
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
  Modal,
  Platform,
} from 'react-native';
import meshService from '../services/MeshService';

const DeadDropScreen = ({ navigation }) => {
  const [deadDrops, setDeadDrops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchDeadDrops = useCallback(async () => {
    try {
      const data = await meshService.getDeadDrops();
      setDeadDrops(data.dead_drops || []);
    } catch (error) {
      Alert.alert('Error', 'Failed to fetch dead drops');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    meshService.initialize().then(() => {
      fetchDeadDrops();
    });

    return () => {
      meshService.destroy();
    };
  }, [fetchDeadDrops]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDeadDrops();
  };

  const handleCollect = async (dropId) => {
    navigation.navigate('CollectDeadDrop', { dropId });
  };

  const handleCancel = async (dropId) => {
    Alert.alert(
      'Cancel Dead Drop',
      'Are you sure you want to cancel this dead drop?',
      [
        { text: 'No', style: 'cancel' },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: async () => {
            try {
              await meshService.cancelDeadDrop(dropId);
              fetchDeadDrops();
            } catch (error) {
              Alert.alert('Error', error.message);
            }
          },
        },
      ]
    );
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: '#ffc107',
      distributed: '#17a2b8',
      active: '#28a745',
      collected: '#6c757d',
      expired: '#dc3545',
      cancelled: '#343a40',
    };
    return colors[status] || '#6c757d';
  };

  const formatTime = (seconds) => {
    if (seconds <= 0) return 'Expired';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    if (days > 0) return `${days}d ${hours}h`;
    const mins = Math.floor((seconds % 3600) / 60);
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const renderDropCard = (drop) => (
    <TouchableOpacity
      key={drop.id}
      style={styles.dropCard}
      onPress={() => navigation.navigate('DeadDropDetail', { drop })}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.dropIcon}>📡</Text>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(drop.status) }]}>
          <Text style={styles.statusText}>{drop.status.toUpperCase()}</Text>
        </View>
      </View>

      <Text style={styles.dropTitle}>{drop.title}</Text>

      <View style={styles.infoGrid}>
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>🎯 Threshold</Text>
          <Text style={styles.infoValue}>{drop.threshold_display}</Text>
        </View>
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>⏱️ Expires</Text>
          <Text style={styles.infoValue}>{formatTime(drop.time_remaining_seconds)}</Text>
        </View>
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>📍 Radius</Text>
          <Text style={styles.infoValue}>{drop.radius_meters}m</Text>
        </View>
      </View>

      {drop.location_hint && (
        <Text style={styles.locationHint}>💡 {drop.location_hint}</Text>
      )}

      <View style={styles.verificationBadges}>
        {drop.require_ble_verification && (
          <View style={[styles.verifyBadge, styles.bleBadge]}>
            <Text style={styles.verifyBadgeText}>📶 BLE</Text>
          </View>
        )}
        {drop.require_nfc_tap && (
          <View style={[styles.verifyBadge, styles.nfcBadge]}>
            <Text style={styles.verifyBadgeText}>📱 NFC</Text>
          </View>
        )}
      </View>

      <View style={styles.cardActions}>
        {drop.status === 'active' && (
          <>
            <TouchableOpacity
              style={[styles.actionBtn, styles.collectBtn]}
              onPress={() => handleCollect(drop.id)}
            >
              <Text style={styles.collectBtnText}>📥 Collect</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionBtn, styles.cancelBtn]}
              onPress={() => handleCancel(drop.id)}
            >
              <Text style={styles.cancelBtnText}>❌</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#00e676" />
        <Text style={styles.loadingText}>Loading dead drops...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📡 Dead Drops</Text>
        <Text style={styles.headerSubtitle}>Mesh network password sharing</Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl 
            refreshing={refreshing} 
            onRefresh={handleRefresh}
            tintColor="#00e676"
          />
        }
      >
        {deadDrops.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>No dead drops yet</Text>
            <Text style={styles.emptyHint}>
              Create your first dead drop to share passwords securely
            </Text>
          </View>
        ) : (
          deadDrops.map(renderDropCard)
        )}

        <View style={styles.infoBox}>
          <Text style={styles.infoBoxTitle}>💡 How It Works</Text>
          <View style={styles.infoStep}>
            <Text style={styles.stepNum}>1</Text>
            <Text style={styles.stepText}>
              Create a dead drop with your secret and target location
            </Text>
          </View>
          <View style={styles.infoStep}>
            <Text style={styles.stepNum}>2</Text>
            <Text style={styles.stepText}>
              Secret is split into fragments using Shamir's algorithm
            </Text>
          </View>
          <View style={styles.infoStep}>
            <Text style={styles.stepNum}>3</Text>
            <Text style={styles.stepText}>
              Fragments are distributed to nearby mesh nodes
            </Text>
          </View>
          <View style={styles.infoStep}>
            <Text style={styles.stepNum}>4</Text>
            <Text style={styles.stepText}>
              Recipient collects fragments when at the location
            </Text>
          </View>
        </View>
      </ScrollView>

      <TouchableOpacity
        style={styles.fab}
        onPress={() => setShowCreateModal(true)}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>

      <CreateDeadDropModal
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={() => {
          setShowCreateModal(false);
          fetchDeadDrops();
        }}
      />
    </View>
  );
};

// Create Dead Drop Modal
const CreateDeadDropModal = ({ visible, onClose, onCreated }) => {
  const [step, setStep] = useState(1);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    secret: '',
    latitude: '',
    longitude: '',
    radius_meters: 50,
    location_hint: '',
    required_fragments: 3,
    total_fragments: 5,
    expires_in_hours: 168,
    require_ble_verification: true,
    require_nfc_tap: false,
  });

  const getCurrentLocation = async () => {
    try {
      const location = await meshService.getCurrentLocation();
      setFormData(prev => ({
        ...prev,
        latitude: location.latitude.toFixed(6),
        longitude: location.longitude.toFixed(6),
      }));
    } catch (error) {
      Alert.alert('Error', 'Failed to get location');
    }
  };

  const handleCreate = async () => {
    if (!formData.title || !formData.secret) {
      Alert.alert('Error', 'Please fill in title and secret');
      return;
    }
    if (!formData.latitude || !formData.longitude) {
      Alert.alert('Error', 'Please set a location');
      return;
    }

    setCreating(true);
    try {
      const result = await meshService.createDeadDrop(formData);
      if (result.dead_drop) {
        Alert.alert('Success', 'Dead drop created successfully!');
        onCreated();
      } else {
        Alert.alert('Error', JSON.stringify(result));
      }
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
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>📡 Create Dead Drop</Text>
            <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
              <Text style={styles.closeBtnText}>×</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody}>
            {step === 1 && (
              <>
                <Text style={styles.inputLabel}>Title</Text>
                <TextInput
                  style={styles.input}
                  value={formData.title}
                  onChangeText={text => setFormData({ ...formData, title: text })}
                  placeholder="e.g., Emergency Access Codes"
                  placeholderTextColor="#666"
                />

                <Text style={styles.inputLabel}>Secret Data</Text>
                <TextInput
                  style={[styles.input, styles.textArea]}
                  value={formData.secret}
                  onChangeText={text => setFormData({ ...formData, secret: text })}
                  placeholder="Enter the secret..."
                  placeholderTextColor="#666"
                  multiline
                  numberOfLines={4}
                  secureTextEntry
                />

                <TouchableOpacity style={styles.locationBtn} onPress={getCurrentLocation}>
                  <Text style={styles.locationBtnText}>📍 Use Current Location</Text>
                </TouchableOpacity>

                <View style={styles.coordsRow}>
                  <View style={styles.coordInput}>
                    <Text style={styles.inputLabel}>Latitude</Text>
                    <TextInput
                      style={styles.input}
                      value={formData.latitude}
                      onChangeText={text => setFormData({ ...formData, latitude: text })}
                      placeholder="40.7128"
                      placeholderTextColor="#666"
                      keyboardType="numeric"
                    />
                  </View>
                  <View style={styles.coordInput}>
                    <Text style={styles.inputLabel}>Longitude</Text>
                    <TextInput
                      style={styles.input}
                      value={formData.longitude}
                      onChangeText={text => setFormData({ ...formData, longitude: text })}
                      placeholder="-74.0060"
                      placeholderTextColor="#666"
                      keyboardType="numeric"
                    />
                  </View>
                </View>

                <Text style={styles.inputLabel}>Location Hint</Text>
                <TextInput
                  style={styles.input}
                  value={formData.location_hint}
                  onChangeText={text => setFormData({ ...formData, location_hint: text })}
                  placeholder="e.g., Behind the fountain"
                  placeholderTextColor="#666"
                />
              </>
            )}

            {step === 2 && (
              <>
                <Text style={styles.sectionTitle}>🔐 Security Settings</Text>

                <View style={styles.thresholdRow}>
                  <View style={styles.thresholdInput}>
                    <Text style={styles.inputLabel}>Required (k)</Text>
                    <TextInput
                      style={styles.input}
                      value={String(formData.required_fragments)}
                      onChangeText={text => setFormData({ ...formData, required_fragments: parseInt(text) || 3 })}
                      keyboardType="numeric"
                    />
                  </View>
                  <View style={styles.thresholdInput}>
                    <Text style={styles.inputLabel}>Total (n)</Text>
                    <TextInput
                      style={styles.input}
                      value={String(formData.total_fragments)}
                      onChangeText={text => setFormData({ ...formData, total_fragments: parseInt(text) || 5 })}
                      keyboardType="numeric"
                    />
                  </View>
                </View>

                <TouchableOpacity
                  style={styles.toggleRow}
                  onPress={() => setFormData({ ...formData, require_ble_verification: !formData.require_ble_verification })}
                >
                  <Text style={styles.toggleLabel}>📶 Require BLE Verification</Text>
                  <View style={[styles.toggle, formData.require_ble_verification && styles.toggleActive]}>
                    <View style={styles.toggleKnob} />
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.toggleRow}
                  onPress={() => setFormData({ ...formData, require_nfc_tap: !formData.require_nfc_tap })}
                >
                  <Text style={styles.toggleLabel}>📱 Require NFC Tap</Text>
                  <View style={[styles.toggle, formData.require_nfc_tap && styles.toggleActive]}>
                    <View style={styles.toggleKnob} />
                  </View>
                </TouchableOpacity>
              </>
            )}
          </ScrollView>

          <View style={styles.modalFooter}>
            {step > 1 && (
              <TouchableOpacity
                style={[styles.footerBtn, styles.secondaryBtn]}
                onPress={() => setStep(s => s - 1)}
              >
                <Text style={styles.secondaryBtnText}>Back</Text>
              </TouchableOpacity>
            )}

            {step < 2 ? (
              <TouchableOpacity
                style={[styles.footerBtn, styles.primaryBtn]}
                onPress={() => setStep(2)}
              >
                <Text style={styles.primaryBtnText}>Next</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={[styles.footerBtn, styles.primaryBtn]}
                onPress={handleCreate}
                disabled={creating}
              >
                <Text style={styles.primaryBtnText}>
                  {creating ? 'Creating...' : '🚀 Create'}
                </Text>
              </TouchableOpacity>
            )}
          </View>
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
    color: '#808080',
    marginTop: 16,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 50,
    paddingBottom: 16,
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  dropCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  dropIcon: {
    fontSize: 28,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
  },
  dropTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 12,
  },
  infoGrid: {
    marginBottom: 12,
  },
  infoItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  infoLabel: {
    color: '#808080',
    fontSize: 13,
  },
  infoValue: {
    color: '#e0e0e0',
    fontSize: 13,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  locationHint: {
    fontSize: 12,
    color: '#a0a0a0',
    fontStyle: 'italic',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    padding: 8,
    borderRadius: 6,
    marginBottom: 12,
  },
  verificationBadges: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  verifyBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  bleBadge: {
    backgroundColor: 'rgba(33, 150, 243, 0.2)',
  },
  nfcBadge: {
    backgroundColor: 'rgba(156, 39, 176, 0.2)',
  },
  verifyBadgeText: {
    fontSize: 11,
    fontWeight: '500',
    color: '#fff',
  },
  cardActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  collectBtn: {
    flex: 1,
    backgroundColor: 'rgba(0, 230, 118, 0.2)',
  },
  collectBtnText: {
    color: '#00e676',
    fontWeight: '600',
  },
  cancelBtn: {
    backgroundColor: 'rgba(244, 67, 54, 0.1)',
    paddingHorizontal: 12,
  },
  cancelBtnText: {
    color: '#f44336',
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
    backgroundColor: 'rgba(0, 230, 118, 0.05)',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    borderWidth: 1,
    borderColor: 'rgba(0, 230, 118, 0.2)',
  },
  infoBoxTitle: {
    color: '#00e676',
    fontWeight: '600',
    marginBottom: 12,
  },
  infoStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  stepNum: {
    width: 24,
    height: 24,
    backgroundColor: 'rgba(0, 230, 118, 0.2)',
    borderRadius: 12,
    textAlign: 'center',
    lineHeight: 24,
    color: '#00e676',
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
    backgroundColor: '#00e676',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#00e676',
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
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  closeBtn: {
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
  modalBody: {
    padding: 20,
  },
  inputLabel: {
    color: '#a0a0a0',
    fontSize: 13,
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 15,
  },
  textArea: {
    height: 100,
    textAlignVertical: 'top',
  },
  locationBtn: {
    marginTop: 16,
    padding: 16,
    backgroundColor: 'rgba(33, 150, 243, 0.1)',
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: 'rgba(33, 150, 243, 0.3)',
    borderRadius: 8,
    alignItems: 'center',
  },
  locationBtnText: {
    color: '#2196f3',
    fontSize: 15,
  },
  coordsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  coordInput: {
    flex: 1,
  },
  sectionTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16,
  },
  thresholdRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  thresholdInput: {
    flex: 1,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.05)',
  },
  toggleLabel: {
    color: '#e0e0e0',
    fontSize: 15,
  },
  toggle: {
    width: 50,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    padding: 2,
    justifyContent: 'center',
  },
  toggleActive: {
    backgroundColor: '#00e676',
  },
  toggleKnob: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#fff',
  },
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  footerBtn: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  primaryBtn: {
    backgroundColor: '#00e676',
  },
  primaryBtnText: {
    color: '#1a1a2e',
    fontWeight: '600',
    fontSize: 15,
  },
  secondaryBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  secondaryBtnText: {
    color: '#e0e0e0',
    fontWeight: '600',
    fontSize: 15,
  },
});

export default DeadDropScreen;

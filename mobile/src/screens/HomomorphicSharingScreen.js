import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, RefreshControl, FlatList,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import FHESharingService from '../services/FHESharingService';

const TABS = [
  { key: 'sent', label: 'Shared by Me', icon: 'send-outline' },
  { key: 'received', label: 'Shared with Me', icon: 'download-outline' },
];

export default function HomomorphicSharingScreen() {
  const [activeTab, setActiveTab] = useState('sent');
  const [sentShares, setSentShares] = useState([]);
  const [receivedShares, setReceivedShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [error, setError] = useState(null);

  // Create share form state
  const [form, setForm] = useState({
    vaultItemId: '',
    recipientUsername: '',
    domain: '',
    domains: [],
    maxUses: '',
  });
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [sentRes, receivedRes] = await Promise.allSettled([
        FHESharingService.listMyShares(),
        FHESharingService.listReceivedShares(),
      ]);
      if (sentRes.status === 'fulfilled') setSentShares(sentRes.value?.shares || []);
      if (receivedRes.status === 'fulfilled') setReceivedShares(receivedRes.value?.shares || []);
    } catch (err) {
      setError('Failed to load sharing data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleRevoke = (shareId) => {
    Alert.alert(
      'Revoke Share',
      'The recipient will no longer be able to autofill this password.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revoke',
          style: 'destructive',
          onPress: async () => {
            try {
              await FHESharingService.revokeShare(shareId);
              loadData();
            } catch (err) {
              Alert.alert('Error', err.error || 'Failed to revoke share');
            }
          },
        },
      ]
    );
  };

  const handleAutofill = async (shareId, domain) => {
    try {
      const result = await FHESharingService.useAutofillToken(shareId, domain);
      Alert.alert(
        'Autofill Ready',
        `Autofill data generated for ${domain}.\nUsage: ${result.use_count}${result.remaining_uses != null ? ` / ${result.use_count + result.remaining_uses}` : ''}`,
        [{ text: 'OK' }]
      );
      loadData();
    } catch (err) {
      Alert.alert('Autofill Failed', err.error || 'Could not generate autofill data');
    }
  };

  const addDomain = () => {
    const d = form.domain.trim().toLowerCase();
    if (!d || d.length < 3 || form.domains.includes(d)) return;
    setForm(prev => ({
      ...prev,
      domains: [...prev.domains, d],
      domain: '',
    }));
  };

  const removeDomain = (d) => {
    setForm(prev => ({
      ...prev,
      domains: prev.domains.filter(x => x !== d),
    }));
  };

  const handleCreateShare = async () => {
    if (!form.vaultItemId.trim()) {
      Alert.alert('Error', 'Please enter a Vault Item ID');
      return;
    }
    if (!form.recipientUsername.trim()) {
      Alert.alert('Error', 'Please enter a recipient username');
      return;
    }
    if (form.domains.length === 0) {
      Alert.alert('Error', 'Add at least one domain');
      return;
    }

    setCreating(true);
    try {
      const expiresAt = new Date();
      expiresAt.setHours(expiresAt.getHours() + 72);

      await FHESharingService.createShare(
        form.vaultItemId.trim(),
        form.recipientUsername.trim(),
        {
          domainConstraints: form.domains,
          expiresAt: expiresAt.toISOString(),
          maxUses: form.maxUses ? parseInt(form.maxUses) : null,
        }
      );
      Alert.alert('Success', 'Password shared with FHE encryption!');
      setShowCreateForm(false);
      setForm({ vaultItemId: '', recipientUsername: '', domain: '', domains: [], maxUses: '' });
      loadData();
    } catch (err) {
      Alert.alert('Error', err.error || 'Failed to create share');
    } finally {
      setCreating(false);
    }
  };

  const formatExpiry = (expiresAt) => {
    if (!expiresAt) return 'Never';
    const diff = new Date(expiresAt) - new Date();
    if (diff < 0) return 'Expired';
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours}h left`;
    return `${Math.floor(hours / 24)}d left`;
  };

  const getStatusColor = (share) => {
    if (!share.is_active) return '#DC2626';
    if (share.is_expired) return '#D97706';
    return '#10B981';
  };

  const getStatusText = (share) => {
    if (!share.is_active) return 'Revoked';
    if (share.is_expired) return 'Expired';
    return 'Active';
  };

  const renderSentItem = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {(item.recipient_username || '?')[0].toUpperCase()}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>{item.recipient_username}</Text>
          <Text style={styles.cardSubtitle}>
            <Ionicons name="eye-off-outline" size={12} /> Autofill only
          </Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item) + '20' }]}>
          <Text style={[styles.statusText, { color: getStatusColor(item) }]}>
            {getStatusText(item)}
          </Text>
        </View>
      </View>

      <View style={styles.cardBody}>
        <View style={styles.infoRow}>
          <Ionicons name="globe-outline" size={14} color="#888" />
          <Text style={styles.infoText}>
            {item.bound_domains?.length > 0 ? item.bound_domains.join(', ') : 'Any domain'}
          </Text>
        </View>
        <View style={styles.infoRow}>
          <Ionicons name="bar-chart-outline" size={14} color="#888" />
          <Text style={styles.infoText}>
            Used {item.use_count || 0} times
            {item.remaining_uses != null ? ` (${item.remaining_uses} remaining)` : ''}
          </Text>
        </View>
        <View style={styles.infoRow}>
          <Ionicons name="time-outline" size={14} color="#888" />
          <Text style={styles.infoText}>{formatExpiry(item.expires_at)}</Text>
        </View>
      </View>

      {item.is_active && (
        <TouchableOpacity
          style={styles.revokeButton}
          onPress={() => handleRevoke(item.id)}
        >
          <Text style={styles.revokeText}>Revoke Access</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  const renderReceivedItem = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {(item.owner_username || '?')[0].toUpperCase()}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>From {item.owner_username}</Text>
          <Text style={styles.cardSubtitle}>
            <Ionicons name="shield-checkmark-outline" size={12} /> FHE Encrypted
          </Text>
        </View>
      </View>

      <View style={styles.cardBody}>
        <View style={styles.infoRow}>
          <Ionicons name="lock-closed-outline" size={14} color="#888" />
          <Text style={styles.infoText}>Password hidden — autofill only</Text>
        </View>
        <View style={styles.infoRow}>
          <Ionicons name="time-outline" size={14} color="#888" />
          <Text style={styles.infoText}>{formatExpiry(item.expires_at)}</Text>
        </View>
      </View>

      <View style={styles.autofillSection}>
        {(item.bound_domains || []).map(domain => (
          <TouchableOpacity
            key={domain}
            style={styles.autofillButton}
            onPress={() => handleAutofill(item.id, domain)}
          >
            <Ionicons name="flash-outline" size={16} color="white" />
            <Text style={styles.autofillText}>{domain}</Text>
          </TouchableOpacity>
        ))}
        {(!item.bound_domains || item.bound_domains.length === 0) && (
          <TouchableOpacity
            style={styles.autofillButton}
            onPress={() => handleAutofill(item.id, 'current')}
          >
            <Ionicons name="flash-outline" size={16} color="white" />
            <Text style={styles.autofillText}>Autofill Now</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4A6CF7" />
        <Text style={styles.loadingText}>Loading shares...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <Ionicons name="shield-half-outline" size={22} color="white" />
        </View>
        <View>
          <Text style={styles.headerTitle}>FHE Sharing</Text>
          <Text style={styles.headerSubtitle}>Autofill without revealing passwords</Text>
        </View>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Ionicons name="warning-outline" size={18} color="#B91C1C" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Tabs */}
      <View style={styles.tabBar}>
        {TABS.map(tab => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key)}
          >
            <Ionicons
              name={tab.icon}
              size={16}
              color={activeTab === tab.key ? '#4A6CF7' : '#888'}
            />
            <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      <FlatList
        data={activeTab === 'sent' ? sentShares : receivedShares}
        renderItem={activeTab === 'sent' ? renderSentItem : renderReceivedItem}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4A6CF7" />}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Ionicons name={activeTab === 'sent' ? 'send-outline' : 'download-outline'} size={48} color="#ccc" />
            <Text style={styles.emptyTitle}>
              {activeTab === 'sent' ? 'No Shares Created' : 'No Shares Received'}
            </Text>
            <Text style={styles.emptyText}>
              {activeTab === 'sent'
                ? 'Share a password with FHE encryption so recipients can autofill but not see it.'
                : 'When someone shares a password with you, it will appear here.'}
            </Text>
          </View>
        }
      />

      {/* FAB - Create Share */}
      {activeTab === 'sent' && (
        <TouchableOpacity
          style={styles.fab}
          onPress={() => setShowCreateForm(true)}
        >
          <Ionicons name="add" size={28} color="white" />
        </TouchableOpacity>
      )}

      {/* Create Share Form (bottom sheet style) */}
      {showCreateForm && (
        <View style={styles.overlay}>
          <View style={styles.formContainer}>
            <View style={styles.formHeader}>
              <Text style={styles.formTitle}>New FHE Share</Text>
              <TouchableOpacity onPress={() => setShowCreateForm(false)}>
                <Ionicons name="close" size={24} color="#333" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.formBody}>
              <Text style={styles.formLabel}>Vault Item ID</Text>
              <TextInput
                style={styles.input}
                placeholder="UUID of the password"
                value={form.vaultItemId}
                onChangeText={v => setForm(p => ({ ...p, vaultItemId: v }))}
                placeholderTextColor="#aaa"
              />

              <Text style={styles.formLabel}>Recipient Username</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., john.doe"
                value={form.recipientUsername}
                onChangeText={v => setForm(p => ({ ...p, recipientUsername: v }))}
                placeholderTextColor="#aaa"
              />

              <Text style={styles.formLabel}>Domains (for autofill binding)</Text>
              <View style={styles.domainInputRow}>
                <TextInput
                  style={[styles.input, { flex: 1, marginBottom: 0 }]}
                  placeholder="e.g., github.com"
                  value={form.domain}
                  onChangeText={v => setForm(p => ({ ...p, domain: v }))}
                  onSubmitEditing={addDomain}
                  placeholderTextColor="#aaa"
                />
                <TouchableOpacity style={styles.addDomainBtn} onPress={addDomain}>
                  <Text style={styles.addDomainText}>Add</Text>
                </TouchableOpacity>
              </View>
              <View style={styles.domainChips}>
                {form.domains.map(d => (
                  <TouchableOpacity key={d} style={styles.chip} onPress={() => removeDomain(d)}>
                    <Text style={styles.chipText}>{d} ×</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.formLabel}>Max Uses (optional)</Text>
              <TextInput
                style={styles.input}
                placeholder="Leave empty for unlimited"
                keyboardType="numeric"
                value={form.maxUses}
                onChangeText={v => setForm(p => ({ ...p, maxUses: v }))}
                placeholderTextColor="#aaa"
              />

              <TouchableOpacity
                style={[styles.createButton, creating && { opacity: 0.6 }]}
                onPress={handleCreateShare}
                disabled={creating}
              >
                {creating ? (
                  <ActivityIndicator color="white" />
                ) : (
                  <>
                    <Ionicons name="flash" size={18} color="white" />
                    <Text style={styles.createText}>Create FHE Share</Text>
                  </>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8f9fc' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 12, color: '#888', fontSize: 15 },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: 20, paddingTop: 50, backgroundColor: 'white',
    borderBottomWidth: 1, borderBottomColor: '#eee',
  },
  headerIcon: {
    width: 42, height: 42, borderRadius: 12,
    backgroundColor: '#4A6CF7', alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#1a1a1a' },
  headerSubtitle: { fontSize: 13, color: '#888', marginTop: 2 },

  // Error
  errorBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    margin: 16, padding: 12, backgroundColor: '#FEF2F2',
    borderRadius: 10, borderWidth: 1, borderColor: '#FECACA',
  },
  errorText: { color: '#B91C1C', fontSize: 14, flex: 1 },

  // Tabs
  tabBar: {
    flexDirection: 'row', backgroundColor: '#f0f1f3',
    marginHorizontal: 16, marginTop: 16, borderRadius: 12, padding: 4,
  },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 10, borderRadius: 8,
  },
  tabActive: { backgroundColor: 'white', shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  tabText: { fontSize: 13, fontWeight: '500', color: '#888' },
  tabTextActive: { color: '#4A6CF7', fontWeight: '600' },

  // List
  list: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 100 },

  // Card
  card: {
    backgroundColor: 'white', borderRadius: 14, marginBottom: 12,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, elevation: 3,
    borderWidth: 1, borderColor: '#f0f0f0',
  },
  cardHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: 16, borderBottomWidth: 1, borderBottomColor: '#f5f5f5',
  },
  avatar: {
    width: 38, height: 38, borderRadius: 10,
    backgroundColor: '#4A6CF7', alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { color: 'white', fontWeight: '700', fontSize: 15 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: '#1a1a1a' },
  cardSubtitle: { fontSize: 12, color: '#888', marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  statusText: { fontSize: 12, fontWeight: '600' },
  cardBody: { padding: 16 },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  infoText: { fontSize: 13, color: '#666', flex: 1 },

  // Revoke button
  revokeButton: {
    margin: 16, marginTop: 0, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: '#FECACA',
    alignItems: 'center',
  },
  revokeText: { color: '#DC2626', fontWeight: '600', fontSize: 14 },

  // Autofill
  autofillSection: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, padding: 16, paddingTop: 0 },
  autofillButton: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#4A6CF7', paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 10,
  },
  autofillText: { color: 'white', fontWeight: '600', fontSize: 13 },

  // Empty state
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 17, fontWeight: '600', color: '#333', marginTop: 16 },
  emptyText: { fontSize: 14, color: '#888', textAlign: 'center', marginTop: 8, maxWidth: 280, lineHeight: 20 },

  // FAB
  fab: {
    position: 'absolute', bottom: 24, right: 24,
    width: 56, height: 56, borderRadius: 16,
    backgroundColor: '#4A6CF7', alignItems: 'center', justifyContent: 'center',
    shadowColor: '#4A6CF7', shadowOpacity: 0.35, shadowRadius: 12, elevation: 8,
  },

  // Create form overlay
  overlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end',
  },
  formContainer: {
    backgroundColor: 'white', borderTopLeftRadius: 20, borderTopRightRadius: 20,
    maxHeight: '80%',
  },
  formHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 20, borderBottomWidth: 1, borderBottomColor: '#eee',
  },
  formTitle: { fontSize: 18, fontWeight: '700', color: '#1a1a1a' },
  formBody: { padding: 20 },
  formLabel: { fontSize: 13, fontWeight: '600', color: '#333', marginBottom: 6, marginTop: 12 },
  input: {
    borderWidth: 1.5, borderColor: '#ddd', borderRadius: 10,
    padding: 12, fontSize: 15, color: '#1a1a1a', marginBottom: 4,
  },
  domainInputRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  addDomainBtn: {
    backgroundColor: '#f0f0f0', paddingHorizontal: 16, paddingVertical: 12,
    borderRadius: 10,
  },
  addDomainText: { fontWeight: '600', color: '#333' },
  domainChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8, marginBottom: 4 },
  chip: {
    backgroundColor: 'rgba(74, 108, 247, 0.1)', paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 999,
  },
  chipText: { color: '#4A6CF7', fontSize: 13, fontWeight: '500' },
  createButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#4A6CF7', paddingVertical: 14, borderRadius: 12,
    marginTop: 24, marginBottom: 32,
  },
  createText: { color: 'white', fontWeight: '700', fontSize: 16 },
});

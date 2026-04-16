/**
 * AmbientSetupScreen
 *
 * Landing / onboarding screen for the Ambient Biometric Fusion feature
 * on mobile. Surfaces:
 *   - Current trust + novelty from the most recent ambient observation
 *   - Per-signal availability toggles
 *   - Known contexts list with a "promote current" flow
 *   - Ingest-now button
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import ambientService from '../services/AmbientService';

function Badge({ label, value, tone = 'neutral' }) {
  const color = {
    good: '#2ecc71',
    warn: '#f1c40f',
    bad: '#e74c3c',
    neutral: '#4A6CF7',
  }[tone] || '#4A6CF7';
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={styles.badgeLabel}>{label}</Text>
      <Text style={[styles.badgeValue, { color }]}>{value}</Text>
    </View>
  );
}

const SIGNAL_LABELS = {
  ambient_light: 'Ambient light',
  accelerometer: 'Motion',
  wifi_signature: 'Wi-Fi neighborhood',
  bluetooth_devices: 'Bluetooth neighborhood',
  ambient_audio: 'Ambient audio',
  battery_drain: 'Battery curve',
  network_class: 'Connection type',
  typing_cadence: 'Typing cadence',
};

export default function AmbientSetupScreen() {
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [contexts, setContexts] = useState([]);
  const [label, setLabel] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const loadStatus = useCallback(async () => {
    const on = await ambientService.isEnabled();
    setEnabled(on);
    const list = await ambientService.getContexts();
    setContexts(Array.isArray(list) ? list : []);
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  }, [loadStatus]);

  const handleToggle = async (v) => {
    setEnabled(v);
    await ambientService.setEnabled(v);
  };

  const handleCapture = async () => {
    setLoading(true);
    try {
      await ambientService.requestPermissions();
      const r = await ambientService.ingestOnce();
      setResult(r);
      if (r?.ok) {
        await loadStatus();
      } else if (r?.skipped) {
        Alert.alert('Skipped', r.reason || 'Ambient service is disabled.');
      } else if (r?.status) {
        Alert.alert('Ingest failed', `HTTP ${r.status}`);
      }
    } catch (err) {
      Alert.alert('Error', String(err?.message || err));
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async (contextId) => {
    if (!label.trim()) {
      Alert.alert('Label required', 'Give this context a friendly name (e.g. "Home", "Office").');
      return;
    }
    try {
      await ambientService.promoteContext(contextId, label.trim());
      setLabel('');
      await loadStatus();
    } catch (err) {
      Alert.alert('Promote failed', String(err?.message || err));
    }
  };

  const latestContext = result?.data?.context;
  const trust = result?.data?.trust_score;
  const novelty = result?.data?.novelty_score;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <Text style={styles.title}>Ambient Biometric Fusion</Text>
        <Text style={styles.subtitle}>
          Your device blends passive environmental signals (motion, neighborhood,
          light, battery) into a salted digest. No raw identifiers leave this
          phone — only a 128-bit local-sensitive hash ships to the server.
        </Text>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>Enable ambient collection</Text>
          <Switch value={enabled} onValueChange={handleToggle} />
        </View>

        <TouchableOpacity style={styles.button} onPress={handleCapture} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : (
            <Text style={styles.buttonText}>Capture & send observation</Text>
          )}
        </TouchableOpacity>

        <View style={styles.badgeRow}>
          <Badge
            label="Trust"
            value={trust == null ? '—' : (trust * 100).toFixed(0)}
            tone={trust == null ? 'neutral' : trust > 0.75 ? 'good' : trust > 0.4 ? 'warn' : 'bad'}
          />
          <Badge
            label="Novelty"
            value={novelty == null ? '—' : (novelty * 100).toFixed(0)}
            tone={novelty == null ? 'neutral' : novelty < 0.3 ? 'good' : novelty < 0.6 ? 'warn' : 'bad'}
          />
          <Badge
            label="Context"
            value={latestContext?.label || latestContext?.id || '—'}
          />
        </View>

        {result?.data?.reasons?.length ? (
          <View style={styles.reasons}>
            {result.data.reasons.map((r, i) => (
              <Text key={`r-${i}`} style={styles.reason}>• {r}</Text>
            ))}
          </View>
        ) : null}

        <Text style={styles.sectionTitle}>Signal availability</Text>
        <View style={styles.pillCloud}>
          {Object.entries(result?.data?.signal_availability || {}).map(([k, v]) => (
            <View key={k} style={[styles.pill, v ? styles.pillOn : styles.pillOff]}>
              <Text style={styles.pillText}>
                {(SIGNAL_LABELS[k] || k)}: {v ? 'on' : 'off'}
              </Text>
            </View>
          ))}
        </View>

        <Text style={styles.sectionTitle}>Known contexts</Text>
        <TextInput
          style={styles.input}
          placeholder='Label for current context (e.g. "Home")'
          value={label}
          onChangeText={setLabel}
        />
        {latestContext?.id ? (
          <TouchableOpacity
            style={[styles.button, styles.buttonSecondary]}
            onPress={() => handlePromote(latestContext.id)}
          >
            <Text style={styles.buttonText}>Promote current context</Text>
          </TouchableOpacity>
        ) : null}

        <FlatList
          data={contexts}
          scrollEnabled={false}
          keyExtractor={(c) => String(c.id)}
          renderItem={({ item }) => (
            <View style={styles.contextRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.contextLabel}>{item.label || item.id}</Text>
                <Text style={styles.contextMeta}>
                  Trust {(item.trust_weight ?? 0).toFixed(2)} · seen {item.observation_count ?? 0}x
                </Text>
              </View>
            </View>
          )}
          ListEmptyComponent={(
            <Text style={styles.empty}>No known contexts yet. Capture to seed one.</Text>
          )}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0b1220' },
  container: { padding: 16, paddingBottom: 40 },
  title: { color: '#fff', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#9aa0b4', fontSize: 13, marginTop: 8, marginBottom: 18, lineHeight: 18 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  rowLabel: { color: '#fff', fontSize: 15 },
  button: { backgroundColor: '#4A6CF7', paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginBottom: 12 },
  buttonSecondary: { backgroundColor: '#2b3a67' },
  buttonText: { color: '#fff', fontWeight: '600' },
  badgeRow: { flexDirection: 'row', gap: 10, marginTop: 6, marginBottom: 6, flexWrap: 'wrap' },
  badge: { borderWidth: 1, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10, minWidth: 86, alignItems: 'center' },
  badgeLabel: { color: '#9aa0b4', fontSize: 11 },
  badgeValue: { fontSize: 16, fontWeight: '700' },
  reasons: { marginVertical: 8 },
  reason: { color: '#c9cdd9', fontSize: 12 },
  sectionTitle: { color: '#fff', fontSize: 15, fontWeight: '600', marginTop: 18, marginBottom: 8 },
  pillCloud: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  pill: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, marginRight: 6, marginBottom: 6 },
  pillOn: { borderColor: '#2ecc71' },
  pillOff: { borderColor: '#3b4358' },
  pillText: { color: '#e6e8f0', fontSize: 11 },
  input: { backgroundColor: '#111a2e', color: '#fff', padding: 10, borderRadius: 8, marginBottom: 10, borderWidth: 1, borderColor: '#233058' },
  contextRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1c243f' },
  contextLabel: { color: '#fff', fontSize: 14, fontWeight: '600' },
  contextMeta: { color: '#9aa0b4', fontSize: 12, marginTop: 2 },
  empty: { color: '#9aa0b4', fontStyle: 'italic', marginTop: 10 },
});

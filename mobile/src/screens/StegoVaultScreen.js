/**
 * StegoVaultScreen
 *
 * Mobile entry point for the Steganographic Hidden Vault.
 *
 * Responsibilities:
 *   - List stego containers the user has uploaded from the web/extension
 *     (read-only here; creation stays on the web surface where we can
 *     drive a canvas for the LSB encode).
 *   - Download a container, decrypt it locally with the user's
 *     password, and show the recovered JSON payload.
 *   - Make the failure mode crystal clear when the native Argon2
 *     module isn't linked: we never silently fall back to a weaker
 *     KDF.
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
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import stegoService from '../services/StegoVaultService';

export default function StegoVaultScreen() {
  const [vaults, setVaults] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState(null);
  const [password, setPassword] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [cfg, list] = await Promise.all([
        stegoService.fetchConfig(),
        stegoService.listVaults(),
      ]);
      setConfig(cfg);
      setVaults(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e.message || 'Failed to load stego state.');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const onUnlock = useCallback(async () => {
    if (!selected) { Alert.alert('Select a vault first.'); return; }
    if (!password) { Alert.alert('Password required.'); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const bytes = await stegoService.downloadVault(selected.id);
      const { slotIndex, json } = await stegoService.unlockFromStegoBytes({
        bytes,
        password,
      });
      setResult({ slotIndex, json });
      setPassword('');
    } catch (e) {
      setError(e.message || 'Unlock failed.');
    } finally {
      setLoading(false);
    }
  }, [selected, password]);

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <Text style={styles.title}>🖼️ Stego Vaults</Text>
        <Text style={styles.subtitle}>
          Decrypt a hidden vault locally from an innocent-looking PNG that was
          embedded on the web or extension surface.
        </Text>

        {config && (
          <View style={styles.configCard}>
            <Text style={styles.configItem}>
              Server feature: {config.enabled ? '✅ enabled' : '❌ disabled'}
            </Text>
            <Text style={styles.configItem}>Format: {config.format}</Text>
          </View>
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.sectionTitle}>Available containers</Text>
        {!vaults.length && <Text style={styles.muted}>No stego images on this account yet.</Text>}
        <FlatList
          data={vaults}
          keyExtractor={(item) => item.id}
          scrollEnabled={false}
          renderItem={({ item }) => {
            const isSelected = selected && selected.id === item.id;
            return (
              <TouchableOpacity
                style={[styles.vaultRow, isSelected && styles.vaultRowSelected]}
                onPress={() => setSelected(item)}
              >
                <Text style={styles.vaultLabel}>{item.label}</Text>
                <Text style={styles.muted}>
                  Tier {item.blob_size_tier} · updated{' '}
                  {new Date(item.updated_at).toLocaleString()}
                </Text>
              </TouchableOpacity>
            );
          }}
        />

        <Text style={styles.sectionTitle}>Unlock</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder="Password (real or decoy)"
          secureTextEntry
          style={styles.input}
        />
        <TouchableOpacity
          style={[styles.primaryBtn, (!selected || loading) && styles.primaryBtnDisabled]}
          disabled={!selected || loading}
          onPress={onUnlock}
        >
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Unlock</Text>}
        </TouchableOpacity>

        {result && (
          <View style={styles.resultCard}>
            <Text style={styles.resultTitle}>Unlocked slot {result.slotIndex}</Text>
            <Text style={styles.resultBody} selectable>
              {JSON.stringify(result.json, null, 2)}
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0f172a' },
  scroll: { padding: 16, gap: 12 },
  title: { color: '#fff', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#94a3b8', fontSize: 13, marginBottom: 8 },
  sectionTitle: { color: '#e2e8f0', fontSize: 15, fontWeight: '600', marginTop: 12 },
  muted: { color: '#94a3b8', fontSize: 12 },
  configCard: { backgroundColor: '#1e293b', borderRadius: 8, padding: 10, gap: 4 },
  configItem: { color: '#cbd5e1', fontSize: 12 },
  vaultRow: { backgroundColor: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 6 },
  vaultRowSelected: { borderColor: '#7B68EE', borderWidth: 1 },
  vaultLabel: { color: '#fff', fontWeight: '600', marginBottom: 4 },
  input: {
    backgroundColor: '#1e293b',
    color: '#fff',
    padding: 10,
    borderRadius: 8,
    marginTop: 6,
  },
  primaryBtn: {
    backgroundColor: '#7B68EE',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
  },
  primaryBtnDisabled: { opacity: 0.6 },
  primaryBtnText: { color: '#fff', fontWeight: '600' },
  resultCard: { backgroundColor: '#1e293b', borderRadius: 8, padding: 12, marginTop: 10 },
  resultTitle: { color: '#fff', fontWeight: '700', marginBottom: 6 },
  resultBody: { color: '#cbd5e1', fontFamily: 'monospace', fontSize: 12 },
  error: { color: '#fca5a5', marginTop: 4 },
});

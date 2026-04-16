/**
 * IOSAutofillSettingsScreen — walks the iOS user through enabling
 * the Credential Provider Extension in Settings > Passwords >
 * Password Options > Allow filling from.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, Platform,
  ActivityIndicator, Alert, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import preClient from '../services/fhe/preClient';
import FHESharingService from '../services/FHESharingService';

const IDENTITY_KEY = 'fhe.pre.umbralIdentity.v1';

export default function IOSAutofillSettingsScreen() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [hasIdentity, setHasIdentity] = useState(false);
  const [credentialProviderEnabled, setCredentialProviderEnabled] = useState(false);
  const [umbralAvailable, setUmbralAvailable] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const stored = await SecureStore.getItemAsync(IDENTITY_KEY);
      setHasIdentity(!!stored);
      setUmbralAvailable(await preClient.isAvailable());
      setCredentialProviderEnabled(await preClient.isSystemAutofillEnabled());
    } catch (_e) {
      // soft-fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const enroll = async () => {
    setBusy(true);
    try {
      if (!umbralAvailable) {
        Alert.alert(
          'Umbral unavailable',
          'The Umbral FFI is not yet bundled. Rebuild the iOS project with the Credential Provider extension target.',
        );
        return;
      }
      const identity = await preClient.generateKeyPair();
      await SecureStore.setItemAsync(
        IDENTITY_KEY,
        JSON.stringify({ public: identity.public, secret: identity.secret }),
        { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY },
      );
      try {
        await FHESharingService.registerUmbralPublicKey(identity.public);
      } catch (_err) {
        Alert.alert('Server registration deferred',
          'Key saved locally; will retry pushing the public key next launch.');
      }
      await refresh();
    } catch (err) {
      Alert.alert('Enrollment failed', err?.message || 'Unknown error');
    } finally {
      setBusy(false);
    }
  };

  const openSettings = async () => {
    try {
      await Linking.openURL('App-Prefs:PASSWORDS');
    } catch (_err) {
      try {
        await Linking.openSettings();
      } catch (err) {
        Alert.alert('Cannot open Settings', err?.message || 'Unknown error');
      }
    }
  };

  if (Platform.OS !== 'ios') {
    return (
      <View style={styles.center}>
        <Ionicons name="logo-android" size={48} color="#666" />
        <Text style={styles.muted}>This screen is iOS-only.</Text>
      </View>
    );
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4A6CF7" />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>iOS Credential Provider</Text>
      <Text style={styles.sub}>
        iOS routes shared password autofills through our Credential Provider extension.
        The plaintext never crosses the JS bridge: the extension reads it from a shared
        App Group container and hands it straight to the OS.
      </Text>

      <View style={styles.card}>
        <Row label="Umbral FFI bundled" value={umbralAvailable ? 'Yes' : 'No'} ok={umbralAvailable} />
        <Row label="Umbral identity provisioned" value={hasIdentity ? 'Yes' : 'No'} ok={hasIdentity} />
        <Row label="Credential provider enabled"
             value={credentialProviderEnabled ? 'Yes' : 'No'}
             ok={credentialProviderEnabled} />
      </View>

      <TouchableOpacity style={styles.btnPrimary} onPress={enroll} disabled={busy}>
        <Text style={styles.btnPrimaryText}>
          {busy ? 'Working…' : hasIdentity ? 'Re-sync public key' : 'Enrol Umbral identity'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btn} onPress={openSettings}>
        <Text style={styles.btnText}>Open iOS Passwords settings</Text>
      </TouchableOpacity>

      <View style={styles.helpBox}>
        <Text style={styles.helpHeader}>Enable in Settings:</Text>
        <Text style={styles.helpLine}>1. Settings → Passwords → Password Options</Text>
        <Text style={styles.helpLine}>2. Allow filling from</Text>
        <Text style={styles.helpLine}>3. Enable “Password Manager (PRE)”</Text>
      </View>
    </ScrollView>
  );
}

function Row({ label, value, ok }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, { color: ok ? '#059669' : '#B91C1C' }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24 },
  title: { fontSize: 22, fontWeight: '700', color: '#1a1a1a' },
  sub: { fontSize: 13, color: '#666', lineHeight: 18 },
  muted: { color: '#666', fontSize: 14, textAlign: 'center' },
  card: { padding: 14, borderRadius: 12, backgroundColor: '#fff', borderWidth: 1, borderColor: '#eee' },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  rowLabel: { color: '#333', fontSize: 13 },
  rowValue: { fontWeight: '600', fontSize: 13 },
  btn: { padding: 14, borderRadius: 10, backgroundColor: '#f5f5f5', alignItems: 'center', borderWidth: 1, borderColor: '#e3e3e3' },
  btnText: { color: '#1a1a1a', fontWeight: '600' },
  btnPrimary: { padding: 14, borderRadius: 10, backgroundColor: '#4A6CF7', alignItems: 'center' },
  btnPrimaryText: { color: '#fff', fontWeight: '700' },
  helpBox: { padding: 12, backgroundColor: '#f7f9ff', borderRadius: 10, gap: 4 },
  helpHeader: { fontWeight: '700', color: '#1a1a1a', marginBottom: 4 },
  helpLine: { color: '#444', fontSize: 13 },
});

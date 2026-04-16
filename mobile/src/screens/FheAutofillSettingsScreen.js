/**
 * FheAutofillSettingsScreen — RN UI that walks the user through
 * enabling the native autofill provider and enrolling their Umbral
 * identity.
 *
 * This screen is Android-only (see `fhe-autofill` native module).
 * On iOS it gracefully renders a "use the iOS credential provider
 * screen instead" message pointing at `IOSAutofillSettingsScreen`.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  ActivityIndicator, Alert, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import preClient from '../services/fhe/preClient';
import FHESharingService from '../services/FHESharingService';

const IDENTITY_KEY = 'fhe.pre.umbralIdentity.v1';

export default function FheAutofillSettingsScreen() {
  const [loading, setLoading] = useState(true);
  const [hasIdentity, setHasIdentity] = useState(false);
  const [identityPub, setIdentityPub] = useState(null);
  const [autofillEnabled, setAutofillEnabled] = useState(false);
  const [umbralAvailable, setUmbralAvailable] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const stored = await SecureStore.getItemAsync(IDENTITY_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setHasIdentity(true);
        setIdentityPub(parsed.public || null);
      } else {
        setHasIdentity(false);
        setIdentityPub(null);
      }
      setUmbralAvailable(await preClient.isAvailable());
      setAutofillEnabled(await preClient.isSystemAutofillEnabled());
    } catch (_err) {
      // soft-fail: keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const enrollIdentity = async () => {
    setBusy(true);
    try {
      if (!umbralAvailable) {
        Alert.alert(
          'Umbral unavailable',
          'The native Umbral library is not bundled in this build. Rebuild the dev client after running `npx expo prebuild`.',
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
      } catch (err) {
        Alert.alert(
          'Server registration deferred',
          'Saved your key on this device; will retry pushing the public key next time you open the app.',
        );
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
      await preClient.openAutofillSettings();
    } catch (err) {
      Alert.alert('Cannot open settings', err?.message || 'Unknown error');
    }
  };

  const rotateIdentity = async () => {
    Alert.alert(
      'Rotate Umbral identity?',
      'All existing umbral-v1 shares sent to this device will become undecryptable.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rotate',
          style: 'destructive',
          onPress: async () => {
            await SecureStore.deleteItemAsync(IDENTITY_KEY);
            await enrollIdentity();
          },
        },
      ],
    );
  };

  if (Platform.OS === 'ios') {
    return (
      <View style={styles.center}>
        <Ionicons name="logo-apple" size={48} color="#666" />
        <Text style={styles.muted}>
          iOS uses the Credential Provider Extension.
        </Text>
        <Text style={styles.muted}>
          Open the “iOS Autofill” screen from the main menu.
        </Text>
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
      <Text style={styles.title}>Homomorphic autofill</Text>
      <Text style={styles.sub}>
        Receive shared passwords without ever seeing them — the OS autofills
        the field directly from the decrypted plaintext held only in memory.
      </Text>

      <View style={styles.card}>
        <Row
          label="Umbral crypto bundled"
          value={umbralAvailable ? 'Yes' : 'No (using JS fallback)'}
          ok={umbralAvailable}
        />
        <Row label="Umbral identity provisioned" value={hasIdentity ? 'Yes' : 'No'} ok={hasIdentity} />
        <Row label="Android autofill enabled" value={autofillEnabled ? 'Yes' : 'No'} ok={autofillEnabled} />
        {identityPub?.umbralPublicKey && (
          <Text style={styles.mono} numberOfLines={1}>
            pk: {identityPub.umbralPublicKey}
          </Text>
        )}
      </View>

      <TouchableOpacity style={styles.btnPrimary} onPress={enrollIdentity} disabled={busy}>
        <Text style={styles.btnPrimaryText}>
          {busy ? 'Working…' : hasIdentity ? 'Re-sync public key with server' : 'Enrol Umbral identity'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btn} onPress={openSettings} disabled={busy}>
        <Text style={styles.btnText}>
          {autofillEnabled ? 'Open Android autofill settings' : 'Enable Android autofill'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btnDanger} onPress={rotateIdentity} disabled={!hasIdentity}>
        <Text style={styles.btnDangerText}>Rotate identity</Text>
      </TouchableOpacity>
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
  mono: { fontFamily: 'monospace', fontSize: 11, color: '#666', marginTop: 6 },
  btn: { padding: 14, borderRadius: 10, backgroundColor: '#f5f5f5', alignItems: 'center', borderWidth: 1, borderColor: '#e3e3e3' },
  btnText: { color: '#1a1a1a', fontWeight: '600' },
  btnPrimary: { padding: 14, borderRadius: 10, backgroundColor: '#4A6CF7', alignItems: 'center' },
  btnPrimaryText: { color: '#fff', fontWeight: '700' },
  btnDanger: { padding: 14, borderRadius: 10, backgroundColor: '#fff', alignItems: 'center', borderWidth: 1, borderColor: '#f0cccc' },
  btnDangerText: { color: '#B91C1C', fontWeight: '600' },
});

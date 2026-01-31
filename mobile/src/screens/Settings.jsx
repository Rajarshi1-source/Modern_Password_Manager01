import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, Switch,
  TouchableOpacity, Alert, ScrollView
} from 'react-native';
import MobileSecureStorage from '../services/mobileSecureStorage';
import { Ionicons } from '@expo/vector-icons';
import * as LocalAuthentication from 'expo-local-authentication';
import { authService } from '../services/authService';

const Settings = ({ navigation }) => {
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [biometricEnabled, setBiometricEnabled] = useState(false);
  const [biometricType, setBiometricType] = useState('');

  useEffect(() => {
    checkBiometricStatus();
  }, []);

  const checkBiometricStatus = async () => {
    try {
      // Check if device supports biometrics
      const available = await MobileSecureStorage.isHardwareSecurityAvailable();
      setBiometricAvailable(available);

      if (available) {
        // Check if biometric login is enabled
        const enabled = await MobileSecureStorage.hasSavedCredentials();
        setBiometricEnabled(enabled);

        // Determine biometric type (face or fingerprint)
        const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
        setBiometricType(types.includes(2) ? 'Face ID' : 'Fingerprint');
      }
    } catch (error) {
      console.error('Error checking biometric status:', error);
    }
  };

  const toggleBiometricAuth = async (value) => {
    if (value) {
      // Enable biometric auth
      Alert.prompt(
        'Enable Biometric Login',
        'Please enter your master password to enable biometric authentication',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Enable',
            onPress: async (password) => {
              if (!password) {
                Alert.alert('Error', 'Password is required');
                return;
              }

              try {
                // Verify master password
                const result = await authService.checkMasterPassword(password);

                if (result.success) {
                  // Store credentials for biometric auth
                  await MobileSecureStorage.storeCredentials(
                    authService.getCurrentUser().email,
                    password
                  );
                  setBiometricEnabled(true);
                } else {
                  Alert.alert('Error', 'Invalid master password');
                }
              } catch (error) {
                Alert.alert('Error', 'Failed to enable biometric authentication');
              }
            }
          }
        ],
        'secure-text'
      );
    } else {
      // Disable biometric auth
      Alert.alert(
        'Disable Biometric Login',
        'Are you sure you want to disable biometric login?',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Disable',
            style: 'destructive',
            onPress: async () => {
              await MobileSecureStorage.clearCredentials();
              setBiometricEnabled(false);
            }
          }
        ]
      );
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Security Settings</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Authentication</Text>

        {biometricAvailable ? (
          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Ionicons
                name={biometricType === 'Face ID' ? 'ios-face-id' : 'ios-finger-print'}
                size={24}
                color="#4A6CF7"
                style={styles.icon}
              />
              <View>
                <Text style={styles.settingTitle}>
                  {biometricType} Authentication
                </Text>
                <Text style={styles.settingDescription}>
                  Use {biometricType} to quickly access your vault
                </Text>
              </View>
            </View>
            <Switch
              value={biometricEnabled}
              onValueChange={toggleBiometricAuth}
              trackColor={{ false: '#E5E7EB', true: '#4A6CF7' }}
              thumbColor="#FFFFFF"
            />
          </View>
        ) : (
          <Text style={styles.notAvailable}>
            Biometric authentication is not available on this device
          </Text>
        )}

        <TouchableOpacity style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Ionicons name="ios-key-outline" size={24} color="#4A6CF7" style={styles.icon} />
            <View>
              <Text style={styles.settingTitle}>Change Master Password</Text>
              <Text style={styles.settingDescription}>
                Update your master password
              </Text>
            </View>
          </View>
          <Ionicons name="ios-chevron-forward" size={18} color="#9CA3AF" />
        </TouchableOpacity>
      </View>

      {/* Duress Protection Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Advanced Security</Text>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => navigation.navigate('DuressCode')}
        >
          <View style={styles.settingInfo}>
            <Ionicons name="shield-checkmark" size={24} color="#dc2626" style={styles.icon} />
            <View>
              <Text style={styles.settingTitle}>🎖️ Duress Protection</Text>
              <Text style={styles.settingDescription}>
                Military-grade protection against coerced access
              </Text>
            </View>
          </View>
          <Ionicons name="ios-chevron-forward" size={18} color="#9CA3AF" />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => navigation.navigate('NaturalEntropy')}
        >
          <View style={styles.settingInfo}>
            <Ionicons name="leaf" size={24} color="#22c55e" style={styles.icon} />
            <View>
              <Text style={styles.settingTitle}>🌿 Natural Entropy</Text>
              <Text style={styles.settingDescription}>
                Generate randomness from nature
              </Text>
            </View>
          </View>
          <Ionicons name="ios-chevron-forward" size={18} color="#9CA3AF" />
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 24,
    marginTop: 8,
  },
  section: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  icon: {
    marginRight: 12,
  },
  settingTitle: {
    fontSize: 16,
    fontWeight: '500',
  },
  settingDescription: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  notAvailable: {
    fontSize: 14,
    color: '#6B7280',
    fontStyle: 'italic',
    paddingVertical: 12,
  },
});

export default Settings;

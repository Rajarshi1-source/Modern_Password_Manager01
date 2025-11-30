import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import { Ionicons } from '@expo/vector-icons';

const BiometricAuth = ({ onAuthenticate, onCancel, fallbackToPassword }) => {
  const [biometricType, setBiometricType] = useState(null);
  const [isCompatible, setIsCompatible] = useState(false);

  useEffect(() => {
    (async () => {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      setIsCompatible(compatible);

      if (compatible) {
        const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
        // 1 = Fingerprint, 2 = Facial Recognition
        const isFacial = types.includes(2);
        setBiometricType(isFacial ? 'facial' : 'fingerprint');
      }
    })();
  }, []);

  const handleAuthenticate = async () => {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access your password vault',
        cancelLabel: 'Use Master Password',
        fallbackLabel: 'Use Master Password',
        disableDeviceFallback: false,
      });

      if (result.success) {
        onAuthenticate();
      } else if (result.error === 'user_cancel') {
        onCancel();
      } else {
        fallbackToPassword();
      }
    } catch (error) {
      console.error('Biometric authentication error:', error);
      Alert.alert(
        'Authentication Failed',
        'Biometric authentication failed. Please try again or use your master password.',
        [{ text: 'OK', onPress: fallbackToPassword }]
      );
    }
  };

  if (!isCompatible) {
    return null; // No biometrics available, don't render anything
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.button} onPress={handleAuthenticate}>
        <Ionicons 
          name={biometricType === 'facial' ? 'ios-face-id' : 'ios-finger-print'} 
          size={32} 
          color="#fff" 
        />
        <Text style={styles.buttonText}>
          Use {biometricType === 'facial' ? 'Face ID' : 'Fingerprint'}
        </Text>
      </TouchableOpacity>
      
      <TouchableOpacity style={styles.textButton} onPress={fallbackToPassword}>
        <Text style={styles.textButtonText}>Use Master Password</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginVertical: 20,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#4A6CF7',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    marginBottom: 16,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  textButton: {
    padding: 8,
  },
  textButtonText: {
    color: '#4A6CF7',
    fontSize: 14,
  },
});

export default BiometricAuth;

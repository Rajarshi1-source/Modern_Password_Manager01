import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Image
} from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import { Camera } from 'expo-camera';
import { Audio } from 'expo-av';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import mfaService from '../services/mfaService';

const BiometricAuthScreen = ({ navigation, route }) => {
  const { requiredFactors, onSuccess } = route.params || {};
  
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [hasPermissions, setHasPermissions] = useState(false);
  const [supportedTypes, setSupportedTypes] = useState([]);
  
  useEffect(() => {
    checkBiometricSupport();
  }, []);
  
  const checkBiometricSupport = async () => {
    const compatible = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    
    if (compatible && enrolled) {
      setSupportedTypes(types);
      setHasPermissions(true);
      
      // Auto-select device biometric if available
      if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
        setSelectedMethod('device_face');
      } else if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
        setSelectedMethod('fingerprint');
      }
    } else {
      Alert.alert(
        'Biometric Not Available',
        'Your device does not support biometric authentication or it is not set up.',
        [{ text: 'OK', onPress: () => navigation.goBack() }]
      );
    }
  };
  
  const authenticateWithDeviceBiometric = async () => {
    setIsAuthenticating(true);
    
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access your vault',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
        fallbackLabel: 'Use Passcode'
      });
      
      if (result.success) {
        // Send success to backend
        const authResult = await mfaService.authenticateWithBiometrics({
          method: 'device_biometric',
          device_id: await getDeviceId()
        });
        
        if (authResult.success) {
          if (onSuccess) onSuccess(authResult);
          navigation.goBack();
        } else {
          Alert.alert('Authentication Failed', authResult.message || 'Please try again');
        }
      } else {
        Alert.alert('Authentication Cancelled', 'Please try again');
      }
    } catch (error) {
      console.error('Biometric auth error:', error);
      Alert.alert('Error', 'Authentication failed. Please try again.');
    } finally {
      setIsAuthenticating(false);
    }
  };
  
  const authenticateWithFaceML = async () => {
    setIsAuthenticating(true);
    
    try {
      // Request camera permission
      const { status } = await Camera.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Camera permission is required for face authentication');
        setIsAuthenticating(false);
        return;
      }
      
      // Navigate to camera screen for face capture
      navigation.navigate('FaceCapture', {
        onCapture: async (imageUri) => {
          try {
            const result = await mfaService.authenticateWithFace(imageUri);
            if (result.success) {
              if (onSuccess) onSuccess(result);
              navigation.goBack();
            } else {
              Alert.alert('Face Not Recognized', result.message || 'Please try again');
            }
          } catch (error) {
            Alert.alert('Error', 'Face authentication failed');
          } finally {
            setIsAuthenticating(false);
          }
        }
      });
    } catch (error) {
      console.error('Face auth error:', error);
      Alert.alert('Error', 'Face authentication failed');
      setIsAuthenticating(false);
    }
  };
  
  const authenticateWithVoice = async () => {
    setIsAuthenticating(true);
    
    try {
      // Request microphone permission
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Microphone permission is required for voice authentication');
        setIsAuthenticating(false);
        return;
      }
      
      // Start recording
      Alert.alert(
        'Voice Authentication',
        'Say "My voice is my password" when ready',
        [
          {
            text: 'Start Recording',
            onPress: async () => {
              try {
                const recording = new Audio.Recording();
                await recording.prepareToRecordAsync(Audio.RECORDING_OPTIONS_PRESET_HIGH_QUALITY);
                await recording.startAsync();
                
                // Record for 3 seconds
                setTimeout(async () => {
                  await recording.stopAndUnloadAsync();
                  const uri = recording.getURI();
                  
                  // Send to backend
                  const result = await mfaService.authenticateWithVoice(uri);
                  if (result.success) {
                    if (onSuccess) onSuccess(result);
                    navigation.goBack();
                  } else {
                    Alert.alert('Voice Not Recognized', result.message || 'Please try again');
                  }
                  setIsAuthenticating(false);
                }, 3000);
              } catch (error) {
                console.error('Voice auth error:', error);
                Alert.alert('Error', 'Voice authentication failed');
                setIsAuthenticating(false);
              }
            }
          },
          {
            text: 'Cancel',
            style: 'cancel',
            onPress: () => setIsAuthenticating(false)
          }
        ]
      );
    } catch (error) {
      console.error('Voice auth error:', error);
      Alert.alert('Error', 'Voice authentication failed');
      setIsAuthenticating(false);
    }
  };
  
  const getDeviceId = async () => {
    // Implement device ID retrieval
    return 'device_id_placeholder';
  };
  
  const handleAuthenticate = () => {
    switch (selectedMethod) {
      case 'device_face':
      case 'fingerprint':
        authenticateWithDeviceBiometric();
        break;
      case 'face_ml':
        authenticateWithFaceML();
        break;
      case 'voice':
        authenticateWithVoice();
        break;
      default:
        Alert.alert('Select Method', 'Please select an authentication method');
    }
  };
  
  const renderMethodButton = (method, icon, title, description, available = true) => (
    <TouchableOpacity
      style={[
        styles.methodButton,
        selectedMethod === method && styles.methodButtonActive,
        !available && styles.methodButtonDisabled
      ]}
      onPress={() => available && setSelectedMethod(method)}
      disabled={!available || isAuthenticating}
    >
      <View style={styles.methodIcon}>
        <Icon name={icon} size={32} color={selectedMethod === method ? '#007AFF' : '#666'} />
      </View>
      <Text style={[
        styles.methodTitle,
        selectedMethod === method && styles.methodTitleActive
      ]}>
        {title}
      </Text>
      <Text style={styles.methodDescription}>{description}</Text>
      {!available && (
        <Text style={styles.notAvailable}>Not Available</Text>
      )}
    </TouchableOpacity>
  );
  
  if (!hasPermissions) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Checking biometric support...</Text>
      </View>
    );
  }
  
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Icon name="shield-lock" size={48} color="#007AFF" />
        <Text style={styles.title}>Biometric Authentication</Text>
        <Text style={styles.subtitle}>Select your preferred method</Text>
      </View>
      
      <View style={styles.methodsContainer}>
        {renderMethodButton(
          'device_face',
          'face-recognition',
          'Face ID',
          'Use device Face ID',
          supportedTypes.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)
        )}
        
        {renderMethodButton(
          'fingerprint',
          'fingerprint',
          'Fingerprint',
          'Use device fingerprint',
          supportedTypes.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)
        )}
        
        {renderMethodButton(
          'face_ml',
          'face-recognition',
          'ML Face Recognition',
          'Advanced face verification',
          true
        )}
        
        {renderMethodButton(
          'voice',
          'microphone',
          'Voice Recognition',
          'Voice biometric verification',
          true
        )}
      </View>
      
      <View style={styles.footer}>
        <TouchableOpacity
          style={[
            styles.authenticateButton,
            (!selectedMethod || isAuthenticating) && styles.authenticateButtonDisabled
          ]}
          onPress={handleAuthenticate}
          disabled={!selectedMethod || isAuthenticating}
        >
          {isAuthenticating ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.authenticateButtonText}>Authenticate</Text>
          )}
        </TouchableOpacity>
        
        <TouchableOpacity
          style={styles.cancelButton}
          onPress={() => navigation.goBack()}
          disabled={isAuthenticating}
        >
          <Text style={styles.cancelButtonText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 20
  },
  header: {
    alignItems: 'center',
    marginBottom: 30,
    paddingTop: 20
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginTop: 10
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    marginTop: 5
  },
  loadingText: {
    marginTop: 15,
    color: '#666',
    fontSize: 16
  },
  methodsContainer: {
    flex: 1
  },
  methodButton: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 15,
    borderWidth: 2,
    borderColor: '#e0e0e0',
    alignItems: 'center'
  },
  methodButtonActive: {
    borderColor: '#007AFF',
    backgroundColor: '#f0f7ff'
  },
  methodButtonDisabled: {
    opacity: 0.5
  },
  methodIcon: {
    marginBottom: 10
  },
  methodTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 5
  },
  methodTitleActive: {
    color: '#007AFF'
  },
  methodDescription: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center'
  },
  notAvailable: {
    fontSize: 12,
    color: '#ff3b30',
    marginTop: 5,
    fontStyle: 'italic'
  },
  footer: {
    paddingBottom: 20
  },
  authenticateButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 10
  },
  authenticateButtonDisabled: {
    opacity: 0.5
  },
  authenticateButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600'
  },
  cancelButton: {
    padding: 16,
    alignItems: 'center'
  },
  cancelButtonText: {
    color: '#007AFF',
    fontSize: 16
  }
});

export default BiometricAuthScreen;


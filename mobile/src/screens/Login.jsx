import React, { useState, useEffect } from 'react';
import { 
  View, Text, TextInput, StyleSheet, 
  TouchableOpacity, KeyboardAvoidingView, Platform, Alert 
} from 'react-native';
import BiometricAuth from '../components/BiometricAuth';
import MobileSecureStorage from '../services/mobileSecureStorage';
import { authService } from '../services/authService';
import SocialLogin from '../components/SocialLogin';

const Login = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showBiometric, setShowBiometric] = useState(false);
  
  useEffect(() => {
    checkBiometricAvailability();
  }, []);
  
  const checkBiometricAvailability = async () => {
    try {
      // Check if biometrics are available AND user has previously enabled it
      const hasHardware = await MobileSecureStorage.isHardwareSecurityAvailable();
      const hasSavedCredentials = await MobileSecureStorage.hasSavedCredentials();
      
      setShowBiometric(hasHardware && hasSavedCredentials);
    } catch (error) {
      console.error('Error checking biometric availability:', error);
    }
  };
  
  const handleBiometricAuth = async () => {
    try {
      setLoading(true);
      
      // Attempt to retrieve credentials using biometrics
      const credentials = await MobileSecureStorage.retrieveCredentials();
      
      if (credentials) {
        // Login with retrieved credentials
        const result = await authService.login(
          credentials.email, 
          credentials.password
        );
        
        if (result.success) {
          navigation.navigate('Vault');
        } else {
          throw new Error('Invalid credentials');
        }
      }
    } catch (error) {
      setError('Biometric authentication failed');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      
      if (!email || !password) {
        setError('Email and password are required');
        return;
      }
      
      const result = await authService.login(email, password);
      
      if (result.success) {
        // Ask user if they want to enable biometric login
        if (await MobileSecureStorage.isHardwareSecurityAvailable()) {
          const storeBiometrics = await confirmBiometricSetup();
          
          if (storeBiometrics) {
            await MobileSecureStorage.storeCredentials(email, password);
          }
        }
        
        navigation.navigate('Vault');
      } else {
        setError('Invalid credentials');
      }
    } catch (error) {
      setError(error.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };
  
  const confirmBiometricSetup = () => {
    return new Promise((resolve) => {
      Alert.alert(
        'Enable Biometric Login',
        'Would you like to enable fingerprint/face login for faster access?',
        [
          { text: 'No thanks', onPress: () => resolve(false) },
          { text: 'Enable', onPress: () => resolve(true) },
        ]
      );
    });
  };
  
  return (
    <KeyboardAvoidingView 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <View style={styles.formContainer}>
        <Text style={styles.title}>Sign In</Text>
        
        {error ? <Text style={styles.error}>{error}</Text> : null}
        
        {showBiometric && (
          <BiometricAuth
            onAuthenticate={handleBiometricAuth}
            onCancel={() => {}}
            fallbackToPassword={() => setShowBiometric(false)}
          />
        )}
        
        {(!showBiometric || error) && (
          <>
            <TextInput
              style={styles.input}
              placeholder="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
            />
            
            <TextInput
              style={styles.input}
              placeholder="Master Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />
            
            <TouchableOpacity 
              style={styles.button} 
              onPress={handleLogin}
              disabled={loading}
            >
              <Text style={styles.buttonText}>
                {loading ? 'Signing in...' : 'Sign In'}
              </Text>
            </TouchableOpacity>
          </>
        )}
        
        {/* Social login buttons */}
        <SocialLogin 
          onLoginSuccess={(token) => {
            // Handle login success
            authService.setToken(token);
            navigation.navigate('Vault');
          }} 
        />
        
        {/* Password recovery link */}
        <TouchableOpacity
          style={styles.recoveryLink}
          onPress={() => navigation.navigate('AccountRecovery')}
        >
          <Text style={styles.recoveryText}>Forgot your password?</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  formContainer: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 24,
    textAlign: 'center',
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  button: {
    backgroundColor: '#4A6CF7',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 16,
  },
  error: {
    color: '#EF4444',
    marginBottom: 16,
    textAlign: 'center',
  },
  recoveryLink: {
    padding: 16,
    alignItems: 'center',
  },
  recoveryText: {
    color: '#4A6CF7',
    fontWeight: '500',
  },
});

export default Login;

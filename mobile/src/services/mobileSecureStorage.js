import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';

export default class MobileSecureStorage {
  static async isHardwareSecurityAvailable() {
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      return hasHardware && isEnrolled;
    } catch (error) {
      console.error('Error checking biometric hardware:', error);
      return false;
    }
  }
  
  static async storeKey(keyId, keyData) {
    try {
      // Convert keyData to string if it's a buffer
      const keyString = typeof keyData === 'string' 
        ? keyData 
        : Buffer.from(keyData).toString('base64');
      
      // Store in device keychain/keystore with biometric protection
      await SecureStore.setItemAsync(`key_${keyId}`, keyString, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        requireAuthentication: true,
        authenticationPrompt: 'Authenticate to access your keys'
      });
      
      return true;
    } catch (error) {
      console.error('Error storing key:', error);
      return false;
    }
  }
  
  static async retrieveKey(keyId) {
    try {
      const keyString = await SecureStore.getItemAsync(`key_${keyId}`, {
        requireAuthentication: true,
        authenticationPrompt: 'Authenticate to access your keys'
      });
      
      if (!keyString) {
        throw new Error('Key not found');
      }
      
      // Convert back to Buffer if needed
      return Buffer.from(keyString, 'base64');
    } catch (error) {
      console.error('Error retrieving key:', error);
      throw error;
    }
  }
  
  // Check if user has saved credentials for biometric login
  static async hasSavedCredentials() {
    try {
      const result = await SecureStore.getItemAsync('has_biometric_credentials');
      return result === 'true';
    } catch (error) {
      return false;
    }
  }
  
  // Store user credentials securely
  static async storeCredentials(email, password) {
    try {
      // First authenticate with biometrics to confirm user identity
      const auth = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to enable biometric login',
        disableDeviceFallback: false,
      });
      
      if (!auth.success) {
        throw new Error('Biometric authentication failed');
      }
      
      // Store credentials
      await SecureStore.setItemAsync('credentials_email', email, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
      
      await SecureStore.setItemAsync('credentials_password', password, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
      
      // Mark that we have credentials stored
      await SecureStore.setItemAsync('has_biometric_credentials', 'true');
      
      return true;
    } catch (error) {
      console.error('Error storing credentials:', error);
      return false;
    }
  }
  
  // Retrieve credentials using biometric authentication
  static async retrieveCredentials() {
    try {
      // Authenticate with biometrics
      const auth = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access your password vault',
        fallbackLabel: 'Use master password instead',
        disableDeviceFallback: false,
      });
      
      if (!auth.success) {
        throw new Error('Biometric authentication failed');
      }
      
      // Retrieve credentials
      const email = await SecureStore.getItemAsync('credentials_email');
      const password = await SecureStore.getItemAsync('credentials_password');
      
      if (!email || !password) {
        throw new Error('No stored credentials found');
      }
      
      return { email, password };
    } catch (error) {
      console.error('Error retrieving credentials:', error);
      throw error;
    }
  }
  
  // Remove stored credentials
  static async clearCredentials() {
    try {
      await SecureStore.deleteItemAsync('credentials_email');
      await SecureStore.deleteItemAsync('credentials_password');
      await SecureStore.deleteItemAsync('has_biometric_credentials');
      return true;
    } catch (error) {
      console.error('Error clearing credentials:', error);
      return false;
    }
  }
}

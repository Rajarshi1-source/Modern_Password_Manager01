import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Location from 'expo-location';
import { API_URL } from '../config';

class MFAService {
  constructor() {
    this.baseURL = `${API_URL}/api/auth`;
  }

  async getAuthHeaders() {
    const token = await AsyncStorage.getItem('authToken');
    const deviceFingerprint = await this.getDeviceFingerprint();
    const location = await this.getCurrentLocation();
    
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'X-Device-Fingerprint': deviceFingerprint,
      'X-Location': location
    };
  }

  async getDeviceFingerprint() {
    try {
      let fingerprint = await AsyncStorage.getItem('device_fingerprint');
      if (!fingerprint) {
        fingerprint = `${Platform.OS}_${Device.modelName}_${Device.osVersion}_${Date.now()}`;
        await AsyncStorage.setItem('device_fingerprint', fingerprint);
      }
      return fingerprint;
    } catch (error) {
      console.error('Error getting device fingerprint:', error);
      return `${Platform.OS}_unknown`;
    }
  }

  async getCurrentLocation() {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        return 'unknown';
      }

      const location = await Location.getCurrentPositionAsync({});
      return `${location.coords.latitude},${location.coords.longitude}`;
    } catch (error) {
      console.error('Error getting location:', error);
      return 'unknown';
    }
  }

  // ====================
  // Biometric Registration
  // ====================

  async registerFace(imageBlob) {
    try {
      const headers = await this.getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';

      const formData = new FormData();
      formData.append('face_image', {
        uri: imageBlob,
        type: 'image/jpeg',
        name: 'face.jpg'
      });

      const response = await axios.post(
        `${this.baseURL}/mfa/biometric/face/register/`,
        formData,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Face registration error:', error);
      throw error;
    }
  }

  async registerVoice(audioUri) {
    try {
      const headers = await this.getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';

      const formData = new FormData();
      formData.append('voice_sample', {
        uri: audioUri,
        type: 'audio/m4a',
        name: 'voice.m4a'
      });

      const response = await axios.post(
        `${this.baseURL}/mfa/biometric/voice/register/`,
        formData,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Voice registration error:', error);
      throw error;
    }
  }

  // ====================
  // Biometric Authentication
  // ====================

  async authenticateWithFace(imageUri) {
    try {
      const headers = await this.getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';

      const formData = new FormData();
      formData.append('face_image', {
        uri: imageUri,
        type: 'image/jpeg',
        name: 'face.jpg'
      });

      const response = await axios.post(
        `${this.baseURL}/mfa/biometric/authenticate/`,
        formData,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Face authentication error:', error);
      return { success: false, message: error.message };
    }
  }

  async authenticateWithVoice(audioUri) {
    try {
      const headers = await this.getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';

      const formData = new FormData();
      formData.append('voice_sample', {
        uri: audioUri,
        type: 'audio/m4a',
        name: 'voice.m4a'
      });

      const response = await axios.post(
        `${this.baseURL}/mfa/biometric/authenticate/`,
        formData,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Voice authentication error:', error);
      return { success: false, message: error.message };
    }
  }

  async authenticateWithBiometrics(data) {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/biometric/authenticate/`,
        data,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Biometric authentication error:', error);
      return { success: false, message: error.message };
    }
  }

  // ====================
  // Integrated MFA + 2FA
  // ====================

  async getMFARequirements(operationType = 'login') {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.get(
        `${this.baseURL}/mfa/requirements/`,
        {
          params: { operation_type: operationType },
          headers
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error getting MFA requirements:', error);
      throw error;
    }
  }

  async verifyIntegratedMFA(factors) {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/verify/`,
        { factors },
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('MFA verification error:', error);
      return {
        success: false,
        message: error.response?.data?.message || error.message
      };
    }
  }

  // ====================
  // Adaptive MFA
  // ====================

  async assessRisk() {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/assess-risk/`,
        {},
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Risk assessment error:', error);
      throw error;
    }
  }

  async getEnabledFactors() {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.get(
        `${this.baseURL}/mfa/factors/`,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Error getting enabled factors:', error);
      throw error;
    }
  }

  async getMFAPolicy() {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.get(
        `${this.baseURL}/mfa/policy/`,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Error getting MFA policy:', error);
      throw error;
    }
  }

  async updateMFAPolicy(policy) {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/policy/`,
        policy,
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Error updating MFA policy:', error);
      throw error;
    }
  }

  // ====================
  // Authentication History
  // ====================

  async getAuthHistory(params = {}) {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.get(
        `${this.baseURL}/mfa/auth-attempts/`,
        {
          params,
          headers
        }
      );

      return response.data;
    } catch (error) {
      console.error('Error getting auth history:', error);
      throw error;
    }
  }

  // ====================
  // Continuous Authentication
  // ====================

  async startContinuousAuth() {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/continuous-auth/start/`,
        {},
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Error starting continuous auth:', error);
      throw error;
    }
  }

  async updateContinuousAuth(behavioralData) {
    try {
      const headers = await this.getAuthHeaders();
      
      const response = await axios.post(
        `${this.baseURL}/mfa/continuous-auth/update/`,
        { behavioral_data: behavioralData },
        { headers }
      );

      return response.data;
    } catch (error) {
      console.error('Error updating continuous auth:', error);
      throw error;
    }
  }
}

export default new MFAService();


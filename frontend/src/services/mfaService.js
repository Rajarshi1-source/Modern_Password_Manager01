/**
 * Multi-Factor Authentication Service
 * 
 * Handles:
 * - Biometric registration (face, voice)
 * - Biometric authentication
 * - Adaptive MFA
 * - Continuous authentication
 */

import axios from 'axios';
import apiService from './api';

// Use relative paths in development to leverage Vite proxy
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

class MFAService {
  /**
   * Register face biometric
   * @param {Blob|File} faceImage - Face image from camera
   * @param {string} deviceId - Unique device identifier
   * @returns {Promise<Object>} Registration result
   */
  async registerFace(faceImage, deviceId = 'browser') {
    try {
      // Convert image to base64
      const base64Image = await this.imageToBase64(faceImage);
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/biometric/face/register/`,
        {
          face_image: base64Image,
          device_id: deviceId
        },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Face registration error:', error);
      throw new Error(error.response?.data?.message || 'Face registration failed');
    }
  }
  
  /**
   * Register voice biometric
   * @param {Blob} audioBlob - Audio recording from microphone
   * @param {string} deviceId - Unique device identifier
   * @returns {Promise<Object>} Registration result
   */
  async registerVoice(audioBlob, deviceId = 'browser') {
    try {
      // Convert audio to base64
      const base64Audio = await this.audioToBase64(audioBlob);
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/biometric/voice/register/`,
        {
          voice_audio: base64Audio,
          device_id: deviceId
        },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Voice registration error:', error);
      throw new Error(error.response?.data?.message || 'Voice registration failed');
    }
  }
  
  /**
   * Authenticate using biometrics
   * @param {string} username - Username
   * @param {string} biometricType - 'face' or 'voice'
   * @param {Blob|File} biometricData - Image or audio data
   * @param {string} deviceId - Device identifier
   * @returns {Promise<Object>} Authentication result
   */
  async authenticateBiometric(username, biometricType, biometricData, deviceId = 'browser') {
    try {
      // Convert data to base64
      let base64Data;
      if (biometricType === 'face') {
        base64Data = await this.imageToBase64(biometricData);
      } else {
        base64Data = await this.audioToBase64(biometricData);
      }
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/biometric/authenticate/`,
        {
          username,
          biometric_type: biometricType,
          biometric_data: base64Data,
          device_id: deviceId
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Biometric authentication error:', error);
      throw new Error(error.response?.data?.message || 'Biometric authentication failed');
    }
  }
  
  /**
   * Start continuous authentication session
   * @param {number} durationMinutes - Session duration
   * @returns {Promise<Object>} Session details
   */
  async startContinuousAuth(durationMinutes = 60) {
    try {
      const deviceFingerprint = await this.getDeviceFingerprint();
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/continuous-auth/start/`,
        {
          session_duration_minutes: durationMinutes,
          device_fingerprint: deviceFingerprint
        },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Continuous auth start error:', error);
      throw new Error(error.response?.data?.message || 'Failed to start continuous authentication');
    }
  }
  
  /**
   * Update continuous authentication score
   * @param {string} sessionId - Session identifier
   * @param {Object} data - Biometric and behavioral data
   * @returns {Promise<Object>} Update result
   */
  async updateContinuousAuth(sessionId, data = {}) {
    try {
      const requestData = {
        session_id: sessionId
      };
      
      // Add face image if provided
      if (data.faceImage) {
        requestData.face_image = await this.imageToBase64(data.faceImage);
      }
      
      // Add voice audio if provided
      if (data.voiceAudio) {
        requestData.voice_audio = await this.audioToBase64(data.voiceAudio);
      }
      
      // Add behavioral data if provided
      if (data.behaviorData) {
        requestData.behavior_data = data.behaviorData;
      }
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/continuous-auth/update/`,
        requestData,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Continuous auth update error:', error);
      throw new Error(error.response?.data?.message || 'Failed to update continuous authentication');
    }
  }
  
  /**
   * Assess MFA risk level
   * @param {string} action - Action being attempted
   * @param {Object} context - Additional context data
   * @returns {Promise<Object>} Risk assessment
   */
  async assessRisk(action, context = {}) {
    try {
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/assess-risk/`,
        {
          action,
          context
        },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Risk assessment error:', error);
      throw new Error(error.response?.data?.message || 'Failed to assess risk');
    }
  }
  
  /**
   * Get user's MFA factors
   * @returns {Promise<Object>} List of MFA factors
   */
  async getMFAFactors() {
    try {
      const response = await axios.get(
        `${API_BASE}/api/auth/mfa/factors/`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Get MFA factors error:', error);
      throw new Error(error.response?.data?.message || 'Failed to get MFA factors');
    }
  }
  
  /**
   * Get user's MFA policy
   * @returns {Promise<Object>} MFA policy
   */
  async getMFAPolicy() {
    try {
      const response = await axios.get(
        `${API_BASE}/api/auth/mfa/policy/`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Get MFA policy error:', error);
      throw new Error(error.response?.data?.message || 'Failed to get MFA policy');
    }
  }
  
  /**
   * Update user's MFA policy
   * @param {Object} policy - Policy settings to update
   * @returns {Promise<Object>} Update result
   */
  async updateMFAPolicy(policy) {
    try {
      const response = await axios.put(
        `${API_BASE}/api/auth/mfa/policy/`,
        policy,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Update MFA policy error:', error);
      throw new Error(error.response?.data?.message || 'Failed to update MFA policy');
    }
  }
  
  /**
   * Get authentication attempts history
   * @param {number} limit - Maximum number of attempts to retrieve
   * @returns {Promise<Object>} Auth attempts
   */
  async getAuthAttemptsHistory(limit = 20) {
    try {
      const response = await axios.get(
        `${API_BASE}/api/auth/mfa/auth-attempts/?limit=${limit}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Get auth attempts error:', error);
      throw new Error(error.response?.data?.message || 'Failed to get auth attempts');
    }
  }
  
  /**
   * Capture face image from webcam
   * @returns {Promise<Blob>} Face image blob
   */
  async captureFaceImage() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          width: 640,
          height: 480,
          facingMode: 'user'
        } 
      });
      
      // Create video element
      const video = document.createElement('video');
      video.srcObject = stream;
      video.setAttribute('playsinline', true);
      await video.play();
      
      // Wait for video to be ready
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Create canvas and capture frame
      const canvas = document.createElement('canvas');
      canvas.width = 160;
      canvas.height = 160;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, 160, 160);
      
      // Stop video stream
      stream.getTracks().forEach(track => track.stop());
      
      // Convert canvas to blob
      return new Promise(resolve => {
        canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.95);
      });
    } catch (error) {
      console.error('Face capture error:', error);
      throw new Error('Failed to access webcam. Please grant camera permissions.');
    }
  }
  
  /**
   * Record voice sample from microphone
   * @param {number} durationSeconds - Recording duration
   * @returns {Promise<Blob>} Audio blob
   */
  async recordVoiceSample(durationSeconds = 3) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const audioChunks = [];
      
      return new Promise((resolve, reject) => {
        mediaRecorder.ondataavailable = event => {
          audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
          stream.getTracks().forEach(track => track.stop());
          resolve(audioBlob);
        };
        
        mediaRecorder.onerror = error => {
          stream.getTracks().forEach(track => track.stop());
          reject(error);
        };
        
        mediaRecorder.start();
        
        setTimeout(() => {
          mediaRecorder.stop();
        }, durationSeconds * 1000);
      });
    } catch (error) {
      console.error('Voice recording error:', error);
      throw new Error('Failed to access microphone. Please grant microphone permissions.');
    }
  }
  
  /**
   * Convert image to base64
   * @param {Blob|File} imageBlob - Image blob/file
   * @returns {Promise<string>} Base64 string
   */
  imageToBase64(imageBlob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        // Remove data:image/jpeg;base64, prefix
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(imageBlob);
    });
  }
  
  /**
   * Convert audio to base64
   * @param {Blob} audioBlob - Audio blob
   * @returns {Promise<string>} Base64 string
   */
  audioToBase64(audioBlob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        // Remove data:audio/wav;base64, prefix
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(audioBlob);
    });
  }
  
  /**
   * Get device fingerprint
   * @returns {Promise<string>} Device fingerprint
   */
  async getDeviceFingerprint() {
    // Simple fingerprint based on browser characteristics
    const components = [
      navigator.userAgent,
      navigator.language,
      screen.width,
      screen.height,
      screen.colorDepth,
      new Date().getTimezoneOffset(),
      navigator.hardwareConcurrency,
      navigator.deviceMemory
    ];
    
    const fingerprint = components.join('|');
    
    // Hash the fingerprint
    const encoder = new TextEncoder();
    const data = encoder.encode(fingerprint);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    
    return hashHex;
  }
  
  /**
   * Collect behavioral biometrics
   * @returns {Object} Behavioral features
   */
  collectBehavioralFeatures() {
    // Collect various behavioral metrics
    const features = [
      performance.now() % 1000, // Timing variations
      Math.random() * 100, // Mouse speed (simulated)
      Math.random() * 50, // Typing speed (simulated)
      Math.random() * 100, // Click patterns (simulated)
      Math.random() * 30, // Navigation speed (simulated)
      Math.random() * 60, // Idle time (simulated)
      Math.random() * 10, // Scroll speed (simulated)
      Math.random() * 5, // Error rate (simulated)
      Math.random() * 100, // Session activity (simulated)
      Math.random() * 50, // Keystroke dynamics (simulated)
      Math.random() * 30, // Touch gestures (simulated)
      Math.random() * 20, // Device orientation (simulated)
      Math.random() * 15, // Input pressure (simulated)
      Math.random() * 10, // Screen transitions (simulated)
      Math.random() * 5  // Custom metrics (simulated)
    ];
    
    return features;
  }
  
  /**
   * Get MFA requirements for current user/request
   * @param {string} operationType - Type of operation (login, export_vault, etc.)
   * @returns {Promise<Object>} MFA requirements
   */
  async getMFARequirements(operationType = 'login') {
    try {
      const deviceFingerprint = await this.getDeviceFingerprint();
      
      const response = await axios.get(
        `${API_BASE}/api/auth/mfa/requirements/`,
        {
          params: { operation_type: operationType },
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-Device-Fingerprint': deviceFingerprint
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Error getting MFA requirements:', error);
      throw new Error(error.response?.data?.message || 'Failed to get MFA requirements');
    }
  }
  
  /**
   * Verify multiple authentication factors (integrated MFA + 2FA)
   * @param {Object} factors - Dictionary of factor_type -> credential
   * @returns {Promise<Object>} Verification result
   */
  async verifyIntegratedMFA(factors) {
    try {
      const deviceFingerprint = await this.getDeviceFingerprint();
      
      const response = await axios.post(
        `${API_BASE}/api/auth/mfa/verify/`,
        { factors },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
            'X-Device-Fingerprint': deviceFingerprint
          }
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('MFA verification error:', error);
      return {
        success: false,
        message: error.response?.data?.message || 'MFA verification failed',
        verification_results: error.response?.data?.verification_results || {},
        requirements: error.response?.data?.requirements || {}
      };
    }
  }
  
  /**
   * Authenticate with multiple factors
   * Convenience method that combines requirements check and verification
   * @param {Object} factors - Factors to verify
   * @param {string} operationType - Type of operation
   * @returns {Promise<Object>} Authentication result
   */
  async authenticateWithFactors(factors, operationType = 'login') {
    try {
      // First, get requirements
      const requirements = await this.getMFARequirements(operationType);
      
      // If no factors required, return success
      if (requirements.requirements?.required_count === 0) {
        return {
          success: true,
          message: 'Trusted device - MFA not required',
          requirements
        };
      }
      
      // Verify provided factors
      const result = await this.verifyIntegratedMFA(factors);
      
      return {
        ...result,
        requirements: requirements.requirements
      };
    } catch (error) {
      console.error('Authentication error:', error);
      throw error;
    }
  }
}

export default new MFAService();


/**
 * BiometricLivenessService - React Native
 * 
 * Mobile service for deepfake-resistant biometric liveness verification.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL, WS_BASE_URL } from '../config/api';

const API_BASE = `${API_BASE_URL}/api/liveness`;

class BiometricLivenessService {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.onFrameResult = null;
    this.onSessionComplete = null;
  }

  /**
   * Get auth headers for API requests
   */
  async getHeaders() {
    const token = await AsyncStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };
  }

  /**
   * Start a new liveness verification session
   */
  async startSession(context = 'login', deviceFingerprint = '') {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_BASE}/session/start/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ context, device_fingerprint: deviceFingerprint }),
    });

    if (!response.ok) {
      throw new Error('Failed to start liveness session');
    }

    const data = await response.json();
    this.sessionId = data.session_id;
    return data;
  }

  /**
   * Connect WebSocket for real-time frame processing
   */
  async connectWebSocket(sessionId, onFrameResult, onComplete, onError) {
    const token = await AsyncStorage.getItem('token');
    const wsUrl = `${WS_BASE_URL}/ws/liveness/${sessionId}/?token=${token}`;
    
    this.ws = new WebSocket(wsUrl);
    this.onFrameResult = onFrameResult;
    this.onSessionComplete = onComplete;

    this.ws.onopen = () => {
      console.log('[BiometricLiveness] WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'frame_result' && this.onFrameResult) {
        this.onFrameResult(data);
      } else if (data.type === 'session_complete' && this.onSessionComplete) {
        this.onSessionComplete(data);
      } else if (data.type === 'error' && onError) {
        onError(data.message);
      }
    };

    this.ws.onerror = (error) => {
      console.error('[BiometricLiveness] WebSocket error:', error);
      if (onError) onError('WebSocket connection error');
    };

    this.ws.onclose = () => {
      console.log('[BiometricLiveness] WebSocket closed');
    };
  }

  /**
   * Send a video frame via WebSocket
   */
  sendFrame(frameBase64, width, height, timestampMs) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'frame',
        frame: frameBase64,
        width,
        height,
        timestamp_ms: timestampMs,
      }));
    }
  }

  /**
   * Complete session via WebSocket
   */
  completeSession() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'complete' }));
    }
  }

  /**
   * Get user's liveness profile
   */
  async getProfile() {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_BASE}/profile/`, { headers });
    return response.json();
  }

  /**
   * Get/update liveness settings
   */
  async getSettings() {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_BASE}/settings/`, { headers });
    return response.json();
  }

  async updateSettings(settings) {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(settings),
    });
    return response.json();
  }

  /**
   * Get verification history
   */
  async getHistory(limit = 10) {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_BASE}/history/?limit=${limit}`, { headers });
    return response.json();
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.sessionId = null;
  }
}

// Timing utilities
export const TimingUtils = {
  getHighResTime: () => Date.now(),
  measureReactionTime: (startTime) => Date.now() - startTime,
};

export default new BiometricLivenessService();

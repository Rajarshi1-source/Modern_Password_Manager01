/**
 * Neuro-Feedback Service for React Native Mobile
 * 
 * Handles EEG device connections via BLE, training sessions,
 * and API communication for neuro-feedback password training.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
// Note: BleManager from react-native-ble-plx would be imported in production
// import { BleManager } from 'react-native-ble-plx';

const API_BASE = '/api/neuro-feedback';

class NeuroFeedbackService {
  constructor() {
    this.baseUrl = null;
    this.token = null;
    this.bleManager = null; // Would be BleManager instance
    this.connectedDevice = null;
    this.wsConnection = null;
    this.listeners = new Map();
  }

  /**
   * Initialize the service with API base URL and authentication.
   */
  async init(baseUrl) {
    this.baseUrl = baseUrl;
    this.token = await AsyncStorage.getItem('accessToken');
    
    // Initialize BLE manager
    // this.bleManager = new BleManager();
    
    return this;
  }

  /**
   * Make authenticated API request.
   */
  async _request(method, endpoint, data = null) {
    const options = {
      method,
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
    };

    if (data && method !== 'GET') {
      options.body = JSON.stringify(data);
    }

    try {
      const response = await fetch(`${this.baseUrl}${API_BASE}${endpoint}`, options);
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Request failed');
      }

      return result;
    } catch (error) {
      console.error(`NeuroFeedback API Error [${method} ${endpoint}]:`, error);
      throw error;
    }
  }

  // =========================================================================
  // Bluetooth Device Discovery (BLE)
  // =========================================================================

  /**
   * Scan for nearby EEG devices via Bluetooth Low Energy.
   * @param {number} timeoutMs - Scan duration in milliseconds
   * @returns {Promise<Array>} List of discovered devices
   */
  async scanForDevices(timeoutMs = 10000) {
    // In production, this would use react-native-ble-plx
    return new Promise((resolve) => {
      const devices = [];
      
      console.log('Starting BLE scan for EEG devices...');
      
      // Simulated scan results
      setTimeout(() => {
        devices.push({
          id: 'BT-MUSE2-001',
          name: 'Muse 2 Headband',
          type: 'muse_2',
          rssi: -65,
        });
        resolve(devices);
      }, timeoutMs);
    });
  }

  /**
   * Connect to an EEG device via Bluetooth.
   */
  async connectToDevice(deviceId) {
    // In production: await this.bleManager.connectToDevice(deviceId);
    console.log(`Connecting to device: ${deviceId}`);
    
    this.connectedDevice = { id: deviceId, status: 'connected' };
    return this.connectedDevice;
  }

  /**
   * Disconnect from current device.
   */
  async disconnectDevice() {
    if (this.connectedDevice) {
      // In production: await this.bleManager.cancelDeviceConnection(this.connectedDevice.id);
      this.connectedDevice = null;
    }
  }

  // =========================================================================
  // Device Management API
  // =========================================================================

  async getDevices() {
    return this._request('GET', '/devices/');
  }

  async registerDevice(deviceId, deviceType, deviceName) {
    return this._request('POST', '/devices/', {
      device_id: deviceId,
      device_type: deviceType,
      device_name: deviceName,
    });
  }

  async removeDevice(deviceId) {
    return this._request('DELETE', `/devices/${deviceId}/`);
  }

  async calibrateDevice(deviceId) {
    return this._request('POST', `/devices/${deviceId}/calibrate/`);
  }

  // =========================================================================
  // Training Programs
  // =========================================================================

  async getPrograms() {
    return this._request('GET', '/programs/');
  }

  async createProgram(vaultItemId, password) {
    return this._request('POST', '/programs/', {
      vault_item_id: vaultItemId,
      password,
    });
  }

  async getProgram(programId) {
    return this._request('GET', `/programs/${programId}/`);
  }

  async startSession(programId) {
    return this._request('POST', `/programs/${programId}/start/`);
  }

  async getMemoryProgress(programId) {
    return this._request('GET', `/programs/${programId}/progress/`);
  }

  async abandonProgram(programId) {
    return this._request('DELETE', `/programs/${programId}/`);
  }

  // =========================================================================
  // Schedule & Due Reviews
  // =========================================================================

  async getSchedule() {
    return this._request('GET', '/schedule/');
  }

  async getDueReviews() {
    return this._request('GET', '/due/');
  }

  // =========================================================================
  // Settings
  // =========================================================================

  async getSettings() {
    return this._request('GET', '/settings/');
  }

  async updateSettings(settings) {
    return this._request('PUT', '/settings/', settings);
  }

  // =========================================================================
  // Statistics
  // =========================================================================

  async getStatistics() {
    return this._request('GET', '/stats/');
  }

  // =========================================================================
  // WebSocket for Real-time Training
  // =========================================================================

  /**
   * Connect to training WebSocket for real-time neurofeedback.
   */
  connectWebSocket(sessionId) {
    const wsProtocol = this.baseUrl.startsWith('https') ? 'wss' : 'ws';
    const wsHost = this.baseUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}://${wsHost}/ws/neuro-training/${sessionId}/?token=${this.token}`;

    this.wsConnection = new WebSocket(wsUrl);

    this.wsConnection.onopen = () => {
      console.log('Training WebSocket connected');
      this._emit('connected', { sessionId });
    };

    this.wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleMessage(data);
      } catch (e) {
        console.error('WebSocket parse error:', e);
      }
    };

    this.wsConnection.onclose = (event) => {
      console.log('Training WebSocket closed:', event.code);
      this._emit('disconnected', { code: event.code });
    };

    this.wsConnection.onerror = (error) => {
      console.error('Training WebSocket error:', error);
      this._emit('error', { error });
    };

    return this.wsConnection;
  }

  /**
   * Disconnect WebSocket.
   */
  disconnectWebSocket() {
    if (this.wsConnection) {
      this.wsConnection.close();
      this.wsConnection = null;
    }
  }

  /**
   * Send message via WebSocket.
   */
  send(type, data = {}) {
    if (this.wsConnection?.readyState === WebSocket.OPEN) {
      this.wsConnection.send(JSON.stringify({ type, ...data }));
    }
  }

  // Training commands
  sendEEGData(channels, sampleRate) {
    this.send('eeg_data', { channels, sample_rate: sampleRate, timestamp: Date.now() / 1000 });
  }

  startTraining(programId, password) {
    this.send('start_training', { program_id: programId, password });
  }

  requestNextChunk() {
    this.send('request_next_chunk');
  }

  submitRecall(chunkIndex, input, responseTimeMs) {
    this.send('recall_attempt', { chunk_index: chunkIndex, input, response_time_ms: responseTimeMs });
  }

  endSession() {
    this.send('end_session');
  }

  // =========================================================================
  // Event Handling
  // =========================================================================

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      this.listeners.set(event, callbacks.filter(cb => cb !== callback));
    }
  }

  _emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(cb => cb(data));
    }
  }

  _handleMessage(data) {
    const { type, ...payload } = data;
    
    switch (type) {
      case 'connection_established':
        this._emit('session_ready', payload);
        break;
      case 'neurofeedback':
        this._emit('feedback', payload);
        break;
      case 'training_started':
        this._emit('training_started', payload);
        break;
      case 'chunk_ready':
        this._emit('chunk_ready', payload);
        break;
      case 'recall_result':
        this._emit('recall_result', payload);
        break;
      case 'session_ended':
        this._emit('session_ended', payload);
        break;
      case 'error':
        this._emit('error', payload);
        break;
      default:
        console.log('Unknown message type:', type);
    }
  }

  // =========================================================================
  // Local Storage
  // =========================================================================

  async cachePrograms(programs) {
    await AsyncStorage.setItem('neuro_programs', JSON.stringify(programs));
  }

  async getCachedPrograms() {
    const data = await AsyncStorage.getItem('neuro_programs');
    return data ? JSON.parse(data) : [];
  }

  async clearCache() {
    await AsyncStorage.removeItem('neuro_programs');
  }
}

// Singleton instance
const neuroFeedbackService = new NeuroFeedbackService();
export default neuroFeedbackService;

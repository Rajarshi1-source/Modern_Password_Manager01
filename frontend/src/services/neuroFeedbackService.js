/**
 * Neuro-Feedback Service
 * 
 * Frontend service for neuro-feedback password training API.
 * Handles device management, training sessions, and WebSocket connections.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

const API_BASE = '/api/neuro-feedback';

/**
 * NeuroFeedbackService class for managing brain-training features.
 */
class NeuroFeedbackService {
  constructor() {
    this.socket = null;
    this.callbacks = {};
  }

  /**
   * Get auth headers with JWT token.
   */
  _getHeaders() {
    const token = localStorage.getItem('access_token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  /**
   * Make API request with error handling.
   */
  async _request(method, endpoint, data = null) {
    const options = {
      method,
      headers: this._getHeaders(),
    };

    if (data && method !== 'GET') {
      options.body = JSON.stringify(data);
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, options);
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Request failed');
      }

      return result;
    } catch (error) {
      console.error(`API Error [${method} ${endpoint}]:`, error);
      throw error;
    }
  }

  // =========================================================================
  // Device Management
  // =========================================================================

  /**
   * Get all registered EEG devices.
   */
  async getDevices() {
    return this._request('GET', '/devices/');
  }

  /**
   * Register a new EEG device.
   */
  async registerDevice(deviceId, deviceType, deviceName, firmwareVersion = '') {
    return this._request('POST', '/devices/', {
      device_id: deviceId,
      device_type: deviceType,
      device_name: deviceName,
      firmware_version: firmwareVersion,
    });
  }

  /**
   * Get device details.
   */
  async getDevice(deviceId) {
    return this._request('GET', `/devices/${deviceId}/`);
  }

  /**
   * Remove a device.
   */
  async removeDevice(deviceId) {
    return this._request('DELETE', `/devices/${deviceId}/`);
  }

  /**
   * Start device calibration.
   */
  async calibrateDevice(deviceId) {
    return this._request('POST', `/devices/${deviceId}/calibrate/`);
  }

  // =========================================================================
  // Training Programs
  // =========================================================================

  /**
   * Get all training programs.
   */
  async getPrograms() {
    return this._request('GET', '/programs/');
  }

  /**
   * Create a new training program.
   */
  async createProgram(vaultItemId, password) {
    return this._request('POST', '/programs/', {
      vault_item_id: vaultItemId,
      password: password,
    });
  }

  /**
   * Get program details.
   */
  async getProgram(programId) {
    return this._request('GET', `/programs/${programId}/`);
  }

  /**
   * Start a training session.
   */
  async startSession(programId) {
    return this._request('POST', `/programs/${programId}/start/`);
  }

  /**
   * Get memory progress for a program.
   */
  async getMemoryProgress(programId) {
    return this._request('GET', `/programs/${programId}/progress/`);
  }

  /**
   * Abandon a program.
   */
  async abandonProgram(programId) {
    return this._request('DELETE', `/programs/${programId}/`);
  }

  // =========================================================================
  // Schedule
  // =========================================================================

  /**
   * Get upcoming review schedule.
   */
  async getSchedule() {
    return this._request('GET', '/schedule/');
  }

  /**
   * Get programs due for review.
   */
  async getDueReviews() {
    return this._request('GET', '/due/');
  }

  // =========================================================================
  // Settings
  // =========================================================================

  /**
   * Get neuro-feedback settings.
   */
  async getSettings() {
    return this._request('GET', '/settings/');
  }

  /**
   * Update neuro-feedback settings.
   */
  async updateSettings(settings) {
    return this._request('PUT', '/settings/', settings);
  }

  // =========================================================================
  // Statistics
  // =========================================================================

  /**
   * Get training statistics.
   */
  async getStatistics() {
    return this._request('GET', '/stats/');
  }

  // =========================================================================
  // WebSocket Connection
  // =========================================================================

  /**
   * Connect to neuro-training WebSocket.
   * @param {string} sessionId - Training session ID
   */
  connectWebSocket(sessionId) {
    const token = localStorage.getItem('access_token');
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/neuro-training/${sessionId}/?token=${token}`;

    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      console.log('Neuro-feedback WebSocket connected');
      this._emit('connected', { sessionId });
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleSocketMessage(data);
      } catch (error) {
        console.error('WebSocket message parse error:', error);
      }
    };

    this.socket.onclose = (event) => {
      console.log('Neuro-feedback WebSocket closed:', event.code);
      this._emit('disconnected', { code: event.code });
    };

    this.socket.onerror = (error) => {
      console.error('Neuro-feedback WebSocket error:', error);
      this._emit('error', { error });
    };

    return this.socket;
  }

  /**
   * Disconnect WebSocket.
   */
  disconnectWebSocket() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * Send message via WebSocket.
   */
  send(type, data = {}) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, ...data }));
    }
  }

  /**
   * Send EEG data for analysis.
   */
  sendEEGData(channels, sampleRate) {
    this.send('eeg_data', {
      channels,
      sample_rate: sampleRate,
      timestamp: Date.now() / 1000,
    });
  }

  /**
   * Start training via WebSocket.
   */
  startTraining(programId, password) {
    this.send('start_training', { program_id: programId, password });
  }

  /**
   * Request next chunk to practice.
   */
  requestNextChunk() {
    this.send('request_next_chunk');
  }

  /**
   * Submit recall attempt.
   */
  submitRecall(chunkIndex, input, responseTimeMs) {
    this.send('recall_attempt', {
      chunk_index: chunkIndex,
      input,
      response_time_ms: responseTimeMs,
    });
  }

  /**
   * End training session.
   */
  endSession() {
    this.send('end_session');
  }

  /**
   * Register callback for WebSocket events.
   */
  on(event, callback) {
    if (!this.callbacks[event]) {
      this.callbacks[event] = [];
    }
    this.callbacks[event].push(callback);
  }

  /**
   * Remove callback.
   */
  off(event, callback) {
    if (this.callbacks[event]) {
      this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
    }
  }

  _emit(event, data) {
    if (this.callbacks[event]) {
      this.callbacks[event].forEach(cb => cb(data));
    }
  }

  _handleSocketMessage(data) {
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
      case 'calibration_started':
        this._emit('calibration', payload);
        break;
      case 'error':
        this._emit('error', payload);
        break;
      default:
        console.log('Unknown WebSocket message type:', type);
    }
  }
}

// Singleton instance
const neuroFeedbackService = new NeuroFeedbackService();

export default neuroFeedbackService;
export { NeuroFeedbackService };

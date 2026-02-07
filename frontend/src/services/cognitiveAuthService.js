/**
 * Cognitive Auth Service
 * ======================
 * 
 * Frontend service for cognitive password verification testing.
 * Handles API communication, WebSocket connections, and timing measurements.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

class CognitiveAuthService {
  constructor() {
    this.baseUrl = '/api/cognitive';
    this.websocket = null;
    this.sessionId = null;
    this.timingOffset = 0; // Server-client time offset
    
    // Performance timing API for high-precision measurements
    this.performanceNow = window.performance?.now?.bind(window.performance) || Date.now;
  }

  /**
   * Start a new verification session.
   * @param {string} password - Password to verify
   * @param {Object} options - Session options
   * @returns {Promise<Object>} Session data with first challenge
   */
  async startSession(password, options = {}) {
    const response = await this._fetch('/challenge/start/', {
      method: 'POST',
      body: JSON.stringify({
        password,
        vault_item_id: options.vaultItemId,
        context: options.context || 'login',
        difficulty: options.difficulty || 'medium',
      }),
    });

    this.sessionId = response.session_id;
    return response;
  }

  /**
   * Submit a challenge response.
   * @param {string} challengeId - Challenge ID
   * @param {string} response - User's response
   * @param {Object} timing - Timing data
   * @returns {Promise<Object>} Response result
   */
  async submitResponse(challengeId, userResponse, timing) {
    const serverTimestamp = this._getServerTimestamp();

    return await this._fetch('/challenge/respond/', {
      method: 'POST',
      body: JSON.stringify({
        session_id: this.sessionId,
        challenge_id: challengeId,
        response: userResponse,
        client_timestamp: serverTimestamp,
        reaction_time_ms: timing.reactionTime,
        first_keystroke_ms: timing.firstKeystroke,
        total_input_duration_ms: timing.totalInputDuration,
        hesitation_count: timing.hesitationCount || 0,
        correction_count: timing.correctionCount || 0,
      }),
    });
  }

  /**
   * Get user's cognitive profile.
   * @returns {Promise<Object>} Profile data
   */
  async getProfile() {
    return await this._fetch('/profile/');
  }

  /**
   * Start a calibration session.
   * @param {string} password - Password to calibrate with
   * @returns {Promise<Object>} Calibration session data
   */
  async startCalibration(password) {
    const response = await this._fetch('/calibrate/', {
      method: 'POST',
      body: JSON.stringify({ password }),
    });

    this.sessionId = response.session_id;
    return response;
  }

  /**
   * Get verification settings.
   * @returns {Promise<Object>} Settings object
   */
  async getSettings() {
    return await this._fetch('/settings/');
  }

  /**
   * Update verification settings.
   * @param {Object} settings - Settings to update
   * @returns {Promise<Object>} Updated settings
   */
  async updateSettings(settings) {
    return await this._fetch('/settings/update/', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  /**
   * Get verification history.
   * @param {number} limit - Max number of sessions to return
   * @returns {Promise<Object>} History object
   */
  async getHistory(limit = 10) {
    return await this._fetch(`/history/?limit=${limit}`);
  }

  /**
   * Connect to WebSocket for real-time challenges.
   * @param {string} sessionId - Session ID
   * @param {Object} handlers - Event handlers
   * @returns {Promise<WebSocket>}
   */
  connectWebSocket(sessionId, handlers = {}) {
    return new Promise((resolve, reject) => {
      const wsUrl = `${this._getWsProtocol()}//${window.location.host}/ws/cognitive/${sessionId}/`;
      
      this.websocket = new WebSocket(wsUrl);

      this.websocket.onopen = () => {
        // Sync time with server
        this._syncTime();
        if (handlers.onOpen) handlers.onOpen();
        resolve(this.websocket);
      };

      this.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'connection_established':
            this.timingOffset = data.server_time - this.performanceNow();
            if (handlers.onConnected) handlers.onConnected(data);
            break;
          case 'challenge':
            if (handlers.onChallenge) handlers.onChallenge(data);
            break;
          case 'response_result':
            if (handlers.onResult) handlers.onResult(data);
            break;
          case 'session_complete':
            if (handlers.onComplete) handlers.onComplete(data);
            break;
          case 'pong':
            this.timingOffset = data.server_time - data.client_time;
            break;
          case 'error':
            if (handlers.onError) handlers.onError(data);
            break;
          default:
            console.log('Unknown message type:', data.type);
        }
      };

      this.websocket.onerror = (error) => {
        if (handlers.onError) handlers.onError(error);
        reject(error);
      };

      this.websocket.onclose = () => {
        if (handlers.onClose) handlers.onClose();
      };
    });
  }

  /**
   * Send message via WebSocket.
   * @param {Object} message - Message to send
   */
  sendWsMessage(message) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(message));
    }
  }

  /**
   * Request next challenge via WebSocket.
   * @param {number} sequenceNumber - Sequence number of challenge to request
   */
  requestChallenge(sequenceNumber) {
    this.sendWsMessage({
      type: 'request_challenge',
      sequence_number: sequenceNumber,
    });
  }

  /**
   * Submit response via WebSocket.
   * @param {string} challengeId - Challenge ID
   * @param {string} response - User response
   * @param {Object} timing - Timing data
   */
  submitWsResponse(challengeId, userResponse, timing) {
    this.sendWsMessage({
      type: 'submit_response',
      challenge_id: challengeId,
      response: userResponse,
      client_timestamp: this._getServerTimestamp(),
      reaction_time_ms: timing.reactionTime,
      first_keystroke_ms: timing.firstKeystroke,
      total_input_duration_ms: timing.totalInputDuration,
      hesitation_count: timing.hesitationCount || 0,
      correction_count: timing.correctionCount || 0,
    });
  }

  /**
   * Close WebSocket connection.
   */
  disconnect() {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    this.sessionId = null;
  }

  // ============ Timing Utilities ============

  /**
   * Start a timer for reaction time measurement.
   * @returns {Object} Timer object with methods
   */
  createTimer() {
    let startTime = null;
    let firstKeystrokeTime = null;
    let keystrokes = [];
    let corrections = 0;
    let hesitations = 0;
    let lastKeystrokeTime = null;

    return {
      start: () => {
        startTime = this.performanceNow();
        keystrokes = [];
        corrections = 0;
        hesitations = 0;
        lastKeystrokeTime = null;
      },

      recordKeystroke: (isBackspace = false) => {
        const now = this.performanceNow();
        
        if (firstKeystrokeTime === null) {
          firstKeystrokeTime = now;
        }

        if (isBackspace) {
          corrections++;
        }

        // Detect hesitation (pause > 500ms)
        if (lastKeystrokeTime && (now - lastKeystrokeTime) > 500) {
          hesitations++;
        }

        keystrokes.push(now);
        lastKeystrokeTime = now;
      },

      stop: () => {
        const endTime = this.performanceNow();
        
        return {
          reactionTime: Math.round(firstKeystrokeTime - startTime),
          firstKeystroke: Math.round(firstKeystrokeTime - startTime),
          totalInputDuration: Math.round(endTime - startTime),
          keystrokeCount: keystrokes.length,
          hesitationCount: hesitations,
          correctionCount: corrections,
        };
      },

      getElapsed: () => {
        return startTime ? this.performanceNow() - startTime : 0;
      },
    };
  }

  // ============ Private Methods ============

  async _fetch(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const token = localStorage.getItem('token');

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Token ${token}` : '',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }));
      throw new Error(error.error || error.message || 'Request failed');
    }

    return response.json();
  }

  _getWsProtocol() {
    return window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  }

  _getServerTimestamp() {
    return Math.round(this.performanceNow() + this.timingOffset);
  }

  _syncTime() {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.sendWsMessage({
        type: 'ping',
        client_time: this.performanceNow(),
      });
    }
  }
}

// Export singleton instance
const cognitiveAuthService = new CognitiveAuthService();
export default cognitiveAuthService;

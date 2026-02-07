/**
 * Cognitive Auth Service (Mobile)
 * =================================
 * 
 * React Native service for cognitive password verification.
 * 
 * @author Password Manager Team
 * @created 2026-02-07
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = __DEV__ 
  ? 'http://localhost:8000/api/cognitive'
  : 'https://api.yourapp.com/api/cognitive';

class CognitiveAuthService {
  constructor() {
    this.sessionId = null;
  }

  /**
   * Get auth headers with token
   */
  async _getHeaders() {
    const token = await AsyncStorage.getItem('authToken');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Token ${token}` : '',
    };
  }

  /**
   * Make API request
   */
  async _fetch(endpoint, options = {}) {
    const headers = await this._getHeaders();
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }));
      throw new Error(error.error || 'Request failed');
    }

    return response.json();
  }

  /**
   * Start verification session
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
   * Submit challenge response
   */
  async submitResponse(challengeId, userResponse, timing) {
    return await this._fetch('/challenge/respond/', {
      method: 'POST',
      body: JSON.stringify({
        session_id: this.sessionId,
        challenge_id: challengeId,
        response: userResponse,
        client_timestamp: Date.now(),
        reaction_time_ms: timing.reactionTime,
        first_keystroke_ms: timing.firstKeystroke,
        total_input_duration_ms: timing.totalInputDuration,
        hesitation_count: timing.hesitationCount || 0,
        correction_count: timing.correctionCount || 0,
      }),
    });
  }

  /**
   * Get user profile
   */
  async getProfile() {
    return await this._fetch('/profile/');
  }

  /**
   * Start calibration
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
   * Get settings
   */
  async getSettings() {
    return await this._fetch('/settings/');
  }

  /**
   * Update settings
   */
  async updateSettings(settings) {
    return await this._fetch('/settings/update/', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  /**
   * Get history
   */
  async getHistory(limit = 10) {
    return await this._fetch(`/history/?limit=${limit}`);
  }

  /**
   * Create a timer for reaction time measurement
   */
  createTimer() {
    let startTime = null;
    let firstKeystrokeTime = null;
    let corrections = 0;
    let hesitations = 0;
    let lastKeystrokeTime = null;

    return {
      start: () => {
        startTime = Date.now();
        corrections = 0;
        hesitations = 0;
        lastKeystrokeTime = null;
      },

      recordKeystroke: (isBackspace = false) => {
        const now = Date.now();
        
        if (firstKeystrokeTime === null) {
          firstKeystrokeTime = now;
        }

        if (isBackspace) corrections++;
        
        if (lastKeystrokeTime && (now - lastKeystrokeTime) > 500) {
          hesitations++;
        }

        lastKeystrokeTime = now;
      },

      stop: () => {
        const endTime = Date.now();
        
        return {
          reactionTime: firstKeystrokeTime - startTime,
          firstKeystroke: firstKeystrokeTime - startTime,
          totalInputDuration: endTime - startTime,
          hesitationCount: hesitations,
          correctionCount: corrections,
        };
      },
    };
  }

  /**
   * Reset session
   */
  reset() {
    this.sessionId = null;
  }
}

export default new CognitiveAuthService();

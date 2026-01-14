/**
 * Adversarial AI Password Defense Service
 * 
 * Frontend service for communicating with the adversarial AI backend.
 * Provides real-time password analysis, battle simulation, and recommendations.
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');
const API_BASE = `${API_URL}/api/adversarial`;
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

class AdversarialService {
  constructor() {
    this.wsConnection = null;
    this.wsCallbacks = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  // ==========================================================================
  // REST API Methods
  // ==========================================================================

  /**
   * Analyze password using adversarial AI
   * @param {Object} features - Password features
   * @param {boolean} runFullBattle - Whether to run full battle simulation
   * @returns {Promise} Analysis results
   */
  async analyzePassword(features, runFullBattle = false) {
    try {
      const response = await axios.post(`${API_BASE}/analyze/`, {
        features,
        run_full_battle: runFullBattle,
        save_result: true
      });
      return response.data;
    } catch (error) {
      console.error('Error analyzing password:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Get quick assessment (for real-time feedback)
   * @param {Object} features - Password features
   * @returns {Promise} Quick assessment
   */
  async getQuickAssessment(features) {
    try {
      const response = await axios.post(`${API_BASE}/analyze/`, {
        features,
        run_full_battle: false
      });
      return response.data;
    } catch (error) {
      console.error('Error getting quick assessment:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Get personalized recommendations
   * @param {Object} options - Query options (limit, status)
   * @returns {Promise} Recommendations list
   */
  async getRecommendations(options = {}) {
    try {
      const params = new URLSearchParams(options);
      const response = await axios.get(`${API_BASE}/recommendations/?${params}`);
      return response.data;
    } catch (error) {
      console.error('Error getting recommendations:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Update recommendation status
   * @param {number} recommendationId - Recommendation ID
   * @param {string} status - New status (viewed/applied/dismissed)
   * @returns {Promise} Update result
   */
  async updateRecommendationStatus(recommendationId, status) {
    try {
      const response = await axios.post(
        `${API_BASE}/recommendations/${recommendationId}/status/`,
        { status }
      );
      return response.data;
    } catch (error) {
      console.error('Error updating recommendation:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Get battle history
   * @param {Object} options - Query options (limit, outcome)
   * @returns {Promise} Battle history
   */
  async getBattleHistory(options = {}) {
    try {
      const params = new URLSearchParams(options);
      const response = await axios.get(`${API_BASE}/history/?${params}`);
      return response.data;
    } catch (error) {
      console.error('Error getting battle history:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Get trending attacks
   * @param {number} limit - Number of trends to fetch
   * @returns {Promise} Trending attacks
   */
  async getTrendingAttacks(limit = 5) {
    try {
      const response = await axios.get(`${API_BASE}/trending-attacks/?limit=${limit}`);
      return response.data;
    } catch (error) {
      console.error('Error getting trending attacks:', error);
      throw this._handleError(error);
    }
  }

  /**
   * Get user's defense profile
   * @returns {Promise} Defense profile
   */
  async getDefenseProfile() {
    try {
      const response = await axios.get(`${API_BASE}/profile/`);
      return response.data;
    } catch (error) {
      console.error('Error getting defense profile:', error);
      throw this._handleError(error);
    }
  }

  // ==========================================================================
  // WebSocket Methods
  // ==========================================================================

  /**
   * Connect to adversarial WebSocket for real-time updates
   * @param {string} userId - User ID
   * @param {Object} callbacks - Event callbacks
   */
  connectWebSocket(userId, callbacks = {}) {
    if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.wsCallbacks = callbacks;
    const token = localStorage.getItem('access_token');
    const wsUrl = `${WS_URL}/ws/adversarial/${userId}/?token=${token}`;

    try {
      this.wsConnection = new WebSocket(wsUrl);

      this.wsConnection.onopen = () => {
        console.log('Adversarial WebSocket connected');
        this.reconnectAttempts = 0;
        if (callbacks.onConnect) callbacks.onConnect();
      };

      this.wsConnection.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleWebSocketMessage(data);
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      this.wsConnection.onclose = (event) => {
        console.log('Adversarial WebSocket disconnected:', event.code);
        if (callbacks.onDisconnect) callbacks.onDisconnect(event);
        this._attemptReconnect(userId, callbacks);
      };

      this.wsConnection.onerror = (error) => {
        console.error('Adversarial WebSocket error:', error);
        if (callbacks.onError) callbacks.onError(error);
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket() {
    if (this.wsConnection) {
      this.wsConnection.close();
      this.wsConnection = null;
    }
  }

  /**
   * Request real-time password analysis via WebSocket
   * @param {Object} features - Password features
   */
  requestQuickAnalysis(features) {
    if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
      this.wsConnection.send(JSON.stringify({
        type: 'analyze_password',
        features
      }));
    }
  }

  /**
   * Start full battle simulation via WebSocket
   * @param {Object} features - Password features
   */
  startBattle(features) {
    if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
      this.wsConnection.send(JSON.stringify({
        type: 'start_battle',
        features
      }));
    }
  }

  /**
   * Request recommendations via WebSocket
   */
  requestRecommendations() {
    if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
      this.wsConnection.send(JSON.stringify({
        type: 'get_recommendations'
      }));
    }
  }

  _handleWebSocketMessage(data) {
    const { type } = data;

    switch (type) {
      case 'connection_established':
        console.log('WebSocket connection confirmed');
        break;

      case 'quick_analysis':
        if (this.wsCallbacks.onQuickAnalysis) {
          this.wsCallbacks.onQuickAnalysis(data.result);
        }
        break;

      case 'battle_starting':
        if (this.wsCallbacks.onBattleStart) {
          this.wsCallbacks.onBattleStart(data.message);
        }
        break;

      case 'battle_round':
        if (this.wsCallbacks.onBattleRound) {
          this.wsCallbacks.onBattleRound(data.round);
        }
        break;

      case 'battle_complete':
        if (this.wsCallbacks.onBattleComplete) {
          this.wsCallbacks.onBattleComplete(data.result);
        }
        break;

      case 'recommendations':
        if (this.wsCallbacks.onRecommendations) {
          this.wsCallbacks.onRecommendations(data.recommendations);
        }
        break;

      case 'trending_attack':
        if (this.wsCallbacks.onTrendingAttack) {
          this.wsCallbacks.onTrendingAttack(data.message);
        }
        break;

      case 'error':
        console.error('WebSocket error message:', data.message);
        if (this.wsCallbacks.onError) {
          this.wsCallbacks.onError(data.message);
        }
        break;

      default:
        console.log('Unknown WebSocket message type:', type);
    }
  }

  _attemptReconnect(userId, callbacks) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connectWebSocket(userId, callbacks), delay);
    }
  }

  // ==========================================================================
  // Helper Methods
  // ==========================================================================

  /**
   * Extract password features for analysis
   * @param {string} password - Password to analyze
   * @returns {Object} Extracted features
   */
  extractFeatures(password) {
    const features = {
      length: password.length,
      has_upper: /[A-Z]/.test(password),
      has_lower: /[a-z]/.test(password),
      has_digit: /\d/.test(password),
      has_special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
      character_diversity: this._calculateDiversity(password),
      entropy: this._calculateEntropy(password),
      has_common_patterns: this._checkCommonPatterns(password),
      guessability_score: this._estimateGuessability(password),
      pattern_info: this._extractPatternInfo(password)
    };

    return features;
  }

  _calculateDiversity(password) {
    if (!password) return 0;
    const uniqueChars = new Set(password.toLowerCase()).size;
    return uniqueChars / password.length;
  }

  _calculateEntropy(password) {
    if (!password) return 0;

    let charsetSize = 0;
    if (/[a-z]/.test(password)) charsetSize += 26;
    if (/[A-Z]/.test(password)) charsetSize += 26;
    if (/\d/.test(password)) charsetSize += 10;
    if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) charsetSize += 32;

    return password.length * Math.log2(charsetSize || 1);
  }

  _checkCommonPatterns(password) {
    const patterns = [
      /^123/, /123$/, /^password/i, /password$/i,
      /qwerty/i, /asdf/i, /zxcv/i,
      /(.)\1{2,}/, // Repeated characters
      /\d{4}$/, // Year at end
    ];
    return patterns.some(p => p.test(password));
  }

  _estimateGuessability(password) {
    let score = 50; // Base score

    // Length factor
    if (password.length < 8) score += 30;
    else if (password.length < 12) score += 15;
    else if (password.length >= 16) score -= 20;

    // Complexity factors
    if (!/[A-Z]/.test(password)) score += 10;
    if (!/\d/.test(password)) score += 10;
    if (!/[!@#$%^&*]/.test(password)) score += 10;

    // Pattern penalties
    if (this._checkCommonPatterns(password)) score += 20;

    return Math.min(Math.max(score, 0), 100);
  }

  _extractPatternInfo(password) {
    return {
      keyboard_walk: /qwerty|asdf|zxcv|qazwsx/i.test(password),
      date_pattern: /\d{4}|\d{2}\/\d{2}|19\d{2}|20\d{2}/.test(password),
      repeated_chars: /(.)\1{2,}/.test(password),
      sequential: /abc|bcd|cde|123|234|345/i.test(password)
    };
  }

  _handleError(error) {
    if (error.response) {
      return {
        status: error.response.status,
        message: error.response.data?.message || 'API error',
        details: error.response.data
      };
    }
    return { status: 0, message: error.message || 'Network error' };
  }
}

// Export singleton instance
const adversarialService = new AdversarialService();
export default adversarialService;

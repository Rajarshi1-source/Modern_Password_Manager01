/**
 * Predictive Intent Mobile Service
 * ==================================
 *
 * React Native service for AI-powered password prediction:
 * - Context signal sending
 * - Prediction retrieval
 * - Feedback recording
 * - Settings management
 *
 * @author Password Manager Team
 * @created 2026-02-07
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState, Platform } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

const API_BASE = '/api/ml-security';
const STORAGE_KEY = 'predictive_intent_cache';

class PredictiveIntentService {
  constructor() {
    this.predictions = [];
    this.settings = null;
    this.isEnabled = true;
    this.appStateSubscription = null;
    this.lastActiveTime = null;
    this.sessionPatterns = [];
  }

  // ===========================================================================
  // Initialization
  // ===========================================================================

  async initialize(authToken) {
    this.authToken = authToken;

    // Load cached settings
    await this.loadCachedSettings();

    // Subscribe to app state changes
    this.appStateSubscription = AppState.addEventListener(
      'change',
      this.handleAppStateChange.bind(this)
    );

    // Load initial predictions
    await this.refreshPredictions();

    console.log('PredictiveIntentService initialized');
  }

  cleanup() {
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
    }
  }

  // ===========================================================================
  // API Requests
  // ===========================================================================

  async apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.authToken}`,
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }

  // ===========================================================================
  // Predictions
  // ===========================================================================

  async getPredictions(domain = '') {
    try {
      const queryParams = domain ? `?domain=${encodeURIComponent(domain)}` : '';
      const response = await this.apiRequest(`/intent/predictions/${queryParams}`);

      if (response.success) {
        this.predictions = response.predictions || [];
        await this.cachePredictions(this.predictions);
        return this.predictions;
      }

      return [];
    } catch (error) {
      console.error('Failed to get predictions:', error);
      // Fall back to cached predictions
      return await this.getCachedPredictions();
    }
  }

  async refreshPredictions() {
    return this.getPredictions();
  }

  async getCachedPredictions() {
    try {
      const cached = await AsyncStorage.getItem(`${STORAGE_KEY}_predictions`);
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  }

  async cachePredictions(predictions) {
    try {
      await AsyncStorage.setItem(
        `${STORAGE_KEY}_predictions`,
        JSON.stringify(predictions)
      );
    } catch (error) {
      console.warn('Failed to cache predictions:', error);
    }
  }

  // ===========================================================================
  // Context Signals
  // ===========================================================================

  async sendContextSignal(contextData) {
    if (!this.isEnabled) return null;

    try {
      const response = await this.apiRequest('/intent/context/', {
        method: 'POST',
        body: JSON.stringify({
          domain: contextData.domain,
          url_hash: contextData.urlHash,
          page_title: contextData.pageTitle,
          form_fields: contextData.formFields,
          time_on_page: contextData.timeOnPage || 0,
          is_new_tab: contextData.isNewTab || false,
          device_type: Platform.OS === 'ios' ? 'ios' : 'android',
        }),
      });

      if (response.success) {
        // Update predictions if returned
        if (response.predictions && response.predictions.length > 0) {
          this.predictions = response.predictions;
          await this.cachePredictions(this.predictions);
        }

        return {
          signalId: response.signal_id,
          shouldPredict: response.should_predict,
          loginProbability: response.login_probability,
          predictions: response.predictions,
        };
      }

      return null;
    } catch (error) {
      console.error('Failed to send context signal:', error);
      return null;
    }
  }

  // ===========================================================================
  // Usage Recording
  // ===========================================================================

  async recordUsage(vaultItemId, domain, accessMethod = 'mobile_app') {
    if (!this.isEnabled || !this.settings?.learn_from_vault_access) {
      return null;
    }

    try {
      // Track session pattern
      const previousItemId =
        this.sessionPatterns.length > 0
          ? this.sessionPatterns[this.sessionPatterns.length - 1].vaultItemId
          : null;

      this.sessionPatterns.push({
        vaultItemId,
        domain,
        timestamp: Date.now(),
      });

      // Limit session pattern memory
      if (this.sessionPatterns.length > 20) {
        this.sessionPatterns = this.sessionPatterns.slice(-20);
      }

      const response = await this.apiRequest('/intent/usage/', {
        method: 'POST',
        body: JSON.stringify({
          vault_item_id: vaultItemId,
          domain: domain,
          access_method: accessMethod,
          previous_item_id: previousItemId,
          device_fingerprint: await this.getDeviceFingerprint(),
        }),
      });

      return response.success ? response.pattern_id : null;
    } catch (error) {
      console.error('Failed to record usage:', error);
      return null;
    }
  }

  async getDeviceFingerprint() {
    try {
      const deviceId = await AsyncStorage.getItem('device_id');
      if (deviceId) return deviceId;

      // Generate and store device ID
      const newId = `${Platform.OS}_${Date.now()}_${Math.random()
        .toString(36)
        .substr(2, 9)}`;
      await AsyncStorage.setItem('device_id', newId);
      return newId;
    } catch {
      return `${Platform.OS}_unknown`;
    }
  }

  // ===========================================================================
  // Feedback
  // ===========================================================================

  async recordFeedback(predictionId, feedbackType, options = {}) {
    try {
      const response = await this.apiRequest('/intent/feedback/', {
        method: 'POST',
        body: JSON.stringify({
          prediction_id: predictionId,
          feedback_type: feedbackType,
          time_to_use_ms: options.timeToUseMs,
          alternative_item_id: options.alternativeItemId,
          rating: options.rating,
          comment: options.comment,
        }),
      });

      return response.success ? response.feedback_id : null;
    } catch (error) {
      console.error('Failed to record feedback:', error);
      return null;
    }
  }

  async markPredictionUsed(predictionId, timeToUseMs = null) {
    return this.recordFeedback(predictionId, 'used', { timeToUseMs });
  }

  async markPredictionDismissed(predictionId) {
    return this.recordFeedback(predictionId, 'dismissed');
  }

  // ===========================================================================
  // Settings
  // ===========================================================================

  async getSettings() {
    try {
      const response = await this.apiRequest('/intent/settings/');

      if (response.success) {
        this.settings = response.settings;
        this.isEnabled = response.settings.is_enabled;
        await this.cacheSettings(this.settings);
        return this.settings;
      }

      return this.settings;
    } catch (error) {
      console.error('Failed to get settings:', error);
      return await this.loadCachedSettings();
    }
  }

  async updateSettings(updates) {
    try {
      const response = await this.apiRequest('/intent/settings/update/', {
        method: 'PUT',
        body: JSON.stringify(updates),
      });

      if (response.success) {
        this.settings = response.settings;
        this.isEnabled = response.settings.is_enabled;
        await this.cacheSettings(this.settings);
        return this.settings;
      }

      return null;
    } catch (error) {
      console.error('Failed to update settings:', error);
      return null;
    }
  }

  async loadCachedSettings() {
    try {
      const cached = await AsyncStorage.getItem(`${STORAGE_KEY}_settings`);
      if (cached) {
        this.settings = JSON.parse(cached);
        this.isEnabled = this.settings?.is_enabled ?? true;
      }
      return this.settings;
    } catch {
      return null;
    }
  }

  async cacheSettings(settings) {
    try {
      await AsyncStorage.setItem(
        `${STORAGE_KEY}_settings`,
        JSON.stringify(settings)
      );
    } catch (error) {
      console.warn('Failed to cache settings:', error);
    }
  }

  // ===========================================================================
  // Statistics
  // ===========================================================================

  async getStatistics() {
    try {
      const response = await this.apiRequest('/intent/stats/');
      return response.success ? response.statistics : null;
    } catch (error) {
      console.error('Failed to get statistics:', error);
      return null;
    }
  }

  // ===========================================================================
  // Data Privacy (GDPR)
  // ===========================================================================

  async exportData() {
    try {
      const response = await this.apiRequest('/intent/export/');
      return response.success ? response.export : null;
    } catch (error) {
      console.error('Failed to export data:', error);
      return null;
    }
  }

  async deleteAllData(includeSettings = false) {
    try {
      const queryParams = `?confirm=true${includeSettings ? '&include_settings=true' : ''}`;
      const response = await this.apiRequest(`/intent/data/${queryParams}`, {
        method: 'DELETE',
      });

      if (response.success) {
        // Clear local cache
        await this.clearLocalCache();
        this.predictions = [];
        this.sessionPatterns = [];

        return response.deleted;
      }

      return null;
    } catch (error) {
      console.error('Failed to delete data:', error);
      return null;
    }
  }

  async clearLocalCache() {
    try {
      await AsyncStorage.multiRemove([
        `${STORAGE_KEY}_predictions`,
        `${STORAGE_KEY}_settings`,
      ]);
    } catch (error) {
      console.warn('Failed to clear cache:', error);
    }
  }

  // ===========================================================================
  // App State Handling
  // ===========================================================================

  handleAppStateChange(nextAppState) {
    const now = Date.now();

    if (nextAppState === 'active') {
      // App coming to foreground
      if (this.lastActiveTime) {
        const inactiveTime = now - this.lastActiveTime;

        // If inactive for more than 5 minutes, refresh predictions
        if (inactiveTime > 5 * 60 * 1000) {
          this.refreshPredictions();
        }
      }

      this.lastActiveTime = now;
    } else if (nextAppState === 'background') {
      // App going to background - save session patterns
      this.lastActiveTime = now;
    }
  }

  // ===========================================================================
  // Push Notification Suggestions
  // ===========================================================================

  async checkForHighConfidencePredictions() {
    if (!this.settings?.notify_high_confidence) {
      return null;
    }

    const highConfidence = this.predictions.filter(
      (p) => p.confidence >= (this.settings?.preload_confidence_threshold || 0.85)
    );

    if (highConfidence.length > 0) {
      return {
        shouldNotify: true,
        predictions: highConfidence,
        message: `${highConfidence.length} password${highConfidence.length > 1 ? 's' : ''} ready for quick access`,
      };
    }

    return null;
  }
}

// Singleton instance
let serviceInstance = null;

export const getPredictiveIntentService = () => {
  if (!serviceInstance) {
    serviceInstance = new PredictiveIntentService();
  }
  return serviceInstance;
};

export default PredictiveIntentService;

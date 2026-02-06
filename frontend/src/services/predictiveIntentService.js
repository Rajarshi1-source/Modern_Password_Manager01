/**
 * Predictive Intent Service
 * 
 * Frontend service for AI-powered password prediction.
 * Handles context signals, prediction fetching, and feedback.
 * 
 * @author Password Manager Team
 * @created 2026-02-06
 */

import axios from 'axios';

const API_BASE = '/api/ml';

/**
 * Predictive Intent Service
 */
class PredictiveIntentService {
  constructor() {
    this.predictions = [];
    this.settings = null;
    this.isEnabled = true;
    this.contextBuffer = [];
    this.bufferTimeout = null;
  }

  /**
   * Get auth headers
   */
  getAuthHeaders() {
    const token = localStorage.getItem('authToken');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  // ===========================================================================
  // Settings
  // ===========================================================================

  /**
   * Get predictive intent settings
   */
  async getSettings() {
    try {
      const response = await axios.get(`${API_BASE}/intent/settings/`, {
        headers: this.getAuthHeaders(),
      });
      
      if (response.data.success) {
        this.settings = response.data.settings;
        this.isEnabled = this.settings.is_enabled;
        return this.settings;
      }
      throw new Error(response.data.error || 'Failed to get settings');
    } catch (error) {
      console.error('Failed to get predictive intent settings:', error);
      throw error;
    }
  }

  /**
   * Update predictive intent settings
   */
  async updateSettings(settings) {
    try {
      const response = await axios.put(
        `${API_BASE}/intent/settings/update/`,
        settings,
        { headers: this.getAuthHeaders() }
      );
      
      if (response.data.success) {
        this.settings = response.data.settings;
        this.isEnabled = this.settings.is_enabled;
        return this.settings;
      }
      throw new Error(response.data.error || 'Failed to update settings');
    } catch (error) {
      console.error('Failed to update predictive intent settings:', error);
      throw error;
    }
  }

  // ===========================================================================
  // Predictions
  // ===========================================================================

  /**
   * Get current predictions
   */
  async getPredictions(domain = '') {
    try {
      const params = domain ? { domain } : {};
      const response = await axios.get(`${API_BASE}/intent/predictions/`, {
        headers: this.getAuthHeaders(),
        params,
      });
      
      if (response.data.success) {
        this.predictions = response.data.predictions;
        return this.predictions;
      }
      throw new Error(response.data.error || 'Failed to get predictions');
    } catch (error) {
      console.error('Failed to get predictions:', error);
      throw error;
    }
  }

  /**
   * Get preloaded credentials
   */
  async getPreloadedCredentials() {
    try {
      const response = await axios.get(`${API_BASE}/intent/preloaded/`, {
        headers: this.getAuthHeaders(),
      });
      
      if (response.data.success) {
        return response.data.preloaded;
      }
      throw new Error(response.data.error || 'Failed to get preloaded credentials');
    } catch (error) {
      console.error('Failed to get preloaded credentials:', error);
      throw error;
    }
  }

  // ===========================================================================
  // Context Signals
  // ===========================================================================

  /**
   * Send a context signal
   */
  async sendContextSignal(context) {
    if (!this.isEnabled) {
      return { predictions: [] };
    }

    try {
      const response = await axios.post(
        `${API_BASE}/intent/context/`,
        {
          domain: context.domain,
          url_hash: context.urlHash,
          page_title: context.pageTitle,
          form_fields: context.formFields,
          time_on_page: context.timeOnPage || 0,
          is_new_tab: context.isNewTab || false,
          device_type: context.deviceType || 'desktop',
        },
        { headers: this.getAuthHeaders() }
      );
      
      if (response.data.success) {
        // Update local predictions cache
        if (response.data.predictions) {
          this.predictions = response.data.predictions;
        }
        return response.data;
      }
      throw new Error(response.data.error || 'Failed to send context signal');
    } catch (error) {
      console.error('Failed to send context signal:', error);
      throw error;
    }
  }

  /**
   * Buffer context signals for batch sending
   */
  bufferContextSignal(context) {
    this.contextBuffer.push({
      ...context,
      timestamp: Date.now(),
    });

    // Clear existing timeout
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
    }

    // Send after 1 second of inactivity
    this.bufferTimeout = setTimeout(() => {
      this.flushContextBuffer();
    }, 1000);
  }

  /**
   * Flush buffered context signals
   */
  async flushContextBuffer() {
    if (this.contextBuffer.length === 0) return;

    // Take the most recent signal
    const latestContext = this.contextBuffer[this.contextBuffer.length - 1];
    this.contextBuffer = [];

    try {
      await this.sendContextSignal(latestContext);
    } catch (error) {
      console.error('Failed to flush context buffer:', error);
    }
  }

  // ===========================================================================
  // Feedback
  // ===========================================================================

  /**
   * Record feedback on a prediction
   */
  async recordFeedback(predictionId, feedbackType, options = {}) {
    try {
      const response = await axios.post(
        `${API_BASE}/intent/feedback/`,
        {
          prediction_id: predictionId,
          feedback_type: feedbackType,
          time_to_use_ms: options.timeToUseMs,
          alternative_item_id: options.alternativeItemId,
          rating: options.rating,
          comment: options.comment,
        },
        { headers: this.getAuthHeaders() }
      );
      
      if (response.data.success) {
        return response.data;
      }
      throw new Error(response.data.error || 'Failed to record feedback');
    } catch (error) {
      console.error('Failed to record feedback:', error);
      throw error;
    }
  }

  /**
   * Mark a prediction as used
   */
  async markPredictionUsed(predictionId, timeToUseMs = null) {
    return this.recordFeedback(predictionId, 'used', { timeToUseMs });
  }

  /**
   * Mark a prediction as dismissed
   */
  async markPredictionDismissed(predictionId) {
    return this.recordFeedback(predictionId, 'dismissed');
  }

  // ===========================================================================
  // Usage Recording
  // ===========================================================================

  /**
   * Record a password usage event
   */
  async recordUsage(vaultItemId, domain, options = {}) {
    try {
      const response = await axios.post(
        `${API_BASE}/intent/usage/`,
        {
          vault_item_id: vaultItemId,
          domain: domain,
          access_method: options.accessMethod || 'browse',
          device_fingerprint: options.deviceFingerprint,
          previous_item_id: options.previousItemId,
          time_to_access_ms: options.timeToAccessMs,
        },
        { headers: this.getAuthHeaders() }
      );
      
      if (response.data.success) {
        return response.data;
      }
      throw new Error(response.data.error || 'Failed to record usage');
    } catch (error) {
      console.error('Failed to record usage:', error);
      throw error;
    }
  }

  // ===========================================================================
  // Statistics
  // ===========================================================================

  /**
   * Get prediction statistics
   */
  async getStatistics() {
    try {
      const response = await axios.get(`${API_BASE}/intent/stats/`, {
        headers: this.getAuthHeaders(),
      });
      
      if (response.data.success) {
        return response.data.statistics;
      }
      throw new Error(response.data.error || 'Failed to get statistics');
    } catch (error) {
      console.error('Failed to get statistics:', error);
      throw error;
    }
  }

  // ===========================================================================
  // Helpers
  // ===========================================================================

  /**
   * Extract domain from URL
   */
  extractDomain(url) {
    try {
      const urlObj = new URL(url);
      return urlObj.hostname;
    } catch {
      return '';
    }
  }

  /**
   * Hash a URL for privacy
   */
  async hashUrl(url) {
    const encoder = new TextEncoder();
    const data = encoder.encode(url);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Detect form fields on the current page
   */
  detectFormFields() {
    const fields = [];
    const inputs = document.querySelectorAll('input');
    
    inputs.forEach(input => {
      const type = input.type || 'text';
      const name = input.name || input.id || '';
      
      if (['password', 'email', 'text'].includes(type)) {
        fields.push(`${type}:${name}`);
      }
    });
    
    return fields;
  }

  /**
   * Get best prediction for a domain
   */
  getBestPredictionForDomain(domain) {
    const normalizedDomain = domain.toLowerCase().replace(/^www\./, '');
    
    return this.predictions.find(pred => {
      const predDomain = (pred.trigger_domain || '').toLowerCase().replace(/^www\./, '');
      return predDomain === normalizedDomain || 
             predDomain.endsWith(`.${normalizedDomain}`) ||
             normalizedDomain.endsWith(`.${predDomain}`);
    });
  }
}

// Export singleton instance
const predictiveIntentService = new PredictiveIntentService();
export default predictiveIntentService;

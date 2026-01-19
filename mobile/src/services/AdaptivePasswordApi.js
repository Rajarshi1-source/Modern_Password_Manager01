/**
 * AdaptivePasswordApi Service
 * ===========================
 * 
 * Mobile service for adaptive password API interactions.
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = '/api/security';

/**
 * Get authentication headers.
 */
const getHeaders = async () => {
  const token = await AsyncStorage.getItem('authToken');
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };
};

/**
 * Adaptive Password API service.
 */
const adaptivePasswordApi = {
  /**
   * Get adaptive password configuration.
   */
  async getConfig() {
    const headers = await getHeaders();
    const response = await axios.get(`${API_BASE}/adaptive/config/`, { headers });
    return response.data;
  },

  /**
   * Enable adaptive passwords with consent.
   */
  async enable(options = {}) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/enable/`, {
      consent: true,
      consent_version: '1.0',
      suggestion_frequency_days: options.frequencyDays || 30,
      allow_centralized_training: options.allowCentralized ?? true,
      allow_federated_learning: options.allowFederated ?? false,
    }, { headers });
    return response.data;
  },

  /**
   * Disable adaptive passwords.
   */
  async disable(deleteData = false) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/disable/`, {
      delete_data: deleteData,
    }, { headers });
    return response.data;
  },

  /**
   * Record a typing session.
   */
  async recordSession(data) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/record-session/`, data, { headers });
    return response.data;
  },

  /**
   * Get adaptation suggestion for a password.
   */
  async suggestAdaptation(password, force = false) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/suggest/`, {
      password,
      force,
    }, { headers });
    return response.data;
  },

  /**
   * Apply a password adaptation.
   */
  async applyAdaptation(originalPassword, adaptedPassword, substitutions) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/apply/`, {
      original_password: originalPassword,
      adapted_password: adaptedPassword,
      substitutions,
    }, { headers });
    return response.data;
  },

  /**
   * Rollback an adaptation.
   */
  async rollback(adaptationId) {
    const headers = await getHeaders();
    const response = await axios.post(`${API_BASE}/adaptive/rollback/`, {
      adaptation_id: adaptationId,
    }, { headers });
    return response.data;
  },

  /**
   * Get typing profile.
   */
  async getProfile() {
    const headers = await getHeaders();
    const response = await axios.get(`${API_BASE}/adaptive/profile/`, { headers });
    return response.data;
  },

  /**
   * Get adaptation history.
   */
  async getHistory() {
    const headers = await getHeaders();
    const response = await axios.get(`${API_BASE}/adaptive/history/`, { headers });
    return response.data;
  },

  /**
   * Get evolution statistics.
   */
  async getStats() {
    const headers = await getHeaders();
    const response = await axios.get(`${API_BASE}/adaptive/stats/`, { headers });
    return response.data;
  },

  /**
   * Delete all adaptive data (GDPR).
   */
  async deleteAllData() {
    const headers = await getHeaders();
    const response = await axios.delete(`${API_BASE}/adaptive/data/`, { headers });
    return response.data;
  },

  /**
   * Export all adaptive data (GDPR).
   */
  async exportData() {
    const headers = await getHeaders();
    const response = await axios.get(`${API_BASE}/adaptive/export/`, { headers });
    return response.data;
  },
};

export default adaptivePasswordApi;

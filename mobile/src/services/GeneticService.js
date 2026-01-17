/**
 * Genetic Service for React Native
 * ==================================
 * 
 * Mobile service for DNA-based password generation.
 * Handles DNA provider OAuth (via WebBrowser), file upload,
 * and genetic password generation.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as WebBrowser from 'expo-web-browser';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { API_URL } from '../config';

const API_BASE = `${API_URL}/api/security/genetic`;

class GeneticService {
  constructor() {
    this._connectionCache = null;
    this._connectionCacheTime = null;
    this._cacheTTL = 30000; // 30 seconds
  }

  async _getAuthHeaders() {
    const token = await AsyncStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    };
  }

  // ==========================================================================
  // DNA Provider Connection
  // ==========================================================================

  /**
   * Get list of supported DNA providers
   */
  getSupportedProviders() {
    return {
      sequencing: {
        id: 'sequencing',
        name: 'Sequencing.com',
        description: 'Universal DNA API - works with most consumer tests',
        icon: '🧬',
        color: '#10B981',
        recommended: true,
      },
      '23andme': {
        id: '23andme',
        name: '23andMe',
        description: 'Direct connection (limited to ancestry data)',
        icon: '🔬',
        color: '#8B5CF6',
        recommended: false,
      },
      manual: {
        id: 'manual',
        name: 'File Upload',
        description: 'Upload DNA raw data file',
        icon: '📁',
        color: '#6B7280',
      },
    };
  }

  /**
   * Initiate OAuth connection with DNA provider
   * Opens a web browser for authentication
   */
  async initiateConnection(provider) {
    try {
      const headers = await this._getAuthHeaders();
      const redirectUri = `${API_URL}/genetic-callback-mobile`;
      
      const response = await fetch(`${API_BASE}/connect/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          provider,
          redirect_uri: redirectUri,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to initiate connection');
      }

      // Store state for verification
      await AsyncStorage.setItem('genetic_oauth_state', data.state);
      await AsyncStorage.setItem('genetic_oauth_provider', provider);

      // Open browser for OAuth
      const result = await WebBrowser.openAuthSessionAsync(
        data.auth_url,
        redirectUri
      );

      if (result.type === 'success') {
        // Parse the callback URL to get code and state
        const url = new URL(result.url);
        const code = url.searchParams.get('code');
        const state = url.searchParams.get('state');

        // Exchange code for tokens
        return await this.handleOAuthCallback(code, state);
      } else if (result.type === 'cancel') {
        throw new Error('Authentication was cancelled');
      } else {
        throw new Error('Authentication failed');
      }
    } catch (error) {
      console.error('Genetic OAuth error:', error);
      throw error;
    }
  }

  /**
   * Handle OAuth callback
   */
  async handleOAuthCallback(code, state) {
    try {
      // Verify state
      const storedState = await AsyncStorage.getItem('genetic_oauth_state');
      if (state !== storedState) {
        throw new Error('Invalid state token');
      }

      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/callback/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ code, state }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'OAuth callback failed');
      }

      // Clear stored state
      await AsyncStorage.removeItem('genetic_oauth_state');
      await AsyncStorage.removeItem('genetic_oauth_provider');

      // Invalidate cache
      this._connectionCache = null;

      return {
        success: true,
        message: data.message,
        provider: data.provider,
        snpCount: data.snp_count,
        geneticHashPrefix: data.genetic_hash_prefix,
      };
    } catch (error) {
      console.error('OAuth callback error:', error);
      throw error;
    }
  }

  // ==========================================================================
  // File Upload
  // ==========================================================================

  /**
   * Upload DNA file using document picker
   */
  async uploadDNAFile() {
    try {
      // Pick a file
      const result = await DocumentPicker.getDocumentAsync({
        type: ['text/plain', 'text/csv', 'application/octet-stream'],
        copyToCacheDirectory: true,
      });

      if (result.type === 'cancel') {
        return { success: false, cancelled: true };
      }

      // Read file content
      const fileUri = result.assets[0].uri;
      const fileName = result.assets[0].name;
      const fileContent = await FileSystem.readAsStringAsync(fileUri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Upload to server
      const token = await AsyncStorage.getItem('access_token');
      const formData = new FormData();
      formData.append('dna_file', {
        uri: fileUri,
        name: fileName,
        type: 'application/octet-stream',
      });

      const response = await fetch(`${API_BASE}/upload/`, {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Upload failed');
      }

      // Invalidate cache
      this._connectionCache = null;

      return {
        success: true,
        message: data.message,
        formatDetected: data.format_detected,
        snpCount: data.snp_count,
        geneticHashPrefix: data.genetic_hash_prefix,
      };
    } catch (error) {
      console.error('DNA file upload error:', error);
      return { success: false, error: error.message };
    }
  }

  // ==========================================================================
  // Password Generation
  // ==========================================================================

  /**
   * Generate a genetic password
   */
  async generateGeneticPassword(options = {}) {
    const {
      length = 16,
      uppercase = true,
      lowercase = true,
      numbers = true,
      symbols = true,
      combineWithQuantum = true,
      saveCertificate = false,
    } = options;

    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/generate-password/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          length,
          uppercase,
          lowercase,
          numbers,
          symbols,
          combine_with_quantum: combineWithQuantum,
          save_certificate: saveCertificate,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.requires_connection) {
          throw new Error('DNA_CONNECTION_REQUIRED');
        }
        throw new Error(data.error || 'Generation failed');
      }

      return {
        success: true,
        password: data.password,
        certificate: data.certificate,
        evolutionGeneration: data.evolution_generation,
        snpCount: data.snp_count,
      };
    } catch (error) {
      console.error('Genetic password generation failed:', error);
      return { success: false, error: error.message };
    }
  }

  // ==========================================================================
  // Connection Status
  // ==========================================================================

  /**
   * Get DNA connection status
   */
  async getConnectionStatus(forceRefresh = false) {
    if (!forceRefresh && this._connectionCache && 
        Date.now() - this._connectionCacheTime < this._cacheTTL) {
      return { success: true, ...this._connectionCache };
    }

    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/connection-status/`, { headers });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get status');
      }

      this._connectionCache = {
        connected: data.connected,
        availableProviders: data.available_providers,
        subscription: data.subscription,
        connection: data.connection,
      };
      this._connectionCacheTime = Date.now();

      return { success: true, ...this._connectionCache };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Check if DNA is connected
   */
  async isConnected() {
    try {
      const status = await this.getConnectionStatus();
      return status.success && status.connected;
    } catch {
      return false;
    }
  }

  /**
   * Disconnect DNA
   */
  async disconnect() {
    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/disconnect/`, {
        method: 'DELETE',
        headers,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Disconnect failed');
      }

      // Invalidate cache
      this._connectionCache = null;

      return { success: true, message: data.message };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ==========================================================================
  // Epigenetic Evolution
  // ==========================================================================

  /**
   * Get evolution status
   */
  async getEvolutionStatus() {
    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/evolution-status/`, { headers });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get evolution status');
      }

      return { success: true, evolution: data.evolution };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Trigger password evolution
   */
  async triggerEvolution(options = {}) {
    const { newBiologicalAge, force = false } = options;

    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/trigger-evolution/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          new_biological_age: newBiologicalAge,
          force,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.requires_premium) {
          throw new Error('PREMIUM_REQUIRED');
        }
        throw new Error(data.error || 'Evolution failed');
      }

      return {
        success: true,
        evolved: data.evolved,
        message: data.message,
        evolution: data.evolution,
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ==========================================================================
  // Certificates
  // ==========================================================================

  /**
   * List certificates
   */
  async listCertificates(limit = 50, offset = 0) {
    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(
        `${API_BASE}/certificates/?limit=${limit}&offset=${offset}`,
        { headers }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to list certificates');
      }

      return {
        success: true,
        certificates: data.certificates,
        total: data.total,
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get provider display info
   */
  getProviderInfo(providerName) {
    const providers = {
      sequencing: {
        name: 'Sequencing.com',
        description: 'Universal DNA API',
        icon: '🧬',
        color: '#10B981',
      },
      '23andme': {
        name: '23andMe',
        description: 'Consumer Genetics',
        icon: '🔬',
        color: '#8B5CF6',
      },
      ancestry: {
        name: 'AncestryDNA',
        description: 'Heritage Genetics',
        icon: '🌳',
        color: '#F59E0B',
      },
      manual: {
        name: 'File Upload',
        description: 'Direct DNA Data',
        icon: '📁',
        color: '#6B7280',
      },
    };

    return providers[providerName] || {
      name: providerName,
      description: 'DNA Provider',
      icon: '🧬',
      color: '#6B7280',
    };
  }
}

export default new GeneticService();

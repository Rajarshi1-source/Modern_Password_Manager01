/**
 * Genetic Password Service
 * ========================
 * 
 * Frontend service for DNA-based password generation.
 * 
 * Features:
 * - DNA provider OAuth connection
 * - Manual DNA file upload
 * - Genetic password generation
 * - Epigenetic evolution management (Premium)
 * - Certificate handling
 * 
 * Privacy: Raw DNA data is never stored. Only cryptographic
 * hashes are retained for verification.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/security/genetic`;

// Cache for connection status
let connectionStatusCache = null;
let connectionStatusCacheTime = null;
const CACHE_DURATION_MS = 30000; // 30 seconds

/**
 * Genetic Password Service Class
 */
class GeneticService {
  constructor() {
    this._connectionStatus = null;
    this._oauthWindow = null;
  }

  // ===========================================================================
  // DNA Provider Connection
  // ===========================================================================

  /**
   * Get list of supported DNA providers
   * @returns {Object} Provider information for UI display
   */
  getSupportedProviders() {
    return {
      sequencing: {
        id: 'sequencing',
        name: 'Sequencing.com',
        description: 'Universal DNA API - works with 23andMe, AncestryDNA, and more',
        icon: '🧬',
        color: '#10B981',
        oauthSupported: true,
        recommended: true,
      },
      '23andme': {
        id: '23andme',
        name: '23andMe',
        description: 'Direct 23andMe connection (limited to ancestry data)',
        icon: '🔬',
        color: '#8B5CF6',
        oauthSupported: true,
        recommended: false,
        note: 'For full SNP access, download your raw data and use manual upload',
      },
      manual: {
        id: 'manual',
        name: 'Manual Upload',
        description: 'Upload raw DNA data file (23andMe, AncestryDNA, VCF)',
        icon: '📁',
        color: '#6B7280',
        oauthSupported: false,
        supportedFormats: ['.txt', '.csv', '.vcf'],
      },
    };
  }

  /**
   * Initiate OAuth connection to DNA provider
   * @param {string} provider - Provider ID (sequencing, 23andme)
   * @param {string} redirectUri - OAuth callback URL
   * @returns {Promise<Object>} Auth URL and state token
   */
  async initiateConnection(provider, redirectUri) {
    try {
      const response = await axios.post(`${API_BASE}/connect/`, {
        provider,
        redirect_uri: redirectUri,
      });

      return {
        success: true,
        authUrl: response.data.auth_url,
        state: response.data.state,
        provider: response.data.provider,
      };
    } catch (error) {
      console.error('Failed to initiate DNA connection:', error);
      throw new Error(error.response?.data?.error || 'Failed to initiate connection');
    }
  }

  /**
   * Open OAuth popup for DNA provider connection
   * @param {string} provider - Provider ID
   * @param {Function} onSuccess - Callback on successful connection
   * @param {Function} onError - Callback on error
   */
  async openOAuthPopup(provider, onSuccess, onError) {
    try {
      // Get current origin for redirect
      const redirectUri = `${window.location.origin}/genetic-callback`;
      
      const { authUrl, state } = await this.initiateConnection(provider, redirectUri);
      
      // Store state for verification
      sessionStorage.setItem('genetic_oauth_state', state);
      sessionStorage.setItem('genetic_oauth_provider', provider);
      
      // Open popup
      const width = 600;
      const height = 700;
      const left = (window.screen.width - width) / 2;
      const top = (window.screen.height - height) / 2;
      
      this._oauthWindow = window.open(
        authUrl,
        'genetic_oauth',
        `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
      );
      
      // Listen for callback
      const handleMessage = (event) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === 'genetic_oauth_callback') {
          window.removeEventListener('message', handleMessage);
          
          if (event.data.success) {
            this.invalidateCache();
            onSuccess?.(event.data);
          } else {
            onError?.(event.data.error);
          }
        }
      };
      
      window.addEventListener('message', handleMessage);
      
      // Check if popup closed without completing
      const checkClosed = setInterval(() => {
        if (this._oauthWindow?.closed) {
          clearInterval(checkClosed);
          window.removeEventListener('message', handleMessage);
        }
      }, 500);
      
    } catch (error) {
      onError?.(error.message);
    }
  }

  /**
   * Handle OAuth callback (called from callback page)
   * @param {string} code - Authorization code
   * @param {string} state - State token
   * @returns {Promise<Object>} Connection result
   */
  async handleOAuthCallback(code, state) {
    try {
      // Verify state
      const storedState = sessionStorage.getItem('genetic_oauth_state');
      if (state !== storedState) {
        throw new Error('Invalid state token');
      }
      
      const response = await axios.post(`${API_BASE}/callback/`, {
        code,
        state,
      });
      
      // Clear stored state
      sessionStorage.removeItem('genetic_oauth_state');
      sessionStorage.removeItem('genetic_oauth_provider');
      
      this.invalidateCache();
      
      return {
        success: true,
        message: response.data.message,
        provider: response.data.provider,
        snpCount: response.data.snp_count,
        geneticHashPrefix: response.data.genetic_hash_prefix,
      };
    } catch (error) {
      console.error('OAuth callback failed:', error);
      throw new Error(error.response?.data?.error || 'OAuth callback failed');
    }
  }

  // ===========================================================================
  // File Upload
  // ===========================================================================

  /**
   * Upload DNA file for manual connection
   * @param {File} file - DNA data file
   * @param {Function} onProgress - Progress callback (0-100)
   * @returns {Promise<Object>} Upload result
   */
  async uploadDNAFile(file, onProgress) {
    try {
      // Validate file type
      const validExtensions = ['.txt', '.csv', '.vcf'];
      const extension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
      
      if (!validExtensions.includes(extension)) {
        throw new Error(`Unsupported file type. Supported: ${validExtensions.join(', ')}`);
      }
      
      // Validate file size (max 50MB)
      if (file.size > 50 * 1024 * 1024) {
        throw new Error('File too large. Maximum size is 50MB.');
      }
      
      const formData = new FormData();
      formData.append('dna_file', file);
      
      const response = await axios.post(`${API_BASE}/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress?.(percent);
        },
      });
      
      this.invalidateCache();
      
      return {
        success: true,
        message: response.data.message,
        formatDetected: response.data.format_detected,
        snpCount: response.data.snp_count,
        geneticHashPrefix: response.data.genetic_hash_prefix,
      };
    } catch (error) {
      console.error('DNA file upload failed:', error);
      throw new Error(error.response?.data?.error || 'File upload failed');
    }
  }

  // ===========================================================================
  // Password Generation
  // ===========================================================================

  /**
   * Generate a genetic password
   * @param {Object} options - Generation options
   * @returns {Promise<Object>} Generated password and certificate
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
      const response = await axios.post(`${API_BASE}/generate-password/`, {
        length,
        uppercase,
        lowercase,
        numbers,
        symbols,
        combine_with_quantum: combineWithQuantum,
        save_certificate: saveCertificate,
      });
      
      return {
        success: true,
        password: response.data.password,
        certificate: response.data.certificate,
        evolutionGeneration: response.data.evolution_generation,
        snpCount: response.data.snp_count,
      };
    } catch (error) {
      console.error('Genetic password generation failed:', error);
      
      // Check for specific error types
      if (error.response?.data?.requires_connection) {
        throw new Error('DNA_CONNECTION_REQUIRED');
      }
      
      throw new Error(error.response?.data?.error || 'Password generation failed');
    }
  }

  // ===========================================================================
  // Connection Status
  // ===========================================================================

  /**
   * Get DNA connection status
   * @param {boolean} forceRefresh - Skip cache
   * @returns {Promise<Object>} Connection status
   */
  async getConnectionStatus(forceRefresh = false) {
    // Check cache
    if (!forceRefresh && connectionStatusCache && connectionStatusCacheTime) {
      const age = Date.now() - connectionStatusCacheTime;
      if (age < CACHE_DURATION_MS) {
        return connectionStatusCache;
      }
    }
    
    try {
      const response = await axios.get(`${API_BASE}/connection-status/`);
      
      const status = {
        connected: response.data.connected,
        availableProviders: response.data.available_providers,
        subscription: response.data.subscription,
        connection: response.data.connection || null,
      };
      
      // Update cache
      connectionStatusCache = status;
      connectionStatusCacheTime = Date.now();
      
      return status;
    } catch (error) {
      console.error('Failed to get connection status:', error);
      throw new Error(error.response?.data?.error || 'Failed to get status');
    }
  }

  /**
   * Check if DNA is connected
   * @returns {Promise<boolean>}
   */
  async isConnected() {
    try {
      const status = await this.getConnectionStatus();
      return status.connected;
    } catch {
      return false;
    }
  }

  /**
   * Disconnect DNA connection
   * @returns {Promise<Object>}
   */
  async disconnect() {
    try {
      const response = await axios.delete(`${API_BASE}/disconnect/`);
      this.invalidateCache();
      
      return {
        success: true,
        message: response.data.message,
      };
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Disconnect failed');
    }
  }

  /**
   * Update preferences
   * @param {Object} preferences - Preference updates
   * @returns {Promise<Object>}
   */
  async updatePreferences(preferences) {
    try {
      const response = await axios.put(`${API_BASE}/preferences/`, preferences);
      this.invalidateCache();
      
      return {
        success: true,
        preferences: response.data.preferences,
      };
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to update preferences');
    }
  }

  // ===========================================================================
  // Epigenetic Evolution (Premium)
  // ===========================================================================

  /**
   * Get evolution status
   * @returns {Promise<Object>} Evolution status
   */
  async getEvolutionStatus() {
    try {
      const response = await axios.get(`${API_BASE}/evolution-status/`);
      
      return {
        success: true,
        evolution: response.data.evolution,
      };
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to get evolution status');
    }
  }

  /**
   * Trigger password evolution (Premium)
   * @param {Object} options - Evolution options
   * @returns {Promise<Object>} Evolution result
   */
  async triggerEvolution(options = {}) {
    const { newBiologicalAge, force = false } = options;
    
    try {
      const response = await axios.post(`${API_BASE}/trigger-evolution/`, {
        new_biological_age: newBiologicalAge,
        force,
      });
      
      return {
        success: true,
        evolved: response.data.evolved,
        message: response.data.message,
        evolution: response.data.evolution,
      };
    } catch (error) {
      // Check for premium requirement
      if (error.response?.data?.requires_premium) {
        throw new Error('PREMIUM_REQUIRED');
      }
      
      throw new Error(error.response?.data?.error || 'Evolution trigger failed');
    }
  }

  // ===========================================================================
  // Certificates
  // ===========================================================================

  /**
   * Get a specific certificate
   * @param {string} certificateId - Certificate UUID
   * @returns {Promise<Object>}
   */
  async getCertificate(certificateId) {
    try {
      const response = await axios.get(`${API_BASE}/certificate/${certificateId}/`);
      return {
        success: true,
        certificate: response.data.certificate,
      };
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Certificate not found');
    }
  }

  /**
   * List user's certificates
   * @param {number} limit - Max results
   * @param {number} offset - Pagination offset
   * @returns {Promise<Object>}
   */
  async listCertificates(limit = 50, offset = 0) {
    try {
      const response = await axios.get(`${API_BASE}/certificates/`, {
        params: { limit, offset },
      });
      
      return {
        success: true,
        certificates: response.data.certificates,
        total: response.data.total,
      };
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to list certificates');
    }
  }

  /**
   * Format certificate for display
   * @param {Object} certificate - Certificate data
   * @returns {Object} Formatted certificate
   */
  formatCertificateForDisplay(certificate) {
    if (!certificate) return null;
    
    const providerInfo = this.getProviderInfo(certificate.provider);
    
    return {
      id: certificate.certificate_id,
      provider: providerInfo,
      snpCount: certificate.snp_markers_used,
      evolutionGeneration: certificate.evolution_generation,
      epigeneticAge: certificate.epigenetic_age,
      combinedWithQuantum: certificate.combined_with_quantum,
      passwordLength: certificate.password_length,
      entropyBits: certificate.entropy_bits,
      timestamp: new Date(certificate.generation_timestamp),
      timestampFormatted: new Date(certificate.generation_timestamp).toLocaleString(),
      signature: certificate.signature,
      passwordHashPrefix: certificate.password_hash_prefix,
      geneticHashPrefix: certificate.genetic_hash_prefix,
    };
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Get provider display info
   * @param {string} providerName - Provider ID
   * @returns {Object} Provider info
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

  /**
   * Invalidate connection status cache
   */
  invalidateCache() {
    connectionStatusCache = null;
    connectionStatusCacheTime = null;
  }

  /**
   * Download certificate as JSON
   * @param {Object} certificate - Certificate data
   */
  downloadCertificate(certificate) {
    const formatted = this.formatCertificateForDisplay(certificate);
    const content = JSON.stringify({
      ...certificate,
      _formatted: formatted,
      _downloadedAt: new Date().toISOString(),
    }, null, 2);
    
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `genetic-certificate-${certificate.certificate_id.slice(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

// Export singleton instance
const geneticService = new GeneticService();
export default geneticService;

// Also export class for testing
export { GeneticService };

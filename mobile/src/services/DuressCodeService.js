/**
 * DuressCodeService - Mobile
 * 
 * Service for managing Military-Grade Duress Codes on mobile devices.
 * Provides methods for:
 * - Duress configuration management
 * - Code CRUD operations
 * - Decoy vault handling
 * - Trusted authority management
 * - Event logging
 * - Evidence package handling
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = 'http://localhost:8000/api/security';

class DuressCodeService {
  constructor() {
    this.cachedConfig = null;
    this.cachedCodes = null;
  }

  /**
   * Get auth headers
   */
  async _getHeaders() {
    const token = await AsyncStorage.getItem('authToken');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  }

  // =========================================================================
  // Configuration
  // =========================================================================

  /**
   * Get duress configuration for the current user
   */
  async getConfig() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/config/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch duress configuration');

      const data = await response.json();
      this.cachedConfig = data;
      return data;
    } catch (error) {
      console.error('getConfig error:', error);
      throw error;
    }
  }

  /**
   * Update duress configuration
   * @param {Object} config - Configuration updates
   */
  async updateConfig(config) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/config/`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(config)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to update configuration');
      }

      const data = await response.json();
      this.cachedConfig = data;
      return data;
    } catch (error) {
      console.error('updateConfig error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Duress Codes CRUD
  // =========================================================================

  /**
   * Get all duress codes for the current user
   */
  async getCodes() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/codes/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch duress codes');

      const data = await response.json();
      this.cachedCodes = data.codes || [];
      return data;
    } catch (error) {
      console.error('getCodes error:', error);
      throw error;
    }
  }

  /**
   * Create a new duress code
   * @param {Object} codeData - { code, threatLevel, codeHint, actionConfig }
   */
  async createCode(codeData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/codes/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          code: codeData.code,
          threat_level: codeData.threatLevel || 'medium',
          code_hint: codeData.codeHint || '',
          action_config: codeData.actionConfig || {}
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to create duress code');
      }

      return response.json();
    } catch (error) {
      console.error('createCode error:', error);
      throw error;
    }
  }

  /**
   * Get details of a specific duress code
   * @param {string} codeId - Duress code UUID
   */
  async getCode(codeId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/codes/${codeId}/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch duress code');

      return response.json();
    } catch (error) {
      console.error('getCode error:', error);
      throw error;
    }
  }

  /**
   * Update a duress code
   * @param {string} codeId - Duress code UUID
   * @param {Object} codeData - Updated code data
   */
  async updateCode(codeId, codeData) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/codes/${codeId}/`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({
          new_code: codeData.code || null,
          threat_level: codeData.threatLevel || null,
          code_hint: codeData.codeHint || null,
          action_config: codeData.actionConfig || null
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to update duress code');
      }

      return response.json();
    } catch (error) {
      console.error('updateCode error:', error);
      throw error;
    }
  }

  /**
   * Delete (deactivate) a duress code
   * @param {string} codeId - Duress code UUID
   */
  async deleteCode(codeId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/codes/${codeId}/`, {
        method: 'DELETE',
        headers
      });

      if (!response.ok) throw new Error('Failed to delete duress code');

      return { success: true };
    } catch (error) {
      console.error('deleteCode error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Decoy Vault
  // =========================================================================

  /**
   * Get decoy vault for the current user
   * @param {string} threatLevel - Threat level (low, medium, high, critical)
   */
  async getDecoyVault(threatLevel = 'medium') {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/decoy/?threat_level=${threatLevel}`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch decoy vault');

      return response.json();
    } catch (error) {
      console.error('getDecoyVault error:', error);
      throw error;
    }
  }

  /**
   * Regenerate decoy vault with new fake data
   * @param {string} threatLevel - Threat level for regeneration
   */
  async regenerateDecoyVault(threatLevel = 'medium') {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/decoy/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ threat_level: threatLevel })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to regenerate decoy vault');
      }

      return response.json();
    } catch (error) {
      console.error('regenerateDecoyVault error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Trusted Authorities
  // =========================================================================

  /**
   * Get all trusted authorities for silent alarms
   */
  async getAuthorities() {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/authorities/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch trusted authorities');

      return response.json();
    } catch (error) {
      console.error('getAuthorities error:', error);
      throw error;
    }
  }

  /**
   * Add a new trusted authority
   * @param {Object} authority - Authority data
   */
  async addAuthority(authority) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/authorities/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          authority_type: authority.type,
          contact_method: authority.contactMethod,
          contact_details: authority.contactDetails,
          threat_levels: authority.threatLevels || ['high', 'critical'],
          name: authority.name || ''
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to add trusted authority');
      }

      return response.json();
    } catch (error) {
      console.error('addAuthority error:', error);
      throw error;
    }
  }

  /**
   * Update a trusted authority
   * @param {string} authorityId - Authority UUID
   * @param {Object} authority - Updated authority data
   */
  async updateAuthority(authorityId, authority) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/authorities/${authorityId}/`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(authority)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to update authority');
      }

      return response.json();
    } catch (error) {
      console.error('updateAuthority error:', error);
      throw error;
    }
  }

  /**
   * Delete a trusted authority
   * @param {string} authorityId - Authority UUID
   */
  async deleteAuthority(authorityId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/authorities/${authorityId}/`, {
        method: 'DELETE',
        headers
      });

      if (!response.ok) throw new Error('Failed to delete authority');

      return { success: true };
    } catch (error) {
      console.error('deleteAuthority error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Duress Events
  // =========================================================================

  /**
   * Get duress event history
   * @param {Object} options - Query options { limit, threatLevel, startDate, endDate }
   */
  async getEvents(options = {}) {
    try {
      const headers = await this._getHeaders();
      
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit);
      if (options.threatLevel) params.append('threat_level', options.threatLevel);
      if (options.startDate) params.append('start_date', options.startDate);
      if (options.endDate) params.append('end_date', options.endDate);

      const response = await fetch(`${API_BASE}/duress/events/?${params}`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch duress events');

      return response.json();
    } catch (error) {
      console.error('getEvents error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Evidence Packages
  // =========================================================================

  /**
   * Get evidence package details
   * @param {string} packageId - Evidence package UUID
   */
  async getEvidencePackage(packageId) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/evidence/${packageId}/`, {
        headers
      });

      if (!response.ok) throw new Error('Failed to fetch evidence package');

      return response.json();
    } catch (error) {
      console.error('getEvidencePackage error:', error);
      throw error;
    }
  }

  /**
   * Export evidence package for legal use
   * @param {string} packageId - Evidence package UUID
   * @param {string} requestingUser - Identity of requesting user
   */
  async exportEvidencePackage(packageId, requestingUser) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/evidence/${packageId}/export/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ requesting_user: requestingUser })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to export evidence package');
      }

      return response.json();
    } catch (error) {
      console.error('exportEvidencePackage error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Test Activation
  // =========================================================================

  /**
   * Test duress code activation in safe mode (no real alerts sent)
   * @param {string} code - Duress code to test
   */
  async testActivation(code) {
    try {
      const headers = await this._getHeaders();
      
      const response = await fetch(`${API_BASE}/duress/test/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ code })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to test duress activation');
      }

      return response.json();
    } catch (error) {
      console.error('testActivation error:', error);
      throw error;
    }
  }

  // =========================================================================
  // Utility Functions
  // =========================================================================

  /**
   * Format threat level for display
   * @param {string} level - Threat level key
   * @returns {Object} { icon, label, color, description }
   */
  formatThreatLevel(level) {
    const levels = {
      low: { 
        icon: '🟢', 
        label: 'Low', 
        color: '#22c55e',
        description: 'Show limited decoy vault'
      },
      medium: { 
        icon: '🟡', 
        label: 'Medium', 
        color: '#eab308',
        description: 'Full decoy + preserve evidence'
      },
      high: { 
        icon: '🟠', 
        label: 'High', 
        color: '#f97316',
        description: 'Decoy + alert authorities'
      },
      critical: { 
        icon: '🔴', 
        label: 'Critical', 
        color: '#ef4444',
        description: 'Full response + wipe real data access'
      }
    };
    return levels[level] || levels.medium;
  }

  /**
   * Format authority type for display
   * @param {string} type - Authority type key
   * @returns {Object} { icon, label }
   */
  formatAuthorityType(type) {
    const types = {
      law_enforcement: { icon: '🚔', label: 'Law Enforcement' },
      legal_counsel: { icon: '⚖️', label: 'Legal Counsel' },
      security_team: { icon: '🛡️', label: 'Security Team' },
      family: { icon: '👨‍👩‍👧', label: 'Family Member' },
      custom: { icon: '📋', label: 'Custom Contact' }
    };
    return types[type] || types.custom;
  }

  /**
   * Format contact method for display
   * @param {string} method - Contact method key
   * @returns {Object} { icon, label }
   */
  formatContactMethod(method) {
    const methods = {
      email: { icon: '📧', label: 'Email' },
      sms: { icon: '📱', label: 'SMS' },
      phone: { icon: '📞', label: 'Phone Call' },
      webhook: { icon: '🔗', label: 'Webhook' },
      signal: { icon: '💬', label: 'Signal' }
    };
    return methods[method] || methods.email;
  }

  /**
   * Calculate duress code strength
   * @param {string} code - The duress code
   * @returns {Object} { score: 0-100, label, suggestions[] }
   */
  calculateCodeStrength(code) {
    let score = 0;
    const suggestions = [];
    
    // Length check
    if (code.length >= 8) score += 25;
    else if (code.length >= 6) score += 15;
    else suggestions.push('Use at least 8 characters');
    
    // Has numbers
    if (/\d/.test(code)) score += 20;
    else suggestions.push('Add numbers');
    
    // Has lowercase
    if (/[a-z]/.test(code)) score += 15;
    
    // Has uppercase
    if (/[A-Z]/.test(code)) score += 15;
    else suggestions.push('Add uppercase letters');
    
    // Has special chars
    if (/[!@#$%^&*(),.?":{}|<>]/.test(code)) score += 25;
    else suggestions.push('Add special characters');
    
    // Determine label
    let label = 'Weak';
    if (score >= 80) label = 'Strong';
    else if (score >= 60) label = 'Moderate';
    else if (score >= 40) label = 'Fair';
    
    return { score, label, suggestions };
  }

  /**
   * Get cached configuration (without network request)
   */
  getCachedConfig() {
    return this.cachedConfig;
  }

  /**
   * Get cached codes (without network request)
   */
  getCachedCodes() {
    return this.cachedCodes;
  }
}

// Export singleton
const duressCodeService = new DuressCodeService();
export default duressCodeService;

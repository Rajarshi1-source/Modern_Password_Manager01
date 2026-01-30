/**
 * Ocean Entropy Service
 * ======================
 * 
 * Mobile service for ocean wave entropy harvesting.
 * Communicates with the NOAA Ocean Wave API endpoints.
 * 
 * "Powered by the ocean's chaos" 🌊
 * 
 * @author Password Manager Team
 * @created 2026-01-23
 */

import { API_URL } from '../config';

const OCEAN_API = `${API_URL}/api/security/ocean`;

/**
 * Ocean Entropy Service
 */
class OceanEntropyService {
  /**
   * Get ocean entropy provider status
   * @returns {Promise<Object>} Provider status including healthy buoys
   */
  async getStatus() {
    try {
      const response = await fetch(`${OCEAN_API}/status/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Ocean status fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get list of active NOAA buoys
   * @param {string} [region] - Optional region filter (atlantic, pacific, gulf, caribbean)
   * @returns {Promise<Object>} List of buoys with locations
   */
  async getBuoys(region = null) {
    try {
      const params = region ? `?region=${region}` : '';
      const response = await fetch(`${OCEAN_API}/buoys/${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Buoy list fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get latest readings from buoys
   * @param {string} [buoyId] - Specific buoy ID (optional)
   * @param {number} [limit=5] - Number of buoys to fetch
   * @returns {Promise<Object>} Latest buoy readings with entropy values
   */
  async getReadings(buoyId = null, limit = 5) {
    try {
      let params = [];
      if (buoyId) params.push(`buoy_id=${buoyId}`);
      if (limit) params.push(`limit=${limit}`);
      
      const queryString = params.length ? `?${params.join('&')}` : '';
      
      const response = await fetch(`${OCEAN_API}/readings/${queryString}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Readings fetch failed:', error);
      throw error;
    }
  }

  /**
   * Generate entropy from ocean wave data
   * @param {number} [count=32] - Number of bytes to generate (1-256)
   * @param {string} [format='hex'] - Output format ('hex' or 'base64')
   * @returns {Promise<Object>} Generated entropy with source buoys
   */
  async generateEntropy(count = 32, format = 'hex') {
    try {
      const response = await fetch(`${OCEAN_API}/generate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
        body: JSON.stringify({ count, format }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        entropy: data.entropy,
        format: data.format,
        bytesCount: data.bytes_count,
        sourceBuoys: data.source_buoys,
        sourceId: data.source_id,
        provider: data.provider,
        quantumSource: data.quantum_source,
        generatedAt: new Date(data.generated_at),
        message: data.message,
      };
    } catch (error) {
      console.error('Entropy generation failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Get ocean pool contribution status
   * @returns {Promise<Object>} Pool status and contribution percentage
   */
  async getPoolStatus() {
    try {
      const response = await fetch(`${OCEAN_API}/pool/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Pool status fetch failed:', error);
      throw error;
    }
  }

  /**
   * Check if ocean entropy is available
   * @returns {Promise<boolean>}
   */
  async isAvailable() {
    try {
      const status = await this.getStatus();
      return status.status === 'available';
    } catch {
      return false;
    }
  }

  /**
   * Get provider info for display
   * @returns {Object} Provider display info
   */
  getProviderInfo() {
    return {
      name: 'NOAA Ocean Wave',
      description: 'National Data Buoy Center',
      source: 'Ocean wave patterns & temperature',
      icon: '🌊',
      color: '#0077B6',
      tagline: "Powered by the ocean's chaos",
    };
  }

  /**
   * Generate a hybrid password using ocean entropy
   * @param {Object} options - Password generation options
   * @param {number} [options.length=16] - Password length
   * @param {boolean} [options.includeUppercase=true] - Include uppercase letters
   * @param {boolean} [options.includeLowercase=true] - Include lowercase letters
   * @param {boolean} [options.includeNumbers=true] - Include numbers
   * @param {boolean} [options.includeSymbols=true] - Include symbols
   * @returns {Promise<Object>} Generated password with metadata
   */
  async generateHybridPassword(options = {}) {
    try {
      const {
        length = 16,
        includeUppercase = true,
        includeLowercase = true,
        includeNumbers = true,
        includeSymbols = true,
      } = options;

      const response = await fetch(`${OCEAN_API}/generate-hybrid-password/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
        body: JSON.stringify({
          length,
          include_uppercase: includeUppercase,
          include_lowercase: includeLowercase,
          include_numbers: includeNumbers,
          include_symbols: includeSymbols,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        password: data.password,
        sources: data.sources || ['quantum', 'ocean'],
        entropyBits: data.entropy_bits || 95,
        qualityScore: data.quality_score || 0.95,
        oceanDetails: data.ocean_details || {},
        certificateId: data.certificate_id,
      };
    } catch (error) {
      console.error('Hybrid password generation failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  // =========================================================================
  // 🌀 Storm Chase Mode Methods
  // =========================================================================

  /**
   * Get active storm alerts
   * @returns {Promise<Object>} List of active storm alerts
   */
  async getActiveStorms() {
    try {
      const response = await fetch(`${OCEAN_API}/storms/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Storm list fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get storm chase mode status
   * @returns {Promise<Object>} Storm chase status with alerts and bonus info
   */
  async getStormStatus() {
    try {
      const response = await fetch(`${OCEAN_API}/storms/status/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        isActive: data.is_active,
        activeStormsCount: data.active_storms_count,
        mostSevere: data.most_severe,
        maxEntropyBonus: data.max_entropy_bonus,
        regionsAffected: data.regions_affected || [],
        stormAlerts: data.storm_alerts || [],
        message: data.message,
        lastScan: data.last_scan,
      };
    } catch (error) {
      console.error('Storm status fetch failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Generate entropy prioritizing storm-affected buoys
   * @param {number} [count=32] - Number of bytes to generate
   * @param {string} [format='hex'] - Output format
   * @returns {Promise<Object>} Generated entropy with storm info
   */
  async generateStormEntropy(count = 32, format = 'hex') {
    try {
      const response = await fetch(`${OCEAN_API}/generate-storm-entropy/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
        body: JSON.stringify({ count, format }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        entropy: data.entropy,
        format: data.format,
        bytesCount: data.bytes_count,
        sourceBuoys: data.source_buoys,
        stormMode: data.storm_mode,
        entropyBonus: data.entropy_bonus,
        message: data.message,
      };
    } catch (error) {
      console.error('Storm entropy generation failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Trigger a manual storm scan
   * @returns {Promise<Object>} Scan results
   */
  async scanForStorms() {
    try {
      const response = await fetch(`${OCEAN_API}/storms/scan/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        stormsFound: data.storms_found,
        alerts: data.alerts || [],
        scannedAt: data.scanned_at,
      };
    } catch (error) {
      console.error('Storm scan failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  // =========================================================================
  // ⚡ Natural Entropy (Multi-Source) Methods
  // =========================================================================

  /**
   * Generate password from multiple natural entropy sources
   * @param {string[]} sources - Array of sources: 'ocean', 'lightning', 'seismic', 'solar'
   * @param {number} length - Password length (8-64)
   * @param {string} charset - Character set: 'standard', 'alphanumeric', 'max_entropy'
   * @returns {Promise<Object>} Generated password and certificate
   */
  async generateNaturalPassword(sources = ['ocean', 'lightning', 'seismic', 'solar'], length = 24, charset = 'standard') {
    try {
      const response = await fetch(`${OCEAN_API}/natural/generate-password/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
        body: JSON.stringify({ sources, length, charset }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        password: data.password,
        sourcesUsed: data.sources_used,
        qualityScore: data.quality_score,
        generationTimeMs: data.generation_time_ms,
        certificate: data.certificate,
        errors: data.errors,
      };
    } catch (error) {
      console.error('Natural password generation failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Get global entropy status for all sources
   * @returns {Promise<Object>} Status of all entropy sources
   */
  async getGlobalEntropyStatus() {
    try {
      const response = await fetch(`${OCEAN_API}/natural/status/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        sources: data.sources,
        availableSources: data.available_sources,
        totalSources: data.total_sources,
        timestamp: data.timestamp,
      };
    } catch (error) {
      console.error('Global status fetch failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Get lightning activity data
   * @returns {Promise<Object>} Recent lightning strikes and global activity
   */
  async getLightningActivity() {
    try {
      const response = await fetch(`${OCEAN_API}/natural/lightning/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Lightning activity fetch failed:', error);
      return { error: error.message };
    }
  }

  /**
   * Get seismic activity data
   * @returns {Promise<Object>} Recent earthquakes and global activity
   */
  async getSeismicActivity() {
    try {
      const response = await fetch(`${OCEAN_API}/natural/seismic/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Seismic activity fetch failed:', error);
      return { error: error.message };
    }
  }

  /**
   * Get solar wind status
   * @returns {Promise<Object>} Solar wind readings and space weather
   */
  async getSolarWindStatus() {
    try {
      const response = await fetch(`${OCEAN_API}/natural/solar/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Solar wind fetch failed:', error);
      return { error: error.message };
    }
  }

  /**
   * Get user entropy preferences
   * @returns {Promise<Object>} User's source preferences
   */
  async getEntropyPreferences() {
    try {
      const response = await fetch(`${OCEAN_API}/natural/preferences/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Preferences fetch failed:', error);
      return { error: error.message };
    }
  }

  /**
   * Update user entropy preferences
   * @param {Object} preferences - Preference updates
   * @returns {Promise<Object>} Update result
   */
  async updateEntropyPreferences(preferences) {
    try {
      const response = await fetch(`${OCEAN_API}/natural/preferences/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await this._getToken()}`,
        },
        body: JSON.stringify(preferences),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Preferences update failed:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Get auth token from secure storage
   * @private
   */
  async _getToken() {
    // This would integrate with the mobile secure storage
    try {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      return await AsyncStorage.getItem('auth_token');
    } catch {
      return null;
    }
  }
}

// Export singleton
const oceanEntropyService = new OceanEntropyService();
export default oceanEntropyService;

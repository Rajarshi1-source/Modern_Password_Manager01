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

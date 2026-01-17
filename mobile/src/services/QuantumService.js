/**
 * Quantum Service for React Native
 * =================================
 * 
 * Mobile service for quantum-certified password generation.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_URL } from '../config';

const API_BASE = `${API_URL}/api/security/quantum`;

class QuantumService {
  constructor() {
    this._poolCache = null;
    this._poolCacheTime = null;
    this._poolCacheTTL = 30000;
  }

  async _getAuthHeaders() {
    const token = await AsyncStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    };
  }

  /**
   * Generate a quantum-certified password
   */
  async generateQuantumPassword(options = {}) {
    const {
      length = 16,
      uppercase = true,
      lowercase = true,
      numbers = true,
      symbols = true,
      saveCertificate = true,
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
          save_certificate: saveCertificate,
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        return {
          success: true,
          password: data.password,
          certificate: data.certificate,
          quantumCertified: data.quantum_certified,
        };
      }

      return {
        success: false,
        error: data.error || 'Generation failed',
      };
    } catch (error) {
      console.error('Quantum password generation failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Get raw quantum random bytes
   */
  async getRandomBytes(count = 32, format = 'hex') {
    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(
        `${API_BASE}/random-bytes/?count=${count}&format=${format}`,
        { headers }
      );

      const data = await response.json();

      if (response.ok && data.success) {
        return {
          success: true,
          bytes: data.bytes,
          format: data.format,
          count: data.count,
          provider: data.provider,
        };
      }

      return { success: false, error: data.error };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get quantum entropy pool status
   */
  async getPoolStatus() {
    if (this._poolCache && Date.now() - this._poolCacheTime < this._poolCacheTTL) {
      return { success: true, ...this._poolCache };
    }

    try {
      const headers = await this._getAuthHeaders();
      const response = await fetch(`${API_BASE}/pool-status/`, { headers });
      const data = await response.json();

      if (response.ok && data.success) {
        this._poolCache = {
          pool: data.pool,
          providers: data.providers,
        };
        this._poolCacheTime = Date.now();

        return {
          success: true,
          pool: data.pool,
          providers: data.providers,
        };
      }

      return { success: false, error: data.error };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get provider info by name
   */
  getProviderInfo(providerName) {
    const providers = {
      'anu_qrng': {
        name: 'ANU Quantum RNG',
        description: 'Australian National University',
        source: 'Quantum vacuum fluctuations',
        icon: '🇦🇺',
        color: '#FFD700',
      },
      'ibm_quantum': {
        name: 'IBM Quantum',
        description: 'IBM Quantum Computing',
        source: 'Superconducting qubit superposition',
        icon: '🔵',
        color: '#0062FF',
      },
      'ionq_quantum': {
        name: 'IonQ Quantum',
        description: 'IonQ Trapped Ion',
        source: 'Trapped ion qubit superposition',
        icon: '⚛️',
        color: '#7C3AED',
      },
      'cryptographic_fallback': {
        name: 'Cryptographic RNG',
        description: 'Secure Fallback',
        source: 'Cryptographic PRNG',
        icon: '🔐',
        color: '#6B7280',
      },
    };
    
    return providers[providerName] || providers['cryptographic_fallback'];
  }
}

export default new QuantumService();

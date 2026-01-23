/**
 * Quantum RNG Service
 * ===================
 * 
 * Frontend service for quantum-certified password generation.
 * Communicates with the quantum RNG backend API.
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';
const API_BASE = `${API_URL}/api/security/quantum`;

class QuantumService {
  constructor() {
    this._poolCache = null;
    this._poolCacheTime = null;
    this._poolCacheTTL = 30000; // 30 seconds
  }

  /**
   * Generate a quantum-certified password
   * @param {Object} options - Generation options
   * @returns {Promise<{password: string, certificate: Object, quantumCertified: boolean}>}
   */
  async generateQuantumPassword(options = {}) {
    const {
      length = 16,
      uppercase = true,
      lowercase = true,
      numbers = true,
      symbols = true,
      customCharset = null,
      saveCertificate = true,
    } = options;

    try {
      const response = await axios.post(`${API_BASE}/generate-password/`, {
        length,
        uppercase,
        lowercase,
        numbers,
        symbols,
        custom_charset: customCharset,
        save_certificate: saveCertificate,
      });

      return {
        success: true,
        password: response.data.password,
        certificate: response.data.certificate,
        quantumCertified: response.data.quantum_certified,
      };
    } catch (error) {
      console.error('Quantum password generation failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Get raw quantum random bytes
   * @param {number} count - Number of bytes (1-256)
   * @param {string} format - 'hex' or 'base64'
   * @returns {Promise<{bytes: string, provider: string}>}
   */
  async getRandomBytes(count = 32, format = 'hex') {
    try {
      const response = await axios.get(`${API_BASE}/random-bytes/`, {
        params: { count, format }
      });

      return {
        success: true,
        bytes: response.data.bytes,
        format: response.data.format,
        count: response.data.count,
        provider: response.data.provider,
      };
    } catch (error) {
      console.error('Random bytes fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Get a quantum certificate by ID
   * @param {string} certificateId - UUID of the certificate
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
      console.error('Certificate fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * List user's quantum certificates
   * @param {number} limit - Maximum number to return
   * @returns {Promise<{certificates: Array, total: number}>}
   */
  async listCertificates(limit = 20) {
    try {
      const response = await axios.get(`${API_BASE}/certificates/`, {
        params: { limit }
      });
      return {
        success: true,
        certificates: response.data.certificates,
        total: response.data.total,
      };
    } catch (error) {
      console.error('Certificate listing failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Get quantum entropy pool status
   * @returns {Promise<{pool: Object, providers: Object}>}
   */
  async getPoolStatus() {
    // Return cached value if fresh
    if (this._poolCache && Date.now() - this._poolCacheTime < this._poolCacheTTL) {
      return { success: true, ...this._poolCache };
    }

    try {
      const response = await axios.get(`${API_BASE}/pool-status/`);
      
      this._poolCache = {
        pool: response.data.pool,
        providers: response.data.providers,
      };
      this._poolCacheTime = Date.now();

      return {
        success: true,
        pool: response.data.pool,
        providers: response.data.providers,
      };
    } catch (error) {
      console.error('Pool status fetch failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Check if quantum RNG is available
   * @returns {Promise<boolean>}
   */
  async isQuantumAvailable() {
    const status = await this.getPoolStatus();
    if (!status.success) return false;
    
    // Check if any true quantum provider is available
    const providers = status.providers;
    return providers?.anu_qrng?.available || 
           providers?.ibm_quantum?.available ||
           providers?.ionq_quantum?.available;
  }

  /**
   * Get provider info by name
   * @param {string} providerName - Provider identifier
   * @returns {Object}
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
      'noaa_ocean_wave': {
        name: 'NOAA Ocean Wave',
        description: 'National Data Buoy Center',
        source: 'Ocean wave patterns & temperature',
        icon: '🌊',
        color: '#0077B6',
        tagline: 'Powered by the ocean\'s chaos',
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

  /**
   * Format certificate for display
   * @param {Object} certificate - Raw certificate object
   * @returns {Object}
   */
  formatCertificateForDisplay(certificate) {
    const providerInfo = this.getProviderInfo(certificate.provider);
    
    return {
      id: certificate.certificate_id,
      provider: providerInfo,
      source: certificate.quantum_source,
      entropyBits: certificate.entropy_bits,
      timestamp: new Date(certificate.generation_timestamp),
      timestampFormatted: new Date(certificate.generation_timestamp).toLocaleString(),
      circuitId: certificate.circuit_id,
      signature: certificate.signature,
      isQuantum: certificate.provider !== 'cryptographic_fallback',
    };
  }
}

// Export singleton
const quantumService = new QuantumService();
export default quantumService;

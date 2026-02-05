/**
 * QuantumService Tests
 * ====================
 * 
 * Unit tests for the quantum password generation service.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

// Mock axios
vi.mock('axios');

// Import service after mocking
import quantumService from '../quantumService';

describe('QuantumService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear cache
    quantumService._poolCache = null;
    quantumService._poolCacheTime = null;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('generateQuantumPassword', () => {
    it('should generate a quantum password successfully', async () => {
      const mockResponse = {
        data: {
          success: true,
          password: 'xK9mP2nL5qR8', // gitleaks:allow
          certificate: {
            certificate_id: 'abc-123',
            provider: 'anu_qrng',
            entropy_bits: 128,
            signature: 'test-sig'
          },
          quantum_certified: true
        }
      };
      
      axios.post.mockResolvedValue(mockResponse);
      
      const result = await quantumService.generateQuantumPassword({
        length: 16,
        uppercase: true,
        lowercase: true,
        numbers: true,
        symbols: false
      });
      
      expect(result.success).toBe(true);
      expect(result.password).toBe('xK9mP2nL5qR8');
      expect(result.certificate).toBeDefined();
      expect(result.quantumCertified).toBe(true);
    });

    it('should handle generation errors gracefully', async () => {
      axios.post.mockRejectedValue(new Error('Network error'));
      
      const result = await quantumService.generateQuantumPassword({ length: 16 });
      
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('should use default options when none provided', async () => {
      axios.post.mockResolvedValue({
        data: {
          success: true,
          password: 'testpassword',
          certificate: {},
          quantum_certified: true
        }
      });
      
      await quantumService.generateQuantumPassword();
      
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/generate-password/'),
        expect.objectContaining({
          length: 16,
          uppercase: true,
          lowercase: true,
          numbers: true,
          symbols: true
        })
      );
    });
  });

  describe('getRandomBytes', () => {
    it('should fetch random bytes in hex format', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          bytes: 'a1b2c3d4e5f6',
          format: 'hex',
          count: 6,
          provider: 'anu_qrng'
        }
      });
      
      const result = await quantumService.getRandomBytes(6, 'hex');
      
      expect(result.success).toBe(true);
      expect(result.bytes).toBe('a1b2c3d4e5f6');
      expect(result.format).toBe('hex');
      expect(result.provider).toBe('anu_qrng');
    });

    it('should fetch random bytes in base64 format', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          bytes: 'YWJjMTIz',
          format: 'base64',
          count: 6,
          provider: 'anu_qrng'
        }
      });
      
      const result = await quantumService.getRandomBytes(6, 'base64');
      
      expect(result.format).toBe('base64');
    });

    it('should handle errors', async () => {
      axios.get.mockRejectedValue(new Error('API error'));
      
      const result = await quantumService.getRandomBytes(32);
      
      expect(result.success).toBe(false);
    });
  });

  describe('getCertificate', () => {
    it('should fetch a certificate by ID', async () => {
      const certId = 'cert-uuid-123';
      axios.get.mockResolvedValue({
        data: {
          success: true,
          certificate: {
            certificate_id: certId,
            provider: 'ibm_quantum',
            entropy_bits: 256
          }
        }
      });
      
      const result = await quantumService.getCertificate(certId);
      
      expect(result.success).toBe(true);
      expect(result.certificate.certificate_id).toBe(certId);
    });

    it('should handle not found errors', async () => {
      axios.get.mockRejectedValue({
        response: {
          data: { error: 'Certificate not found' }
        }
      });
      
      const result = await quantumService.getCertificate('invalid-id');
      
      expect(result.success).toBe(false);
    });
  });

  describe('listCertificates', () => {
    it('should list user certificates', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          certificates: [
            { certificate_id: '1', provider: 'anu_qrng' },
            { certificate_id: '2', provider: 'ibm_quantum' }
          ],
          total: 2
        }
      });
      
      const result = await quantumService.listCertificates(20);
      
      expect(result.success).toBe(true);
      expect(result.certificates).toHaveLength(2);
      expect(result.total).toBe(2);
    });
  });

  describe('getPoolStatus', () => {
    it('should fetch pool status', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          pool: {
            total_bytes_available: 2048,
            health: 'good'
          },
          providers: {
            anu_qrng: { available: true },
            ibm_quantum: { available: false }
          }
        }
      });
      
      const result = await quantumService.getPoolStatus();
      
      expect(result.success).toBe(true);
      expect(result.pool.health).toBe('good');
      expect(result.providers.anu_qrng.available).toBe(true);
    });

    it('should use cached status within TTL', async () => {
      // First call
      axios.get.mockResolvedValue({
        data: {
          success: true,
          pool: { health: 'good' },
          providers: {}
        }
      });
      
      await quantumService.getPoolStatus();
      
      // Second call (should use cache)
      const result = await quantumService.getPoolStatus();
      
      expect(result.success).toBe(true);
      expect(axios.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('isQuantumAvailable', () => {
    it('should return true when quantum provider available', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          pool: {},
          providers: {
            anu_qrng: { available: true },
            ibm_quantum: { available: false }
          }
        }
      });
      
      const result = await quantumService.isQuantumAvailable();
      
      expect(result).toBe(true);
    });

    it('should return false when no quantum providers available', async () => {
      axios.get.mockResolvedValue({
        data: {
          success: true,
          pool: {},
          providers: {
            anu_qrng: { available: false },
            ibm_quantum: { available: false }
          }
        }
      });
      
      const result = await quantumService.isQuantumAvailable();
      
      expect(result).toBe(false);
    });
  });

  describe('getProviderInfo', () => {
    it('should return ANU provider info', () => {
      const info = quantumService.getProviderInfo('anu_qrng');
      
      expect(info.name).toBe('ANU Quantum RNG');
      expect(info.source).toBe('Quantum vacuum fluctuations');
      expect(info.color).toBe('#FFD700');
    });

    it('should return IBM provider info', () => {
      const info = quantumService.getProviderInfo('ibm_quantum');
      
      expect(info.name).toBe('IBM Quantum');
      expect(info.color).toBe('#0062FF');
    });

    it('should return IonQ provider info', () => {
      const info = quantumService.getProviderInfo('ionq_quantum');
      
      expect(info.name).toBe('IonQ Quantum');
      expect(info.source).toBe('Trapped ion qubit superposition');
    });

    it('should return fallback for unknown provider', () => {
      const info = quantumService.getProviderInfo('unknown');
      
      expect(info.name).toBe('Cryptographic RNG');
    });
  });

  describe('formatCertificateForDisplay', () => {
    it('should format certificate correctly', () => {
      const rawCert = {
        certificate_id: 'cert-123',
        provider: 'anu_qrng',
        quantum_source: 'vacuum_fluctuations',
        entropy_bits: 128,
        generation_timestamp: '2026-01-16T12:00:00Z',
        circuit_id: null,
        signature: 'sig-abc'
      };
      
      const formatted = quantumService.formatCertificateForDisplay(rawCert);
      
      expect(formatted.id).toBe('cert-123');
      expect(formatted.provider.name).toBe('ANU Quantum RNG');
      expect(formatted.entropyBits).toBe(128);
      expect(formatted.isQuantum).toBe(true);
      expect(formatted.timestamp).toBeInstanceOf(Date);
    });

    it('should mark fallback as non-quantum', () => {
      const rawCert = {
        certificate_id: 'cert-456',
        provider: 'cryptographic_fallback',
        quantum_source: 'cryptographic_prng',
        entropy_bits: 128,
        generation_timestamp: '2026-01-16T12:00:00Z',
        signature: 'sig-xyz'
      };
      
      const formatted = quantumService.formatCertificateForDisplay(rawCert);
      
      expect(formatted.isQuantum).toBe(false);
    });
  });
});

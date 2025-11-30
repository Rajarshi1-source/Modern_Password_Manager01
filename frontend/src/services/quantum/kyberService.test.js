/**
 * Tests for Kyber Service (Post-Quantum Cryptography)
 * 
 * @jest-environment jsdom
 */

import { describe, it, expect, beforeAll, afterEach } from 'vitest';
import { kyberService, KyberService, KyberError, KYBER_CONSTANTS } from './kyberService';

describe('KyberService', () => {
  beforeAll(async () => {
    // Initialize the service
    await kyberService.initialize();
  });

  afterEach(() => {
    // Reset metrics after each test
    kyberService.resetMetrics();
  });

  describe('Initialization', () => {
    it('should initialize successfully', () => {
      expect(kyberService.isInitialized).toBe(true);
    });

    it('should not initialize twice', async () => {
      const promise1 = kyberService.initialize();
      const promise2 = kyberService.initialize();
      
      await Promise.all([promise1, promise2]);
      
      expect(kyberService.isInitialized).toBe(true);
    });

    it('should provide algorithm information', () => {
      const info = kyberService.getAlgorithmInfo();
      
      expect(info).toHaveProperty('algorithm');
      expect(info).toHaveProperty('quantumResistant');
      expect(info).toHaveProperty('securityLevel');
      expect(info).toHaveProperty('status');
    });
  });

  describe('Keypair Generation', () => {
    it('should generate a valid keypair', async () => {
      const keypair = await kyberService.generateKeypair();
      
      expect(keypair).toHaveProperty('publicKey');
      expect(keypair).toHaveProperty('privateKey');
      expect(keypair.publicKey).toBeInstanceOf(Uint8Array);
      expect(keypair.privateKey).toBeInstanceOf(Uint8Array);
      expect(keypair.publicKey.length).toBeGreaterThan(0);
      expect(keypair.privateKey.length).toBeGreaterThan(0);
    });

    it('should generate unique keypairs', async () => {
      const keypair1 = await kyberService.generateKeypair();
      const keypair2 = await kyberService.generateKeypair();
      
      // Public keys should be different
      expect(keypair1.publicKey).not.toEqual(keypair2.publicKey);
      expect(keypair1.privateKey).not.toEqual(keypair2.privateKey);
    });

    it('should validate generated keys', async () => {
      const keypair = await kyberService.generateKeypair();
      
      expect(kyberService.validateKey(keypair.publicKey, 'public')).toBe(true);
      expect(kyberService.validateKey(keypair.privateKey, 'private')).toBe(true);
    });

    it('should track keypair generation metrics', async () => {
      const metricsBefore = kyberService.getMetrics();
      
      await kyberService.generateKeypair();
      
      const metricsAfter = kyberService.getMetrics();
      expect(metricsAfter.keypairGenerations).toBe(metricsBefore.keypairGenerations + 1);
    });
  });

  describe('Encapsulation & Decapsulation', () => {
    it('should encapsulate and produce ciphertext and shared secret', async () => {
      const keypair = await kyberService.generateKeypair();
      const result = await kyberService.encapsulate(keypair.publicKey);
      
      expect(result).toHaveProperty('ciphertext');
      expect(result).toHaveProperty('sharedSecret');
      expect(result.ciphertext).toBeInstanceOf(Uint8Array);
      expect(result.sharedSecret).toBeInstanceOf(Uint8Array);
      expect(result.ciphertext.length).toBeGreaterThan(0);
      expect(result.sharedSecret.length).toBeGreaterThan(0);
    });

    it('should decapsulate and recover the shared secret', async () => {
      const keypair = await kyberService.generateKeypair();
      const { ciphertext, sharedSecret } = await kyberService.encapsulate(keypair.publicKey);
      
      const recoveredSecret = await kyberService.decapsulate(ciphertext, keypair.privateKey);
      
      expect(recoveredSecret).toBeInstanceOf(Uint8Array);
      expect(recoveredSecret.length).toBe(sharedSecret.length);
      expect(recoveredSecret).toEqual(sharedSecret);
    });

    it('should produce consistent shared secrets', async () => {
      const keypair = await kyberService.generateKeypair();
      
      // Multiple encapsulations should produce different ciphertexts
      const result1 = await kyberService.encapsulate(keypair.publicKey);
      const result2 = await kyberService.encapsulate(keypair.publicKey);
      
      expect(result1.ciphertext).not.toEqual(result2.ciphertext);
      
      // But decapsulation should work for both
      const secret1 = await kyberService.decapsulate(result1.ciphertext, keypair.privateKey);
      const secret2 = await kyberService.decapsulate(result2.ciphertext, keypair.privateKey);
      
      expect(secret1).toEqual(result1.sharedSecret);
      expect(secret2).toEqual(result2.sharedSecret);
    });

    it('should fail to decapsulate with wrong private key', async () => {
      const keypair1 = await kyberService.generateKeypair();
      const keypair2 = await kyberService.generateKeypair();
      
      const { ciphertext, sharedSecret } = await kyberService.encapsulate(keypair1.publicKey);
      
      // Try to decapsulate with wrong key
      const wrongSecret = await kyberService.decapsulate(ciphertext, keypair2.privateKey);
      
      // Secrets should not match
      expect(wrongSecret).not.toEqual(sharedSecret);
    });

    it('should track encapsulation and decapsulation metrics', async () => {
      const keypair = await kyberService.generateKeypair();
      const metricsBefore = kyberService.getMetrics();
      
      const { ciphertext } = await kyberService.encapsulate(keypair.publicKey);
      await kyberService.decapsulate(ciphertext, keypair.privateKey);
      
      const metricsAfter = kyberService.getMetrics();
      expect(metricsAfter.encapsulations).toBe(metricsBefore.encapsulations + 1);
      expect(metricsAfter.decapsulations).toBe(metricsBefore.decapsulations + 1);
    });
  });

  describe('Error Handling', () => {
    it('should throw error for invalid public key in encapsulation', async () => {
      await expect(async () => {
        await kyberService.encapsulate(null);
      }).rejects.toThrow(KyberError);
      
      await expect(async () => {
        await kyberService.encapsulate(new Uint8Array(10)); // Wrong size
      }).rejects.toThrow();
    });

    it('should throw error for invalid inputs in decapsulation', async () => {
      const keypair = await kyberService.generateKeypair();
      
      await expect(async () => {
        await kyberService.decapsulate(null, keypair.privateKey);
      }).rejects.toThrow(KyberError);
      
      await expect(async () => {
        await kyberService.decapsulate(new Uint8Array(10), keypair.privateKey);
      }).rejects.toThrow();
    });

    it('should track errors in metrics', async () => {
      const metricsBefore = kyberService.getMetrics();
      
      try {
        await kyberService.encapsulate(null);
      } catch (error) {
        // Expected error
      }
      
      const metricsAfter = kyberService.getMetrics();
      expect(metricsAfter.errors).toBeGreaterThan(metricsBefore.errors);
    });
  });

  describe('Serialization', () => {
    it('should convert buffer to Base64 and back', () => {
      const original = new Uint8Array([1, 2, 3, 4, 5, 255, 128, 0]);
      
      const base64 = kyberService.arrayBufferToBase64(original);
      expect(typeof base64).toBe('string');
      
      const recovered = kyberService.base64ToArrayBuffer(base64);
      expect(recovered).toEqual(original);
    });

    it('should convert buffer to hex and back', () => {
      const original = new Uint8Array([1, 2, 3, 4, 5, 255, 128, 0]);
      
      const hex = kyberService.arrayBufferToHex(original);
      expect(typeof hex).toBe('string');
      expect(hex).toBe('010203040' + '5ff8000');
      
      const recovered = kyberService.hexToArrayBuffer(hex);
      expect(recovered).toEqual(original);
    });

    it('should handle large buffers', () => {
      const large = new Uint8Array(10000);
      for (let i = 0; i < large.length; i++) {
        large[i] = i % 256;
      }
      
      const base64 = kyberService.arrayBufferToBase64(large);
      const recovered = kyberService.base64ToArrayBuffer(base64);
      
      expect(recovered).toEqual(large);
    });
  });

  describe('Security Features', () => {
    it('should indicate if quantum resistant', () => {
      const isQR = kyberService.isQuantumResistant();
      expect(typeof isQR).toBe('boolean');
    });

    it('should securely clear buffers', () => {
      const sensitive = new Uint8Array([1, 2, 3, 4, 5]);
      kyberService.secureClear(sensitive);
      
      expect(Array.from(sensitive)).toEqual([0, 0, 0, 0, 0]);
    });

    it('should validate key formats', async () => {
      const keypair = await kyberService.generateKeypair();
      
      expect(kyberService.validateKey(keypair.publicKey, 'public')).toBe(true);
      expect(kyberService.validateKey(keypair.privateKey, 'private')).toBe(true);
      expect(kyberService.validateKey(new Uint8Array(10), 'public')).toBe(false);
    });
  });

  describe('Performance', () => {
    it('should complete full cycle in reasonable time', async () => {
      const start = performance.now();
      
      const keypair = await kyberService.generateKeypair();
      const { ciphertext, sharedSecret } = await kyberService.encapsulate(keypair.publicKey);
      const recovered = await kyberService.decapsulate(ciphertext, keypair.privateKey);
      
      const elapsed = performance.now() - start;
      
      expect(recovered).toEqual(sharedSecret);
      expect(elapsed).toBeLessThan(1000); // Should complete in < 1 second
    });

    it('should track average operation times', async () => {
      // Perform multiple operations
      for (let i = 0; i < 5; i++) {
        const keypair = await kyberService.generateKeypair();
        const { ciphertext } = await kyberService.encapsulate(keypair.publicKey);
        await kyberService.decapsulate(ciphertext, keypair.privateKey);
      }
      
      const metrics = kyberService.getMetrics();
      
      expect(metrics.averageKeypairTime).toBeGreaterThan(0);
      expect(metrics.averageEncapsulateTime).toBeGreaterThan(0);
      expect(metrics.averageDecapsulateTime).toBeGreaterThan(0);
    });
  });

  describe('Constants', () => {
    it('should export correct constants', () => {
      expect(KYBER_CONSTANTS).toHaveProperty('PUBLIC_KEY_SIZE');
      expect(KYBER_CONSTANTS).toHaveProperty('SECRET_KEY_SIZE');
      expect(KYBER_CONSTANTS).toHaveProperty('CIPHERTEXT_SIZE');
      expect(KYBER_CONSTANTS).toHaveProperty('SHARED_SECRET_SIZE');
      expect(KYBER_CONSTANTS).toHaveProperty('SECURITY_LEVEL');
      
      expect(KYBER_CONSTANTS.PUBLIC_KEY_SIZE).toBe(1184);
      expect(KYBER_CONSTANTS.SECRET_KEY_SIZE).toBe(2400);
      expect(KYBER_CONSTANTS.CIPHERTEXT_SIZE).toBe(1088);
      expect(KYBER_CONSTANTS.SHARED_SECRET_SIZE).toBe(32);
    });
  });
});

describe('Multiple KyberService Instances', () => {
  it('should allow multiple instances', async () => {
    const service1 = new KyberService();
    const service2 = new KyberService();
    
    await service1.initialize();
    await service2.initialize();
    
    expect(service1.isInitialized).toBe(true);
    expect(service2.isInitialized).toBe(true);
  });

  it('should have independent metrics', async () => {
    const service1 = new KyberService();
    const service2 = new KyberService();
    
    await service1.initialize();
    await service2.initialize();
    
    await service1.generateKeypair();
    
    const metrics1 = service1.getMetrics();
    const metrics2 = service2.getMetrics();
    
    expect(metrics1.keypairGenerations).toBe(1);
    expect(metrics2.keypairGenerations).toBe(0);
  });
});


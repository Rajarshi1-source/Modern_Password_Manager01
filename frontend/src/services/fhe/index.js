/**
 * FHE (Fully Homomorphic Encryption) Service Module
 * 
 * Exports:
 * - fheService: Main FHE client service
 * - fheKeyManager: Key management service for IndexedDB storage
 * - FHE_CONFIG: Configuration constants
 * - EncryptionTier: Encryption tier enum
 */

export { 
  fheService, 
  FHE_CONFIG, 
  EncryptionTier,
  default 
} from './fheService';

export { 
  fheKeyManager, 
  DB_CONFIG, 
  KEY_SETTINGS 
} from './fheKeys';


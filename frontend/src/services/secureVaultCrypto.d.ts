export interface EncryptedPackage {
    v: '2.0';
    alg: 'AES-256-GCM-ARGON2ID';
    nonce: string;        // base64
    ct: string;           // base64
    compressed: boolean;
    ts: number;           // unix ms
    aad?: boolean;
  }
  
  export interface CryptoStatus {
    initialized: boolean;
    deviceCapability: 'high' | 'medium' | 'low';
    algorithm: string;
    keyLength: number;
    argon2Params: { time: number; mem: number; parallelism: number };
    webcryptoAvailable: boolean;
    hardwareAccelerated: boolean;
  }
  
  export interface PasswordOptions {
    uppercase?: boolean;
    lowercase?: boolean;
    numbers?: boolean;
    symbols?: boolean;
    excludeAmbiguous?: boolean;
    customChars?: string;
  }
  
  export interface EncryptOptions {
    compress?: boolean;
    additionalData?: Record<string, unknown> | null;
  }
  
  export declare class SecureVaultCrypto {
    initialized: boolean;
    deviceCapability: 'high' | 'medium' | 'low';
  
    initialize(masterPassword: string, salt: Uint8Array | string): Promise<boolean>;
    deriveKeyFromPassword(masterPassword: string, salt: Uint8Array | string): Promise<CryptoKey>;
    encrypt(data: object | string, options?: EncryptOptions): Promise<EncryptedPackage>;
    decrypt(encryptedPackage: EncryptedPackage | string, options?: EncryptOptions): Promise<unknown>;
    batchEncrypt(items: Array<{ data: unknown; options?: EncryptOptions }>): Promise<Array<{ index: number; encrypted?: EncryptedPackage; success: boolean; error?: string }>>;
    batchDecrypt(encryptedItems: Array<{ encryptedPackage: EncryptedPackage; options?: EncryptOptions }>): Promise<Array<{ index: number; decrypted?: unknown; success: boolean; error?: string }>>;
    generateAuthHash(masterPassword: string, salt: Uint8Array | string): Promise<string>;
    generatePassword(length?: number, options?: PasswordOptions): string;
    generateSalt(): Uint8Array;
    clearKeys(): void;
    getStatus(): CryptoStatus;
  }
  
  export declare function getSecureVaultCrypto(): SecureVaultCrypto;
  export declare function resetSecureVaultCrypto(): void;
  export default SecureVaultCrypto;
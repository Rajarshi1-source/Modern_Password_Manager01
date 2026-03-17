export interface KyberKeypair {
    publicKey: Uint8Array;
    privateKey: Uint8Array;
    algorithm: 'Kyber768+X25519' | 'X25519';
    keySize: number;
    timestamp: number;
    kyberPublicKey?: Uint8Array;
    x25519PublicKey?: Uint8Array;
  }
  
  export interface EncapsulationResult {
    ciphertext: Uint8Array;
    sharedSecret: Uint8Array;
    algorithm: string;
    ciphertextSize: number;
    sharedSecretSize: number;
    timestamp: number;
  }
  
  export interface AlgorithmInfo {
    algorithm: string;
    mode: string;
    quantumResistant: boolean;
    publicKeySize: number;
    privateKeySize: number;
    ciphertextSize: number;
    sharedSecretSize: number;
    securityLevel: string;
    status: string;
    initialized: boolean;
    metrics: KyberMetrics;
  }
  
  export interface KyberMetrics {
    keypairGenerations: number;
    encapsulations: number;
    decapsulations: number;
    errors: number;
    fallbackUsed: number;
    averageKeypairTime: number;
    averageEncapsulateTime: number;
    averageDecapsulateTime: number;
  }
  
  export declare class KyberError extends Error {
    code: string;
    originalError: Error | null;
    timestamp: string;
  }
  
  export declare class KyberService {
    isInitialized: boolean;
    useFallback: boolean;
  
    initialize(): Promise<void>;
    generateKeypair(): Promise<KyberKeypair>;
    encapsulate(publicKey: Uint8Array): Promise<EncapsulationResult>;
    decapsulate(ciphertext: Uint8Array, privateKey: Uint8Array): Promise<Uint8Array>;
    getAlgorithmInfo(): AlgorithmInfo;
    getMetrics(): KyberMetrics;
    isQuantumResistant(): boolean;
    validateKey(key: Uint8Array, keyType: 'public' | 'private'): boolean;
    secureClear(buffer: Uint8Array): void;
    arrayBufferToBase64(buffer: Uint8Array | ArrayBuffer): string;
    base64ToArrayBuffer(base64: string): Uint8Array;
    resetMetrics(): void;
  }
  
  export declare const kyberService: KyberService;
  
  export declare const KYBER_CONSTANTS: {
    PUBLIC_KEY_SIZE: 1184;
    SECRET_KEY_SIZE: 2400;
    CIPHERTEXT_SIZE: 1088;
    SHARED_SECRET_SIZE: 32;
    HYBRID_SHARED_SECRET_SIZE: 64;
    X25519_KEY_SIZE: 32;
    SECURITY_LEVEL: string;
  };
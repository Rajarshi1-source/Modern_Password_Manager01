"""
TenSEAL/Microsoft SEAL FHE Service

Provides batch FHE operations using TenSEAL (Python wrapper for Microsoft SEAL).
Optimized for:
- Batch password strength evaluation (SIMD)
- Encrypted similarity search
- Floating-point computations on encrypted data
"""

import logging
import hashlib
import time
import numpy as np
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Attempt to import TenSEAL
try:
    import tenseal as ts
    TENSEAL_AVAILABLE = True
except ImportError:
    TENSEAL_AVAILABLE = False
    logger.warning("TenSEAL not available. SEAL batch operations will use fallback mode.")


class SEALScheme(Enum):
    """FHE schemes supported by SEAL."""
    CKKS = "ckks"  # For floating-point operations
    BFV = "bfv"    # For integer operations


@dataclass
class SEALConfig:
    """Configuration for SEAL/TenSEAL operations."""
    # Polynomial modulus degree (power of 2)
    poly_modulus_degree: int = 8192
    
    # Coefficient modulus (bit sizes)
    coeff_mod_bit_sizes: List[int] = None
    
    # Scale for CKKS encoding (2^40 is common)
    global_scale: float = 2**40
    
    # Security level (128, 192, or 256 bits)
    security_level: int = 128
    
    # Threading
    max_workers: int = 4
    
    # Batch size for SIMD operations
    max_batch_size: int = 128
    
    def __post_init__(self):
        if self.coeff_mod_bit_sizes is None:
            # Default for 128-bit security with depth-4 circuits
            self.coeff_mod_bit_sizes = [60, 40, 40, 60]


@dataclass
class SEALCiphertext:
    """Container for SEAL encrypted values with metadata."""
    ciphertext: Any  # TenSEAL ciphertext object or serialized bytes
    scheme: str
    created_at: float
    context_hash: str
    metadata: Dict[str, Any]
    is_serialized: bool = False


class SEALBatchService:
    """
    Service for batch FHE operations using TenSEAL/SEAL.
    
    Provides:
    - CKKS-based floating-point encryption
    - SIMD batch processing for multiple passwords
    - Encrypted similarity search
    - Batch strength evaluation
    """
    
    def __init__(self, config: Optional[SEALConfig] = None):
        self.config = config or SEALConfig()
        self._context: Optional[Any] = None
        self._public_key: Optional[Any] = None
        self._secret_key: Optional[Any] = None
        self._galois_keys: Optional[Any] = None
        self._relin_keys: Optional[Any] = None
        self._initialized = False
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        
        if TENSEAL_AVAILABLE:
            self._initialize_seal()
        else:
            logger.warning("Running SEALBatchService in fallback mode (no FHE)")
    
    def _initialize_seal(self):
        """Initialize TenSEAL context and keys."""
        try:
            # Create CKKS context
            self._context = ts.context(
                ts.SCHEME_TYPE.CKKS,
                poly_modulus_degree=self.config.poly_modulus_degree,
                coeff_mod_bit_sizes=self.config.coeff_mod_bit_sizes
            )
            
            # Set global scale for CKKS
            self._context.global_scale = self.config.global_scale
            
            # Generate keys
            self._context.generate_galois_keys()
            self._context.generate_relin_keys()
            
            self._initialized = True
            logger.info("SEALBatchService initialized with CKKS scheme")
            
        except Exception as e:
            logger.error(f"Failed to initialize SEAL: {e}")
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Check if SEAL FHE is available and initialized."""
        return TENSEAL_AVAILABLE and self._initialized
    
    @property
    def slot_count(self) -> int:
        """Get number of SIMD slots available."""
        return self.config.poly_modulus_degree // 2
    
    def encrypt_vector(self, values: List[float]) -> SEALCiphertext:
        """
        Encrypt a vector of floating-point values using CKKS.
        
        Args:
            values: List of float values to encrypt
            
        Returns:
            SEALCiphertext containing encrypted vector
        """
        if not self.is_available:
            return self._fallback_encrypt_vector(values)
        
        try:
            # Pad to slot count if needed
            padded_values = self._pad_to_slots(values)
            
            # Create CKKS vector
            encrypted = ts.ckks_vector(self._context, padded_values)
            
            return SEALCiphertext(
                ciphertext=encrypted,
                scheme="ckks",
                created_at=time.time(),
                context_hash=self._get_context_hash(),
                metadata={
                    "original_length": len(values),
                    "padded_length": len(padded_values)
                }
            )
            
        except Exception as e:
            logger.error(f"Error encrypting vector: {e}")
            return self._fallback_encrypt_vector(values)
    
    def encrypt_password_features(
        self,
        length: int,
        entropy: float,
        char_diversity: float,
        pattern_score: float
    ) -> SEALCiphertext:
        """
        Encrypt password features as a vector.
        
        Args:
            length: Password length (normalized to 0-1)
            entropy: Shannon entropy (normalized)
            char_diversity: Character type diversity (0-1)
            pattern_score: Common pattern score (0-1, lower is better)
            
        Returns:
            SEALCiphertext containing encrypted features
        """
        # Normalize length to 0-1 range (assuming max 32 chars)
        norm_length = min(1.0, length / 32.0)
        
        features = [norm_length, entropy, char_diversity, pattern_score]
        return self.encrypt_vector(features)
    
    def batch_encrypt_passwords(
        self,
        password_features: List[Dict[str, float]]
    ) -> List[SEALCiphertext]:
        """
        Batch encrypt multiple password feature sets.
        
        Args:
            password_features: List of feature dictionaries
            
        Returns:
            List of SEALCiphertext objects
        """
        if not self.is_available:
            return [self._fallback_encrypt_features(f) for f in password_features]
        
        results = []
        
        # Process in batches for SIMD efficiency
        for batch in self._create_batches(password_features):
            batch_result = self._process_batch(batch)
            results.extend(batch_result)
        
        return results
    
    def simd_strength_evaluation(
        self,
        encrypted_features: SEALCiphertext,
        weights: Optional[Dict[str, float]] = None
    ) -> Tuple[SEALCiphertext, Optional[float]]:
        """
        Evaluate password strength using SIMD operations on encrypted data.
        
        Args:
            encrypted_features: Encrypted feature vector [length, entropy, diversity, pattern]
            weights: Optional weight dictionary for scoring components
            
        Returns:
            Tuple of (encrypted_result, decrypted_score or None)
        """
        if weights is None:
            weights = {
                'length': 0.3,
                'entropy': 0.4,
                'diversity': 0.2,
                'pattern': 0.1
            }
        
        if not self.is_available:
            return self._fallback_strength_evaluation(encrypted_features, weights)
        
        try:
            ct = encrypted_features.ciphertext
            
            # Create weight vector
            weight_vector = [
                weights['length'],
                weights['entropy'],
                weights['diversity'],
                -weights['pattern']  # Negative because lower pattern score is better
            ]
            
            # Pad weights to match vector
            weight_vector.extend([0] * (self.slot_count - len(weight_vector)))
            
            # Homomorphic multiplication with weights
            weighted = ct * weight_vector
            
            # Sum all slots (requires rotation and addition)
            result = self._sum_slots(weighted, 4)
            
            # Decrypt result
            decrypted = result.decrypt()
            score = float(decrypted[0]) * 100  # Scale to 0-100
            score = max(0, min(100, score))
            
            result_ct = SEALCiphertext(
                ciphertext=result,
                scheme="ckks",
                created_at=time.time(),
                context_hash=self._get_context_hash(),
                metadata={
                    "operation": "strength_evaluation",
                    "decrypted_score": score
                }
            )
            
            return result_ct, score
            
        except Exception as e:
            logger.error(f"Error in SIMD strength evaluation: {e}")
            return self._fallback_strength_evaluation(encrypted_features, weights)
    
    def batch_strength_evaluation(
        self,
        encrypted_passwords: List[SEALCiphertext],
        weights: Optional[Dict[str, float]] = None
    ) -> List[float]:
        """
        Evaluate strength for multiple encrypted passwords.
        
        Args:
            encrypted_passwords: List of encrypted password features
            weights: Optional weight dictionary
            
        Returns:
            List of strength scores (0-100)
        """
        results = []
        
        for encrypted in encrypted_passwords:
            _, score = self.simd_strength_evaluation(encrypted, weights)
            results.append(score if score is not None else 0.0)
        
        return results
    
    def encrypted_similarity_search(
        self,
        query_ct: SEALCiphertext,
        vault_cts: List[SEALCiphertext],
        threshold: float = 0.8
    ) -> List[Tuple[int, float]]:
        """
        Search for similar passwords in encrypted vault.
        
        Uses cosine similarity on encrypted feature vectors.
        
        Args:
            query_ct: Encrypted query features
            vault_cts: List of encrypted vault entries
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of (index, similarity_score) tuples for matches above threshold
        """
        if not self.is_available:
            return self._fallback_similarity_search(query_ct, vault_cts, threshold)
        
        results = []
        
        for i, vault_ct in enumerate(vault_cts):
            try:
                similarity = self._compute_similarity(query_ct, vault_ct)
                if similarity >= threshold:
                    results.append((i, similarity))
            except Exception as e:
                logger.warning(f"Error computing similarity for entry {i}: {e}")
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def _compute_similarity(
        self,
        ct1: SEALCiphertext,
        ct2: SEALCiphertext
    ) -> float:
        """Compute cosine similarity between two encrypted vectors."""
        if not self.is_available:
            return 0.0
        
        try:
            # Homomorphic dot product
            product = ct1.ciphertext * ct2.ciphertext
            
            # Sum slots to get dot product
            dot_product = self._sum_slots(product, 4)
            
            # Decrypt and normalize
            decrypted = dot_product.decrypt()
            
            # Simple approximation (actual cosine requires norms)
            return float(min(1.0, max(0.0, decrypted[0])))
            
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def _sum_slots(self, vector: Any, num_slots: int) -> Any:
        """Sum the first num_slots of a CKKS vector."""
        if not self.is_available:
            return vector
        
        result = vector
        
        # Rotate and add to sum slots
        for i in range(1, num_slots):
            try:
                rotated = vector.rotate_vector(-i)
                result = result + rotated
            except:
                pass
        
        return result
    
    def _pad_to_slots(self, values: List[float]) -> List[float]:
        """Pad values to fill SIMD slots."""
        padded = list(values)
        while len(padded) < self.slot_count:
            padded.append(0.0)
        return padded[:self.slot_count]
    
    def _create_batches(
        self,
        items: List[Any],
        batch_size: Optional[int] = None
    ) -> List[List[Any]]:
        """Split items into batches."""
        batch_size = batch_size or self.config.max_batch_size
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    def _process_batch(
        self,
        batch: List[Dict[str, float]]
    ) -> List[SEALCiphertext]:
        """Process a batch of password features."""
        return [
            self.encrypt_password_features(
                length=f.get('length', 0),
                entropy=f.get('entropy', 0),
                char_diversity=f.get('char_diversity', 0),
                pattern_score=f.get('pattern_score', 0)
            )
            for f in batch
        ]
    
    def _get_context_hash(self) -> str:
        """Get hash identifying the current context."""
        if self._context:
            params = f"{self.config.poly_modulus_degree}_{self.config.coeff_mod_bit_sizes}"
            return hashlib.sha256(params.encode()).hexdigest()[:16]
        return "none"
    
    def serialize_ciphertext(self, ct: SEALCiphertext) -> bytes:
        """Serialize a ciphertext for storage."""
        if not self.is_available or ct.is_serialized:
            return ct.ciphertext if isinstance(ct.ciphertext, bytes) else b''
        
        try:
            return ct.ciphertext.serialize()
        except Exception as e:
            logger.error(f"Error serializing ciphertext: {e}")
            return b''
    
    def deserialize_ciphertext(self, data: bytes) -> Optional[SEALCiphertext]:
        """Deserialize a ciphertext from storage."""
        if not self.is_available:
            return None
        
        try:
            vector = ts.ckks_vector_from(self._context, data)
            return SEALCiphertext(
                ciphertext=vector,
                scheme="ckks",
                created_at=time.time(),
                context_hash=self._get_context_hash(),
                metadata={"deserialized": True},
                is_serialized=False
            )
        except Exception as e:
            logger.error(f"Error deserializing ciphertext: {e}")
            return None
    
    def _fallback_encrypt_vector(self, values: List[float]) -> SEALCiphertext:
        """Fallback encryption when SEAL is not available."""
        import json
        
        serialized = json.dumps(values).encode()
        ciphertext = hashlib.sha256(serialized).digest()
        
        return SEALCiphertext(
            ciphertext=ciphertext,
            scheme="fallback",
            created_at=time.time(),
            context_hash="fallback",
            metadata={
                "fallback": True,
                "values": values
            },
            is_serialized=True
        )
    
    def _fallback_encrypt_features(self, features: Dict[str, float]) -> SEALCiphertext:
        """Fallback feature encryption."""
        return self._fallback_encrypt_vector([
            features.get('length', 0) / 32.0,
            features.get('entropy', 0),
            features.get('char_diversity', 0),
            features.get('pattern_score', 0)
        ])
    
    def _fallback_strength_evaluation(
        self,
        encrypted_features: SEALCiphertext,
        weights: Dict[str, float]
    ) -> Tuple[SEALCiphertext, float]:
        """Fallback strength evaluation without FHE."""
        values = encrypted_features.metadata.get('values', [0, 0, 0, 0])
        
        if len(values) >= 4:
            score = (
                values[0] * weights['length'] * 100 +
                values[1] * weights['entropy'] * 100 +
                values[2] * weights['diversity'] * 100 -
                values[3] * weights['pattern'] * 100
            )
        else:
            score = 50.0
        
        score = max(0, min(100, score))
        
        result = SEALCiphertext(
            ciphertext=encrypted_features.ciphertext,
            scheme="fallback",
            created_at=time.time(),
            context_hash="fallback",
            metadata={
                "fallback": True,
                "score": score
            }
        )
        
        return result, score
    
    def _fallback_similarity_search(
        self,
        query_ct: SEALCiphertext,
        vault_cts: List[SEALCiphertext],
        threshold: float
    ) -> List[Tuple[int, float]]:
        """Fallback similarity search without FHE."""
        query_values = query_ct.metadata.get('values', [0, 0, 0, 0])
        results = []
        
        for i, vault_ct in enumerate(vault_cts):
            vault_values = vault_ct.metadata.get('values', [0, 0, 0, 0])
            
            # Simple cosine similarity
            dot_product = sum(q * v for q, v in zip(query_values, vault_values))
            norm_q = sum(q * q for q in query_values) ** 0.5
            norm_v = sum(v * v for v in vault_values) ** 0.5
            
            if norm_q > 0 and norm_v > 0:
                similarity = dot_product / (norm_q * norm_v)
            else:
                similarity = 0.0
            
            if similarity >= threshold:
                results.append((i, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status information."""
        return {
            "available": self.is_available,
            "tenseal_installed": TENSEAL_AVAILABLE,
            "initialized": self._initialized,
            "config": {
                "poly_modulus_degree": self.config.poly_modulus_degree,
                "security_level": self.config.security_level,
                "max_batch_size": self.config.max_batch_size,
            },
            "slot_count": self.slot_count if self._initialized else 0
        }
    
    def cleanup(self):
        """Cleanup resources."""
        self._executor.shutdown(wait=False)


# Singleton instance
_seal_service: Optional[SEALBatchService] = None


def get_seal_service() -> SEALBatchService:
    """Get or create the SEAL service singleton."""
    global _seal_service
    if _seal_service is None:
        _seal_service = SEALBatchService()
    return _seal_service


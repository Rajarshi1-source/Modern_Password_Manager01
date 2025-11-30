"""
Concrete-Python FHE Service

Provides lightweight FHE operations using Zama's Concrete-Python library.
Optimized for simple operations like:
- Password length comparisons (encrypted)
- Character type counting (encrypted)
- Simple boolean operations on encrypted data
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Attempt to import concrete-python
try:
    import concrete.fhe as fhe
    from concrete.fhe import Configuration
    CONCRETE_AVAILABLE = True
except ImportError:
    CONCRETE_AVAILABLE = False
    logger.warning("concrete-python not available. FHE operations will use fallback mode.")


class ConcreteOperationType(Enum):
    """Types of operations supported by Concrete service."""
    PASSWORD_LENGTH = "password_length"
    CHARACTER_COUNT = "character_count"
    HOMOMORPHIC_COMPARE = "homomorphic_compare"
    STRENGTH_CIRCUIT = "strength_circuit"
    BOOLEAN_AND = "boolean_and"
    BOOLEAN_OR = "boolean_or"


@dataclass
class ConcreteConfig:
    """Configuration for Concrete-Python operations."""
    # Security parameters
    security_level: int = 128  # bits
    
    # Performance parameters
    enable_parallel: bool = True
    use_gpu: bool = False
    
    # Circuit parameters
    max_circuit_depth: int = 10
    parameter_selection_strategy: str = "v0"  # v0 or multi
    
    # Optimization
    enable_optimization: bool = True
    optimize_for_latency: bool = True


@dataclass
class EncryptedValue:
    """Container for encrypted values with metadata."""
    ciphertext: bytes
    operation_type: str
    encrypted_at: float
    circuit_hash: str
    metadata: Dict[str, Any]


class ConcreteService:
    """
    Service for lightweight FHE operations using Concrete-Python.
    
    Provides:
    - Password length encryption and comparison
    - Character count encryption
    - Simple boolean operations on encrypted data
    - Strength evaluation circuits
    """
    
    def __init__(self, config: Optional[ConcreteConfig] = None):
        self.config = config or ConcreteConfig()
        self._circuits: Dict[str, Any] = {}
        self._compiled_circuits: Dict[str, Any] = {}
        self._initialized = False
        
        if CONCRETE_AVAILABLE:
            self._initialize_concrete()
        else:
            logger.warning("Running ConcreteService in fallback mode (no FHE)")
    
    def _initialize_concrete(self):
        """Initialize Concrete-Python configuration."""
        try:
            self._configuration = Configuration(
                enable_unsafe_features=False,
                use_insecure_key_cache=False,
                insecure_key_cache_location=None,
                show_optimizer=False,
                show_progress=False,
                progress_tag=False,
            )
            
            # Pre-compile common circuits
            self._compile_standard_circuits()
            self._initialized = True
            logger.info("ConcreteService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Concrete: {e}")
            self._initialized = False
    
    def _compile_standard_circuits(self):
        """Pre-compile commonly used circuits for better performance."""
        if not CONCRETE_AVAILABLE:
            return
        
        try:
            # Password length comparison circuit
            self._compile_length_comparison_circuit()
            
            # Character count circuit
            self._compile_character_count_circuit()
            
            # Basic strength evaluation circuit
            self._compile_strength_circuit()
            
            logger.info("Standard circuits compiled successfully")
            
        except Exception as e:
            logger.error(f"Failed to compile standard circuits: {e}")
    
    def _compile_length_comparison_circuit(self):
        """Compile circuit for comparing encrypted password lengths."""
        if not CONCRETE_AVAILABLE:
            return
        
        @fhe.compiler({"length1": "encrypted", "length2": "encrypted"})
        def compare_lengths(length1, length2):
            """Compare two encrypted lengths, return 1 if length1 >= length2."""
            return (length1 >= length2).astype(int)
        
        try:
            # Create inputset for compilation
            inputset = [(i, j) for i in range(0, 128, 8) for j in range(0, 128, 8)]
            
            circuit = compare_lengths.compile(
                inputset,
                configuration=self._configuration
            )
            
            self._compiled_circuits['length_comparison'] = circuit
            logger.debug("Length comparison circuit compiled")
            
        except Exception as e:
            logger.warning(f"Could not compile length comparison circuit: {e}")
    
    def _compile_character_count_circuit(self):
        """Compile circuit for encrypted character type counting."""
        if not CONCRETE_AVAILABLE:
            return
        
        @fhe.compiler({
            "lowercase": "encrypted",
            "uppercase": "encrypted", 
            "digits": "encrypted",
            "special": "encrypted"
        })
        def count_character_types(lowercase, uppercase, digits, special):
            """Count total character types present (0-4)."""
            has_lower = (lowercase > 0).astype(int)
            has_upper = (uppercase > 0).astype(int)
            has_digit = (digits > 0).astype(int)
            has_special = (special > 0).astype(int)
            return has_lower + has_upper + has_digit + has_special
        
        try:
            inputset = [
                (l, u, d, s) 
                for l in range(0, 32, 4) 
                for u in range(0, 32, 4)
                for d in range(0, 16, 4)
                for s in range(0, 16, 4)
            ]
            
            circuit = count_character_types.compile(
                inputset,
                configuration=self._configuration
            )
            
            self._compiled_circuits['character_count'] = circuit
            logger.debug("Character count circuit compiled")
            
        except Exception as e:
            logger.warning(f"Could not compile character count circuit: {e}")
    
    def _compile_strength_circuit(self):
        """Compile circuit for basic password strength evaluation."""
        if not CONCRETE_AVAILABLE:
            return
        
        @fhe.compiler({
            "length": "encrypted",
            "char_types": "encrypted",
            "has_common_pattern": "encrypted"
        })
        def evaluate_strength(length, char_types, has_common_pattern):
            """
            Evaluate password strength score (0-100).
            
            Formula:
            - Length score: min(length * 4, 40)
            - Char type score: char_types * 10
            - Pattern penalty: -20 if has_common_pattern
            """
            # Simplified scoring (Concrete requires bounded operations)
            length_score = fhe.min(length * 4, 40)
            char_score = char_types * 10
            pattern_penalty = has_common_pattern * 20
            
            return length_score + char_score - pattern_penalty
        
        try:
            inputset = [
                (length, types, pattern)
                for length in range(0, 32, 4)
                for types in range(0, 5)
                for pattern in [0, 1]
            ]
            
            circuit = evaluate_strength.compile(
                inputset,
                configuration=self._configuration
            )
            
            self._compiled_circuits['strength'] = circuit
            logger.debug("Strength evaluation circuit compiled")
            
        except Exception as e:
            logger.warning(f"Could not compile strength circuit: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if Concrete FHE is available and initialized."""
        return CONCRETE_AVAILABLE and self._initialized
    
    def encrypt_password_length(self, length: int) -> EncryptedValue:
        """
        Encrypt a password length value.
        
        Args:
            length: Password length (0-127)
            
        Returns:
            EncryptedValue containing the ciphertext
        """
        if not self.is_available:
            return self._fallback_encrypt(length, "password_length")
        
        try:
            # Clamp length to valid range
            length = max(0, min(127, length))
            
            circuit = self._compiled_circuits.get('length_comparison')
            if circuit:
                # Encrypt using the circuit's keyset
                encrypted = circuit.encrypt(length, length)  # Encrypt as first arg
                
                return EncryptedValue(
                    ciphertext=encrypted,
                    operation_type="password_length",
                    encrypted_at=time.time(),
                    circuit_hash=self._get_circuit_hash('length_comparison'),
                    metadata={"original_length": length}
                )
            else:
                return self._fallback_encrypt(length, "password_length")
                
        except Exception as e:
            logger.error(f"Error encrypting password length: {e}")
            return self._fallback_encrypt(length, "password_length")
    
    def encrypt_character_counts(self, counts: Dict[str, int]) -> EncryptedValue:
        """
        Encrypt character type counts.
        
        Args:
            counts: Dictionary with keys: lowercase, uppercase, digits, special
            
        Returns:
            EncryptedValue containing encrypted counts
        """
        if not self.is_available:
            return self._fallback_encrypt(counts, "character_count")
        
        try:
            lowercase = min(31, counts.get('lowercase', 0))
            uppercase = min(31, counts.get('uppercase', 0))
            digits = min(15, counts.get('digits', 0))
            special = min(15, counts.get('special', 0))
            
            circuit = self._compiled_circuits.get('character_count')
            if circuit:
                encrypted = circuit.encrypt(lowercase, uppercase, digits, special)
                
                return EncryptedValue(
                    ciphertext=encrypted,
                    operation_type="character_count",
                    encrypted_at=time.time(),
                    circuit_hash=self._get_circuit_hash('character_count'),
                    metadata={"count_types": 4}
                )
            else:
                return self._fallback_encrypt(counts, "character_count")
                
        except Exception as e:
            logger.error(f"Error encrypting character counts: {e}")
            return self._fallback_encrypt(counts, "character_count")
    
    def homomorphic_compare(
        self, 
        ct1: EncryptedValue, 
        ct2: EncryptedValue
    ) -> EncryptedValue:
        """
        Homomorphically compare two encrypted lengths.
        
        Args:
            ct1: First encrypted value
            ct2: Second encrypted value
            
        Returns:
            EncryptedValue containing result (1 if ct1 >= ct2, else 0)
        """
        if not self.is_available:
            return self._fallback_compare(ct1, ct2)
        
        try:
            circuit = self._compiled_circuits.get('length_comparison')
            if circuit and ct1.ciphertext and ct2.ciphertext:
                # Run homomorphic comparison
                result = circuit.run(ct1.ciphertext, ct2.ciphertext)
                
                return EncryptedValue(
                    ciphertext=result,
                    operation_type="homomorphic_compare",
                    encrypted_at=time.time(),
                    circuit_hash=self._get_circuit_hash('length_comparison'),
                    metadata={"operation": "comparison"}
                )
            else:
                return self._fallback_compare(ct1, ct2)
                
        except Exception as e:
            logger.error(f"Error in homomorphic comparison: {e}")
            return self._fallback_compare(ct1, ct2)
    
    def evaluate_strength_circuit(
        self,
        length: int,
        char_types: int,
        has_common_pattern: bool
    ) -> Tuple[EncryptedValue, Optional[int]]:
        """
        Evaluate password strength using encrypted computation.
        
        Args:
            length: Password length
            char_types: Number of character types (0-4)
            has_common_pattern: Whether password contains common patterns
            
        Returns:
            Tuple of (EncryptedValue, decrypted_score or None)
        """
        if not self.is_available:
            score = self._fallback_strength(length, char_types, has_common_pattern)
            return self._fallback_encrypt(score, "strength_circuit"), score
        
        try:
            circuit = self._compiled_circuits.get('strength')
            if circuit:
                # Encrypt inputs
                enc_length = min(31, length)
                enc_types = min(4, char_types)
                enc_pattern = 1 if has_common_pattern else 0
                
                # Run encrypted computation
                encrypted_result = circuit.encrypt_run_decrypt(
                    enc_length, enc_types, enc_pattern
                )
                
                enc_value = EncryptedValue(
                    ciphertext=None,  # Result was decrypted
                    operation_type="strength_circuit",
                    encrypted_at=time.time(),
                    circuit_hash=self._get_circuit_hash('strength'),
                    metadata={
                        "decrypted": True,
                        "score": int(encrypted_result)
                    }
                )
                
                return enc_value, int(encrypted_result)
            else:
                score = self._fallback_strength(length, char_types, has_common_pattern)
                return self._fallback_encrypt(score, "strength_circuit"), score
                
        except Exception as e:
            logger.error(f"Error in strength evaluation: {e}")
            score = self._fallback_strength(length, char_types, has_common_pattern)
            return self._fallback_encrypt(score, "strength_circuit"), score
    
    def decrypt_value(self, encrypted_value: EncryptedValue, circuit_name: str) -> Any:
        """
        Decrypt an encrypted value.
        
        Args:
            encrypted_value: The encrypted value to decrypt
            circuit_name: Name of the circuit used for encryption
            
        Returns:
            Decrypted value
        """
        if not self.is_available or encrypted_value.ciphertext is None:
            return encrypted_value.metadata.get('fallback_value')
        
        try:
            circuit = self._compiled_circuits.get(circuit_name)
            if circuit:
                return circuit.decrypt(encrypted_value.ciphertext)
            return None
            
        except Exception as e:
            logger.error(f"Error decrypting value: {e}")
            return None
    
    def _fallback_encrypt(self, value: Any, operation_type: str) -> EncryptedValue:
        """Fallback encryption using standard cryptography (not FHE)."""
        import json
        
        # Serialize value
        if isinstance(value, dict):
            serialized = json.dumps(value).encode()
        else:
            serialized = str(value).encode()
        
        # Simple hash for demo (in production, use actual encryption)
        ciphertext = hashlib.sha256(serialized).digest()
        
        return EncryptedValue(
            ciphertext=ciphertext,
            operation_type=operation_type,
            encrypted_at=time.time(),
            circuit_hash="fallback",
            metadata={
                "fallback": True,
                "fallback_value": value
            }
        )
    
    def _fallback_compare(
        self, 
        ct1: EncryptedValue, 
        ct2: EncryptedValue
    ) -> EncryptedValue:
        """Fallback comparison using stored values."""
        val1 = ct1.metadata.get('fallback_value', 0)
        val2 = ct2.metadata.get('fallback_value', 0)
        
        if isinstance(val1, dict):
            val1 = val1.get('original_length', 0)
        if isinstance(val2, dict):
            val2 = val2.get('original_length', 0)
        
        result = 1 if val1 >= val2 else 0
        return self._fallback_encrypt(result, "homomorphic_compare")
    
    def _fallback_strength(
        self, 
        length: int, 
        char_types: int, 
        has_common_pattern: bool
    ) -> int:
        """Calculate strength score without FHE."""
        length_score = min(length * 4, 40)
        char_score = char_types * 10
        pattern_penalty = 20 if has_common_pattern else 0
        
        return max(0, min(100, length_score + char_score - pattern_penalty))
    
    def _get_circuit_hash(self, circuit_name: str) -> str:
        """Get hash identifying a compiled circuit."""
        circuit = self._compiled_circuits.get(circuit_name)
        if circuit:
            return hashlib.sha256(circuit_name.encode()).hexdigest()[:16]
        return "none"
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status information."""
        return {
            "available": self.is_available,
            "concrete_installed": CONCRETE_AVAILABLE,
            "initialized": self._initialized,
            "compiled_circuits": list(self._compiled_circuits.keys()),
            "config": {
                "security_level": self.config.security_level,
                "enable_parallel": self.config.enable_parallel,
                "use_gpu": self.config.use_gpu,
            }
        }


# Singleton instance
_concrete_service: Optional[ConcreteService] = None


def get_concrete_service() -> ConcreteService:
    """Get or create the Concrete service singleton."""
    global _concrete_service
    if _concrete_service is None:
        _concrete_service = ConcreteService()
    return _concrete_service


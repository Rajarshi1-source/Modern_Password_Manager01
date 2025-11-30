"""
FHE Operation Router

Intelligently routes FHE operations to the appropriate service based on:
- Operation type and complexity
- Security requirements
- Performance budget
- Cache availability
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from .concrete_service import ConcreteService, get_concrete_service, EncryptedValue
from .seal_service import SEALBatchService, get_seal_service, SEALCiphertext

logger = logging.getLogger(__name__)


class EncryptionTier(Enum):
    """Encryption tiers for different security/performance tradeoffs."""
    
    CLIENT_ONLY = 1      # Never touches server (handled on client)
    HYBRID_FHE = 2       # Lightweight FHE using Concrete
    FULL_FHE = 3         # Heavy FHE using SEAL batch
    CACHED_FHE = 4       # Pre-computed cached results


class OperationType(Enum):
    """Types of FHE operations."""
    
    PASSWORD_SEARCH = "password_search"
    STRENGTH_CHECK = "strength_check"
    BATCH_STRENGTH = "batch_strength"
    BREACH_DETECTION = "breach_detection"
    SIMILARITY_SEARCH = "similarity_search"
    ENCRYPTED_COMPARE = "encrypted_compare"
    CHARACTER_COUNT = "character_count"


@dataclass
class ComputationalBudget:
    """Defines computational constraints for FHE operations."""
    
    max_latency_ms: int = 1000     # Maximum acceptable latency
    max_memory_mb: int = 512       # Maximum memory usage
    min_accuracy: float = 0.9      # Minimum acceptable accuracy
    priority: int = 5              # Priority level (1-10, higher = more important)
    
    def allows_full_fhe(self) -> bool:
        """Check if budget allows full FHE operations."""
        return self.max_latency_ms >= 500 and self.max_memory_mb >= 256
    
    def allows_hybrid_fhe(self) -> bool:
        """Check if budget allows hybrid FHE operations."""
        return self.max_latency_ms >= 100 and self.max_memory_mb >= 64


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    
    tier: EncryptionTier
    service_name: str
    estimated_latency_ms: int
    estimated_accuracy: float
    cache_key: Optional[str] = None
    metadata: Dict[str, Any] = None


class FHEOperationRouter:
    """
    Routes FHE operations to appropriate encryption tier and service.
    
    Routing logic:
    - password_search -> HYBRID_FHE (Concrete)
    - strength_check -> FULL_FHE (SEAL batch)
    - breach_detection -> FULL_FHE (SEAL)
    - similarity_search -> HYBRID_FHE (Concrete)
    - batch operations -> FULL_FHE (SEAL with SIMD)
    """
    
    # Operation complexity ratings (1-10)
    COMPLEXITY_RATINGS = {
        OperationType.PASSWORD_SEARCH: 3,
        OperationType.STRENGTH_CHECK: 5,
        OperationType.BATCH_STRENGTH: 8,
        OperationType.BREACH_DETECTION: 7,
        OperationType.SIMILARITY_SEARCH: 4,
        OperationType.ENCRYPTED_COMPARE: 2,
        OperationType.CHARACTER_COUNT: 3,
    }
    
    # Default tier assignments
    DEFAULT_TIERS = {
        OperationType.PASSWORD_SEARCH: EncryptionTier.HYBRID_FHE,
        OperationType.STRENGTH_CHECK: EncryptionTier.FULL_FHE,
        OperationType.BATCH_STRENGTH: EncryptionTier.FULL_FHE,
        OperationType.BREACH_DETECTION: EncryptionTier.FULL_FHE,
        OperationType.SIMILARITY_SEARCH: EncryptionTier.HYBRID_FHE,
        OperationType.ENCRYPTED_COMPARE: EncryptionTier.HYBRID_FHE,
        OperationType.CHARACTER_COUNT: EncryptionTier.HYBRID_FHE,
    }
    
    # Estimated latencies per tier (ms)
    ESTIMATED_LATENCIES = {
        EncryptionTier.CLIENT_ONLY: 10,
        EncryptionTier.HYBRID_FHE: 100,
        EncryptionTier.FULL_FHE: 500,
        EncryptionTier.CACHED_FHE: 5,
    }
    
    def __init__(
        self,
        concrete_service: Optional[ConcreteService] = None,
        seal_service: Optional[SEALBatchService] = None,
        cache: Optional[Any] = None
    ):
        self._concrete = concrete_service
        self._seal = seal_service
        self._cache = cache
        
        # Lazy initialization
        self._concrete_initialized = False
        self._seal_initialized = False
    
    @property
    def concrete_service(self) -> ConcreteService:
        """Get or initialize Concrete service."""
        if self._concrete is None and not self._concrete_initialized:
            self._concrete = get_concrete_service()
            self._concrete_initialized = True
        return self._concrete
    
    @property
    def seal_service(self) -> SEALBatchService:
        """Get or initialize SEAL service."""
        if self._seal is None and not self._seal_initialized:
            self._seal = get_seal_service()
            self._seal_initialized = True
        return self._seal
    
    def route_operation(
        self,
        operation_type: str,
        data: Any,
        budget: Optional[ComputationalBudget] = None
    ) -> Tuple[RoutingDecision, Any]:
        """
        Route an operation to the appropriate tier and execute it.
        
        Args:
            operation_type: Type of operation (from OperationType enum or string)
            data: Input data for the operation
            budget: Optional computational budget constraints
            
        Returns:
            Tuple of (RoutingDecision, result)
        """
        budget = budget or ComputationalBudget()
        
        # Parse operation type
        try:
            op_type = OperationType(operation_type)
        except ValueError:
            op_type = OperationType.STRENGTH_CHECK  # Default
        
        # Check cache first
        cache_key = self._generate_cache_key(operation_type, data)
        cached_result = self._check_cache(cache_key)
        
        if cached_result is not None:
            decision = RoutingDecision(
                tier=EncryptionTier.CACHED_FHE,
                service_name="cache",
                estimated_latency_ms=self.ESTIMATED_LATENCIES[EncryptionTier.CACHED_FHE],
                estimated_accuracy=1.0,
                cache_key=cache_key,
                metadata={"cache_hit": True}
            )
            return decision, cached_result
        
        # Determine optimal tier
        tier = self._select_tier(op_type, budget)
        
        # Execute operation
        decision, result = self._execute_operation(op_type, tier, data, budget)
        
        # Cache result if appropriate
        if decision.tier != EncryptionTier.CACHED_FHE:
            self._cache_result(cache_key, result)
        
        return decision, result
    
    def _select_tier(
        self,
        op_type: OperationType,
        budget: ComputationalBudget
    ) -> EncryptionTier:
        """Select the optimal encryption tier for an operation."""
        
        default_tier = self.DEFAULT_TIERS.get(op_type, EncryptionTier.FULL_FHE)
        
        # Check service availability
        concrete_available = self.concrete_service.is_available if self._concrete else False
        seal_available = self.seal_service.is_available if self._seal else False
        
        # Adjust based on budget constraints
        if default_tier == EncryptionTier.FULL_FHE:
            if not budget.allows_full_fhe():
                # Downgrade to hybrid if budget is tight
                if budget.allows_hybrid_fhe() and concrete_available:
                    return EncryptionTier.HYBRID_FHE
                # Otherwise client-only
                return EncryptionTier.CLIENT_ONLY
            
            if not seal_available:
                # Fall back to hybrid or client
                if concrete_available:
                    return EncryptionTier.HYBRID_FHE
                return EncryptionTier.CLIENT_ONLY
        
        elif default_tier == EncryptionTier.HYBRID_FHE:
            if not budget.allows_hybrid_fhe():
                return EncryptionTier.CLIENT_ONLY
            
            if not concrete_available:
                # Try upgrading to full FHE
                if seal_available and budget.allows_full_fhe():
                    return EncryptionTier.FULL_FHE
                return EncryptionTier.CLIENT_ONLY
        
        return default_tier
    
    def _execute_operation(
        self,
        op_type: OperationType,
        tier: EncryptionTier,
        data: Any,
        budget: ComputationalBudget
    ) -> Tuple[RoutingDecision, Any]:
        """Execute the operation on the selected tier."""
        
        start_time = time.time()
        
        if tier == EncryptionTier.HYBRID_FHE:
            result = self._execute_hybrid(op_type, data)
            service_name = "concrete"
        elif tier == EncryptionTier.FULL_FHE:
            result = self._execute_full_fhe(op_type, data)
            service_name = "seal"
        else:
            result = self._execute_client_only(op_type, data)
            service_name = "client"
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        decision = RoutingDecision(
            tier=tier,
            service_name=service_name,
            estimated_latency_ms=elapsed_ms,
            estimated_accuracy=0.95 if tier != EncryptionTier.CLIENT_ONLY else 0.8,
            metadata={
                "operation_type": op_type.value,
                "actual_latency_ms": elapsed_ms
            }
        )
        
        return decision, result
    
    def _execute_hybrid(self, op_type: OperationType, data: Any) -> Any:
        """Execute operation using Concrete (hybrid FHE)."""
        
        service = self.concrete_service
        
        if op_type == OperationType.ENCRYPTED_COMPARE:
            # Expect data to be tuple of two values
            if isinstance(data, tuple) and len(data) == 2:
                ct1 = service.encrypt_password_length(data[0])
                ct2 = service.encrypt_password_length(data[1])
                return service.homomorphic_compare(ct1, ct2)
        
        elif op_type == OperationType.CHARACTER_COUNT:
            # Expect data to be character count dict
            if isinstance(data, dict):
                return service.encrypt_character_counts(data)
        
        elif op_type == OperationType.PASSWORD_SEARCH:
            # For search, encrypt the query length
            if isinstance(data, (int, str)):
                length = len(data) if isinstance(data, str) else data
                return service.encrypt_password_length(length)
        
        elif op_type == OperationType.STRENGTH_CHECK:
            # Extract features and evaluate
            features = self._extract_password_features(data)
            result, score = service.evaluate_strength_circuit(
                length=features['length'],
                char_types=features['char_types'],
                has_common_pattern=features['has_common_pattern']
            )
            return {'encrypted': result, 'score': score}
        
        elif op_type == OperationType.SIMILARITY_SEARCH:
            # Encrypt for similarity search
            if isinstance(data, str):
                return service.encrypt_password_length(len(data))
        
        # Default: return data as-is
        return data
    
    def _execute_full_fhe(self, op_type: OperationType, data: Any) -> Any:
        """Execute operation using SEAL (full FHE)."""
        
        service = self.seal_service
        
        if op_type == OperationType.STRENGTH_CHECK:
            features = self._extract_password_features(data)
            encrypted = service.encrypt_password_features(
                length=features['length'],
                entropy=features['entropy'],
                char_diversity=features['char_diversity'],
                pattern_score=features['pattern_score']
            )
            result, score = service.simd_strength_evaluation(encrypted)
            return {'encrypted': result, 'score': score}
        
        elif op_type == OperationType.BATCH_STRENGTH:
            # Expect data to be list of password feature dicts
            if isinstance(data, list):
                encrypted_list = service.batch_encrypt_passwords(data)
                scores = service.batch_strength_evaluation(encrypted_list)
                return {'encrypted': encrypted_list, 'scores': scores}
        
        elif op_type == OperationType.SIMILARITY_SEARCH:
            # Expect data to be dict with 'query' and 'vault'
            if isinstance(data, dict):
                query_features = self._extract_password_features(data.get('query', ''))
                query_ct = service.encrypt_password_features(**query_features)
                
                vault_features = [
                    self._extract_password_features(p) 
                    for p in data.get('vault', [])
                ]
                vault_cts = service.batch_encrypt_passwords(vault_features)
                
                results = service.encrypted_similarity_search(
                    query_ct, 
                    vault_cts,
                    threshold=data.get('threshold', 0.8)
                )
                return {'matches': results}
        
        elif op_type == OperationType.BREACH_DETECTION:
            # Encrypt features for breach detection
            features = self._extract_password_features(data)
            encrypted = service.encrypt_password_features(**features)
            return {'encrypted': encrypted}
        
        # Default: encrypt as vector
        if isinstance(data, list):
            return service.encrypt_vector([float(x) for x in data])
        
        return data
    
    def _execute_client_only(self, op_type: OperationType, data: Any) -> Any:
        """Execute operation client-side (fallback)."""
        
        if op_type == OperationType.STRENGTH_CHECK:
            features = self._extract_password_features(data)
            score = self._calculate_strength_score(features)
            return {'score': score, 'mode': 'client_only'}
        
        elif op_type == OperationType.ENCRYPTED_COMPARE:
            if isinstance(data, tuple) and len(data) == 2:
                return {'result': data[0] >= data[1], 'mode': 'client_only'}
        
        return {'data': data, 'mode': 'client_only'}
    
    def _extract_password_features(self, password: Any) -> Dict[str, Any]:
        """Extract features from a password for FHE operations."""
        
        if isinstance(password, dict):
            # Already extracted features
            return {
                'length': password.get('length', 0),
                'entropy': password.get('entropy', 0.0),
                'char_diversity': password.get('char_diversity', 0.0),
                'pattern_score': password.get('pattern_score', 0.0),
                'char_types': password.get('char_types', 0),
                'has_common_pattern': password.get('has_common_pattern', False),
            }
        
        if not isinstance(password, str):
            password = str(password)
        
        length = len(password)
        
        # Count character types
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        char_types = sum([has_lower, has_upper, has_digit, has_special])
        char_diversity = char_types / 4.0
        
        # Simple entropy estimation
        unique_chars = len(set(password))
        entropy = (unique_chars / max(1, length)) * (length / 32.0)
        
        # Common pattern detection (simplified)
        common_patterns = ['123', 'abc', 'qwerty', 'password', 'admin']
        has_common_pattern = any(
            p in password.lower() for p in common_patterns
        )
        pattern_score = 0.5 if has_common_pattern else 0.0
        
        return {
            'length': length,
            'entropy': min(1.0, entropy),
            'char_diversity': char_diversity,
            'pattern_score': pattern_score,
            'char_types': char_types,
            'has_common_pattern': has_common_pattern,
        }
    
    def _calculate_strength_score(self, features: Dict[str, Any]) -> float:
        """Calculate password strength score."""
        
        length_score = min(40, features['length'] * 4)
        char_score = features['char_types'] * 10
        entropy_score = features['entropy'] * 30
        pattern_penalty = 20 if features['has_common_pattern'] else 0
        
        score = length_score + char_score + entropy_score - pattern_penalty
        return max(0, min(100, score))
    
    def _generate_cache_key(self, operation_type: str, data: Any) -> str:
        """Generate a cache key for the operation."""
        
        # Hash the data (first 64 bytes only for performance)
        data_str = str(data)[:64]
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        
        return f"fhe:{operation_type}:{data_hash}"
    
    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Check if result is in cache."""
        if self._cache is None:
            return None
        
        try:
            return self._cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return None
    
    def _cache_result(self, cache_key: str, result: Any) -> bool:
        """Cache the operation result."""
        if self._cache is None:
            return False
        
        try:
            self._cache.set(cache_key, result)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get router status information."""
        return {
            "concrete_available": self.concrete_service.is_available if self._concrete else False,
            "seal_available": self.seal_service.is_available if self._seal else False,
            "cache_enabled": self._cache is not None,
            "supported_operations": [op.value for op in OperationType],
            "tier_latencies": {
                tier.name: latency 
                for tier, latency in self.ESTIMATED_LATENCIES.items()
            }
        }


# Singleton instance
_router: Optional[FHEOperationRouter] = None


def get_fhe_router(cache: Optional[Any] = None) -> FHEOperationRouter:
    """Get or create the FHE router singleton."""
    global _router
    if _router is None:
        _router = FHEOperationRouter(cache=cache)
    return _router


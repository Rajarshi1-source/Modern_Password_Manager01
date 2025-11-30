"""
Adaptive Circuit Depth Manager

Dynamically adjusts FHE circuit depth based on:
- Available computational budget
- Current system load
- Accuracy requirements
- Operation priority

Provides fallback mechanisms when operations exceed budgets.
"""

import logging
import time
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)

# Attempt to import psutil for system metrics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available. System load metrics will be estimated.")


class DepthProfile(Enum):
    """Predefined circuit depth profiles."""
    
    ULTRA_FAST = "ultra_fast"   # Depth 2, ~50ms
    FAST = "fast"               # Depth 4, ~200ms
    BALANCED = "balanced"       # Depth 6, ~500ms
    ACCURATE = "accurate"       # Depth 10, ~2000ms


@dataclass
class ProfileConfig:
    """Configuration for a depth profile."""
    
    depth: int
    accuracy: float  # 0.0 to 1.0
    expected_latency_ms: int
    max_latency_ms: int
    description: str
    
    # Circuit parameters
    noise_budget: int = 50
    security_bits: int = 128


@dataclass
class ComputationalBudget:
    """Defines computational constraints for FHE operations."""
    
    max_latency_ms: int = 1000     # Maximum acceptable latency
    max_memory_mb: int = 512       # Maximum memory usage
    min_accuracy: float = 0.9      # Minimum acceptable accuracy
    priority: int = 5              # Priority level (1-10)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_latency_ms': self.max_latency_ms,
            'max_memory_mb': self.max_memory_mb,
            'min_accuracy': self.min_accuracy,
            'priority': self.priority
        }


@dataclass
class ExecutionResult:
    """Result of an adaptive FHE execution."""
    
    success: bool
    result: Any
    profile_used: str
    actual_latency_ms: int
    fallback_used: bool
    accuracy_estimate: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdaptiveFHEManager:
    """
    Manages FHE circuit depth adaptively based on system load
    and computational budget constraints.
    
    Features:
    - Dynamic profile selection
    - Automatic fallback to simpler circuits
    - System load monitoring
    - Performance history tracking
    """
    
    # Depth profile configurations
    DEPTH_PROFILES: Dict[str, ProfileConfig] = {
        'ultra_fast': ProfileConfig(
            depth=2,
            accuracy=0.85,
            expected_latency_ms=50,
            max_latency_ms=100,
            description='Real-time search, simple comparisons',
            noise_budget=30,
            security_bits=128
        ),
        'fast': ProfileConfig(
            depth=4,
            accuracy=0.92,
            expected_latency_ms=200,
            max_latency_ms=400,
            description='Password strength check, basic operations',
            noise_budget=40,
            security_bits=128
        ),
        'balanced': ProfileConfig(
            depth=6,
            accuracy=0.97,
            expected_latency_ms=500,
            max_latency_ms=1000,
            description='Breach detection, similarity search',
            noise_budget=50,
            security_bits=128
        ),
        'accurate': ProfileConfig(
            depth=10,
            accuracy=0.995,
            expected_latency_ms=2000,
            max_latency_ms=4000,
            description='Advanced analytics, complex operations',
            noise_budget=60,
            security_bits=128
        )
    }
    
    def __init__(self, enable_monitoring: bool = True):
        self.enable_monitoring = enable_monitoring
        
        # Performance history (last 100 operations)
        self._performance_history: deque = deque(maxlen=100)
        
        # Current system load (0.0 to 1.0)
        self._current_load: float = 0.0
        
        # Load update interval
        self._last_load_update: float = 0.0
        self._load_update_interval: float = 1.0  # seconds
        
        # Fallback statistics
        self._fallback_count: int = 0
        self._total_operations: int = 0
    
    def select_optimal_profile(
        self,
        budget: ComputationalBudget,
        operation_type: str = "default"
    ) -> Tuple[str, ProfileConfig]:
        """
        Select the optimal FHE depth profile based on budget and system load.
        
        Args:
            budget: Computational budget constraints
            operation_type: Type of operation for context
            
        Returns:
            Tuple of (profile_name, ProfileConfig)
        """
        # Update system load
        self._update_load_metrics()
        
        # Filter profiles that meet minimum accuracy requirement
        viable_profiles = {
            name: profile
            for name, profile in self.DEPTH_PROFILES.items()
            if profile.accuracy >= budget.min_accuracy
        }
        
        if not viable_profiles:
            # No profile meets accuracy requirement, use most accurate
            logger.warning(f"No profile meets accuracy {budget.min_accuracy}, using 'accurate'")
            return 'accurate', self.DEPTH_PROFILES['accurate']
        
        # Adjust latencies for current system load
        load_factor = 1.0 + (self._current_load * 0.5)
        
        # Find best profile within latency budget
        best_profile = None
        best_score = float('inf')
        
        for name, profile in viable_profiles.items():
            adjusted_latency = profile.expected_latency_ms * load_factor
            
            if adjusted_latency <= budget.max_latency_ms:
                # Score: lower is better (balance latency and accuracy)
                # Higher accuracy is better, lower latency is better
                score = adjusted_latency / (profile.accuracy * 100)
                
                # Adjust score based on priority
                score = score / (budget.priority / 5.0)
                
                if score < best_score:
                    best_score = score
                    best_profile = (name, profile)
        
        if best_profile is None:
            # No profile fits budget, use ultra_fast as fallback
            logger.info(f"No profile fits latency budget {budget.max_latency_ms}ms, using 'ultra_fast'")
            return 'ultra_fast', self.DEPTH_PROFILES['ultra_fast']
        
        return best_profile
    
    async def execute_with_adaptive_depth(
        self,
        operation: Callable,
        budget: ComputationalBudget,
        operation_type: str = "default"
    ) -> ExecutionResult:
        """
        Execute an FHE operation with adaptive circuit depth.
        Falls back to simpler circuits if computation exceeds budget.
        
        Args:
            operation: Async callable that takes circuit_depth parameter
            budget: Computational budget
            operation_type: Type of operation
            
        Returns:
            ExecutionResult with operation outcome
        """
        profile_name, profile = self.select_optimal_profile(budget, operation_type)
        
        start_time = time.time()
        self._total_operations += 1
        
        try:
            # Attempt with selected profile
            result = await self._execute_with_timeout(
                operation,
                profile.depth,
                profile.max_latency_ms
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Record success
            self._record_performance(
                profile_name=profile_name,
                latency_ms=elapsed_ms,
                success=True,
                fallback=False
            )
            
            return ExecutionResult(
                success=True,
                result=result,
                profile_used=profile_name,
                actual_latency_ms=elapsed_ms,
                fallback_used=False,
                accuracy_estimate=profile.accuracy,
                metadata={
                    'depth': profile.depth,
                    'budget': budget.to_dict()
                }
            )
            
        except TimeoutError:
            logger.warning(f"Timeout with profile '{profile_name}', attempting fallback")
            return await self._execute_with_fallback(operation, budget, start_time)
            
        except Exception as e:
            logger.error(f"Error with profile '{profile_name}': {e}")
            return await self._execute_with_fallback(operation, budget, start_time)
    
    def execute_sync_with_adaptive_depth(
        self,
        operation: Callable,
        budget: ComputationalBudget,
        operation_type: str = "default"
    ) -> ExecutionResult:
        """
        Synchronous version of execute_with_adaptive_depth.
        
        Args:
            operation: Callable that takes circuit_depth parameter
            budget: Computational budget
            operation_type: Type of operation
            
        Returns:
            ExecutionResult with operation outcome
        """
        profile_name, profile = self.select_optimal_profile(budget, operation_type)
        
        start_time = time.time()
        self._total_operations += 1
        
        try:
            # Attempt with selected profile
            result = operation(circuit_depth=profile.depth)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Check if exceeded expected latency significantly
            if elapsed_ms > profile.max_latency_ms:
                logger.warning(
                    f"Operation exceeded max latency: {elapsed_ms}ms > {profile.max_latency_ms}ms"
                )
            
            # Record success
            self._record_performance(
                profile_name=profile_name,
                latency_ms=elapsed_ms,
                success=True,
                fallback=False
            )
            
            return ExecutionResult(
                success=True,
                result=result,
                profile_used=profile_name,
                actual_latency_ms=elapsed_ms,
                fallback_used=False,
                accuracy_estimate=profile.accuracy,
                metadata={
                    'depth': profile.depth,
                    'budget': budget.to_dict()
                }
            )
            
        except Exception as e:
            logger.error(f"Error with profile '{profile_name}': {e}")
            return self._execute_sync_fallback(operation, budget, start_time)
    
    async def _execute_with_timeout(
        self,
        operation: Callable,
        depth: int,
        timeout_ms: int
    ) -> Any:
        """Execute operation with timeout."""
        import asyncio
        
        try:
            timeout_seconds = timeout_ms / 1000.0
            result = await asyncio.wait_for(
                operation(circuit_depth=depth),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout_ms}ms")
    
    async def _execute_with_fallback(
        self,
        operation: Callable,
        budget: ComputationalBudget,
        start_time: float
    ) -> ExecutionResult:
        """Execute with progressively simpler profiles until success."""
        
        # Order profiles by depth (simplest first)
        fallback_order = ['ultra_fast', 'fast', 'balanced', 'accurate']
        
        for profile_name in fallback_order:
            profile = self.DEPTH_PROFILES[profile_name]
            
            try:
                result = await self._execute_with_timeout(
                    operation,
                    profile.depth,
                    profile.max_latency_ms * 2  # More lenient timeout for fallback
                )
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                self._fallback_count += 1
                
                self._record_performance(
                    profile_name=profile_name,
                    latency_ms=elapsed_ms,
                    success=True,
                    fallback=True
                )
                
                return ExecutionResult(
                    success=True,
                    result=result,
                    profile_used=profile_name,
                    actual_latency_ms=elapsed_ms,
                    fallback_used=True,
                    accuracy_estimate=profile.accuracy,
                    metadata={
                        'depth': profile.depth,
                        'fallback_reason': 'timeout'
                    }
                )
                
            except Exception as e:
                logger.warning(f"Fallback to '{profile_name}' failed: {e}")
                continue
        
        # All fallbacks failed
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ExecutionResult(
            success=False,
            result=None,
            profile_used='none',
            actual_latency_ms=elapsed_ms,
            fallback_used=True,
            accuracy_estimate=0.0,
            metadata={'error': 'All profiles failed'}
        )
    
    def _execute_sync_fallback(
        self,
        operation: Callable,
        budget: ComputationalBudget,
        start_time: float
    ) -> ExecutionResult:
        """Synchronous fallback execution."""
        
        fallback_order = ['ultra_fast', 'fast']
        
        for profile_name in fallback_order:
            profile = self.DEPTH_PROFILES[profile_name]
            
            try:
                result = operation(circuit_depth=profile.depth)
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                self._fallback_count += 1
                
                self._record_performance(
                    profile_name=profile_name,
                    latency_ms=elapsed_ms,
                    success=True,
                    fallback=True
                )
                
                return ExecutionResult(
                    success=True,
                    result=result,
                    profile_used=profile_name,
                    actual_latency_ms=elapsed_ms,
                    fallback_used=True,
                    accuracy_estimate=profile.accuracy,
                    metadata={'depth': profile.depth}
                )
                
            except Exception as e:
                logger.warning(f"Sync fallback to '{profile_name}' failed: {e}")
                continue
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ExecutionResult(
            success=False,
            result=None,
            profile_used='none',
            actual_latency_ms=elapsed_ms,
            fallback_used=True,
            accuracy_estimate=0.0,
            metadata={'error': 'All profiles failed'}
        )
    
    def _update_load_metrics(self):
        """Update system load based on recent measurements."""
        now = time.time()
        
        if now - self._last_load_update < self._load_update_interval:
            return
        
        self._last_load_update = now
        
        if PSUTIL_AVAILABLE and self.enable_monitoring:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                
                # Combine CPU and memory load
                self._current_load = (cpu_percent + memory_percent) / 200.0
                
            except Exception as e:
                logger.warning(f"Error getting system metrics: {e}")
                self._current_load = 0.3  # Assume moderate load
        else:
            # Estimate based on recent performance
            if self._performance_history:
                recent_latencies = [
                    p['latency_ms'] for p in list(self._performance_history)[-10:]
                ]
                avg_latency = sum(recent_latencies) / len(recent_latencies)
                
                # Higher latencies suggest higher load
                self._current_load = min(1.0, avg_latency / 1000.0)
            else:
                self._current_load = 0.2  # Assume light load
    
    def _record_performance(
        self,
        profile_name: str,
        latency_ms: int,
        success: bool,
        fallback: bool
    ):
        """Record performance metrics."""
        self._performance_history.append({
            'timestamp': time.time(),
            'profile': profile_name,
            'latency_ms': latency_ms,
            'success': success,
            'fallback': fallback,
            'load': self._current_load
        })
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self._performance_history:
            return {
                'total_operations': 0,
                'avg_latency_ms': 0,
                'success_rate': 0,
                'fallback_rate': 0
            }
        
        history = list(self._performance_history)
        
        latencies = [p['latency_ms'] for p in history]
        successes = [p['success'] for p in history]
        fallbacks = [p['fallback'] for p in history]
        
        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        p50_idx = int(n * 0.5)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        return {
            'total_operations': self._total_operations,
            'avg_latency_ms': sum(latencies) / n,
            'p50_latency_ms': sorted_latencies[p50_idx] if p50_idx < n else 0,
            'p95_latency_ms': sorted_latencies[p95_idx] if p95_idx < n else 0,
            'p99_latency_ms': sorted_latencies[p99_idx] if p99_idx < n else 0,
            'success_rate': sum(successes) / n,
            'fallback_rate': sum(fallbacks) / n if successes else 0,
            'total_fallbacks': self._fallback_count,
            'current_load': self._current_load,
            'history_size': n,
            'profile_distribution': self._get_profile_distribution(history)
        }
    
    def _get_profile_distribution(self, history: list) -> Dict[str, int]:
        """Get distribution of profiles used."""
        distribution = {}
        for entry in history:
            profile = entry['profile']
            distribution[profile] = distribution.get(profile, 0) + 1
        return distribution
    
    def get_recommended_profile(
        self,
        operation_type: str,
        latency_requirement_ms: int
    ) -> str:
        """
        Get recommended profile for an operation type.
        
        Args:
            operation_type: Type of operation
            latency_requirement_ms: Maximum acceptable latency
            
        Returns:
            Profile name
        """
        # Update load
        self._update_load_metrics()
        
        load_factor = 1.0 + (self._current_load * 0.5)
        
        for profile_name in ['ultra_fast', 'fast', 'balanced', 'accurate']:
            profile = self.DEPTH_PROFILES[profile_name]
            adjusted_latency = profile.expected_latency_ms * load_factor
            
            if adjusted_latency <= latency_requirement_ms:
                return profile_name
        
        return 'ultra_fast'
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        return {
            'monitoring_enabled': self.enable_monitoring,
            'psutil_available': PSUTIL_AVAILABLE,
            'current_load': self._current_load,
            'profiles': {
                name: {
                    'depth': p.depth,
                    'accuracy': p.accuracy,
                    'expected_latency_ms': p.expected_latency_ms,
                    'description': p.description
                }
                for name, p in self.DEPTH_PROFILES.items()
            },
            'performance': self.get_performance_stats()
        }


# Singleton instance
_adaptive_manager: Optional[AdaptiveFHEManager] = None


def get_adaptive_manager() -> AdaptiveFHEManager:
    """Get or create the adaptive FHE manager singleton."""
    global _adaptive_manager
    if _adaptive_manager is None:
        _adaptive_manager = AdaptiveFHEManager()
    return _adaptive_manager


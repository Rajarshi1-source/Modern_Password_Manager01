"""
FHE Service Performance Benchmarks

Measures:
- Encryption latency
- Batch processing throughput
- Cache hit rate
- Memory usage
- Tier distribution
"""

import time
import statistics
import json
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

import sys
sys.path.insert(0, '../../password_manager')

from fhe_service.services.concrete_service import ConcreteService
from fhe_service.services.seal_service import SEALBatchService
from fhe_service.services.fhe_router import FHEOperationRouter, ComputationalBudget
from fhe_service.services.fhe_cache import FHEComputationCache, CacheConfig
from fhe_service.services.adaptive_manager import AdaptiveFHEManager


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    name: str
    iterations: int
    total_time_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_ops_per_sec: float
    errors: int = 0
    metadata: Dict[str, Any] = None


class FHEBenchmarks:
    """FHE Service performance benchmarks."""
    
    def __init__(self):
        self.concrete_service = ConcreteService()
        self.seal_service = SEALBatchService()
        self.router = FHEOperationRouter()
        
        cache_config = CacheConfig(host='invalid', port=0)  # Force memory cache
        self.cache = FHEComputationCache(cache_config)
        
        self.adaptive_manager = AdaptiveFHEManager()
        self.results: List[BenchmarkResult] = []
    
    def _run_benchmark(
        self,
        name: str,
        func,
        iterations: int = 100,
        warmup: int = 10,
        **kwargs
    ) -> BenchmarkResult:
        """Run a benchmark and collect statistics."""
        
        # Warmup
        for _ in range(warmup):
            try:
                func(**kwargs)
            except Exception:
                pass
        
        # Benchmark
        latencies = []
        errors = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func(**kwargs)
            except Exception as e:
                errors += 1
            latencies.append((time.perf_counter() - start) * 1000)  # ms
        
        # Calculate statistics
        latencies.sort()
        n = len(latencies)
        
        total_time = sum(latencies)
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        p50_idx = int(n * 0.5)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        p50 = latencies[p50_idx] if p50_idx < n else latencies[-1]
        p95 = latencies[p95_idx] if p95_idx < n else latencies[-1]
        p99 = latencies[p99_idx] if p99_idx < n else latencies[-1]
        
        throughput = (iterations - errors) / (total_time / 1000) if total_time > 0 else 0
        
        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total_time,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            throughput_ops_per_sec=throughput,
            errors=errors
        )
        
        self.results.append(result)
        return result
    
    def benchmark_concrete_encryption(self, iterations: int = 100):
        """Benchmark Concrete service encryption."""
        
        def encrypt_length():
            self.concrete_service.encrypt_password_length(12)
        
        return self._run_benchmark(
            "Concrete: Password Length Encryption",
            encrypt_length,
            iterations
        )
    
    def benchmark_concrete_character_count(self, iterations: int = 100):
        """Benchmark Concrete character count encryption."""
        
        def encrypt_counts():
            self.concrete_service.encrypt_character_counts({
                'lowercase': 5,
                'uppercase': 3,
                'digits': 2,
                'special': 1
            })
        
        return self._run_benchmark(
            "Concrete: Character Count Encryption",
            encrypt_counts,
            iterations
        )
    
    def benchmark_concrete_strength_circuit(self, iterations: int = 100):
        """Benchmark Concrete strength evaluation circuit."""
        
        def evaluate_strength():
            self.concrete_service.evaluate_strength_circuit(
                length=16,
                char_types=4,
                has_common_pattern=False
            )
        
        return self._run_benchmark(
            "Concrete: Strength Circuit Evaluation",
            evaluate_strength,
            iterations
        )
    
    def benchmark_seal_vector_encryption(self, iterations: int = 100):
        """Benchmark SEAL vector encryption."""
        
        def encrypt_vector():
            self.seal_service.encrypt_vector([0.5, 0.3, 0.2, 0.1])
        
        return self._run_benchmark(
            "SEAL: Vector Encryption",
            encrypt_vector,
            iterations
        )
    
    def benchmark_seal_password_features(self, iterations: int = 100):
        """Benchmark SEAL password feature encryption."""
        
        def encrypt_features():
            self.seal_service.encrypt_password_features(
                length=16,
                entropy=0.8,
                char_diversity=0.75,
                pattern_score=0.1
            )
        
        return self._run_benchmark(
            "SEAL: Password Feature Encryption",
            encrypt_features,
            iterations
        )
    
    def benchmark_seal_batch_encryption(self, batch_size: int = 10, iterations: int = 50):
        """Benchmark SEAL batch encryption."""
        
        features = [
            {'length': 12, 'entropy': 0.7, 'char_diversity': 0.5, 'pattern_score': 0.1}
            for _ in range(batch_size)
        ]
        
        def batch_encrypt():
            self.seal_service.batch_encrypt_passwords(features)
        
        result = self._run_benchmark(
            f"SEAL: Batch Encryption ({batch_size} passwords)",
            batch_encrypt,
            iterations
        )
        result.metadata = {'batch_size': batch_size}
        return result
    
    def benchmark_router_strength_check(self, iterations: int = 100):
        """Benchmark router strength check."""
        
        budget = ComputationalBudget(max_latency_ms=1000)
        
        def route_strength():
            self.router.route_operation('strength_check', 'TestPassword123!', budget)
        
        return self._run_benchmark(
            "Router: Strength Check",
            route_strength,
            iterations
        )
    
    def benchmark_cache_operations(self, iterations: int = 1000):
        """Benchmark cache get/set operations."""
        
        # Pre-populate cache
        for i in range(100):
            self.cache.set(f'bench_key_{i}', b'test_value_' + str(i).encode(), 'test')
        
        def cache_get():
            import random
            key = f'bench_key_{random.randint(0, 99)}'
            self.cache.get(key)
        
        return self._run_benchmark(
            "Cache: Get Operation",
            cache_get,
            iterations
        )
    
    def benchmark_adaptive_selection(self, iterations: int = 100):
        """Benchmark adaptive profile selection."""
        
        budget = ComputationalBudget()
        
        def select_profile():
            self.adaptive_manager.select_optimal_profile(budget, 'strength_check')
        
        return self._run_benchmark(
            "Adaptive: Profile Selection",
            select_profile,
            iterations
        )
    
    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all benchmarks and return results."""
        
        print("Running FHE Service Benchmarks...")
        print("=" * 60)
        
        # Concrete benchmarks
        result = self.benchmark_concrete_encryption()
        self._print_result(result)
        
        result = self.benchmark_concrete_character_count()
        self._print_result(result)
        
        result = self.benchmark_concrete_strength_circuit()
        self._print_result(result)
        
        # SEAL benchmarks
        result = self.benchmark_seal_vector_encryption()
        self._print_result(result)
        
        result = self.benchmark_seal_password_features()
        self._print_result(result)
        
        result = self.benchmark_seal_batch_encryption(batch_size=10)
        self._print_result(result)
        
        result = self.benchmark_seal_batch_encryption(batch_size=50)
        self._print_result(result)
        
        # Router benchmarks
        result = self.benchmark_router_strength_check()
        self._print_result(result)
        
        # Cache benchmarks
        result = self.benchmark_cache_operations()
        self._print_result(result)
        
        # Adaptive benchmarks
        result = self.benchmark_adaptive_selection()
        self._print_result(result)
        
        print("=" * 60)
        print("Benchmarks completed!")
        
        return self.results
    
    def _print_result(self, result: BenchmarkResult):
        """Print a benchmark result."""
        print(f"\n{result.name}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg Latency: {result.avg_latency_ms:.3f}ms")
        print(f"  P50 Latency: {result.p50_latency_ms:.3f}ms")
        print(f"  P95 Latency: {result.p95_latency_ms:.3f}ms")
        print(f"  P99 Latency: {result.p99_latency_ms:.3f}ms")
        print(f"  Throughput: {result.throughput_ops_per_sec:.1f} ops/sec")
        if result.errors > 0:
            print(f"  Errors: {result.errors}")
    
    def export_results(self, filepath: str = 'fhe_benchmark_results.json'):
        """Export results to JSON file."""
        data = {
            'timestamp': time.time(),
            'results': [asdict(r) for r in self.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results exported to {filepath}")


def main():
    """Run benchmarks."""
    benchmarks = FHEBenchmarks()
    results = benchmarks.run_all_benchmarks()
    
    # Export results
    benchmarks.export_results()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for result in results:
        status = "✓" if result.avg_latency_ms < 100 else "△" if result.avg_latency_ms < 500 else "✗"
        print(f"{status} {result.name}: {result.avg_latency_ms:.1f}ms avg")


if __name__ == '__main__':
    main()


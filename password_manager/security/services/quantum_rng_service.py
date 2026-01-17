"""
Quantum Random Number Generator Service
========================================

Provides true random number generation using quantum computing APIs.
Supports multiple quantum providers with fallback mechanisms.

Providers:
- ANU QRNG (Australian National University) - Free, reliable REST API
- IBM Qiskit - Real quantum hardware via cloud
- IonQ Quantum Cloud - Enterprise trapped-ion qubits
"""

import os
import uuid
import hashlib
import logging
import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import base64
import hmac

# For HTTP requests
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# For IBM Qiskit
try:
    from qiskit import QuantumCircuit
    from qiskit_ibm_runtime import QiskitRuntimeService
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False

logger = logging.getLogger(__name__)


class QuantumProvider(Enum):
    """Available quantum random number generator providers."""
    ANU = "anu_qrng"
    IBM = "ibm_quantum"
    IONQ = "ionq_quantum"
    FALLBACK = "cryptographic_fallback"


@dataclass
class QuantumEntropyBatch:
    """Represents a batch of quantum-derived entropy."""
    provider: QuantumProvider
    entropy_bytes: bytes
    fetched_at: datetime
    certificate_id: str
    circuit_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class QuantumCertificate:
    """Certificate proving quantum origin of random data."""
    certificate_id: str
    password_hash_prefix: str
    provider: str
    generation_timestamp: datetime
    quantum_source: str
    entropy_bits: int
    circuit_id: Optional[str]
    signature: str
    
    def to_dict(self) -> Dict:
        return {
            "certificate_id": self.certificate_id,
            "password_hash_prefix": self.password_hash_prefix,
            "provider": self.provider,
            "generation_timestamp": self.generation_timestamp.isoformat(),
            "quantum_source": self.quantum_source,
            "entropy_bits": self.entropy_bits,
            "circuit_id": self.circuit_id,
            "signature": self.signature
        }


class QuantumRNGProvider(ABC):
    """Abstract base class for quantum RNG providers."""
    
    @abstractmethod
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """
        Fetch random bytes from quantum source.
        
        Args:
            count: Number of random bytes to generate
            
        Returns:
            Tuple of (random_bytes, circuit_id)
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> QuantumProvider:
        """Return the provider identifier."""
        pass
    
    @abstractmethod
    def get_quantum_source(self) -> str:
        """Return description of quantum phenomenon used."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        pass


class ANUQuantumProvider(QuantumRNGProvider):
    """
    Australian National University Quantum Random Number Generator.
    
    Uses quantum vacuum fluctuations to generate true random numbers.
    API: https://qrng.anu.edu.au/
    
    Advantages:
    - Free to use
    - No authentication required
    - Fast and reliable
    - Quantum source: Vacuum fluctuations
    """
    
    BASE_URL = "https://qrng.anu.edu.au/API/jsonI.php"
    MAX_ARRAY_LENGTH = 1024
    
    def __init__(self):
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            if not HTTPX_AVAILABLE:
                raise RuntimeError("httpx not installed. Run: pip install httpx")
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """Fetch random bytes from ANU QRNG API."""
        client = await self._get_client()
        
        # ANU returns uint8 (0-255), perfect for bytes
        # We may need multiple requests for large counts
        all_bytes = []
        remaining = count
        
        while remaining > 0:
            batch_size = min(remaining, self.MAX_ARRAY_LENGTH)
            
            try:
                response = await client.get(
                    self.BASE_URL,
                    params={
                        "length": batch_size,
                        "type": "uint8"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("success"):
                    random_values = data.get("data", [])
                    all_bytes.extend(random_values)
                    remaining -= len(random_values)
                else:
                    raise RuntimeError(f"ANU API error: {data}")
                    
            except Exception as e:
                logger.error(f"ANU QRNG fetch failed: {e}")
                raise
        
        return bytes(all_bytes[:count]), None
    
    def get_provider_name(self) -> QuantumProvider:
        return QuantumProvider.ANU
    
    def get_quantum_source(self) -> str:
        return "vacuum_fluctuations"
    
    def is_available(self) -> bool:
        return HTTPX_AVAILABLE


class IBMQuantumProvider(QuantumRNGProvider):
    """
    IBM Quantum random number generator using Qiskit.
    
    Uses Hadamard gates to create superposition states on real quantum hardware.
    Measurements collapse to truly random classical bits.
    
    Advantages:
    - Real quantum hardware execution
    - Verifiable circuit execution ID
    - Multiple backends available
    """
    
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get("IBM_QUANTUM_TOKEN")
        self._service = None
    
    def _get_service(self):
        if self._service is None:
            if not QISKIT_AVAILABLE:
                raise RuntimeError("Qiskit not installed. Run: pip install qiskit qiskit-ibm-runtime")
            self._service = QiskitRuntimeService(
                channel="ibm_quantum",
                token=self.api_token
            )
        return self._service
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """Generate random bytes using IBM quantum hardware."""
        if not self.is_available():
            raise RuntimeError("IBM Quantum not available or not configured")
        
        service = self._get_service()
        
        # We need count * 8 qubits for count bytes
        # But quantum computers have limited qubits, so we batch
        n_bits = count * 8
        max_qubits = 127  # IBM Eagle processor
        
        all_bits = []
        job_id = None
        
        # Generate in batches fitting qubit limit
        remaining_bits = n_bits
        while remaining_bits > 0:
            batch_bits = min(remaining_bits, max_qubits)
            
            # Create quantum circuit with Hadamard gates
            qc = QuantumCircuit(batch_bits, batch_bits)
            qc.h(range(batch_bits))  # Apply Hadamard to create superposition
            qc.measure(range(batch_bits), range(batch_bits))
            
            # Run on least busy backend
            backend = service.least_busy(simulator=False, operational=True)
            
            # Execute circuit (this runs synchronously)
            job = backend.run(qc, shots=1)
            job_id = job.job_id()
            result = job.result()
            
            # Get measurement result (bit string)
            counts = result.get_counts()
            bit_string = list(counts.keys())[0]
            all_bits.extend([int(b) for b in bit_string])
            
            remaining_bits -= batch_bits
        
        # Convert bits to bytes
        random_bytes = self._bits_to_bytes(all_bits[:n_bits])
        
        return random_bytes, job_id
    
    def _bits_to_bytes(self, bits: List[int]) -> bytes:
        """Convert list of bits to bytes."""
        result = []
        for i in range(0, len(bits), 8):
            byte_bits = bits[i:i+8]
            byte_val = sum(b << (7-j) for j, b in enumerate(byte_bits))
            result.append(byte_val)
        return bytes(result)
    
    def get_provider_name(self) -> QuantumProvider:
        return QuantumProvider.IBM
    
    def get_quantum_source(self) -> str:
        return "superconducting_qubit_superposition"
    
    def is_available(self) -> bool:
        return QISKIT_AVAILABLE and bool(self.api_token)


class IonQQuantumProvider(QuantumRNGProvider):
    """
    IonQ Quantum random number generator.
    
    Uses trapped-ion quantum technology to generate true random numbers
    via the IonQ Cloud API. Trapped-ion qubits offer high fidelity and
    long coherence times.
    
    API Documentation: https://docs.ionq.com/
    
    Advantages:
    - High-fidelity trapped-ion qubits
    - All-to-all qubit connectivity
    - Low error rates
    - Enterprise-grade reliability
    
    Requirements:
    - IONQ_API_KEY environment variable
    - httpx library for API calls
    """
    
    BASE_URL = "https://api.ionq.co/v0.3"
    MAX_QUBITS = 32  # IonQ Aria has up to 25+ qubits
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("IONQ_API_KEY")
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            if not HTTPX_AVAILABLE:
                raise RuntimeError("httpx not installed. Run: pip install httpx")
            self._client = httpx.AsyncClient(
                timeout=120.0,  # IonQ jobs can take time
                headers={
                    "Authorization": f"apiKey {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """
        Generate random bytes using IonQ trapped-ion quantum hardware.
        
        Creates a circuit with Hadamard gates on all qubits to create
        superposition states. Measurement collapses to random bits.
        """
        if not self.is_available():
            raise RuntimeError("IonQ Quantum not available or not configured")
        
        client = await self._get_client()
        
        # Calculate qubits needed
        n_bits = count * 8
        all_bits = []
        job_id = None
        
        # Generate in batches fitting qubit limit
        remaining_bits = n_bits
        while remaining_bits > 0:
            batch_bits = min(remaining_bits, self.MAX_QUBITS)
            
            # Build IonQ circuit JSON
            # Apply Hadamard (using GPI2) on each qubit for superposition
            circuit = self._build_hadamard_circuit(batch_bits)
            
            try:
                # Submit job to IonQ
                job_response = await client.post(
                    f"{self.BASE_URL}/jobs",
                    json={
                        "target": "ionq.qpu.aria-1",  # Use Aria QPU
                        "shots": 1,
                        "input": {
                            "format": "ionq.circuit.v0",
                            "gateset": "qis",
                            "qubits": batch_bits,
                            "circuit": circuit
                        }
                    }
                )
                job_response.raise_for_status()
                job_data = job_response.json()
                job_id = job_data.get("id")
                
                # Poll for job completion
                result_bits = await self._poll_job_result(client, job_id, batch_bits)
                all_bits.extend(result_bits)
                
                remaining_bits -= batch_bits
                
            except Exception as e:
                logger.error(f"IonQ job failed: {e}")
                raise
        
        # Convert bits to bytes
        random_bytes = self._bits_to_bytes(all_bits[:n_bits])
        
        return random_bytes, job_id
    
    def _build_hadamard_circuit(self, n_qubits: int) -> List[Dict]:
        """
        Build IonQ circuit JSON for Hadamard gates.
        
        IonQ uses GPI2 gate with phi=0 to achieve Hadamard-like behavior,
        or we can use the native 'h' gate in the QIS gateset.
        """
        circuit = []
        
        # Apply Hadamard to each qubit
        for qubit in range(n_qubits):
            circuit.append({
                "gate": "h",
                "target": qubit
            })
        
        # Measure all qubits (implicit in IonQ - all qubits measured at end)
        return circuit
    
    async def _poll_job_result(
        self, 
        client: "httpx.AsyncClient", 
        job_id: str, 
        n_qubits: int,
        max_wait_seconds: int = 300
    ) -> List[int]:
        """Poll IonQ for job completion and extract result bits."""
        import asyncio
        
        start_time = time.time()
        poll_interval = 2.0  # Start with 2 second polling
        
        while time.time() - start_time < max_wait_seconds:
            response = await client.get(f"{self.BASE_URL}/jobs/{job_id}")
            response.raise_for_status()
            job_data = response.json()
            
            status = job_data.get("status")
            
            if status == "completed":
                # Extract measurement results
                # IonQ returns histogram of results
                results = job_data.get("data", {}).get("histogram", {})
                
                if results:
                    # Get the single shot result (most likely outcome)
                    bit_string = max(results.keys(), key=lambda k: results[k])
                    # Pad to n_qubits if needed
                    bit_string = bit_string.zfill(n_qubits)
                    return [int(b) for b in bit_string]
                else:
                    raise RuntimeError(f"No results from IonQ job {job_id}")
                    
            elif status == "failed":
                error = job_data.get("failure", {}).get("error", "Unknown error")
                raise RuntimeError(f"IonQ job failed: {error}")
                
            elif status in ("ready", "submitted", "running"):
                # Still processing, wait and poll again
                await asyncio.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 10.0)  # Exponential backoff
            else:
                raise RuntimeError(f"Unknown IonQ job status: {status}")
        
        raise TimeoutError(f"IonQ job {job_id} timed out after {max_wait_seconds}s")
    
    def _bits_to_bytes(self, bits: List[int]) -> bytes:
        """Convert list of bits to bytes."""
        result = []
        for i in range(0, len(bits), 8):
            byte_bits = bits[i:i+8]
            # Pad if needed
            while len(byte_bits) < 8:
                byte_bits.append(0)
            byte_val = sum(b << (7-j) for j, b in enumerate(byte_bits))
            result.append(byte_val)
        return bytes(result)
    
    def get_provider_name(self) -> QuantumProvider:
        return QuantumProvider.IONQ
    
    def get_quantum_source(self) -> str:
        return "trapped_ion_superposition"
    
    def is_available(self) -> bool:
        return HTTPX_AVAILABLE and bool(self.api_key)


class FallbackCryptoProvider(QuantumRNGProvider):
    """
    Cryptographic fallback when quantum providers are unavailable.
    
    Uses os.urandom() which is cryptographically secure but not quantum.
    Should only be used as last resort.
    """
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        return os.urandom(count), None
    
    def get_provider_name(self) -> QuantumProvider:
        return QuantumProvider.FALLBACK
    
    def get_quantum_source(self) -> str:
        return "cryptographic_prng"
    
    def is_available(self) -> bool:
        return True


class QuantumEntropyPool:
    """
    Pre-fetched quantum entropy pool for low-latency password generation.
    
    Maintains a buffer of quantum random bytes that can be consumed
    immediately without waiting for API calls.
    """
    
    def __init__(
        self,
        min_pool_size: int = 1024,
        max_pool_size: int = 4096,
        batch_size: int = 512,
        expiry_hours: int = 24
    ):
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.batch_size = batch_size
        self.expiry_hours = expiry_hours
        
        self._pool: List[QuantumEntropyBatch] = []
        self._total_available: int = 0
        self._lock = asyncio.Lock()
        
        # Provider priority order
        self._providers: List[QuantumRNGProvider] = [
            ANUQuantumProvider(),
            IBMQuantumProvider(),
            IonQQuantumProvider(),
            FallbackCryptoProvider(),
        ]
    
    async def get_random_bytes(self, count: int) -> Tuple[bytes, QuantumCertificate]:
        """
        Get random bytes from the pool.
        
        Returns:
            Tuple of (random_bytes, certificate)
        """
        async with self._lock:
            # Refill if needed
            if self._total_available < count:
                await self._refill_pool()
            
            # Extract bytes from pool
            result_bytes = bytearray()
            certificate_id = str(uuid.uuid4())
            provider_used = None
            circuit_id = None
            
            while len(result_bytes) < count and self._pool:
                batch = self._pool[0]
                
                # Skip expired batches
                if batch.is_expired():
                    self._pool.pop(0)
                    self._total_available -= len(batch.entropy_bytes)
                    continue
                
                needed = count - len(result_bytes)
                available = len(batch.entropy_bytes)
                
                if available <= needed:
                    # Use entire batch
                    result_bytes.extend(batch.entropy_bytes)
                    provider_used = batch.provider
                    circuit_id = batch.circuit_id
                    self._pool.pop(0)
                    self._total_available -= available
                else:
                    # Use partial batch
                    result_bytes.extend(batch.entropy_bytes[:needed])
                    batch.entropy_bytes = batch.entropy_bytes[needed:]
                    provider_used = batch.provider
                    circuit_id = batch.circuit_id
                    self._total_available -= needed
            
            # Generate certificate
            password_hash = hashlib.sha256(bytes(result_bytes)).hexdigest()
            certificate = self._create_certificate(
                certificate_id=certificate_id,
                password_hash=password_hash,
                provider=provider_used or QuantumProvider.FALLBACK,
                entropy_bits=len(result_bytes) * 8,
                circuit_id=circuit_id
            )
            
            return bytes(result_bytes), certificate
    
    async def _refill_pool(self):
        """Refill the entropy pool from quantum sources."""
        target_size = self.max_pool_size - self._total_available
        
        for provider in self._providers:
            if not provider.is_available():
                continue
            
            try:
                # Fetch batch
                entropy_bytes, circuit_id = await provider.fetch_random_bytes(
                    min(target_size, self.batch_size)
                )
                
                # Create batch entry
                batch = QuantumEntropyBatch(
                    provider=provider.get_provider_name(),
                    entropy_bytes=entropy_bytes,
                    fetched_at=datetime.now(),
                    certificate_id=str(uuid.uuid4()),
                    circuit_id=circuit_id,
                    expires_at=datetime.now() + timedelta(hours=self.expiry_hours)
                )
                
                self._pool.append(batch)
                self._total_available += len(entropy_bytes)
                
                logger.info(
                    f"Refilled pool with {len(entropy_bytes)} bytes from {provider.get_provider_name().value}"
                )
                
                if self._total_available >= self.min_pool_size:
                    break
                    
            except Exception as e:
                logger.warning(f"Provider {provider.get_provider_name().value} failed: {e}")
                continue
    
    def _create_certificate(
        self,
        certificate_id: str,
        password_hash: str,
        provider: QuantumProvider,
        entropy_bits: int,
        circuit_id: Optional[str]
    ) -> QuantumCertificate:
        """Create a signed quantum certificate."""
        # Get quantum source description
        source = "unknown"
        for p in self._providers:
            if p.get_provider_name() == provider:
                source = p.get_quantum_source()
                break
        
        # Create signature
        secret_key = os.environ.get("QUANTUM_CERT_SECRET", "quantum-dice-secret")
        message = f"{certificate_id}:{password_hash[:16]}:{provider.value}:{entropy_bits}"
        signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return QuantumCertificate(
            certificate_id=certificate_id,
            password_hash_prefix=f"sha256:{password_hash[:16]}...",
            provider=provider.value,
            generation_timestamp=datetime.now(),
            quantum_source=source,
            entropy_bits=entropy_bits,
            circuit_id=circuit_id,
            signature=signature
        )
    
    def get_pool_status(self) -> Dict:
        """Get current pool status."""
        return {
            "total_bytes_available": self._total_available,
            "batch_count": len(self._pool),
            "min_pool_size": self.min_pool_size,
            "max_pool_size": self.max_pool_size,
            "health": "good" if self._total_available >= self.min_pool_size else "low"
        }


class QuantumPasswordGenerator:
    """
    Quantum-certified password generator.
    
    Generates passwords using true quantum randomness with
    cryptographic certificates proving quantum origin.
    """
    
    DEFAULT_CHARSETS = {
        "uppercase": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "lowercase": "abcdefghijklmnopqrstuvwxyz",
        "numbers": "0123456789",
        "symbols": "!@#$%^&*()_+-=[]{}|;:,.<>?"
    }
    
    def __init__(self, entropy_pool: Optional[QuantumEntropyPool] = None):
        self.pool = entropy_pool or QuantumEntropyPool()
    
    async def generate_password(
        self,
        length: int = 16,
        use_uppercase: bool = True,
        use_lowercase: bool = True,
        use_numbers: bool = True,
        use_symbols: bool = True,
        custom_charset: Optional[str] = None
    ) -> Tuple[str, QuantumCertificate]:
        """
        Generate a quantum-certified password.
        
        Args:
            length: Password length (8-128)
            use_uppercase: Include uppercase letters
            use_lowercase: Include lowercase letters
            use_numbers: Include digits
            use_symbols: Include special characters
            custom_charset: Optional custom character set
            
        Returns:
            Tuple of (password, quantum_certificate)
        """
        # Validate length
        length = max(8, min(128, length))
        
        # Build charset
        if custom_charset:
            charset = custom_charset
        else:
            charset = ""
            if use_uppercase:
                charset += self.DEFAULT_CHARSETS["uppercase"]
            if use_lowercase:
                charset += self.DEFAULT_CHARSETS["lowercase"]
            if use_numbers:
                charset += self.DEFAULT_CHARSETS["numbers"]
            if use_symbols:
                charset += self.DEFAULT_CHARSETS["symbols"]
            
            if not charset:
                charset = self.DEFAULT_CHARSETS["lowercase"]
        
        # Get quantum random bytes
        # We need extra bytes because of modulo bias reduction
        bytes_needed = length * 2  # Extra for rejection sampling
        random_bytes, certificate = await self.pool.get_random_bytes(bytes_needed)
        
        # Generate password using rejection sampling to avoid modulo bias
        password_chars = []
        byte_index = 0
        charset_len = len(charset)
        
        while len(password_chars) < length and byte_index < len(random_bytes):
            byte_val = random_bytes[byte_index]
            byte_index += 1
            
            # Rejection sampling: only use values that fit evenly
            max_valid = (256 // charset_len) * charset_len
            if byte_val < max_valid:
                password_chars.append(charset[byte_val % charset_len])
        
        # If we ran out of bytes (unlikely), get more
        while len(password_chars) < length:
            extra_bytes, _ = await self.pool.get_random_bytes(1)
            byte_val = extra_bytes[0]
            max_valid = (256 // charset_len) * charset_len
            if byte_val < max_valid:
                password_chars.append(charset[byte_val % charset_len])
        
        return "".join(password_chars), certificate
    
    async def get_raw_random_bytes(self, count: int) -> Tuple[bytes, QuantumCertificate]:
        """Get raw quantum random bytes with certificate."""
        return await self.pool.get_random_bytes(count)
    
    def get_pool_status(self) -> Dict:
        """Get entropy pool status."""
        return self.pool.get_pool_status()


# Singleton instance
_quantum_generator: Optional[QuantumPasswordGenerator] = None


def get_quantum_generator() -> QuantumPasswordGenerator:
    """Get or create the quantum password generator singleton."""
    global _quantum_generator
    if _quantum_generator is None:
        _quantum_generator = QuantumPasswordGenerator()
    return _quantum_generator

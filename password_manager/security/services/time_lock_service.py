"""
Time-Lock Encryption Service
============================

Implements cryptographic time-lock puzzles for delayed password access.
Supports both server-side and client-side solving modes.

Use Cases:
- Emergency access: Family member gets access after 72 hours
- Dead man's switch: Release passwords if user doesn't check in
- Delayed access: Time-sensitive secrets
- Offline recovery: Client can solve puzzle without server

Based on RSA time-lock puzzles (Rivest-Shamir-Wagner, 1996).

@author Password Manager Team
@created 2026-01-17
"""

import os
import time
import hashlib
import secrets
import logging
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import base64
import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Configuration
# =============================================================================

class TimeLockMode(Enum):
    """Time-lock solving modes."""
    SERVER = 'server'    # Server enforces delay (recommended)
    CLIENT = 'client'    # Client solves puzzle (offline capable)
    HYBRID = 'hybrid'    # Both modes available


class TimeLockStatus(Enum):
    """Status of a time-lock capsule."""
    LOCKED = 'locked'
    SOLVING = 'solving'
    UNLOCKED = 'unlocked'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


# Default configuration
DEFAULT_MODULUS_BITS = 2048
DEFAULT_ITERATIONS_PER_SECOND = 100000
MIN_DELAY_SECONDS = 60          # 1 minute minimum
MAX_DELAY_SECONDS = 86400 * 365  # 1 year maximum


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TimeLockPuzzle:
    """Represents a time-lock puzzle."""
    puzzle_id: str
    n: int                  # RSA modulus
    a: int                  # Base value
    t: int                  # Number of squarings required
    encrypted_data: bytes   # AES-encrypted data
    mode: TimeLockMode
    created_at: datetime = field(default_factory=datetime.now)
    unlock_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            'puzzle_id': self.puzzle_id,
            'n': str(self.n),  # Large int as string
            'a': str(self.a),
            't': self.t,
            'encrypted_data': base64.b64encode(self.encrypted_data).decode(),
            'mode': self.mode.value,
            'created_at': self.created_at.isoformat(),
            'unlock_at': self.unlock_at.isoformat() if self.unlock_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TimeLockPuzzle':
        return cls(
            puzzle_id=data['puzzle_id'],
            n=int(data['n']),
            a=int(data['a']),
            t=data['t'],
            encrypted_data=base64.b64decode(data['encrypted_data']),
            mode=TimeLockMode(data['mode']),
            created_at=datetime.fromisoformat(data['created_at']),
            unlock_at=datetime.fromisoformat(data['unlock_at']) if data.get('unlock_at') else None,
        )


@dataclass
class ServerTimeLockCapsule:
    """Server-enforced time-lock capsule."""
    capsule_id: str
    encrypted_data: bytes
    encryption_key_encrypted: bytes  # Key encrypted, released after delay
    unlock_at: datetime
    status: TimeLockStatus = TimeLockStatus.LOCKED
    created_at: datetime = field(default_factory=datetime.now)
    beneficiary_email: Optional[str] = None  # For emergency access
    requires_verification: bool = True
    
    def to_dict(self) -> Dict:
        return {
            'capsule_id': self.capsule_id,
            'unlock_at': self.unlock_at.isoformat(),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'time_remaining_seconds': max(0, (self.unlock_at - datetime.now()).total_seconds()),
            'beneficiary_email': self.beneficiary_email,
        }


# =============================================================================
# Server-Side Time-Lock Service
# =============================================================================

class ServerTimeLockService:
    """
    Server-enforced time-lock service.
    
    Server holds the encrypted password and releases it only after
    the specified delay has elapsed. User cannot skip ahead.
    
    Perfect for:
    - Emergency access for family members
    - Dead man's switch
    - Scheduled access windows
    """
    
    def __init__(self, master_key: bytes = None):
        """
        Initialize server time-lock service.
        
        Args:
            master_key: Master key for encrypting capsule keys
        """
        self.master_key = master_key or os.environ.get(
            'TIMELOCK_MASTER_KEY', 
            Fernet.generate_key()
        )
        if isinstance(self.master_key, str):
            self.master_key = self.master_key.encode()
        
        # Derive Fernet key from master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'timelock_server_salt_v1',
            iterations=100000,
            backend=default_backend()
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(self.master_key[:32]))
        self.fernet = Fernet(derived_key)
    
    def create_capsule(
        self,
        data: bytes,
        delay_seconds: int,
        beneficiary_email: str = None,
        requires_verification: bool = True
    ) -> ServerTimeLockCapsule:
        """
        Create a server-enforced time-lock capsule.
        
        Args:
            data: Data to lock (password bytes)
            delay_seconds: Delay before access is allowed
            beneficiary_email: Optional email for emergency access notification
            requires_verification: Whether to require identity verification
            
        Returns:
            ServerTimeLockCapsule object
        """
        if delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(f"Delay must be at least {MIN_DELAY_SECONDS} seconds")
        if delay_seconds > MAX_DELAY_SECONDS:
            raise ValueError(f"Delay cannot exceed {MAX_DELAY_SECONDS} seconds")
        
        # Generate capsule ID
        capsule_id = secrets.token_urlsafe(16)
        
        # Generate random encryption key for this capsule
        capsule_key = Fernet.generate_key()
        capsule_fernet = Fernet(capsule_key)
        
        # Encrypt the data with capsule-specific key
        encrypted_data = capsule_fernet.encrypt(data)
        
        # Encrypt the capsule key with master key
        # This key is released after the delay
        encryption_key_encrypted = self.fernet.encrypt(capsule_key)
        
        unlock_at = datetime.now() + timedelta(seconds=delay_seconds)
        
        capsule = ServerTimeLockCapsule(
            capsule_id=capsule_id,
            encrypted_data=encrypted_data,
            encryption_key_encrypted=encryption_key_encrypted,
            unlock_at=unlock_at,
            beneficiary_email=beneficiary_email,
            requires_verification=requires_verification,
        )
        
        logger.info(f"Created time-lock capsule {capsule_id}, unlocks at {unlock_at}")
        return capsule
    
    def check_status(self, capsule: ServerTimeLockCapsule) -> Dict:
        """
        Check the status of a capsule.
        
        Returns:
            Status dictionary with remaining time
        """
        now = datetime.now()
        
        if capsule.status in [TimeLockStatus.CANCELLED, TimeLockStatus.EXPIRED]:
            return {
                'status': capsule.status.value,
                'can_unlock': False,
                'time_remaining_seconds': 0,
            }
        
        if now >= capsule.unlock_at:
            return {
                'status': TimeLockStatus.UNLOCKED.value,
                'can_unlock': True,
                'time_remaining_seconds': 0,
            }
        
        remaining = (capsule.unlock_at - now).total_seconds()
        return {
            'status': TimeLockStatus.LOCKED.value,
            'can_unlock': False,
            'time_remaining_seconds': int(remaining),
            'unlock_at': capsule.unlock_at.isoformat(),
        }
    
    def unlock(self, capsule: ServerTimeLockCapsule) -> bytes:
        """
        Unlock a capsule and retrieve the data.
        
        Args:
            capsule: The capsule to unlock
            
        Returns:
            Original data
            
        Raises:
            ValueError: If capsule is still locked
        """
        now = datetime.now()
        
        if capsule.status == TimeLockStatus.CANCELLED:
            raise ValueError("Capsule has been cancelled")
        
        if now < capsule.unlock_at:
            remaining = int((capsule.unlock_at - now).total_seconds())
            raise ValueError(f"Capsule still locked. {remaining} seconds remaining.")
        
        # Decrypt the capsule key
        capsule_key = self.fernet.decrypt(capsule.encryption_key_encrypted)
        capsule_fernet = Fernet(capsule_key)
        
        # Decrypt the data
        data = capsule_fernet.decrypt(capsule.encrypted_data)
        
        capsule.status = TimeLockStatus.UNLOCKED
        logger.info(f"Unlocked capsule {capsule.capsule_id}")
        
        return data
    
    def cancel(self, capsule: ServerTimeLockCapsule) -> bool:
        """
        Cancel a capsule (only owner can do this).
        
        Args:
            capsule: The capsule to cancel
            
        Returns:
            True if cancelled successfully
        """
        capsule.status = TimeLockStatus.CANCELLED
        logger.info(f"Cancelled capsule {capsule.capsule_id}")
        return True


# =============================================================================
# Client-Side Time-Lock Service (RSA Puzzle)
# =============================================================================

class ClientTimeLockService:
    """
    Client-side time-lock using RSA puzzles.
    
    Based on Rivest-Shamir-Wagner time-lock puzzles.
    Requires sequential modular exponentiations that cannot be parallelized.
    
    Perfect for:
    - Offline password recovery
    - Server-independent access
    - Verifiable computation time
    """
    
    def __init__(
        self,
        modulus_bits: int = DEFAULT_MODULUS_BITS,
        iterations_per_second: int = DEFAULT_ITERATIONS_PER_SECOND
    ):
        """
        Initialize client time-lock service.
        
        Args:
            modulus_bits: RSA modulus size (larger = more secure, slower)
            iterations_per_second: Estimated iterations per second on target device
        """
        self.modulus_bits = modulus_bits
        self.iterations_per_second = iterations_per_second
    
    def create_puzzle(
        self,
        data: bytes,
        delay_seconds: int
    ) -> TimeLockPuzzle:
        """
        Create a time-lock puzzle.
        
        Args:
            data: Data to lock
            delay_seconds: Target delay in seconds
            
        Returns:
            TimeLockPuzzle that must be solved to retrieve data
        """
        if delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(f"Delay must be at least {MIN_DELAY_SECONDS} seconds")
        
        # Generate RSA modulus (n = p * q)
        p, q = self._generate_safe_primes()
        n = p * q
        phi_n = (p - 1) * (q - 1)
        
        # Calculate number of squarings needed
        t = delay_seconds * self.iterations_per_second
        
        # Generate random base
        a = secrets.randbelow(n - 2) + 2
        
        # Compute e = 2^t mod phi(n) (fast with knowledge of phi_n)
        e = pow(2, t, phi_n)
        
        # Compute b = a^e mod n (fast)
        b = pow(a, e, n)
        
        # Generate encryption key from b
        key_material = hashlib.sha256(str(b).encode()).digest()
        encryption_key = base64.urlsafe_b64encode(key_material)
        
        # Encrypt data
        fernet = Fernet(encryption_key)
        encrypted_data = fernet.encrypt(data)
        
        puzzle_id = secrets.token_urlsafe(16)
        
        puzzle = TimeLockPuzzle(
            puzzle_id=puzzle_id,
            n=n,
            a=a,
            t=t,
            encrypted_data=encrypted_data,
            mode=TimeLockMode.CLIENT,
            unlock_at=datetime.now() + timedelta(seconds=delay_seconds),
        )
        
        logger.info(f"Created client puzzle {puzzle_id} with {t:,} squarings")
        return puzzle
    
    def solve_puzzle(
        self,
        puzzle: TimeLockPuzzle,
        progress_callback=None
    ) -> bytes:
        """
        Solve a time-lock puzzle to retrieve data.
        
        This requires sequential modular squaring and cannot be sped up.
        
        Args:
            puzzle: The puzzle to solve
            progress_callback: Optional callback(progress_percent, iterations_done)
            
        Returns:
            Original data
        """
        logger.info(f"Starting to solve puzzle {puzzle.puzzle_id}")
        start_time = time.time()
        
        # Sequential squaring: b = a^(2^t) mod n
        b = puzzle.a
        report_interval = puzzle.t // 100  # Report every 1%
        
        for i in range(puzzle.t):
            b = pow(b, 2, puzzle.n)
            
            if progress_callback and report_interval > 0 and i % report_interval == 0:
                progress = (i / puzzle.t) * 100
                progress_callback(progress, i)
        
        elapsed = time.time() - start_time
        logger.info(f"Solved puzzle {puzzle.puzzle_id} in {elapsed:.2f} seconds")
        
        # Derive decryption key from b
        key_material = hashlib.sha256(str(b).encode()).digest()
        encryption_key = base64.urlsafe_b64encode(key_material)
        
        # Decrypt data
        fernet = Fernet(encryption_key)
        data = fernet.decrypt(puzzle.encrypted_data)
        
        return data
    
    def estimate_solve_time(self, puzzle: TimeLockPuzzle) -> Dict:
        """
        Estimate time to solve puzzle on various devices.
        
        Args:
            puzzle: The puzzle to estimate
            
        Returns:
            Dictionary with time estimates
        """
        iterations = puzzle.t
        
        # Rough estimates for different devices
        device_speeds = {
            'high_end_desktop': 150000,
            'laptop': 100000,
            'smartphone': 30000,
            'raspberry_pi': 10000,
        }
        
        estimates = {}
        for device, speed in device_speeds.items():
            seconds = iterations / speed
            estimates[device] = {
                'seconds': int(seconds),
                'human_readable': self._seconds_to_human(seconds),
            }
        
        return estimates
    
    def _generate_safe_primes(self) -> Tuple[int, int]:
        """Generate two safe primes for RSA modulus."""
        # For production, use proper safe prime generation
        # This is a simplified version
        from random import getrandbits
        
        def is_prime(n, k=10):
            """Miller-Rabin primality test."""
            if n < 2:
                return False
            if n == 2 or n == 3:
                return True
            if n % 2 == 0:
                return False
            
            r, d = 0, n - 1
            while d % 2 == 0:
                r += 1
                d //= 2
            
            for _ in range(k):
                a = secrets.randbelow(n - 3) + 2
                x = pow(a, d, n)
                
                if x == 1 or x == n - 1:
                    continue
                
                for _ in range(r - 1):
                    x = pow(x, 2, n)
                    if x == n - 1:
                        break
                else:
                    return False
            
            return True
        
        def generate_prime(bits):
            while True:
                p = getrandbits(bits)
                p |= (1 << bits - 1) | 1  # Ensure odd and correct bit length
                if is_prime(p):
                    return p
        
        half_bits = self.modulus_bits // 2
        p = generate_prime(half_bits)
        q = generate_prime(half_bits)
        
        return p, q
    
    def _seconds_to_human(self, seconds: float) -> str:
        """Convert seconds to human-readable format."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutes"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f} hours"
        else:
            return f"{seconds / 86400:.1f} days"


# =============================================================================
# Hybrid Time-Lock Service
# =============================================================================

class TimeLockService:
    """
    Hybrid time-lock service combining server and client modes.
    
    Provides flexibility between server-enforced and client-solvable puzzles.
    """
    
    def __init__(
        self,
        master_key: bytes = None,
        modulus_bits: int = DEFAULT_MODULUS_BITS
    ):
        self.server_service = ServerTimeLockService(master_key)
        self.client_service = ClientTimeLockService(modulus_bits)
    
    def create_time_lock(
        self,
        data: bytes,
        delay_seconds: int,
        mode: TimeLockMode = TimeLockMode.SERVER,
        **kwargs
    ):
        """
        Create a time-lock of specified mode.
        
        Args:
            data: Data to lock
            delay_seconds: Delay before access
            mode: SERVER, CLIENT, or HYBRID
            **kwargs: Additional mode-specific options
            
        Returns:
            ServerTimeLockCapsule or TimeLockPuzzle
        """
        if mode == TimeLockMode.SERVER:
            return self.server_service.create_capsule(data, delay_seconds, **kwargs)
        elif mode == TimeLockMode.CLIENT:
            return self.client_service.create_puzzle(data, delay_seconds)
        else:
            # HYBRID: create both
            return {
                'server': self.server_service.create_capsule(data, delay_seconds, **kwargs),
                'client': self.client_service.create_puzzle(data, delay_seconds),
            }
    
    def check_status(self, lock) -> Dict:
        """Check status of any time-lock type."""
        if isinstance(lock, ServerTimeLockCapsule):
            return self.server_service.check_status(lock)
        elif isinstance(lock, TimeLockPuzzle):
            return self.client_service.estimate_solve_time(lock)
        elif isinstance(lock, dict):
            return {
                'server': self.server_service.check_status(lock['server']),
                'client': self.client_service.estimate_solve_time(lock['client']),
            }
        else:
            raise ValueError("Unknown lock type")
    
    def unlock(self, lock, **kwargs) -> bytes:
        """Unlock any time-lock type."""
        if isinstance(lock, ServerTimeLockCapsule):
            return self.server_service.unlock(lock)
        elif isinstance(lock, TimeLockPuzzle):
            return self.client_service.solve_puzzle(lock, **kwargs)
        else:
            raise ValueError("Unknown lock type")


# =============================================================================
# Module-level instances
# =============================================================================

time_lock_service = TimeLockService()
server_time_lock = ServerTimeLockService()
client_time_lock = ClientTimeLockService()

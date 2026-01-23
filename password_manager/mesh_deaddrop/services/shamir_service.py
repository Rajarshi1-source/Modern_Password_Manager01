"""
Shamir's Secret Sharing Service
================================

Implements (k,n) threshold secret sharing using finite field arithmetic.

Key Properties:
- Secret is split into n shares
- Any k shares can reconstruct the secret  
- k-1 shares reveal NOTHING about the secret
- Uses Lagrange interpolation for reconstruction

Mathematical basis:
- Secret is encoded as the constant term (a_0) of a random polynomial
- Polynomial: f(x) = a_0 + a_1*x + a_2*x^2 + ... + a_{k-1}*x^{k-1}
- Shares are evaluations: (i, f(i)) for i = 1..n
- Reconstruction uses Lagrange interpolation at x=0

Security:
- Uses cryptographically secure random coefficients
- Operates in GF(p) where p is a large prime
- Includes Feldman VSS commitments for verification

@author Password Manager Team
@created 2026-01-22
"""

import secrets
import hashlib
from typing import List, Tuple, Optional
from dataclasses import dataclass

# Large prime for finite field operations (256-bit)
# This prime p = 2^256 - 189 is suitable for secrets up to 256 bits
DEFAULT_PRIME = 2**256 - 189


@dataclass
class Share:
    """A single Shamir share."""
    index: int  # x-coordinate (1 to n)
    value: bytes  # y-coordinate as bytes
    commitment: Optional[bytes] = None  # Feldman VSS commitment


@dataclass
class SplitResult:
    """Result of splitting a secret."""
    shares: List[Share]
    commitments: List[bytes]  # Feldman commitments for verification
    original_hash: str  # BLAKE3 hash of original secret


class ShamirSecretSharingService:
    """
    Shamir's Secret Sharing with Feldman VSS verification.
    
    Usage:
        service = ShamirSecretSharingService()
        
        # Split secret into 5 shares, need 3 to reconstruct
        result = service.split_secret(b"my secret", k=3, n=5)
        
        # Reconstruct from any 3+ shares
        secret = service.reconstruct_secret(result.shares[:3])
    """
    
    def __init__(self, prime: int = DEFAULT_PRIME):
        """
        Initialize with a prime modulus.
        
        Args:
            prime: Prime number for finite field (default: 2^256 - 189)
        """
        self.prime = prime
        # Generator for Feldman VSS (primitive root mod p)
        # Using 2 as a simple generator for demonstration
        self.generator = 2
    
    def split_secret(
        self, 
        secret: bytes, 
        k: int, 
        n: int,
        with_commitments: bool = True
    ) -> SplitResult:
        """
        Split a secret into n shares with k-threshold.
        
        Args:
            secret: The secret to split (bytes)
            k: Threshold - minimum shares needed to reconstruct
            n: Total number of shares to create
            with_commitments: Include Feldman VSS commitments
            
        Returns:
            SplitResult with shares, commitments, and original hash
            
        Raises:
            ValueError: If k > n or invalid parameters
        """
        if k > n:
            raise ValueError(f"Threshold k ({k}) cannot exceed total shares n ({n})")
        if k < 2:
            raise ValueError("Threshold must be at least 2")
        if n < 2:
            raise ValueError("Must create at least 2 shares")
        if len(secret) == 0:
            raise ValueError("Secret cannot be empty")
        
        # Convert secret to integer
        secret_int = int.from_bytes(secret, 'big')
        if secret_int >= self.prime:
            raise ValueError("Secret too large for current prime")
        
        # Generate random polynomial coefficients
        # f(x) = secret + a_1*x + a_2*x^2 + ... + a_{k-1}*x^{k-1}
        coefficients = [secret_int]
        for _ in range(k - 1):
            coeff = secrets.randbelow(self.prime)
            coefficients.append(coeff)
        
        # Generate Feldman commitments: g^a_i mod p
        commitments = []
        if with_commitments:
            for coeff in coefficients:
                commitment = pow(self.generator, coeff, self.prime)
                commitments.append(commitment.to_bytes(32, 'big'))
        
        # Evaluate polynomial at points 1, 2, ..., n
        shares = []
        for x in range(1, n + 1):
            y = self._evaluate_polynomial(coefficients, x)
            share = Share(
                index=x,
                value=y.to_bytes(32, 'big'),
                commitment=commitments[0] if commitments else None
            )
            shares.append(share)
        
        # Hash original secret for verification
        original_hash = hashlib.blake2b(secret, digest_size=32).hexdigest()
        
        return SplitResult(
            shares=shares,
            commitments=commitments,
            original_hash=original_hash
        )
    
    def reconstruct_secret(
        self, 
        shares: List[Share],
        expected_hash: Optional[str] = None
    ) -> bytes:
        """
        Reconstruct secret from k or more shares using Lagrange interpolation.
        
        Args:
            shares: List of shares (at least k)
            expected_hash: Optional BLAKE3 hash to verify result
            
        Returns:
            Reconstructed secret as bytes
            
        Raises:
            ValueError: If insufficient shares or verification fails
        """
        if len(shares) < 2:
            raise ValueError("Need at least 2 shares to reconstruct")
        
        # Extract x,y coordinates
        points = []
        for share in shares:
            x = share.index
            y = int.from_bytes(share.value, 'big')
            points.append((x, y))
        
        # Lagrange interpolation at x=0 to recover secret
        secret_int = self._lagrange_interpolate(0, points)
        
        # Convert back to bytes
        byte_length = (secret_int.bit_length() + 7) // 8
        byte_length = max(1, byte_length)  # At least 1 byte
        secret = secret_int.to_bytes(byte_length, 'big')
        
        # Verify hash if provided
        if expected_hash:
            actual_hash = hashlib.blake2b(secret, digest_size=32).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError("Reconstructed secret hash mismatch - corruption detected")
        
        return secret
    
    def verify_share(
        self, 
        share: Share, 
        commitments: List[bytes],
        k: int
    ) -> bool:
        """
        Verify a share using Feldman VSS commitments.
        
        Uses the property: g^{f(i)} = prod(C_j^{i^j}) for j=0..k-1
        where C_j = g^{a_j} are the commitments
        
        Args:
            share: The share to verify
            commitments: Feldman commitments [g^a_0, g^a_1, ...]
            k: Threshold (number of commitments expected)
            
        Returns:
            True if share is valid, False otherwise
        """
        if not commitments or len(commitments) < k:
            return False
        
        x = share.index
        y = int.from_bytes(share.value, 'big')
        
        # Compute g^y mod p
        left_side = pow(self.generator, y, self.prime)
        
        # Compute product of C_j^{x^j}
        right_side = 1
        x_power = 1
        for j, commitment_bytes in enumerate(commitments[:k]):
            C_j = int.from_bytes(commitment_bytes, 'big')
            right_side = (right_side * pow(C_j, x_power, self.prime)) % self.prime
            x_power = (x_power * x) % self.prime
        
        return left_side == right_side
    
    def _evaluate_polynomial(self, coefficients: List[int], x: int) -> int:
        """
        Evaluate polynomial at point x using Horner's method.
        
        f(x) = a_0 + a_1*x + a_2*x^2 + ... 
             = a_0 + x*(a_1 + x*(a_2 + ...))
        """
        result = 0
        for coeff in reversed(coefficients):
            result = (result * x + coeff) % self.prime
        return result
    
    def _lagrange_interpolate(self, x: int, points: List[Tuple[int, int]]) -> int:
        """
        Lagrange interpolation at point x.
        
        L(x) = sum_{i} y_i * prod_{j!=i} (x - x_j) / (x_i - x_j)
        """
        n = len(points)
        result = 0
        
        for i in range(n):
            xi, yi = points[i]
            
            # Compute Lagrange basis polynomial at x
            numerator = 1
            denominator = 1
            
            for j in range(n):
                if i != j:
                    xj, _ = points[j]
                    numerator = (numerator * (x - xj)) % self.prime
                    denominator = (denominator * (xi - xj)) % self.prime
            
            # Modular division: numerator / denominator = numerator * denominator^(-1)
            # Using Fermat's little theorem: a^(-1) = a^(p-2) mod p
            denominator_inv = pow(denominator, self.prime - 2, self.prime)
            
            term = (yi * numerator * denominator_inv) % self.prime
            result = (result + term) % self.prime
        
        return result
    
    def generate_refresh_shares(
        self, 
        old_shares: List[Share], 
        k: int, 
        n: int
    ) -> List[Share]:
        """
        Proactive share refresh - generate new shares without reconstructing secret.
        
        Adds shares of zero (which doesn't change the secret) but changes
        all share values, invalidating old shares.
        
        Args:
            old_shares: Current shares (need at least k)
            k: Threshold
            n: Number of new shares to generate
            
        Returns:
            New shares with same secret but different values
        """
        # Generate a random polynomial with zero constant term
        # g(x) = 0 + b_1*x + b_2*x^2 + ... + b_{k-1}*x^{k-1}
        refresh_coeffs = [0]  # Zero constant term
        for _ in range(k - 1):
            refresh_coeffs.append(secrets.randbelow(self.prime))
        
        # Add refresh polynomial values to old shares
        new_shares = []
        for i, old_share in enumerate(old_shares):
            x = old_share.index
            old_y = int.from_bytes(old_share.value, 'big')
            refresh_y = self._evaluate_polynomial(refresh_coeffs, x)
            new_y = (old_y + refresh_y) % self.prime
            
            new_share = Share(
                index=x,
                value=new_y.to_bytes(32, 'big'),
                commitment=None  # Would need to recompute
            )
            new_shares.append(new_share)
        
        return new_shares


# Module-level instance
shamir_service = ShamirSecretSharingService()

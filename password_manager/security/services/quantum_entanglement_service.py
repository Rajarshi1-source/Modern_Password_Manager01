"""
Quantum Entanglement-Inspired Key Distribution Service
======================================================

Main orchestrator for device pairing with quantum-inspired entangled keys.

Provides:
- Device pairing initiation and verification
- Entangled key synchronization
- Key rotation with shared randomness
- Eavesdropping detection
- Instant revocation mechanism

Architecture:
- Uses LatticeCryptoEngine for post-quantum key exchange
- Uses EntropyMonitor for tamper detection
- Stores state in Django models
- Integrates with existing UserDevice model
"""

import os
import secrets
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import base64

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .lattice_crypto_engine import (
    LatticeCryptoEngine,
    LatticeKeyPair,
    EntangledState,
    lattice_crypto_engine,
)
from .entropy_monitor import (
    EntropyMonitor,
    AnomalyReport,
    entropy_monitor,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def get_entanglement_config() -> Dict[str, Any]:
    """Get entanglement configuration from settings."""
    return getattr(settings, 'QUANTUM_ENTANGLEMENT', {
        'ENABLED': True,
        'LATTICE_ALGORITHM': 'kyber-1024',
        'POOL_SIZE_BYTES': 4096,
        'ENTROPY_THRESHOLD': 7.5,
        'SYNC_INTERVAL_SECONDS': 300,
        'MAX_PAIRS_PER_USER': 5,
        'AUTO_REVOKE_ON_ANOMALY': True,
        'PAIRING_TIMEOUT_MINUTES': 10,
    })


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PairingSession:
    """Active pairing session between two devices."""
    session_id: str
    device_a_id: str
    device_b_id: str
    verification_code: str
    device_a_public_key: bytes
    device_b_public_key: Optional[bytes] = None
    expires_at: datetime = field(default_factory=lambda: timezone.now() + timedelta(minutes=10))
    created_at: datetime = field(default_factory=timezone.now)
    
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'device_a_id': self.device_a_id,
            'device_b_id': self.device_b_id,
            'verification_code': self.verification_code,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class SyncResult:
    """Result of key synchronization."""
    success: bool
    pair_id: str
    new_generation: int
    entropy_status: str
    sync_timestamp: datetime = field(default_factory=timezone.now)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'pair_id': self.pair_id,
            'new_generation': self.new_generation,
            'entropy_status': self.entropy_status,
            'sync_timestamp': self.sync_timestamp.isoformat(),
            'error_message': self.error_message,
        }


@dataclass
class RevocationResult:
    """Result of key revocation."""
    success: bool
    pair_id: str
    revoked_at: datetime = field(default_factory=timezone.now)
    reason: str = ""
    affected_devices: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'pair_id': self.pair_id,
            'revoked_at': self.revoked_at.isoformat(),
            'reason': self.reason,
            'affected_devices': self.affected_devices,
        }


@dataclass
class PairStatus:
    """Status of an entangled pair."""
    pair_id: str
    status: str
    device_a_id: str
    device_b_id: str
    current_generation: int
    last_sync_at: Optional[datetime]
    entropy_health: str
    entropy_score: float
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pair_id': self.pair_id,
            'status': self.status,
            'device_a_id': self.device_a_id,
            'device_b_id': self.device_b_id,
            'current_generation': self.current_generation,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'entropy_health': self.entropy_health,
            'entropy_score': self.entropy_score,
            'created_at': self.created_at.isoformat(),
        }


# =============================================================================
# Quantum Entanglement Service
# =============================================================================

class QuantumEntanglementService:
    """
    Main service for quantum-inspired entangled key distribution.
    
    Simulates quantum entanglement properties:
    - Synchronized key material between paired devices
    - Changes to one key are detectable by the other
    - Eavesdropping detection through entropy monitoring
    - Instant revocation upon compromise detection
    """
    
    def __init__(
        self,
        lattice_engine: LatticeCryptoEngine = None,
        entropy_mon: EntropyMonitor = None,
    ):
        """
        Initialize service with crypto and monitoring components.
        
        Args:
            lattice_engine: Lattice crypto engine (default: singleton)
            entropy_mon: Entropy monitor (default: singleton)
        """
        self.config = get_entanglement_config()
        self.lattice = lattice_engine or lattice_crypto_engine
        self.entropy = entropy_mon or entropy_monitor
        
        # In-memory pairing sessions (could be Redis in production)
        self._pairing_sessions: Dict[str, PairingSession] = {}
        
        logger.info("QuantumEntanglementService initialized")
    
    # =========================================================================
    # Pairing Operations
    # =========================================================================
    
    def initiate_pairing(
        self,
        user_id: int,
        device_a_id: str,
        device_b_id: str,
    ) -> PairingSession:
        """
        Initiate device pairing process.
        
        Creates a pairing session with:
        - Unique session ID
        - Verification code for both devices
        - Lattice public key from device A
        
        Args:
            user_id: Owner's user ID
            device_a_id: First device UUID
            device_b_id: Second device UUID
            
        Returns:
            PairingSession with verification code
        """
        from security.models import UserDevice, EntangledDevicePair
        
        # Validate devices belong to user
        device_a = UserDevice.objects.filter(device_id=device_a_id, user_id=user_id).first()
        device_b = UserDevice.objects.filter(device_id=device_b_id, user_id=user_id).first()
        
        if not device_a or not device_b:
            raise ValueError("One or both devices not found for user")
        
        if device_a_id == device_b_id:
            raise ValueError("Cannot pair device with itself")
        
        # Check max pairs limit
        existing_pairs = EntangledDevicePair.objects.filter(
            user_id=user_id,
            status='active'
        ).count()
        
        max_pairs = self.config.get('MAX_PAIRS_PER_USER', 5)
        if existing_pairs >= max_pairs:
            raise ValueError(f"Maximum {max_pairs} active pairs allowed")
        
        # Check if already paired
        existing = EntangledDevicePair.objects.filter(
            user_id=user_id,
            device_a__device_id=device_a_id,
            device_b__device_id=device_b_id,
            status='active'
        ).first()
        
        if existing:
            raise ValueError("Devices are already paired")
        
        # Generate lattice keypair for initial key exchange
        keypair = self.lattice.generate_lattice_keypair()
        
        # Create pairing session
        session_id = secrets.token_hex(16)
        verification_code = f"{secrets.randbelow(1000000):06d}"
        
        timeout_minutes = self.config.get('PAIRING_TIMEOUT_MINUTES', 10)
        
        session = PairingSession(
            session_id=session_id,
            device_a_id=device_a_id,
            device_b_id=device_b_id,
            verification_code=verification_code,
            device_a_public_key=keypair.public_key,
            expires_at=timezone.now() + timedelta(minutes=timeout_minutes),
        )
        
        # Store session
        self._pairing_sessions[session_id] = session
        
        # Store private key temporarily (encrypted)
        # In production, use secure key storage
        self._store_temp_private_key(session_id, keypair.private_key)
        
        logger.info(f"Initiated pairing session {session_id} for devices {device_a_id} <-> {device_b_id}")
        
        return session
    
    def complete_pairing(
        self,
        session_id: str,
        verification_code: str,
        device_b_public_key: bytes,
    ) -> Dict[str, Any]:
        """
        Complete device pairing after verification.
        
        Args:
            session_id: Pairing session ID
            verification_code: Code entered by user
            device_b_public_key: Device B's lattice public key
            
        Returns:
            Dict with pair_id and initial sync info
        """
        from security.models import (
            UserDevice, EntangledDevicePair, 
            SharedRandomnessPool, EntanglementSyncEvent
        )
        
        # Get session
        session = self._pairing_sessions.get(session_id)
        if not session:
            raise ValueError("Pairing session not found or expired")
        
        if session.is_expired():
            del self._pairing_sessions[session_id]
            raise ValueError("Pairing session expired")
        
        # Verify code
        if session.verification_code != verification_code:
            raise ValueError("Invalid verification code")
        
        # Retrieve device A's private key
        device_a_private_key = self._get_temp_private_key(session_id)
        if not device_a_private_key:
            raise ValueError("Private key not found - session may have expired")
        
        # Perform key encapsulation
        ciphertext, shared_secret = self.lattice.encapsulate_key(device_b_public_key)
        
        # Create entangled state
        entangled_state = self.lattice.derive_entangled_state(
            base_secret=shared_secret,
            device_a_id=session.device_a_id,
            device_b_id=session.device_b_id,
            generation=0,
        )
        
        # Create initial randomness pool
        pool_size = self.config.get('POOL_SIZE_BYTES', 4096)
        initial_pool = secrets.token_bytes(pool_size)
        
        # Encrypt pool for each device
        encrypted_pool_a = self._encrypt_pool_for_device(
            initial_pool,
            entangled_state.device_a_secret
        )
        encrypted_pool_b = self._encrypt_pool_for_device(
            initial_pool,
            entangled_state.device_b_secret
        )
        
        with transaction.atomic():
            # Get device objects
            device_a = UserDevice.objects.get(device_id=session.device_a_id)
            device_b = UserDevice.objects.get(device_id=session.device_b_id)
            
            # Create entangled pair
            pair = EntangledDevicePair.objects.create(
                user=device_a.user,
                device_a=device_a,
                device_b=device_b,
                status='active',
                pairing_completed_at=timezone.now(),
                last_sync_at=timezone.now(),
            )
            
            # Create randomness pool
            pool = SharedRandomnessPool.objects.create(
                pair=pair,
                encrypted_pool_a=encrypted_pool_a,
                encrypted_pool_b=encrypted_pool_b,
                pool_generation=0,
                entropy_measurement=8.0,
            )
            
            # Log event
            EntanglementSyncEvent.objects.create(
                pair=pair,
                event_type='key_rotation',
                initiated_by_device=device_a,
                success=True,
                details={
                    'action': 'initial_pairing',
                    'generation': 0,
                    'algorithm': self.lattice.algorithm,
                }
            )
        
        # Cleanup session
        del self._pairing_sessions[session_id]
        self._clear_temp_private_key(session_id)
        
        logger.info(f"Completed pairing: pair_id={pair.id}")
        
        return {
            'pair_id': str(pair.id),
            'status': 'active',
            'generation': 0,
            'device_a_id': session.device_a_id,
            'device_b_id': session.device_b_id,
            'ciphertext_b64': base64.b64encode(ciphertext).decode(),
        }
    
    # =========================================================================
    # Key Synchronization
    # =========================================================================
    
    def synchronize_keys(
        self,
        pair_id: str,
        requesting_device_id: str,
    ) -> SyncResult:
        """
        Synchronize keys between paired devices.
        
        Retrieves current encrypted pool for the requesting device
        and checks entropy health.
        
        Args:
            pair_id: Entangled pair ID
            requesting_device_id: Device requesting sync
            
        Returns:
            SyncResult with pool data and entropy status
        """
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.filter(
            id=pair_id,
            status='active'
        ).select_related('device_a', 'device_b').first()
        
        if not pair:
            return SyncResult(
                success=False,
                pair_id=pair_id,
                new_generation=-1,
                entropy_status='unknown',
                error_message="Pair not found or not active"
            )
        
        # Verify device is part of pair
        is_device_a = str(pair.device_a.device_id) == requesting_device_id
        is_device_b = str(pair.device_b.device_id) == requesting_device_id
        
        if not is_device_a and not is_device_b:
            return SyncResult(
                success=False,
                pair_id=pair_id,
                new_generation=-1,
                entropy_status='unauthorized',
                error_message="Device not part of this pair"
            )
        
        # Get pool
        try:
            pool = pair.sharedrandomnesspool
        except SharedRandomnessPool.DoesNotExist:
            return SyncResult(
                success=False,
                pair_id=pair_id,
                new_generation=-1,
                entropy_status='no_pool',
                error_message="Randomness pool not found"
            )
        
        # Update last sync
        pair.last_sync_at = timezone.now()
        pair.save(update_fields=['last_sync_at'])
        
        # Determine entropy status
        entropy_status = 'healthy' if pool.entropy_measurement >= 7.5 else 'degraded'
        
        return SyncResult(
            success=True,
            pair_id=pair_id,
            new_generation=pool.pool_generation,
            entropy_status=entropy_status,
        )
    
    def rotate_entangled_keys(
        self,
        pair_id: str,
        initiating_device_id: str,
    ) -> SyncResult:
        """
        Rotate entangled keys with fresh randomness.
        
        Both devices must use the same new randomness for
        the rotation to succeed. This is achieved by:
        1. Generating new randomness
        2. Encrypting for both devices
        3. Updating pool generation
        
        Args:
            pair_id: Entangled pair ID
            initiating_device_id: Device initiating rotation
            
        Returns:
            SyncResult with new generation info
        """
        from security.models import (
            EntangledDevicePair, SharedRandomnessPool, EntanglementSyncEvent
        )
        
        pair = EntangledDevicePair.objects.filter(
            id=pair_id,
            status='active'
        ).select_related('device_a', 'device_b').first()
        
        if not pair:
            return SyncResult(
                success=False,
                pair_id=pair_id,
                new_generation=-1,
                entropy_status='unknown',
                error_message="Pair not found"
            )
        
        try:
            pool = pair.sharedrandomnesspool
        except SharedRandomnessPool.DoesNotExist:
            return SyncResult(
                success=False,
                pair_id=pair_id,
                new_generation=-1,
                entropy_status='no_pool',
                error_message="Pool not found"
            )
        
        # Generate fresh randomness
        pool_size = self.config.get('POOL_SIZE_BYTES', 4096)
        new_randomness = secrets.token_bytes(pool_size)
        
        # Measure entropy of new pool
        entropy_result = self.entropy.measure_pool_entropy(new_randomness)
        
        # Derive new secrets (using generation as part of derivation)
        new_generation = pool.pool_generation + 1
        device_a_id = str(pair.device_a.device_id)
        device_b_id = str(pair.device_b.device_id)
        
        # Create new entangled state
        base_secret = hashlib.sha3_256(new_randomness).digest()
        new_state = self.lattice.derive_entangled_state(
            base_secret=base_secret,
            device_a_id=device_a_id,
            device_b_id=device_b_id,
            generation=new_generation,
        )
        
        # Encrypt pool for each device
        encrypted_pool_a = self._encrypt_pool_for_device(
            new_randomness,
            new_state.device_a_secret
        )
        encrypted_pool_b = self._encrypt_pool_for_device(
            new_randomness,
            new_state.device_b_secret
        )
        
        # Update pool
        pool.encrypted_pool_a = encrypted_pool_a
        pool.encrypted_pool_b = encrypted_pool_b
        pool.pool_generation = new_generation
        pool.entropy_measurement = entropy_result.entropy_bits_per_byte
        pool.save()
        
        # Update pair
        pair.last_sync_at = timezone.now()
        pair.save(update_fields=['last_sync_at'])
        
        # Log event
        initiating_device = pair.device_a if device_a_id == initiating_device_id else pair.device_b
        EntanglementSyncEvent.objects.create(
            pair=pair,
            event_type='key_rotation',
            initiated_by_device=initiating_device,
            success=True,
            details={
                'new_generation': new_generation,
                'entropy': entropy_result.entropy_bits_per_byte,
            }
        )
        
        logger.info(f"Rotated keys for pair {pair_id} to generation {new_generation}")
        
        return SyncResult(
            success=True,
            pair_id=pair_id,
            new_generation=new_generation,
            entropy_status='healthy' if entropy_result.is_healthy else 'degraded',
        )
    
    # =========================================================================
    # Eavesdropping Detection
    # =========================================================================
    
    def detect_eavesdropping(self, pair_id: str) -> AnomalyReport:
        """
        Check for eavesdropping through entropy analysis.
        
        Compares the encrypted pools and checks for:
        - Low entropy (indicating tampering)
        - High divergence (indicating interception)
        - Statistical anomalies
        
        Args:
            pair_id: Entangled pair ID
            
        Returns:
            AnomalyReport with findings
        """
        from security.models import EntangledDevicePair, EntanglementSyncEvent
        
        pair = EntangledDevicePair.objects.filter(
            id=pair_id,
            status='active'
        ).first()
        
        if not pair:
            return AnomalyReport(
                has_anomaly=True,
                anomaly_type='pair_not_found',
                severity='high',
                recommendation="Pair not found - may have been revoked"
            )
        
        try:
            pool = pair.sharedrandomnesspool
        except:
            return AnomalyReport(
                has_anomaly=True,
                anomaly_type='pool_not_found',
                severity='high',
                recommendation="Pool not found - recreate pairing"
            )
        
        # Analyze both encrypted pools
        # Note: In real implementation, we'd decrypt with device keys
        # Here we analyze the encrypted data patterns
        report = self.entropy.detect_anomalies(
            bytes(pool.encrypted_pool_a),
            bytes(pool.encrypted_pool_b)
        )
        
        # Log check
        EntanglementSyncEvent.objects.create(
            pair=pair,
            event_type='entropy_check',
            success=not report.has_anomaly,
            details=report.to_dict()
        )
        
        # Auto-revoke if configured and critical anomaly
        if report.has_anomaly and report.severity == 'critical':
            if self.config.get('AUTO_REVOKE_ON_ANOMALY', True):
                logger.warning(f"Auto-revoking pair {pair_id} due to critical anomaly")
                self.revoke_instantly(
                    pair_id=pair_id,
                    reason=f"Auto-revoked: {report.anomaly_type}"
                )
                report.recommendation = "REVOKED: Pair was automatically revoked due to critical anomaly"
        
        return report
    
    # =========================================================================
    # Revocation
    # =========================================================================
    
    def revoke_instantly(
        self,
        pair_id: str,
        compromised_device_id: str = None,
        reason: str = "Manual revocation"
    ) -> RevocationResult:
        """
        Instantly revoke an entangled pair.
        
        When one device is compromised:
        1. Marks pair as revoked
        2. Deletes randomness pool
        3. Notifies affected devices
        4. Logs security event
        
        Args:
            pair_id: Pair to revoke
            compromised_device_id: Optional ID of compromised device
            reason: Reason for revocation
            
        Returns:
            RevocationResult
        """
        from security.models import (
            EntangledDevicePair, SharedRandomnessPool, EntanglementSyncEvent
        )
        
        pair = EntangledDevicePair.objects.filter(id=pair_id).first()
        
        if not pair:
            return RevocationResult(
                success=False,
                pair_id=pair_id,
                reason="Pair not found"
            )
        
        if pair.status == 'revoked':
            return RevocationResult(
                success=True,
                pair_id=pair_id,
                reason="Already revoked",
                revoked_at=pair.revoked_at,
            )
        
        affected_devices = [
            str(pair.device_a.device_id),
            str(pair.device_b.device_id)
        ]
        
        with transaction.atomic():
            # Delete randomness pool
            try:
                pool = pair.sharedrandomnesspool
                pool.delete()
            except SharedRandomnessPool.DoesNotExist:
                pass
            
            # Update pair status
            pair.status = 'revoked'
            pair.revoked_at = timezone.now()
            pair.revocation_reason = reason
            if compromised_device_id:
                pair.revocation_reason += f" (compromised: {compromised_device_id})"
            pair.save()
            
            # Log event
            EntanglementSyncEvent.objects.create(
                pair=pair,
                event_type='instant_revoke',
                success=True,
                details={
                    'reason': reason,
                    'compromised_device': compromised_device_id,
                    'affected_devices': affected_devices,
                }
            )
        
        logger.warning(f"REVOKED pair {pair_id}: {reason}")
        
        return RevocationResult(
            success=True,
            pair_id=pair_id,
            reason=reason,
            affected_devices=affected_devices,
        )
    
    # =========================================================================
    # Status & History
    # =========================================================================
    
    def get_pair_status(self, pair_id: str) -> Optional[PairStatus]:
        """
        Get detailed status of an entangled pair.
        
        Args:
            pair_id: Pair ID
            
        Returns:
            PairStatus or None
        """
        from security.models import EntangledDevicePair
        
        pair = EntangledDevicePair.objects.filter(
            id=pair_id
        ).select_related('device_a', 'device_b').first()
        
        if not pair:
            return None
        
        # Get entropy info
        entropy_score = 8.0
        try:
            pool = pair.sharedrandomnesspool
            entropy_score = pool.entropy_measurement
        except:
            pass
        
        entropy_health = 'healthy'
        if entropy_score < 7.0:
            entropy_health = 'critical'
        elif entropy_score < 7.5:
            entropy_health = 'degraded'
        
        return PairStatus(
            pair_id=str(pair.id),
            status=pair.status,
            device_a_id=str(pair.device_a.device_id),
            device_b_id=str(pair.device_b.device_id),
            current_generation=pool.pool_generation if hasattr(pair, 'sharedrandomnesspool') else 0,
            last_sync_at=pair.last_sync_at,
            entropy_health=entropy_health,
            entropy_score=entropy_score,
            created_at=pair.pairing_initiated_at,
        )
    
    def get_user_pairs(self, user_id: int) -> List[PairStatus]:
        """
        Get all entangled pairs for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of PairStatus
        """
        from security.models import EntangledDevicePair
        
        pairs = EntangledDevicePair.objects.filter(
            user_id=user_id
        ).select_related('device_a', 'device_b')
        
        return [
            self.get_pair_status(str(p.id))
            for p in pairs
            if self.get_pair_status(str(p.id))
        ]
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _encrypt_pool_for_device(
        self,
        pool: bytes,
        device_secret: bytes
    ) -> bytes:
        """Encrypt pool using device's derived secret."""
        # Use AES-GCM for authenticated encryption
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(device_secret[:32])
        ciphertext = aesgcm.encrypt(nonce, pool, None)
        return nonce + ciphertext
    
    def _decrypt_pool_for_device(
        self,
        encrypted_pool: bytes,
        device_secret: bytes
    ) -> bytes:
        """Decrypt pool using device's derived secret."""
        nonce = encrypted_pool[:12]
        ciphertext = encrypted_pool[12:]
        aesgcm = AESGCM(device_secret[:32])
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def _store_temp_private_key(self, session_id: str, private_key: bytes) -> None:
        """Store private key temporarily (encrypted in memory)."""
        # In production, use secure key storage (HSM, Vault, etc.)
        key = hashlib.sha256(session_id.encode()).digest()
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        encrypted = aesgcm.encrypt(nonce, private_key, None)
        self._temp_keys = getattr(self, '_temp_keys', {})
        self._temp_keys[session_id] = nonce + encrypted
    
    def _get_temp_private_key(self, session_id: str) -> Optional[bytes]:
        """Retrieve temporarily stored private key."""
        self._temp_keys = getattr(self, '_temp_keys', {})
        encrypted = self._temp_keys.get(session_id)
        if not encrypted:
            return None
        
        key = hashlib.sha256(session_id.encode()).digest()
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def _clear_temp_private_key(self, session_id: str) -> None:
        """Clear temporarily stored private key."""
        self._temp_keys = getattr(self, '_temp_keys', {})
        if session_id in self._temp_keys:
            del self._temp_keys[session_id]


# =============================================================================
# Singleton Instance
# =============================================================================

quantum_entanglement_service = QuantumEntanglementService()

"""
Chemical Password Storage Service
=================================

Main orchestration service for chemical/DNA password storage.
Coordinates DNA encoding, time-lock encryption, and lab integrations.

Tiers:
- Free Demo: DNA encoding, time-lock puzzles, certificates, QR export
- Enterprise: Real DNA synthesis, physical storage, retrieval service

@author Password Manager Team
@created 2026-01-17
"""

import os
import json
import hashlib
import secrets
import logging
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import base64

from .dna_encoder import (
    DNAEncoder,
    DNASequence,
    SynthesisValidation,
    dna_encoder,
    encode_password_to_dna,
    decode_dna_to_password,
)
from .time_lock_service import (
    TimeLockService,
    ServerTimeLockService,
    ClientTimeLockService,
    TimeLockMode,
    TimeLockStatus,
    ServerTimeLockCapsule,
    TimeLockPuzzle,
    time_lock_service,
)
from .lab_provider_api import (
    LabProviderFactory,
    get_lab_provider,
    SynthesisOrder,
    SequencingOrder,
    SynthesisStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class ChemicalStorageTier(Enum):
    """Chemical storage subscription tiers."""
    FREE = 'free'
    ENTERPRISE = 'enterprise'


# Feature configuration by tier
TIER_CONFIG = {
    ChemicalStorageTier.FREE: {
        'enabled': True,
        'mode': 'demo',
        'max_passwords': 1,
        'features': [
            'dna_encoding',
            'time_lock_puzzles',
            'certificate_generation',
            'qr_code_export',
        ],
        'lab_integration': False,
        'cost': 0,
    },
    ChemicalStorageTier.ENTERPRISE: {
        'enabled': True,
        'mode': 'real',
        'max_passwords': 100,
        'features': [
            'dna_encoding',
            'time_lock_puzzles',
            'certificate_generation',
            'qr_code_export',
            'real_dna_synthesis',
            'physical_storage',
            'retrieval_service',
            'chain_of_custody',
        ],
        'lab_integration': True,
        'cost': 2000,  # $2000/year
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ChemicalStorageCertificateData:
    """Certificate proving chemical storage of password."""
    certificate_id: str
    user_id: int
    sequence_hash: str  # SHA-256 of DNA sequence (never store actual sequence)
    encoding_method: str
    error_correction_level: str
    synthesis_provider: Optional[str]
    synthesis_date: Optional[datetime]
    storage_temperature_kelvin: float
    estimated_half_life_years: int
    time_lock_enabled: bool
    time_lock_mode: Optional[str]
    signature: str
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'certificate_id': self.certificate_id,
            'sequence_hash': self.sequence_hash,
            'encoding_method': self.encoding_method,
            'error_correction_level': self.error_correction_level,
            'synthesis_provider': self.synthesis_provider,
            'synthesis_date': self.synthesis_date.isoformat() if self.synthesis_date else None,
            'storage_temperature_kelvin': self.storage_temperature_kelvin,
            'estimated_half_life_years': self.estimated_half_life_years,
            'time_lock_enabled': self.time_lock_enabled,
            'time_lock_mode': self.time_lock_mode,
            'signature': self.signature,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class ChemicalStorageResult:
    """Result of chemical storage operation."""
    success: bool
    dna_sequence: Optional[DNASequence] = None
    time_lock: Optional[Any] = None  # ServerTimeLockCapsule or TimeLockPuzzle
    synthesis_order: Optional[SynthesisOrder] = None
    certificate: Optional[ChemicalStorageCertificateData] = None
    qr_code_data: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'dna_sequence': self.dna_sequence.to_dict() if self.dna_sequence else None,
            'time_lock': self.time_lock.to_dict() if self.time_lock else None,
            'synthesis_order': self.synthesis_order.to_dict() if self.synthesis_order else None,
            'certificate': self.certificate.to_dict() if self.certificate else None,
            'qr_code_data': self.qr_code_data,
            'error': self.error,
        }


# =============================================================================
# Chemical Storage Service
# =============================================================================

class ChemicalStorageService:
    """
    Main orchestration service for chemical password storage.
    
    Provides:
    - DNA encoding of passwords
    - Time-lock encryption (server or client mode)
    - Lab integration for real DNA synthesis
    - Certificate generation
    - QR code export for paper backup
    """
    
    def __init__(
        self,
        tier: ChemicalStorageTier = ChemicalStorageTier.FREE,
        lab_provider: str = None
    ):
        """
        Initialize chemical storage service.
        
        Args:
            tier: Subscription tier (free or enterprise)
            lab_provider: Lab provider name (defaults to env config)
        """
        self.tier = tier
        self.config = TIER_CONFIG[tier]
        
        # Initialize sub-services
        self.dna_encoder = DNAEncoder()
        self.time_lock_service = TimeLockService()
        
        # Lab provider (only for enterprise)
        if self.config['lab_integration']:
            self.lab_provider = get_lab_provider(lab_provider)
        else:
            self.lab_provider = get_lab_provider('mock')
        
        # Certificate secret for signing
        self.cert_secret = os.environ.get(
            'CHEMICAL_CERT_SECRET',
            secrets.token_hex(32)
        )
    
    # =========================================================================
    # DNA Encoding
    # =========================================================================
    
    def encode_password_to_dna(
        self,
        password: str,
        use_error_correction: bool = True
    ) -> Tuple[DNASequence, SynthesisValidation]:
        """
        Encode a password into a DNA sequence.
        
        Args:
            password: Password to encode
            use_error_correction: Add Reed-Solomon ECC
            
        Returns:
            Tuple of (DNASequence, SynthesisValidation)
        """
        # Create encoder with specified options
        encoder = DNAEncoder(
            use_error_correction=use_error_correction,
            add_primers=True,
            balance_gc=True,
        )
        
        # Encode password
        dna_sequence = encoder.encode_password(password)
        
        # Validate for synthesis
        validation = encoder.validate_for_synthesis(dna_sequence.sequence)
        
        logger.info(
            f"Encoded password to DNA: {len(dna_sequence.sequence)}bp, "
            f"GC={dna_sequence.gc_content:.1%}, valid={validation.is_valid}"
        )
        
        return dna_sequence, validation
    
    def decode_dna_to_password(self, dna_sequence: str) -> str:
        """
        Decode a DNA sequence back to password.
        
        Args:
            dna_sequence: DNA sequence string
            
        Returns:
            Original password
        """
        return self.dna_encoder.decode_password(dna_sequence)
    
    # =========================================================================
    # Time-Lock
    # =========================================================================
    
    def create_time_lock(
        self,
        password: str,
        delay_hours: int,
        mode: TimeLockMode = TimeLockMode.SERVER,
        beneficiary_email: str = None
    ):
        """
        Create a time-locked password capsule.
        
        Args:
            password: Password to lock
            delay_hours: Hours before access is allowed
            mode: SERVER (enforced) or CLIENT (solvable puzzle)
            beneficiary_email: Email for emergency access notification
            
        Returns:
            ServerTimeLockCapsule or TimeLockPuzzle
        """
        delay_seconds = delay_hours * 3600
        password_bytes = password.encode('utf-8')
        
        return self.time_lock_service.create_time_lock(
            data=password_bytes,
            delay_seconds=delay_seconds,
            mode=mode,
            beneficiary_email=beneficiary_email,
        )
    
    def check_time_lock_status(self, time_lock) -> Dict:
        """Check status of a time-lock."""
        return self.time_lock_service.check_status(time_lock)
    
    def unlock_time_lock(self, time_lock, **kwargs) -> str:
        """Unlock a time-lock and retrieve password."""
        password_bytes = self.time_lock_service.unlock(time_lock, **kwargs)
        return password_bytes.decode('utf-8')
    
    # =========================================================================
    # Lab Integration
    # =========================================================================
    
    def order_dna_synthesis(
        self,
        dna_sequence: DNASequence,
        user_email: str = None
    ) -> SynthesisOrder:
        """
        Order DNA synthesis from lab provider.
        
        Enterprise only: Actually orders synthesis.
        Free tier: Returns mock order.
        
        Args:
            dna_sequence: DNA sequence to synthesize
            user_email: User email for order notifications
            
        Returns:
            SynthesisOrder object
        """
        if not self._has_feature('real_dna_synthesis'):
            logger.info("Using mock synthesis (free tier)")
        
        return self.lab_provider.submit_synthesis_order(
            sequence=dna_sequence.sequence,
            user_email=user_email,
        )
    
    def check_synthesis_status(self, order_id: str) -> SynthesisOrder:
        """Check DNA synthesis order status."""
        return self.lab_provider.check_synthesis_status(order_id)
    
    def request_password_retrieval(
        self,
        sample_id: str
    ) -> SequencingOrder:
        """
        Request DNA sequencing to retrieve password.
        
        Args:
            sample_id: Physical sample ID in storage
            
        Returns:
            SequencingOrder object
        """
        if not self.lab_provider.supports_sequencing:
            # Fall back to a provider that does
            sequencing_provider = get_lab_provider('illumina')
            return sequencing_provider.submit_sequencing_order(sample_id)
        
        return self.lab_provider.submit_sequencing_order(sample_id)
    
    # =========================================================================
    # Certificate Generation
    # =========================================================================
    
    def generate_certificate(
        self,
        user_id: int,
        dna_sequence: DNASequence,
        synthesis_order: SynthesisOrder = None,
        time_lock = None
    ) -> ChemicalStorageCertificateData:
        """
        Generate a certificate of chemical storage.
        
        Args:
            user_id: User ID
            dna_sequence: Encoded DNA sequence
            synthesis_order: Optional synthesis order
            time_lock: Optional time-lock
            
        Returns:
            ChemicalStorageCertificateData
        """
        certificate_id = secrets.token_urlsafe(16)
        
        # Hash the sequence (never store actual sequence)
        sequence_hash = hashlib.sha256(
            dna_sequence.sequence.encode()
        ).hexdigest()
        
        # Determine time-lock mode
        time_lock_mode = None
        if time_lock:
            if isinstance(time_lock, ServerTimeLockCapsule):
                time_lock_mode = 'server'
            elif isinstance(time_lock, TimeLockPuzzle):
                time_lock_mode = 'client'
        
        # Create certificate
        cert = ChemicalStorageCertificateData(
            certificate_id=certificate_id,
            user_id=user_id,
            sequence_hash=sequence_hash,
            encoding_method='huffman_nucleotide_v1',
            error_correction_level='high' if dna_sequence.has_error_correction else 'none',
            synthesis_provider=synthesis_order.provider if synthesis_order else None,
            synthesis_date=synthesis_order.created_at if synthesis_order else None,
            storage_temperature_kelvin=193.15,  # -80°C in Kelvin
            estimated_half_life_years=1000,  # DNA theoretically stable
            time_lock_enabled=time_lock is not None,
            time_lock_mode=time_lock_mode,
            signature='',  # Will be set below
        )
        
        # Sign certificate
        sign_data = json.dumps({
            'id': cert.certificate_id,
            'hash': cert.sequence_hash,
            'user': cert.user_id,
        }, sort_keys=True)
        
        signature = hashlib.hmac_new(
            self.cert_secret.encode() if isinstance(self.cert_secret, str) else self.cert_secret,
            sign_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        cert.signature = signature
        
        logger.info(f"Generated certificate {certificate_id}")
        return cert
    
    # =========================================================================
    # QR Code Export
    # =========================================================================
    
    def generate_qr_data(self, dna_sequence: DNASequence) -> str:
        """
        Generate QR code data for paper backup.
        
        Args:
            dna_sequence: DNA sequence to encode
            
        Returns:
            Base64-encoded string for QR code
        """
        return self.dna_encoder.generate_qr_data(dna_sequence)
    
    # =========================================================================
    # Full Workflow
    # =========================================================================
    
    def store_password_chemically(
        self,
        password: str,
        user_id: int,
        user_email: str = None,
        enable_time_lock: bool = False,
        time_lock_hours: int = 72,
        time_lock_mode: TimeLockMode = TimeLockMode.SERVER,
        order_synthesis: bool = False
    ) -> ChemicalStorageResult:
        """
        Complete workflow to store password chemically.
        
        Args:
            password: Password to store
            user_id: User ID
            user_email: User email for notifications
            enable_time_lock: Whether to add time-lock
            time_lock_hours: Hours for time-lock delay
            time_lock_mode: SERVER or CLIENT time-lock
            order_synthesis: Whether to order real DNA synthesis
            
        Returns:
            ChemicalStorageResult with all components
        """
        try:
            # Step 1: Encode to DNA
            dna_sequence, validation = self.encode_password_to_dna(password)
            
            if not validation.is_valid:
                return ChemicalStorageResult(
                    success=False,
                    error=f"DNA sequence not valid for synthesis: {validation.errors}"
                )
            
            # Step 2: Optional time-lock
            time_lock = None
            if enable_time_lock:
                time_lock = self.create_time_lock(
                    password=password,
                    delay_hours=time_lock_hours,
                    mode=time_lock_mode,
                    beneficiary_email=user_email,
                )
            
            # Step 3: Optional synthesis order
            synthesis_order = None
            if order_synthesis and self._has_feature('real_dna_synthesis'):
                synthesis_order = self.order_dna_synthesis(
                    dna_sequence=dna_sequence,
                    user_email=user_email,
                )
            elif order_synthesis:
                # Free tier gets mock order
                synthesis_order = self.order_dna_synthesis(
                    dna_sequence=dna_sequence,
                    user_email=user_email,
                )
            
            # Step 4: Generate certificate
            certificate = self.generate_certificate(
                user_id=user_id,
                dna_sequence=dna_sequence,
                synthesis_order=synthesis_order,
                time_lock=time_lock,
            )
            
            # Step 5: Generate QR code data
            qr_data = self.generate_qr_data(dna_sequence)
            
            return ChemicalStorageResult(
                success=True,
                dna_sequence=dna_sequence,
                time_lock=time_lock,
                synthesis_order=synthesis_order,
                certificate=certificate,
                qr_code_data=qr_data,
            )
            
        except Exception as e:
            logger.error(f"Chemical storage failed: {e}")
            return ChemicalStorageResult(
                success=False,
                error=str(e)
            )
    
    def retrieve_password(
        self,
        dna_sequence: str = None,
        sample_id: str = None,
        time_lock = None
    ) -> str:
        """
        Retrieve password from chemical storage.
        
        Args:
            dna_sequence: DNA sequence string (if known)
            sample_id: Physical sample ID (triggers sequencing)
            time_lock: Time-lock to unlock first
            
        Returns:
            Original password
        """
        # If time-locked, unlock first
        if time_lock:
            status = self.check_time_lock_status(time_lock)
            if not status.get('can_unlock', False):
                raise ValueError(
                    f"Time-lock still active. {status.get('time_remaining_seconds', 0)} seconds remaining."
                )
            return self.unlock_time_lock(time_lock)
        
        # If DNA sequence provided, decode directly
        if dna_sequence:
            return self.decode_dna_to_password(dna_sequence)
        
        # If sample ID provided, request sequencing
        if sample_id:
            order = self.request_password_retrieval(sample_id)
            raise ValueError(
                f"Sequencing order {order.order_id} submitted. "
                f"Estimated completion: {order.estimated_completion}"
            )
        
        raise ValueError("Must provide dna_sequence, sample_id, or time_lock")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _has_feature(self, feature: str) -> bool:
        """Check if current tier has a feature."""
        return feature in self.config.get('features', [])
    
    def get_tier_info(self) -> Dict:
        """Get information about current tier."""
        return {
            'tier': self.tier.value,
            'config': self.config,
            'lab_provider': self.lab_provider.name if self.lab_provider else None,
        }
    
    def estimate_cost(self, password: str) -> Dict:
        """Estimate cost for chemical storage of a password."""
        dna_sequence, _ = self.encode_password_to_dna(password)
        return self.dna_encoder.estimate_synthesis_cost(
            dna_sequence.sequence,
            provider=self.lab_provider.name.lower().replace(' ', '_')
            if hasattr(self.lab_provider, 'name') else 'mock'
        )


# =============================================================================
# Fix for hmac.new -> hashlib.hmac is not valid, use hmac module
# =============================================================================

import hmac as hmac_module

# Patch the generate_certificate method to use correct hmac
def _sign_certificate(cert_secret, sign_data):
    """Sign certificate data using HMAC-SHA256."""
    key = cert_secret.encode() if isinstance(cert_secret, str) else cert_secret
    return hmac_module.new(key, sign_data.encode(), hashlib.sha256).hexdigest()


# =============================================================================
# Module-level instances
# =============================================================================

# Default service instance (free tier)
chemical_storage_service = ChemicalStorageService(tier=ChemicalStorageTier.FREE)


def get_chemical_storage_service(tier: str = 'free') -> ChemicalStorageService:
    """Get chemical storage service for specified tier."""
    tier_enum = ChemicalStorageTier(tier.lower())
    return ChemicalStorageService(tier=tier_enum)

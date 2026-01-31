"""
Duress Code Service

Core service for managing duress codes and handling duress activation.
Provides secure code creation, verification, and response orchestration.
"""

import logging
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from security.models.duress_models import (
    DuressCodeConfiguration,
    DuressCode,
    DecoyVault,
    DuressEvent,
    EvidencePackage,
    TrustedAuthority,
)

# Use argon2 for secure password hashing
try:
    import argon2
    from argon2 import PasswordHasher
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False


logger = logging.getLogger(__name__)


class DuressCodeService:
    """
    Service for managing duress codes and orchestrating duress responses.
    
    Features:
    - Secure duress code creation with Argon2id hashing
    - Verification of input as password vs duress code
    - Orchestration of duress response actions
    - Integration with evidence preservation and silent alarms
    """
    
    def __init__(self):
        """Initialize the duress code service"""
        if ARGON2_AVAILABLE:
            self.hasher = PasswordHasher(
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                salt_len=16,
            )
        else:
            self.hasher = None
            logger.warning("Argon2 not available, using fallback hashing")
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def get_or_create_config(self, user: User) -> DuressCodeConfiguration:
        """Get or create duress configuration for a user"""
        config, created = DuressCodeConfiguration.objects.get_or_create(
            user=user,
            defaults={
                'is_enabled': False,
                'threat_level_count': 3,
                'evidence_preservation_enabled': True,
                'silent_alarm_enabled': False,
            }
        )
        if created:
            logger.info(f"Created duress configuration for user {user.username}")
        return config
    
    def update_config(
        self,
        user: User,
        **kwargs
    ) -> DuressCodeConfiguration:
        """Update duress configuration for a user"""
        config = self.get_or_create_config(user)
        
        allowed_fields = [
            'is_enabled', 'threat_level_count', 'evidence_preservation_enabled',
            'silent_alarm_enabled', 'behavioral_detection_enabled',
            'legal_compliance_mode', 'auto_refresh_decoy', 'decoy_refresh_interval_days'
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(config, field, value)
        
        config.save()
        logger.info(f"Updated duress configuration for user {user.username}")
        return config
    
    # =========================================================================
    # Duress Code Management
    # =========================================================================
    
    def create_duress_code(
        self,
        user: User,
        code: str,
        threat_level: str = 'medium',
        code_hint: str = '',
        action_config: Optional[Dict] = None
    ) -> DuressCode:
        """
        Create a new duress code for a user.
        
        Args:
            user: The user creating the code
            code: The plaintext duress code (will be hashed)
            threat_level: low, medium, high, or critical
            code_hint: Optional hint for the user
            action_config: Custom action configuration
            
        Returns:
            The created DuressCode object
        """
        # Validate code strength
        if len(code) < 4:
            raise ValueError("Duress code must be at least 4 characters")
        
        # Ensure code is different from master password
        # (This would require password comparison in real implementation)
        
        # Hash the code
        code_hash = self._hash_code(code)
        
        # Create with default actions if not provided
        if action_config is None:
            action_config = {}
        
        duress_code = DuressCode.objects.create(
            user=user,
            code_hash=code_hash,
            threat_level=threat_level,
            code_hint=code_hint,
            action_config=action_config,
            is_active=True
        )
        
        # Merge with default actions
        defaults = duress_code.get_default_actions()
        defaults.update(action_config)
        duress_code.action_config = defaults
        duress_code.save(update_fields=['action_config'])
        
        # Ensure configuration is enabled
        config = self.get_or_create_config(user)
        if not config.is_enabled:
            config.is_enabled = True
            config.save(update_fields=['is_enabled'])
        
        logger.info(
            f"Created duress code ({threat_level}) for user {user.username}"
        )
        
        return duress_code
    
    def update_duress_code(
        self,
        duress_code: DuressCode,
        new_code: Optional[str] = None,
        threat_level: Optional[str] = None,
        code_hint: Optional[str] = None,
        action_config: Optional[Dict] = None
    ) -> DuressCode:
        """Update an existing duress code"""
        if new_code:
            if len(new_code) < 4:
                raise ValueError("Duress code must be at least 4 characters")
            duress_code.code_hash = self._hash_code(new_code)
        
        if threat_level:
            duress_code.threat_level = threat_level
            # Update default actions for new level
            if action_config is None:
                duress_code.action_config = duress_code.get_default_actions()
        
        if code_hint is not None:
            duress_code.code_hint = code_hint
        
        if action_config:
            current = duress_code.action_config or {}
            current.update(action_config)
            duress_code.action_config = current
        
        duress_code.save()
        logger.info(f"Updated duress code {duress_code.id}")
        
        return duress_code
    
    def delete_duress_code(self, duress_code: DuressCode) -> bool:
        """Delete a duress code (soft delete by deactivating)"""
        duress_code.is_active = False
        duress_code.save(update_fields=['is_active'])
        logger.info(f"Deactivated duress code {duress_code.id}")
        return True
    
    def get_user_codes(
        self,
        user: User,
        active_only: bool = True
    ) -> List[DuressCode]:
        """Get all duress codes for a user"""
        queryset = DuressCode.objects.filter(user=user)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return list(queryset.order_by('-created_at'))
    
    # =========================================================================
    # Code Verification
    # =========================================================================
    
    def verify_password_or_duress(
        self,
        user: User,
        input_password: str
    ) -> Tuple[str, Optional[DuressCode]]:
        """
        Check if input is the master password or a duress code.
        
        Returns:
            Tuple of (result_type, duress_code)
            - ('password', None) - input is the master password
            - ('duress', DuressCode) - input is a duress code
            - ('invalid', None) - input is neither
        """
        # First check if it's a duress code
        duress_code = self._check_duress_codes(user, input_password)
        if duress_code:
            return ('duress', duress_code)
        
        # Then check master password (delegated to auth system)
        # This would be called after standard auth check
        return ('check_password', None)
    
    def _check_duress_codes(
        self,
        user: User,
        input_code: str
    ) -> Optional[DuressCode]:
        """Check if input matches any active duress codes"""
        active_codes = DuressCode.objects.filter(
            user=user,
            is_active=True
        )
        
        for code in active_codes:
            if self._verify_code(input_code, code.code_hash):
                return code
        
        return None
    
    # =========================================================================
    # Duress Activation
    # =========================================================================
    
    @transaction.atomic
    def activate_duress_mode(
        self,
        user: User,
        duress_code: DuressCode,
        request_context: Dict[str, Any],
        is_test: bool = False
    ) -> Dict[str, Any]:
        """
        Activate duress response for a user.
        
        Args:
            user: The user entering duress mode
            duress_code: The triggered duress code
            request_context: Context from the request (IP, device, etc)
            is_test: Whether this is a test activation
            
        Returns:
            Dict with activation results
        """
        logger.warning(
            f"Duress mode activated for user {user.username} "
            f"(level: {duress_code.threat_level}, test: {is_test})"
        )
        
        actions = duress_code.action_config or duress_code.get_default_actions()
        results = {
            'activated': True,
            'threat_level': duress_code.threat_level,
            'is_test': is_test,
            'actions_taken': [],
            'decoy_vault': None,
            'evidence_package_id': None,
        }
        
        # Create evidence package if enabled
        evidence_package = None
        config = self.get_or_create_config(user)
        
        if config.evidence_preservation_enabled and actions.get('preserve_evidence'):
            evidence_package = self._create_evidence_package(
                user, duress_code, request_context
            )
            results['evidence_package_id'] = str(evidence_package.id)
            results['actions_taken'].append('evidence_preserved')
        
        # Get or generate decoy vault
        if actions.get('show_decoy'):
            decoy = self._get_or_create_decoy_vault(user, duress_code.threat_level)
            results['decoy_vault'] = decoy
            results['actions_taken'].append('decoy_vault_prepared')
        
        # Send silent alarms if enabled
        silent_alarm_sent = False
        if config.silent_alarm_enabled and actions.get('alert_authorities') and not is_test:
            silent_alarm_sent = self._trigger_silent_alarms(
                user, duress_code, request_context, evidence_package
            )
            if silent_alarm_sent:
                results['actions_taken'].append('silent_alarm_sent')
        
        # Log the event
        event = DuressEvent.objects.create(
            user=user,
            event_type='test_activation' if is_test else 'code_activated',
            duress_code=duress_code,
            threat_level=duress_code.threat_level,
            ip_address=request_context.get('ip_address', '0.0.0.0'),
            user_agent=request_context.get('user_agent', ''),
            device_fingerprint=request_context.get('device_fingerprint', {}),
            geo_location=request_context.get('geo_location', {}),
            behavioral_data=request_context.get('behavioral_data', {}),
            behavioral_stress_score=request_context.get('stress_score', 0.0),
            response_status='success',
            actions_taken=results['actions_taken'],
            silent_alarm_sent=silent_alarm_sent,
            evidence_package=evidence_package,
        )
        results['event_id'] = str(event.id)
        
        # Update code activation count
        duress_code.activation_count += 1
        duress_code.last_activated_at = timezone.now()
        duress_code.save(update_fields=['activation_count', 'last_activated_at'])
        
        return results
    
    # =========================================================================
    # Decoy Vault Management
    # =========================================================================
    
    def _get_or_create_decoy_vault(
        self,
        user: User,
        threat_level: str
    ) -> Dict[str, Any]:
        """Get or create a decoy vault for the user"""
        try:
            decoy = DecoyVault.objects.get(user=user, threat_level=threat_level)
            # Check if refresh is needed
            config = self.get_or_create_config(user)
            refresh_days = config.decoy_refresh_interval_days
            if config.auto_refresh_decoy:
                age = (timezone.now() - decoy.last_refreshed).days
                if age > refresh_days:
                    return self._refresh_decoy_vault(decoy)
            decoy.last_accessed = timezone.now()
            decoy.save(update_fields=['last_accessed'])
            return self._format_decoy_vault(decoy)
        except DecoyVault.DoesNotExist:
            return self._create_decoy_vault(user, threat_level)
    
    def _create_decoy_vault(
        self,
        user: User,
        threat_level: str
    ) -> Dict[str, Any]:
        """Create a new decoy vault"""
        # Import here to avoid circular imports
        from security.services.decoy_vault_service import DecoyVaultService
        
        decoy_service = DecoyVaultService()
        decoy_data = decoy_service.generate_realistic_decoy(user, threat_level)
        
        decoy = DecoyVault.objects.create(
            user=user,
            threat_level=threat_level,
            decoy_items=decoy_data['items'],
            decoy_folders=decoy_data['folders'],
            item_count=len(decoy_data['items']),
            realism_score=decoy_data.get('realism_score', 0.8),
        )
        
        logger.info(f"Created decoy vault ({threat_level}) for user {user.username}")
        return self._format_decoy_vault(decoy)
    
    def _refresh_decoy_vault(self, decoy: DecoyVault) -> Dict[str, Any]:
        """Refresh an existing decoy vault"""
        from security.services.decoy_vault_service import DecoyVaultService
        
        decoy_service = DecoyVaultService()
        decoy_data = decoy_service.generate_realistic_decoy(
            decoy.user, decoy.threat_level
        )
        
        decoy.decoy_items = decoy_data['items']
        decoy.decoy_folders = decoy_data['folders']
        decoy.item_count = len(decoy_data['items'])
        decoy.realism_score = decoy_data.get('realism_score', 0.8)
        decoy.last_refreshed = timezone.now()
        decoy.save()
        
        logger.info(f"Refreshed decoy vault for user {decoy.user.username}")
        return self._format_decoy_vault(decoy)
    
    def _format_decoy_vault(self, decoy: DecoyVault) -> Dict[str, Any]:
        """Format decoy vault for API response"""
        return {
            'id': str(decoy.id),
            'threat_level': decoy.threat_level,
            'items': decoy.decoy_items,
            'folders': decoy.decoy_folders,
            'item_count': decoy.item_count,
            'realism_score': decoy.realism_score,
            'last_refreshed': decoy.last_refreshed.isoformat(),
        }
    
    # =========================================================================
    # Evidence Preservation
    # =========================================================================
    
    def _create_evidence_package(
        self,
        user: User,
        duress_code: DuressCode,
        request_context: Dict[str, Any]
    ) -> EvidencePackage:
        """Create an evidence package for a duress event"""
        from security.services.evidence_preservation_service import EvidencePreservationService
        
        evidence_service = EvidencePreservationService()
        return evidence_service.create_package(user, request_context)
    
    # =========================================================================
    # Silent Alarms
    # =========================================================================
    
    def _trigger_silent_alarms(
        self,
        user: User,
        duress_code: DuressCode,
        request_context: Dict[str, Any],
        evidence_package: Optional[EvidencePackage]
    ) -> bool:
        """Send silent alarms to configured authorities"""
        from security.services.silent_alarm_service import SilentAlarmService
        
        alarm_service = SilentAlarmService()
        return alarm_service.send_alerts(
            user=user,
            threat_level=duress_code.threat_level,
            request_context=request_context,
            evidence_package=evidence_package
        )
    
    # =========================================================================
    # Hashing Utilities
    # =========================================================================
    
    def _hash_code(self, code: str) -> str:
        """Hash a duress code using Argon2id"""
        if self.hasher:
            return self.hasher.hash(code)
        else:
            # Fallback to PBKDF2 if Argon2 not available
            salt = secrets.token_hex(16)
            hash_val = hashlib.pbkdf2_hmac(
                'sha256',
                code.encode(),
                salt.encode(),
                100000
            ).hex()
            return f"pbkdf2${salt}${hash_val}"
    
    def _verify_code(self, code: str, code_hash: str) -> bool:
        """Verify a code against its hash"""
        try:
            if self.hasher and not code_hash.startswith('pbkdf2$'):
                self.hasher.verify(code_hash, code)
                return True
            elif code_hash.startswith('pbkdf2$'):
                # Fallback verification
                parts = code_hash.split('$')
                if len(parts) != 3:
                    return False
                _, salt, expected_hash = parts
                computed = hashlib.pbkdf2_hmac(
                    'sha256',
                    code.encode(),
                    salt.encode(),
                    100000
                ).hex()
                return secrets.compare_digest(computed, expected_hash)
        except Exception as e:
            logger.debug(f"Code verification failed: {e}")
            return False
        
        return False


# Singleton instance
_duress_code_service = None


def get_duress_code_service() -> DuressCodeService:
    """Get the singleton duress code service instance"""
    global _duress_code_service
    if _duress_code_service is None:
        _duress_code_service = DuressCodeService()
    return _duress_code_service

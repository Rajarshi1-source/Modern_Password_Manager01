"""
Homomorphic Sharing Service

Business logic for the FHE Password Sharing lifecycle:
- Creating shares (with autofill circuit tokens)
- Using shares (autofill with validation)
- Revoking shares
- Listing and querying shares
- Cleanup of expired shares
"""

import json
import logging
import secrets
import time
from typing import Optional, Dict, Any, List

from django.conf import settings as django_settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from ..models import HomomorphicShare, ShareAccessLog, ShareGroup
from .autofill_circuit_service import get_autofill_circuit_service
from .pre_service import (
    get_pre_service,
    UmbralUnavailableError,
    ReencryptionError,
    is_available as pre_backend_available,
)
from .policy_fhe_service import get_policy_fhe_service

logger = logging.getLogger(__name__)


CIPHER_SUITE_SIMULATED = 'simulated-v1'
CIPHER_SUITE_UMBRAL = 'umbral-v1'
SUPPORTED_SUITES = {CIPHER_SUITE_SIMULATED, CIPHER_SUITE_UMBRAL}


def _get_fhe_sharing_settings():
    """Get FHE sharing settings with defaults."""
    defaults = {
        'DEFAULT_EXPIRY_HOURS': 72,
        'MAX_EXPIRY_DAYS': 90,
        'MAX_USES_DEFAULT': None,
        'MAX_USES_LIMIT': 10000,
        'DOMAIN_BINDING_REQUIRED': True,
        'AUDIT_RETENTION_DAYS': 365,
        'CLEANUP_INTERVAL_HOURS': 6,
        # Umbral PRE rollout controls. See fhe_sharing/SPEC.md §10.
        'PRE_ENABLED': True,
        'ROLLOUT_STAGE': 'opt_in',  # off | opt_in | default_on
    }
    configured = getattr(django_settings, 'FHE_SHARING_SETTINGS', {})
    defaults.update(configured)
    return defaults


def pre_is_enabled() -> bool:
    """Feature-flag gate for the real PRE (umbral-v1) share path."""
    settings = _get_fhe_sharing_settings()
    return bool(settings.get('PRE_ENABLED'))


class HomomorphicSharingService:
    """
    Main service for Homomorphic Password Sharing.

    Orchestrates:
    - Share creation (calling AutofillCircuitService)
    - Share usage validation and autofill payload generation
    - Share revocation and lifecycle management
    - Audit logging
    """

    def __init__(self):
        self._circuit_service = None
        self._pre_service = None
        self._policy_service = None
        self._settings = None

    @property
    def circuit_service(self):
        if self._circuit_service is None:
            self._circuit_service = get_autofill_circuit_service()
        return self._circuit_service

    @property
    def pre_service(self):
        if self._pre_service is None:
            self._pre_service = get_pre_service()
        return self._pre_service

    @property
    def policy_service(self):
        if self._policy_service is None:
            self._policy_service = get_policy_fhe_service()
        return self._policy_service

    @property
    def sharing_settings(self):
        if self._settings is None:
            self._settings = _get_fhe_sharing_settings()
        return self._settings

    # ================================================================
    # Share Creation
    # ================================================================

    @transaction.atomic
    def create_autofill_share(
        self,
        owner,
        vault_item,
        recipient,
        domain_constraints: Optional[List[str]] = None,
        expires_at=None,
        max_uses: Optional[int] = None,
        group: Optional[ShareGroup] = None,
        request=None,
    ) -> HomomorphicShare:
        """
        Create a new homomorphic share with an FHE autofill token.

        Args:
            owner: User who owns the password
            vault_item: EncryptedVaultItem to share
            recipient: User who will receive the share
            domain_constraints: Domains where autofill is allowed
            expires_at: Optional expiration datetime
            max_uses: Optional maximum usage count
            group: Optional ShareGroup to add this share to
            request: Optional HTTP request for audit logging

        Returns:
            The created HomomorphicShare instance

        Raises:
            ValueError: If validation fails
            PermissionError: If owner doesn't own the vault item
        """
        start_time = time.time()

        # === Validation ===
        if owner == recipient:
            raise ValueError("Cannot share a password with yourself")

        if vault_item.user_id != owner.id:
            raise PermissionError("You can only share vault items you own")

        if vault_item.item_type != 'password':
            raise ValueError("Only password items can be shared via FHE")

        if vault_item.deleted:
            raise ValueError("Cannot share a deleted vault item")

        # Validate domain constraints
        if domain_constraints is None:
            domain_constraints = []

        settings = self.sharing_settings
        if settings['DOMAIN_BINDING_REQUIRED'] and not domain_constraints:
            raise ValueError(
                "Domain binding is required. Specify at least one domain "
                "where the autofill token can be used."
            )

        # Validate max_uses
        if max_uses is not None:
            max_limit = settings['MAX_USES_LIMIT']
            if max_uses < 1 or max_uses > max_limit:
                raise ValueError(
                    f"max_uses must be between 1 and {max_limit}"
                )

        # Validate expiration
        if expires_at is not None:
            max_expiry = timezone.now() + timezone.timedelta(
                days=settings['MAX_EXPIRY_DAYS']
            )
            if expires_at > max_expiry:
                raise ValueError(
                    f"Expiration cannot be more than "
                    f"{settings['MAX_EXPIRY_DAYS']} days from now"
                )
            if expires_at <= timezone.now():
                raise ValueError("Expiration must be in the future")
        elif settings['DEFAULT_EXPIRY_HOURS']:
            # Apply default expiry
            expires_at = timezone.now() + timezone.timedelta(
                hours=settings['DEFAULT_EXPIRY_HOURS']
            )

        # Check for existing active share of same item to same recipient
        existing = HomomorphicShare.objects.filter(
            owner=owner,
            recipient=recipient,
            vault_item=vault_item,
            is_active=True,
        ).exclude(
            expires_at__lt=timezone.now()
        ).first()

        if existing:
            raise ValueError(
                f"An active share of this item to {recipient.username} "
                f"already exists (ID: {str(existing.id)[:8]}). "
                f"Revoke it first or wait for it to expire."
            )

        # === Create FHE Autofill Circuit Token ===
        # Get or create FHE-encrypted password data
        fhe_password_data = self._get_fhe_encrypted_password(vault_item)

        circuit_result = self.circuit_service.create_autofill_circuit(
            fhe_encrypted_password=fhe_password_data,
            recipient_public_key=self._get_recipient_public_key(recipient),
            domain_constraints=domain_constraints,
            owner_id=str(owner.id),
            recipient_id=str(recipient.id),
            vault_item_id=str(vault_item.id),
        )

        # === Create the Share Record ===
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=vault_item,
            group=group,
            encrypted_autofill_token=circuit_result['token'],
            encrypted_domain_binding=json.dumps(domain_constraints),
            token_metadata=circuit_result['metadata'],
            permission_level='autofill_only',
            can_autofill=True,
            can_view_password=False,
            can_copy_password=False,
            max_uses=max_uses,
            expires_at=expires_at,
            is_active=True,
        )

        # === Log the creation ===
        self._log_action(
            share=share,
            user=owner,
            action='share_created',
            request=request,
            details={
                'recipient_username': recipient.username,
                'domain_constraints': domain_constraints,
                'max_uses': max_uses,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'creation_time_ms': int((time.time() - start_time) * 1000),
            },
        )

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(
            f"[FHE Sharing] Share created: {owner.username} → "
            f"{recipient.username} (item {str(vault_item.id)[:8]}, "
            f"{elapsed}ms)"
        )

        return share

    # ================================================================
    # PRE-backed share creation (cipher_suite='umbral-v1')
    # ================================================================

    @transaction.atomic
    def create_umbral_share(
        self,
        owner,
        vault_item,
        recipient,
        capsule: bytes,
        ciphertext: bytes,
        kfrag: bytes,
        delegating_pk: bytes,
        verifying_pk: bytes,
        receiving_pk: bytes,
        domain_constraints: Optional[List[str]] = None,
        expires_at=None,
        max_uses: Optional[int] = None,
        group: Optional[ShareGroup] = None,
        request=None,
    ) -> HomomorphicShare:
        """Create a `cipher_suite='umbral-v1'` share.

        The owner has already run client-side Umbral encryption and
        kfrag generation — the server NEVER sees the plaintext password
        or the owner's secret key. We only store the opaque payload
        plus public-key fingerprints for integrity binding.

        Raises:
            ValueError: validation failure.
            PermissionError: owner does not own the vault item.
            RuntimeError: feature flag disabled.
        """
        start_time = time.time()

        if not pre_is_enabled():
            raise RuntimeError("PRE sharing is disabled by server policy")

        if owner == recipient:
            raise ValueError("Cannot share a password with yourself")
        if vault_item.user_id != owner.id:
            raise PermissionError("You can only share vault items you own")
        if vault_item.item_type != 'password':
            raise ValueError("Only password items can be shared via FHE")
        if vault_item.deleted:
            raise ValueError("Cannot share a deleted vault item")

        for name, value in (
            ('capsule', capsule),
            ('ciphertext', ciphertext),
            ('kfrag', kfrag),
            ('delegating_pk', delegating_pk),
            ('verifying_pk', verifying_pk),
            ('receiving_pk', receiving_pk),
        ):
            if not isinstance(value, (bytes, bytearray)) or len(value) == 0:
                raise ValueError(f"'{name}' must be non-empty bytes")

        if domain_constraints is None:
            domain_constraints = []

        settings = self.sharing_settings
        if settings['DOMAIN_BINDING_REQUIRED'] and not domain_constraints:
            raise ValueError("Domain binding is required")

        if max_uses is not None:
            if max_uses < 1 or max_uses > settings['MAX_USES_LIMIT']:
                raise ValueError(
                    f"max_uses must be between 1 and {settings['MAX_USES_LIMIT']}"
                )

        if expires_at is not None:
            max_expiry = timezone.now() + timezone.timedelta(
                days=settings['MAX_EXPIRY_DAYS']
            )
            if expires_at > max_expiry:
                raise ValueError(
                    f"Expiration cannot be more than "
                    f"{settings['MAX_EXPIRY_DAYS']} days from now"
                )
            if expires_at <= timezone.now():
                raise ValueError("Expiration must be in the future")
        elif settings['DEFAULT_EXPIRY_HOURS']:
            expires_at = timezone.now() + timezone.timedelta(
                hours=settings['DEFAULT_EXPIRY_HOURS']
            )

        existing = HomomorphicShare.objects.filter(
            owner=owner,
            recipient=recipient,
            vault_item=vault_item,
            is_active=True,
        ).exclude(
            expires_at__lt=timezone.now()
        ).first()
        if existing:
            raise ValueError(
                f"An active share of this item to {recipient.username} "
                f"already exists. Revoke it first."
            )

        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=vault_item,
            group=group,
            cipher_suite=CIPHER_SUITE_UMBRAL,
            encrypted_autofill_token=None,
            capsule=bytes(capsule),
            ciphertext=bytes(ciphertext),
            kfrag=bytes(kfrag),
            delegating_pk=bytes(delegating_pk),
            verifying_pk=bytes(verifying_pk),
            receiving_pk=bytes(receiving_pk),
            encrypted_domain_binding=json.dumps(domain_constraints),
            token_metadata={
                'cipher_suite': CIPHER_SUITE_UMBRAL,
                'schema_version': 2,
                'capsule_size': len(capsule),
                'ciphertext_size': len(ciphertext),
                'kfrag_size': len(kfrag),
                'server_pyumbral_available': pre_backend_available(),
            },
            permission_level='autofill_only',
            can_autofill=True,
            can_view_password=False,
            can_copy_password=False,
            max_uses=max_uses,
            expires_at=expires_at,
            is_active=True,
        )

        self._log_action(
            share=share,
            user=owner,
            action='share_created',
            request=request,
            details={
                'cipher_suite': CIPHER_SUITE_UMBRAL,
                'recipient_username': recipient.username,
                'domain_constraints': domain_constraints,
                'max_uses': max_uses,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'creation_time_ms': int((time.time() - start_time) * 1000),
            },
        )

        logger.info(
            "[FHE Sharing] umbral-v1 share created: %s -> %s (item %s, %dms)",
            owner.username,
            recipient.username,
            str(vault_item.id)[:8],
            int((time.time() - start_time) * 1000),
        )

        return share

    # ================================================================
    # Share Usage (Autofill)
    # ================================================================

    def use_autofill_token(
        self,
        share_id: str,
        recipient,
        domain: str,
        form_field_selector: str = 'input[type="password"]',
        request=None,
    ) -> Dict[str, Any]:
        """
        Use an autofill token to fill a password form field.

        Validates the share is active, not expired, within limits, and
        the domain matches the binding. Returns the autofill payload.

        Args:
            share_id: UUID of the share
            recipient: The user attempting to use the share
            domain: The domain where autofill is being attempted
            form_field_selector: CSS selector for the target form field
            request: Optional HTTP request for audit

        Returns:
            Dict with the autofill payload

        Raises:
            ValueError: If share is not usable
            PermissionError: If user is not the recipient
        """
        try:
            share = HomomorphicShare.objects.select_related(
                'owner', 'recipient', 'vault_item'
            ).get(id=share_id)
        except HomomorphicShare.DoesNotExist:
            raise ValueError("Share not found")

        # === Permission Check ===
        if share.recipient_id != recipient.id:
            self._log_action(
                share=share,
                user=recipient,
                action='autofill_denied',
                domain=domain,
                success=False,
                failure_reason='Not the authorized recipient',
                request=request,
            )
            raise PermissionError("You are not authorized to use this share")

        # === Usability Checks ===
        if not share.is_active:
            self._log_action(
                share=share, user=recipient, action='autofill_denied',
                domain=domain, success=False,
                failure_reason='Share is revoked/inactive',
                request=request,
            )
            raise ValueError("This share has been revoked")

        if share.is_expired:
            self._log_action(
                share=share, user=recipient, action='share_expired',
                domain=domain, success=False,
                failure_reason='Share has expired',
                request=request,
            )
            raise ValueError("This share has expired")

        if share.is_usage_limit_reached:
            self._log_action(
                share=share, user=recipient, action='usage_limit_reached',
                domain=domain, success=False,
                failure_reason='Usage limit reached',
                request=request,
            )
            raise ValueError(
                f"Usage limit reached ({share.max_uses} uses)"
            )

        # === Domain Binding Check (both suites share this path) ===
        domain_constraints = share.get_bound_domains()
        if not self._domain_matches(domain, domain_constraints):
            self._log_action(
                share=share, user=recipient, action='domain_mismatch',
                domain=domain, success=False,
                failure_reason=(
                    f"Domain '{domain}' not in allowed domains"
                    if domain_constraints else 'Domain constraints missing'
                ),
                request=request,
            )
            raise ValueError(
                f"Autofill denied: domain '{domain}' not allowed"
            )

        # Branch on cipher suite.
        if share.is_umbral:
            response = self._use_umbral_share(
                share=share,
                recipient=recipient,
                domain=domain,
                form_field_selector=form_field_selector,
                request=request,
            )
        else:
            response = self._use_simulated_share(
                share=share,
                recipient=recipient,
                domain=domain,
                form_field_selector=form_field_selector,
                domain_constraints=domain_constraints,
                request=request,
            )

        # === Record Usage (common to both suites) ===
        share.record_use()
        self._log_action(
            share=share, user=recipient, action='autofill_used',
            domain=domain, success=True,
            request=request,
            details={
                'use_count': share.use_count,
                'remaining_uses': share.remaining_uses,
                'cipher_suite': share.cipher_suite,
            },
        )
        logger.info(
            "[FHE Sharing] Autofill used (%s): share %s on %s (use #%d)",
            share.cipher_suite,
            str(share.id)[:8],
            domain,
            share.use_count,
        )

        response.update({
            'share_id': str(share.id),
            'use_count': share.use_count,
            'remaining_uses': share.remaining_uses,
            'expires_at': (
                share.expires_at.isoformat() if share.expires_at else None
            ),
        })
        return response

    # ---------------------------------------------------------------
    # Suite-specific autofill branches
    # ---------------------------------------------------------------

    def _use_simulated_share(
        self,
        share: HomomorphicShare,
        recipient,
        domain: str,
        form_field_selector: str,
        domain_constraints: List[str],
        request=None,
    ) -> Dict[str, Any]:
        """Legacy simulated-v1 path (unchanged behaviour)."""
        token_bytes = (
            bytes(share.encrypted_autofill_token)
            if share.encrypted_autofill_token is not None else b''
        )
        validation = self.circuit_service.validate_autofill_circuit(
            token=token_bytes,
            domain=domain,
            owner_id=str(share.owner_id),
            recipient_id=str(share.recipient_id),
            vault_item_id=str(share.vault_item_id),
            domain_constraints=domain_constraints,
        )
        if not validation['valid']:
            self._log_action(
                share=share, user=recipient, action='autofill_denied',
                domain=domain, success=False,
                failure_reason=validation['reason'],
                request=request,
            )
            raise ValueError(f"Autofill denied: {validation['reason']}")

        payload = self.circuit_service.generate_form_fill_payload(
            token=token_bytes,
            form_field_selector=form_field_selector,
            domain=domain,
        )
        return {
            'schema_version': 1,
            'cipher_suite': CIPHER_SUITE_SIMULATED,
            'payload': payload,
        }

    def _use_umbral_share(
        self,
        share: HomomorphicShare,
        recipient,
        domain: str,
        form_field_selector: str,
        request=None,
    ) -> Dict[str, Any]:
        """Real PRE path — reencrypt capsule with stored kfrag."""
        import base64
        if not pre_is_enabled():
            raise ValueError("PRE sharing is temporarily disabled")

        if share.kfrag is None or share.capsule is None or share.ciphertext is None:
            raise ValueError("This share is missing its PRE payload")

        try:
            cfrag_bytes = self.pre_service.reencrypt(
                capsule_bytes=bytes(share.capsule),
                kfrag_bytes=bytes(share.kfrag),
            )
        except UmbralUnavailableError:
            # Server-side library missing: surface a retryable message.
            raise ValueError(
                "Server PRE backend unavailable — contact administrator"
            )
        except ReencryptionError as exc:
            logger.error("[FHE Sharing] Reencryption failed: %s", exc)
            raise ValueError("Re-encryption failed")

        def _b64(b):
            return base64.urlsafe_b64encode(bytes(b)).decode('ascii').rstrip('=')

        sealed_envelope = {
            'version': 2,
            'cipher_suite': CIPHER_SUITE_UMBRAL,
            'target_selector': form_field_selector,
            'domain': domain,
            'instructions': {
                'method': 'sealed_inject',
                'clear_after_ms': 0,
                'prevent_copy': True,
                'prevent_inspect': True,
            },
        }

        return {
            'schema_version': 2,
            'cipher_suite': CIPHER_SUITE_UMBRAL,
            'capsule': _b64(share.capsule),
            'cfrag': _b64(cfrag_bytes),
            'ciphertext': _b64(share.ciphertext),
            'delegating_pk': _b64(share.delegating_pk) if share.delegating_pk else None,
            'verifying_pk': _b64(share.verifying_pk) if share.verifying_pk else None,
            'target_selector': form_field_selector,
            'sealed_envelope': sealed_envelope,
        }

    def _domain_matches(
        self, domain: str, allowed_domains: List[str],
    ) -> bool:
        """Shared domain-binding check for both suites."""
        if not allowed_domains:
            return False if self.sharing_settings['DOMAIN_BINDING_REQUIRED'] else True
        normalized = domain.lower().strip().split('/')[0]
        for allowed in allowed_domains:
            a = allowed.lower().strip().split('/')[0]
            if normalized == a or normalized.endswith('.' + a):
                return True
        return False

    # ================================================================
    # Share Revocation
    # ================================================================

    @transaction.atomic
    def revoke_share(
        self,
        share_id: str,
        revoking_user,
        reason: str = '',
        request=None,
    ) -> HomomorphicShare:
        """
        Revoke a share. Only the owner can revoke.

        Args:
            share_id: UUID of the share
            revoking_user: User revoking the share
            reason: Optional revocation reason
            request: Optional HTTP request for audit

        Returns:
            The updated HomomorphicShare

        Raises:
            ValueError: If share not found
            PermissionError: If user is not the owner
        """
        try:
            share = HomomorphicShare.objects.select_related(
                'owner', 'recipient'
            ).get(id=share_id)
        except HomomorphicShare.DoesNotExist:
            raise ValueError("Share not found")

        if share.owner_id != revoking_user.id:
            raise PermissionError("Only the share owner can revoke")

        if not share.is_active:
            raise ValueError("Share is already inactive")

        share.revoke(revoking_user, reason)

        self._log_action(
            share=share, user=revoking_user, action='share_revoked',
            request=request,
            details={
                'reason': reason,
                'recipient_username': share.recipient.username,
                'total_uses': share.use_count,
            },
        )

        logger.info(
            f"[FHE Sharing] Share revoked: {str(share.id)[:8]} "
            f"by {revoking_user.username}"
        )

        return share

    # ================================================================
    # Listing / Querying
    # ================================================================

    def list_shares_for_owner(self, user, include_inactive=False):
        """List all shares created by the user."""
        qs = HomomorphicShare.objects.filter(
            owner=user
        ).select_related('recipient', 'vault_item', 'group')

        if not include_inactive:
            qs = qs.filter(is_active=True)

        return qs.order_by('-created_at')

    def list_shares_for_recipient(self, user, only_usable=True):
        """List all shares available to the user."""
        qs = HomomorphicShare.objects.filter(
            recipient=user,
            is_active=True,
        ).select_related('owner', 'vault_item', 'group')

        if only_usable:
            qs = qs.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            ).filter(
                Q(max_uses__isnull=True) | Q(use_count__lt=models.F('max_uses'))
            )

        return qs.order_by('-created_at')

    def get_share_logs(self, share_id: str, user):
        """Get access logs for a share. Only the owner can view logs."""
        try:
            share = HomomorphicShare.objects.get(id=share_id)
        except HomomorphicShare.DoesNotExist:
            raise ValueError("Share not found")

        if share.owner_id != user.id:
            raise PermissionError("Only the share owner can view logs")

        return ShareAccessLog.objects.filter(
            share=share
        ).select_related('user').order_by('-timestamp')

    # ================================================================
    # Group Management
    # ================================================================

    @transaction.atomic
    def create_share_group(
        self,
        owner,
        vault_item,
        name: str,
        description: str = '',
    ) -> ShareGroup:
        """Create a new share group."""
        if vault_item.user_id != owner.id:
            raise PermissionError("You can only create groups for your own items")

        group = ShareGroup.objects.create(
            name=name,
            description=description,
            owner=owner,
            vault_item=vault_item,
        )

        logger.info(
            f"[FHE Sharing] Share group created: {name} "
            f"by {owner.username}"
        )

        return group

    def list_share_groups(self, user):
        """List share groups owned by the user."""
        return ShareGroup.objects.filter(
            owner=user
        ).prefetch_related('shares').order_by('-created_at')

    # ================================================================
    # Cleanup
    # ================================================================

    def cleanup_expired_shares(self) -> Dict[str, int]:
        """
        Deactivate expired shares and log the expiration.

        Should be called periodically (e.g., via celery task or cron).

        Returns:
            Dict with counts of cleaned up items
        """
        now = timezone.now()

        # Find expired but still active shares
        expired_shares = HomomorphicShare.objects.filter(
            is_active=True,
            expires_at__lt=now,
        )

        count = expired_shares.count()

        if count > 0:
            # Log expiration for each share
            for share in expired_shares.select_related('owner', 'recipient'):
                self._log_action(
                    share=share, user=None, action='share_expired',
                    details={'expired_at': now.isoformat()},
                )

            # Bulk deactivate
            expired_shares.update(is_active=False)

            logger.info(
                f"[FHE Sharing] Cleaned up {count} expired shares"
            )

        # Clean up old audit logs
        settings = self.sharing_settings
        retention_cutoff = now - timezone.timedelta(
            days=settings['AUDIT_RETENTION_DAYS']
        )
        old_logs_count = ShareAccessLog.objects.filter(
            timestamp__lt=retention_cutoff
        ).count()

        if old_logs_count > 0:
            ShareAccessLog.objects.filter(
                timestamp__lt=retention_cutoff
            ).delete()
            logger.info(
                f"[FHE Sharing] Cleaned up {old_logs_count} old audit logs"
            )

        return {
            'expired_shares': count,
            'old_logs_deleted': old_logs_count,
        }

    # ================================================================
    # Internal Helpers
    # ================================================================

    def _get_fhe_encrypted_password(self, vault_item) -> bytes:
        """
        Get or create the FHE-encrypted password for a vault item.

        If the vault item already has an fhe_password field populated,
        use that. Otherwise, create a simulated FHE encryption of
        the vault item's encrypted_data.
        """
        # Try to use existing FHE password from the vault item
        if vault_item.fhe_password:
            return bytes(vault_item.fhe_password)

        # Create a simulated FHE encryption from the encrypted vault data
        # In production, this would call the FHE service to encrypt
        # the actual password using the owner's FHE keys
        encrypted_data = vault_item.encrypted_data.encode() \
            if isinstance(vault_item.encrypted_data, str) \
            else vault_item.encrypted_data

        # Add a random pad to make each FHE encryption unique
        pad = secrets.token_bytes(32)

        import hashlib
        fhe_simulated = hashlib.sha512(
            pad + encrypted_data
        ).digest() + pad

        return fhe_simulated

    def _get_recipient_public_key(self, recipient) -> Optional[bytes]:
        """
        Get the recipient's FHE public key, if available.

        Checks the FHEKeyStore for the recipient's active public key.
        Returns None if no key is found (simulated mode).
        """
        try:
            from fhe_service.models import FHEKeyStore

            key_record = FHEKeyStore.objects.filter(
                user=recipient,
                key_type='seal_public',
                is_active=True,
            ).first()

            if key_record:
                return bytes(key_record.encrypted_key_data)
        except Exception:
            pass

        return None

    def _log_action(
        self,
        share: HomomorphicShare,
        user,
        action: str,
        domain: str = '',
        success: bool = True,
        failure_reason: str = '',
        request=None,
        details: Optional[Dict] = None,
    ):
        """Create an audit log entry."""
        try:
            ShareAccessLog.objects.create(
                share=share,
                user=user,
                action=action,
                domain=domain,
                success=success,
                failure_reason=failure_reason,
                ip_address=request.META.get('REMOTE_ADDR') if request else None,
                user_agent=(
                    request.META.get('HTTP_USER_AGENT', '')[:500]
                    if request else ''
                ),
                details=details or {},
            )
        except Exception as e:
            logger.error(
                f"[FHE Sharing] Failed to log action {action}: {e}"
            )



# Singleton instance
_sharing_service: Optional[HomomorphicSharingService] = None


def get_sharing_service() -> HomomorphicSharingService:
    """Get or create the HomomorphicSharingService singleton."""
    global _sharing_service
    if _sharing_service is None:
        _sharing_service = HomomorphicSharingService()
    return _sharing_service

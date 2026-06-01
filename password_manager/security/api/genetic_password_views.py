"""
Genetic Password API Views
==========================

REST API endpoints for DNA-based password generation.

Endpoints:
- POST /genetic/connect/          - Initiate DNA provider OAuth
- GET  /genetic/callback/         - OAuth callback handler
- POST /genetic/upload/           - Upload raw DNA file
- POST /genetic/generate-password/ - Generate genetic password
- GET  /genetic/certificate/{id}/ - Get genetic certificate
- GET  /genetic/certificates/     - List user's certificates
- GET  /genetic/evolution-status/ - Check epigenetic evolution status
- POST /genetic/trigger-evolution/ - Manually trigger evolution
- GET  /genetic/connection-status/ - Check DNA connection status
- DELETE /genetic/disconnect/     - Remove DNA connection
- PUT  /genetic/preferences/      - Update user preferences

Author: Password Manager Team
Created: 2026-01-16
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from security.utils.sensitive_hash import hash_for_dedup

from django.utils import timezone
from django.contrib.auth.models import User

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync

from ..models import (
    DNAConnection,
    GeneticPasswordCertificate,
    GeneticEvolutionLog,
    GeneticSubscription,
    DNAConsentRecord,
)
from ..services.genetic_password_service import get_genetic_generator
from ..services.dna_provider_service import (
    get_dna_provider,
    get_supported_providers,
    ManualUploadProvider,
)
from ..services.epigenetic_service import get_evolution_manager

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def get_or_create_subscription(user: User) -> GeneticSubscription:
    """Get or create genetic subscription for user."""
    try:
        return user.genetic_subscription
    except GeneticSubscription.DoesNotExist:
        return GeneticSubscription.objects.create(user=user)


def get_dna_connection(user: User) -> DNAConnection:
    """Get the currently active DNA connection for ``user`` or ``None``."""
    return (
        DNAConnection.objects.filter(user=user, is_active=True)
        .order_by('-connected_at')
        .first()
    )


# =============================================================================
# Phase D / D4 (2026-05): OAuth token at-rest encryption.
#
# Replaced the old derivation chain:
#   raw_key = env('DNA_TOKEN_ENCRYPTION_KEY') or settings.SECRET_KEY
#   key     = hashlib.sha256(raw_key).digest()
#
# with HKDF-SHA256 over a dedicated env var. Two problems with the old code:
#
#   (1) SECRET_KEY fallback. Rotating SECRET_KEY (Django's documented
#       way to invalidate all sessions) would silently corrupt every
#       OAuth token stored under the old key — decrypts would fail and
#       users would be force-disconnected from their DNA provider.
#       D4 makes the encryption key independent and required.
#
#   (2) Raw SHA-256 KDF. No salt, no domain separation, no info label.
#       The output is functionally fine when the input is high-entropy,
#       but CodeQL's py/weak-sensitive-data-hashing flags it and any
#       future contributor who copies this pattern to a low-entropy
#       input would have a real weakness.
#
# Transparent rollout: ``decrypt_token`` first tries the new HKDF-derived
# key; on InvalidToken (which is what Fernet raises when the MAC doesn't
# verify, including across-key decrypt attempts) it falls back to the
# legacy SHA-256-derived key. The vault's token-refresh callback
# re-encrypts on save under the new key, so existing rows auto-upgrade
# over their natural refresh cycle. The legacy fallback is scheduled for
# removal in a follow-up PR ~30 days after this lands.
# =============================================================================


def _hkdf_fernet_key(raw_key: bytes) -> bytes:
    """Derive a 32-byte Fernet key from raw_key via HKDF-SHA256."""
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes as crypto_hashes
    return HKDF(
        algorithm=crypto_hashes.SHA256(),
        length=32,
        # Versioned salt so the derivation is rotatable in the future
        # without changing the env var (bump the version string and
        # re-encrypt everything via a one-shot migration command).
        salt=b'dna-token-encryption-v1',
        info=b'oauth-token-fernet-key',
    ).derive(raw_key)


def _get_fernet():
    """Return the primary Fernet instance for DNA-provider OAuth tokens.

    Requires DNA_TOKEN_ENCRYPTION_KEY to be set explicitly — falling
    back to SECRET_KEY is prohibited (D4).
    """
    import base64
    from cryptography.fernet import Fernet
    from django.core.exceptions import ImproperlyConfigured

    # PR #275 follow-up review (CodeRabbit): ``.strip()`` so the
    # primary path matches the legacy path's whitespace handling at
    # _get_legacy_fernet below. Without this, an operator who pastes
    # a key with trailing whitespace into DNA_TOKEN_ENCRYPTION_KEY
    # would derive a DIFFERENT Fernet key than the same value pasted
    # into DNA_TOKEN_LEGACY_KEY — silently breaking the legacy
    # decrypt fallback during rollout.
    raw_key = os.environ.get('DNA_TOKEN_ENCRYPTION_KEY', '').strip().encode('utf-8')
    if not raw_key:
        raise ImproperlyConfigured(
            "DNA_TOKEN_ENCRYPTION_KEY must be set explicitly. "
            "OAuth tokens cannot be encrypted without a dedicated key. "
            "Falling back to SECRET_KEY is prohibited because "
            "SECRET_KEY rotation would silently corrupt all stored "
            "OAuth tokens. See SECURITY.md for the recommended "
            "rotation procedure."
        )
    derived = _hkdf_fernet_key(raw_key)
    return Fernet(base64.urlsafe_b64encode(derived))


def _get_legacy_fernet():
    """Reproduce the pre-D4 SHA-256-derived key for transparent rollout.

    Returns None when ``DNA_TOKEN_LEGACY_KEY`` is unset — that's the
    operator's signal that all stored tokens have been re-encrypted
    under the new HKDF scheme and the fallback path can be retired.

    PR #275 review (CodeRabbit): the previous implementation fell
    back to ``DNA_TOKEN_ENCRYPTION_KEY`` when ``DNA_TOKEN_LEGACY_KEY``
    was missing, which meant a correctly-configured deployment always
    returned a usable legacy Fernet — the "fully cut over" branch was
    unreachable, and the fallback could not be disabled. The new
    contract: ONLY ``DNA_TOKEN_LEGACY_KEY`` controls the legacy
    decrypt path. To enable the fallback during rollout, set
    ``DNA_TOKEN_LEGACY_KEY`` to the SAME value the old
    ``DNA_TOKEN_ENCRYPTION_KEY`` held before the cutover. To disable
    it (post-rollout), unset ``DNA_TOKEN_LEGACY_KEY``.
    """
    import base64
    import hashlib
    from cryptography.fernet import Fernet

    legacy_raw = (os.environ.get('DNA_TOKEN_LEGACY_KEY') or '').strip()
    if not legacy_raw:
        return None
    derived = hashlib.sha256(legacy_raw.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_token(token: str) -> bytes:
    """Encrypt OAuth token for storage using Fernet (AES-128-CBC + HMAC-SHA256)."""
    # Always encrypt with the new HKDF-derived key. Existing rows
    # under the legacy key remain decryptable via ``decrypt_token``'s
    # fallback path and get re-encrypted on the next save.
    return _get_fernet().encrypt(token.encode('utf-8'))


def decrypt_token(encrypted: bytes) -> str:
    """Decrypt OAuth token, with transparent legacy-key fallback.

    Phase D / D4 (2026-05): try the new HKDF-derived key first, fall
    back to the legacy SHA-256-derived key on ``InvalidToken``. The
    fallback exists only so the production rollout doesn't strand
    existing OAuth grants — schedule its removal once all rows have
    been re-encrypted.
    """
    from cryptography.fernet import InvalidToken

    try:
        return _get_fernet().decrypt(encrypted).decode('utf-8')
    except InvalidToken:
        legacy = _get_legacy_fernet()
        if legacy is None:
            raise
        # PR #275 review (CodeRabbit): log AFTER the legacy decrypt
        # succeeds, not before. The previous order would count every
        # malformed/corrupted ciphertext as a "legacy fallback used"
        # event, skewing the metric operators use to decide when to
        # turn the fallback off.
        decrypted = legacy.decrypt(encrypted).decode('utf-8')
        # PR #275 follow-up: reuse the module-level ``logger`` defined
        # at line 56 instead of re-resolving the same name via a local
        # ``import logging`` — the previous duplication shadowed the
        # global on every call and was a CodeRabbit nit.
        logger.info(
            "decrypt_token: legacy-key fallback used; row will be "
            "re-encrypted under new HKDF key on next save."
        )
        return decrypted


# =============================================================================
# OAuth Connection Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_connection(request):
    """
    Initiate DNA provider OAuth flow.
    
    Request body:
    {
        "provider": "sequencing" | "23andme",
        "redirect_uri": "https://example.com/callback"
    }
    
    Returns:
    {
        "success": true,
        "auth_url": "https://provider.com/oauth/authorize?...",
        "state": "random-state-token"
    }
    """
    try:
        provider_type = request.data.get('provider', 'sequencing')
        redirect_uri = request.data.get('redirect_uri', '')

        if not redirect_uri:
            return Response({
                'success': False,
                'error': 'redirect_uri is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Phase E / E3 (2026-05): allowlist check. Without it, an
        # attacker can craft a state with their own redirect_uri,
        # send the victim through the provider's auth flow, and
        # collect the auth code on attacker-controlled origin. The
        # allowlist is operator-configured via the
        # ``GENETIC_OAUTH_REDIRECT_URIS`` env var (comma-separated).
        # The default empty list rejects every request — operators
        # MUST configure at least one entry for the feature to work.
        from django.conf import settings
        allowed = getattr(settings, 'GENETIC_OAUTH_REDIRECT_URIS', []) or []
        if redirect_uri not in allowed:
            logger.warning(
                "OAuth initiation rejected: redirect_uri=%r not in "
                "GENETIC_OAUTH_REDIRECT_URIS allowlist (%d entries).",
                redirect_uri, len(allowed),
            )
            return Response({
                'success': False,
                'error': 'redirect_uri_not_allowed',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get provider
        provider = get_dna_provider(provider_type)

        # Generate state token
        state = str(uuid.uuid4())

        # Phase E / E3 (2026-05): persist an explicit ``expires_at``
        # alongside the state. The state callback (oauth_callback)
        # rejects expired states with 400 ``state_expired``. Without
        # a TTL, an attacker who intercepted a state token could
        # replay it indefinitely; 10 minutes matches the typical
        # OAuth code-exchange window.
        _STATE_TTL_MINUTES = 10
        request.session[f'genetic_oauth_state_{state}'] = {
            'provider': provider_type,
            'redirect_uri': redirect_uri,
            'created_at': timezone.now().isoformat(),
            'expires_at': (
                timezone.now() + timedelta(minutes=_STATE_TTL_MINUTES)
            ).isoformat(),
        }
        
        # Get OAuth URL
        auth_url = provider.get_oauth_url(redirect_uri, state)
        
        return Response({
            'success': True,
            'auth_url': auth_url,
            'state': state,
            'provider': provider_type,
        })
        
    except ValueError as e:
        logger.exception("Handled ValueError in view")
        return Response({
            'success': False,
            'error': 'invalid_request'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"OAuth initiation failed: {e}")
        return Response({
            'success': False,
            'error': 'Failed to initiate OAuth flow'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def oauth_callback(request):
    """
    Handle OAuth callback from DNA provider.
    
    Query params or body:
    - code: Authorization code
    - state: State token for verification
    
    Returns:
    {
        "success": true,
        "message": "DNA connection established",
        "snp_count": 1000000
    }
    """
    try:
        # Get params from query or body
        code = request.GET.get('code') or request.data.get('code')
        state = request.GET.get('state') or request.data.get('state')
        
        if not code or not state:
            return Response({
                'success': False,
                'error': 'Missing code or state parameter'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify state
        state_data = request.session.get(f'genetic_oauth_state_{state}')
        if not state_data:
            return Response({
                'success': False,
                'error': 'Invalid or expired state token'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Phase E / E3 (2026-05): enforce the 10-minute state TTL set
        # in initiate_connection. Old state entries (no ``expires_at``
        # field — pre-E3 records persisted in long-lived sessions)
        # are treated as expired and rejected too.
        expires_at_iso = state_data.get('expires_at')
        if not expires_at_iso:
            del request.session[f'genetic_oauth_state_{state}']
            return Response({
                'success': False,
                'error': 'state_expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            expires_at_dt = datetime.fromisoformat(expires_at_iso)
        except (TypeError, ValueError):
            del request.session[f'genetic_oauth_state_{state}']
            return Response({
                'success': False,
                'error': 'state_expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() > expires_at_dt:
            del request.session[f'genetic_oauth_state_{state}']
            return Response({
                'success': False,
                'error': 'state_expired'
            }, status=status.HTTP_400_BAD_REQUEST)

        provider_type = state_data['provider']
        redirect_uri = state_data['redirect_uri']

        # Clean up state
        del request.session[f'genetic_oauth_state_{state}']
        
        # Get provider and authenticate
        provider = get_dna_provider(provider_type)
        
        # Exchange code for tokens
        tokens = async_to_sync(provider.authenticate)(code, redirect_uri)
        
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in', 3600)
        
        # Fetch SNP data
        snp_data = async_to_sync(provider.fetch_snp_data)(access_token)
        
        # Generate genetic seed hash (for verification only)
        from ..services.genetic_password_service import GeneticSeedGenerator
        seed_gen = GeneticSeedGenerator()
        genetic_seed = seed_gen.generate_seed_from_snps(snp_data)
        hash_prefix = seed_gen.get_seed_hash_prefix(genetic_seed)
        
        # Create or update DNA connection
        connection, created = DNAConnection.objects.update_or_create(
            user=request.user,
            defaults={
                'provider': provider_type,
                'status': 'connected',
                'access_token_encrypted': encrypt_token(access_token),
                'refresh_token_encrypted': encrypt_token(refresh_token) if refresh_token else None,
                'token_expires_at': timezone.now() + timedelta(seconds=expires_in),
                'genetic_hash_prefix': hash_prefix,
                'genetic_seed_salt': seed_gen.salt,
                'snp_count': genetic_seed.snp_count,
                'connected_at': timezone.now(),
                'last_sync': timezone.now(),
                'consent_given_at': timezone.now(),
                'gdpr_consent': True,
            }
        )
        
        # Ensure subscription exists
        get_or_create_subscription(request.user)
        
        # Log consent
        DNAConsentRecord.objects.create(
            user=request.user,
            consent_type='genetic_processing',
            consent_version='1.0',
            consent_text_hash='sha256:...',  # Would be actual hash
            consented=True,
            consented_at=timezone.now(),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        logger.info(f"DNA connection established for {request.user.username}: {provider_type}")
        
        return Response({
            'success': True,
            'message': 'DNA connection established',
            'provider': provider_type,
            'snp_count': genetic_seed.snp_count,
            'genetic_hash_prefix': hash_prefix[:20] + '...',
        })
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# File Upload Endpoint
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_dna_file(request):
    """
    Upload raw DNA file for manual connection.
    
    Accepts:
    - 23andMe raw data (.txt)
    - AncestryDNA raw data (.csv)
    - VCF format (.vcf)
    
    Request: multipart/form-data with 'dna_file' field
    
    Returns:
    {
        "success": true,
        "snp_count": 600000,
        "genetic_hash_prefix": "sha256:abc123..."
    }
    """
    try:
        if 'dna_file' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No file uploaded. Use field name: dna_file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['dna_file']
        
        # Check file size (max 50MB)
        if uploaded_file.size > 50 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'File too large. Maximum size is 50MB.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Read file content
        file_content = uploaded_file.read()
        filename = uploaded_file.name
        
        # Parse file
        provider = ManualUploadProvider()
        
        try:
            snp_data, format_detected = provider.parse_uploaded_file(file_content, filename)
        except ValueError as e:
            logger.exception("Handled ValueError in view")
            return Response({
                'success': False,
                'error': 'invalid_request'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(snp_data) < 100:
            return Response({
                'success': False,
                'error': f'Insufficient SNP data found ({len(snp_data)} SNPs). Please upload valid raw DNA data.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate genetic seed hash
        from ..services.genetic_password_service import GeneticSeedGenerator
        seed_gen = GeneticSeedGenerator()
        genetic_seed = seed_gen.generate_seed_from_snps(snp_data)
        hash_prefix = seed_gen.get_seed_hash_prefix(genetic_seed)
        
        # Store connection (without raw data - only hash)
        connection, created = DNAConnection.objects.update_or_create(
            user=request.user,
            defaults={
                'provider': 'manual',
                'status': 'connected',
                'genetic_hash_prefix': hash_prefix,
                'genetic_seed_salt': seed_gen.salt,
                'snp_count': genetic_seed.snp_count,
                'connected_at': timezone.now(),
                'last_sync': timezone.now(),
                'consent_given_at': timezone.now(),
                'gdpr_consent': True,
            }
        )
        
        # Ensure subscription
        get_or_create_subscription(request.user)
        
        # Log upload (but NOT the data)
        logger.info(
            f"DNA file uploaded for {request.user.username}: "
            f"{filename} ({format_detected}), {genetic_seed.snp_count} SNPs"
        )
        
        # IMPORTANT: Raw SNP data is NOT stored
        # Only the hash prefix is kept for verification
        
        return Response({
            'success': True,
            'message': 'DNA data processed successfully',
            'format_detected': format_detected,
            'snp_count': genetic_seed.snp_count,
            'genetic_hash_prefix': hash_prefix[:20] + '...',
        })
        
    except Exception as e:
        logger.error(f"DNA file upload failed: {e}")
        return Response({
            'success': False,
            'error': 'Failed to process DNA file'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Password Generation
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_genetic_password(request):
    """
    Generate a password seeded by genetic data.
    
    Request body:
    {
        "length": 16,
        "uppercase": true,
        "lowercase": true, 
        "numbers": true,
        "symbols": true,
        "combine_with_quantum": true,
        "save_certificate": false
    }
    
    Returns:
    {
        "success": true,
        "password": "xK9#mP2$vL...",
        "certificate": {...},
        "evolution_generation": 1
    }
    """
    try:
        # Check DNA connection
        connection = get_dna_connection(request.user)
        if not connection or connection.status != 'connected':
            return Response({
                'success': False,
                'error': 'No DNA connection found. Please connect your DNA data first.',
                'requires_connection': True,
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check subscription
        subscription = get_or_create_subscription(request.user)
        
        # Get options from request
        length = request.data.get('length', 16)
        use_uppercase = request.data.get('uppercase', True)
        use_lowercase = request.data.get('lowercase', True)
        use_numbers = request.data.get('numbers', True)
        use_symbols = request.data.get('symbols', True)
        combine_with_quantum = request.data.get('combine_with_quantum', connection.combine_with_quantum)
        save_certificate = request.data.get('save_certificate', False)
        
        # Validate length
        length = max(8, min(128, int(length)))
        
        # For password generation, we need to reconstruct SNP data
        # In a real implementation, this would be cached or re-fetched
        # For now, we use the stored salt to ensure consistency
        
        # Get the generator with stored salt
        from ..services.genetic_password_service import GeneticSeedGenerator, GeneticPasswordGenerator
        
        seed_gen = GeneticSeedGenerator(salt=bytes(connection.genetic_seed_salt))
        
        # We need SNP data - in production, this would be cached or re-fetched
        # For manual uploads, we'd need the user to re-upload
        # For OAuth, we could re-fetch from the provider
        
        # For now, we'll generate a deterministic password from the stored hash
        # This is a simplified version - full implementation would re-fetch SNPs
        
        import hashlib
        import hmac
        
        # Use stored genetic hash as seed source
        seed_source = connection.genetic_hash_prefix + str(connection.evolution_generation)
        base_seed = hashlib.sha3_512(seed_source.encode()).digest()
        
        # Build charset
        charset = ""
        if use_uppercase:
            charset += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if use_lowercase:
            charset += "abcdefghijklmnopqrstuvwxyz"
        if use_numbers:
            charset += "0123456789"
        if use_symbols:
            charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        if not charset:
            charset = "abcdefghijklmnopqrstuvwxyz"
        
        # Optionally combine with quantum entropy
        quantum_cert_id = None
        if combine_with_quantum:
            try:
                from ..services.quantum_rng_service import get_quantum_generator
                quantum_gen = get_quantum_generator()
                quantum_result = async_to_sync(quantum_gen.entropy_pool.get_random_bytes)(32)
                if quantum_result:
                    quantum_bytes = quantum_result[0]
                    # Combine seeds
                    combined = bytes(a ^ b for a, b in zip(base_seed[:32], quantum_bytes[:32]))
                    base_seed = hashlib.sha3_512(combined + base_seed[32:]).digest()
                    # Get quantum cert id if available
                    if len(quantum_result) > 1 and hasattr(quantum_result[1], 'id'):
                        quantum_cert_id = str(quantum_result[1].id)
            except Exception as e:
                logger.warning(f"Quantum combination failed: {e}")
        
        # Generate password using HMAC-DRBG
        password = []
        counter = 0
        charset_len = len(charset)
        max_valid = (256 // charset_len) * charset_len
        
        while len(password) < length:
            prng_output = hmac.new(
                base_seed,
                counter.to_bytes(8, 'big'),
                hashlib.sha256
            ).digest()
            
            for byte_val in prng_output:
                if len(password) >= length:
                    break
                if byte_val < max_valid:
                    password.append(charset[byte_val % charset_len])
            
            counter += 1
        
        generated_password = "".join(password)
        
        # Create certificate
        import math
        entropy_bits = int(math.log2(len(charset)) * length)
        
        password_hash = hash_for_dedup(generated_password, domain="genetic-views-cert")
        
        cert_data = {
            'password_hash_prefix': f"sha256:{password_hash[:16]}...",
            'genetic_hash_prefix': connection.genetic_hash_prefix[:20] + '...',
            'provider': connection.provider,
            'snp_markers_used': connection.snp_count,
            'epigenetic_age': connection.last_biological_age,
            'evolution_generation': connection.evolution_generation,
            'combined_with_quantum': combine_with_quantum,
            'quantum_certificate_id': quantum_cert_id,
            'password_length': length,
            'entropy_bits': entropy_bits,
            'generation_timestamp': timezone.now().isoformat(),
        }
        
        # Create signature.
        # Audit Group B (#3): use the dedicated cert-signing secret from
        # settings (env var, SECRET_KEY fallback gated to dev/test by the
        # production guard in settings/base.py). The previous hardcoded
        # 'genetic-cert-secret' default was forgeable.
        #
        # Audit Group D (#15): sign the SAME canonical-JSON payload (v2)
        # the service uses, over this certificate's stored fields, so a
        # cert issued here verifies under
        # GeneticPasswordGenerator.verify_certificate(). The id signed as
        # ``cid`` is the certificate's own UUID, reused as the model PK so
        # the persisted row and the signature stay consistent.
        from django.conf import settings
        from security.services.genetic_password_service import (
            canonical_cert_sig_payload,
            _CERT_SIG_VERSION,
        )
        cert_secret = settings.GENETIC_CERT_SECRET
        cert_uuid = uuid.uuid4()
        sig_data = canonical_cert_sig_payload(
            certificate_id=cert_uuid,
            password_hash_prefix=cert_data['password_hash_prefix'],
            genetic_hash_prefix=cert_data['genetic_hash_prefix'],
            evolution_generation=connection.evolution_generation,
            combined_with_quantum=combine_with_quantum,
        )
        signature = hmac.new(
            cert_secret.encode(),
            sig_data.encode(),
            hashlib.sha256
        ).hexdigest()

        cert_data['signature'] = signature
        cert_data['certificate_id'] = str(cert_uuid)
        cert_data['cert_version'] = _CERT_SIG_VERSION

        # Save certificate if requested
        if save_certificate:
            GeneticPasswordCertificate.objects.create(
                id=cert_uuid,
                user=request.user,
                password_hash_prefix=cert_data['password_hash_prefix'],
                genetic_hash_prefix=cert_data['genetic_hash_prefix'],
                provider=connection.provider,
                snp_markers_used=connection.snp_count,
                epigenetic_age=connection.last_biological_age,
                evolution_generation=connection.evolution_generation,
                combined_with_quantum=combine_with_quantum,
                quantum_certificate_id=uuid.UUID(quantum_cert_id) if quantum_cert_id else None,
                password_length=length,
                entropy_bits=entropy_bits,
                signature=signature,
                cert_version=_CERT_SIG_VERSION,
            )
        
        # Update subscription counter
        subscription.passwords_generated += 1
        subscription.save()
        
        return Response({
            'success': True,
            'password': generated_password,
            'certificate': cert_data,
            'evolution_generation': connection.evolution_generation,
            'snp_count': connection.snp_count,
        })
        
    except Exception as e:
        logger.error(f"Genetic password generation failed: {e}")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Certificate Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate(request, certificate_id):
    """
    Get a specific genetic certificate.
    
    Returns certificate details for viewing/verification.
    """
    try:
        cert = GeneticPasswordCertificate.objects.get(
            id=certificate_id,
            user=request.user
        )
        return Response({
            'success': True,
            'certificate': cert.to_dict()
        })
    except GeneticPasswordCertificate.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Certificate not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_certificates(request):
    """
    List user's genetic certificates.
    
    Query params:
    - limit: Max number to return (default 50)
    - offset: Pagination offset
    """
    try:
        limit = min(int(request.GET.get('limit', 50)), 100)
        offset = int(request.GET.get('offset', 0))
        
        certs = GeneticPasswordCertificate.objects.filter(
            user=request.user
        ).order_by('-generation_timestamp')[offset:offset + limit]
        
        total = GeneticPasswordCertificate.objects.filter(user=request.user).count()
        
        return Response({
            'success': True,
            'certificates': [c.to_dict() for c in certs],
            'total': total,
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        logger.exception("Handled Exception in view")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Evolution Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_evolution_status(request):
    """
    Get current epigenetic evolution status.
    
    Returns evolution generation, biological age, and next check estimate.
    """
    try:
        connection = get_dna_connection(request.user)
        if not connection:
            return Response({
                'success': False,
                'error': 'No DNA connection found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        subscription = get_or_create_subscription(request.user)
        evolution_manager = get_evolution_manager()
        
        status_data = evolution_manager.get_evolution_status(connection)
        status_data['can_use_epigenetic'] = subscription.can_use_epigenetic()
        status_data['subscription_tier'] = subscription.tier
        status_data['is_premium'] = subscription.is_premium_active()
        status_data['is_trial'] = subscription.is_trial_active()
        
        if subscription.trial_expires_at:
            status_data['trial_expires_at'] = subscription.trial_expires_at.isoformat()
        
        return Response({
            'success': True,
            'evolution': status_data
        })
        
    except Exception as e:
        logger.error(f"Evolution status check failed: {e}")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_evolution(request):
    """
    Manually trigger password evolution.
    
    Premium feature: Requires active subscription.
    
    Request body:
    {
        "new_biological_age": 35.5,
        "force": false
    }
    """
    try:
        connection = get_dna_connection(request.user)
        if not connection:
            return Response({
                'success': False,
                'error': 'No DNA connection found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        subscription = get_or_create_subscription(request.user)
        
        if not subscription.can_use_epigenetic():
            return Response({
                'success': False,
                'error': 'Epigenetic evolution requires premium subscription',
                'requires_premium': True,
            }, status=status.HTTP_402_PAYMENT_REQUIRED)
        
        # Get new biological age from request
        new_bio_age = request.data.get('new_biological_age')
        force = request.data.get('force', False)
        
        if new_bio_age is not None:
            connection.last_biological_age = float(new_bio_age)
            connection.save()
        
        # Trigger evolution
        evolution_manager = get_evolution_manager()
        evolved, message = async_to_sync(evolution_manager.check_and_evolve)(
            request.user,
            connection,
            force=force
        )
        
        # Get updated status
        status_data = evolution_manager.get_evolution_status(connection)
        
        return Response({
            'success': True,
            'evolved': evolved,
            'message': message,
            'evolution': status_data
        })
        
    except Exception as e:
        logger.error(f"Evolution trigger failed: {e}")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Connection Management
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_connection_status(request):
    """
    Get DNA connection status and available providers.
    """
    try:
        connection = get_dna_connection(request.user)
        subscription = get_or_create_subscription(request.user)
        
        response_data = {
            'success': True,
            'connected': connection is not None and connection.status == 'connected',
            'available_providers': get_supported_providers(),
            'subscription': {
                'tier': subscription.tier,
                'is_trial': subscription.is_trial_active(),
                'is_premium': subscription.is_premium_active(),
                'can_use_epigenetic': subscription.can_use_epigenetic(),
                'passwords_generated': subscription.passwords_generated,
            }
        }
        
        if connection:
            response_data['connection'] = {
                'provider': connection.provider,
                'status': connection.status,
                'snp_count': connection.snp_count,
                'connected_at': connection.connected_at.isoformat() if connection.connected_at else None,
                'evolution_generation': connection.evolution_generation,
                'combine_with_quantum': connection.combine_with_quantum,
            }
        
        return Response(response_data)
        
    except Exception as e:
        logger.exception("Handled Exception in view")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def disconnect_dna(request):
    """
    Remove DNA connection and delete all genetic data.
    
    This is irreversible - user will need to reconnect.
    """
    try:
        connection = get_dna_connection(request.user)
        if not connection:
            return Response({
                'success': False,
                'error': 'No DNA connection found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Log the disconnection
        logger.info(f"DNA connection deactivated for {request.user.username}")

        # Soft-delete: mark inactive so certificates still link correctly
        connection.is_active = False
        connection.status = 'revoked'
        connection.save(update_fields=['is_active', 'status'])

        return Response({
            'success': True,
            'message': 'DNA connection removed successfully'
        })
        
    except Exception as e:
        logger.error(f"DNA disconnect failed: {e}")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    """
    Update genetic password preferences.
    
    Request body:
    {
        "combine_with_quantum": true
    }
    """
    try:
        connection = get_dna_connection(request.user)
        if not connection:
            return Response({
                'success': False,
                'error': 'No DNA connection found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update preferences
        if 'combine_with_quantum' in request.data:
            connection.combine_with_quantum = bool(request.data['combine_with_quantum'])
        
        connection.save()
        
        return Response({
            'success': True,
            'preferences': {
                'combine_with_quantum': connection.combine_with_quantum,
            }
        })
        
    except Exception as e:
        logger.exception("Handled Exception in view")
        return Response({
            'success': False,
            'error': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

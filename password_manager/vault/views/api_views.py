from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from vault.models.vault_models import EncryptedVaultItem
from vault.models import UserSalt
from vault.serializer import EncryptedVaultItemSerializer
from vault.crypto import derive_auth_key, generate_salt
from password_manager.throttling import VaultOperationThrottle
import base64


import logging as _hp_logging

_hp_logger = _hp_logging.getLogger(__name__)


class _HookFailed(Exception):
    """Raised when a security-relevant hook (honeypot/self-destruct) errors.

    Views translate this into a 5xx so the feature fails *closed* instead of
    silently returning the real vault item when its policy chain throws.
    """


def _honeypot_decoy(request, pk):
    """Return the decoy payload if ``pk`` is a honeypot, else ``None``.

    Fails closed: if the honeypot subsystem raises, we propagate ``_HookFailed``
    rather than letting the view fall through to the real credential — the
    whole point of the honeypot is that attackers must never see a behavioural
    difference between decoy and real access, so policy errors must deny.
    """
    if not getattr(settings, 'HONEYPOT_CREDENTIALS_ENABLED', True):
        return None
    try:
        from honeypot_credentials.services import HoneypotAccessInterceptor
        return HoneypotAccessInterceptor().intercept_retrieve(pk, request)
    except Exception as exc:
        _hp_logger.exception("honeypot interceptor failed; denying read: %s", exc)
        raise _HookFailed("honeypot interceptor error") from exc


def _self_destruct_block(request, vault_item):
    """Return ``(message, reason)`` if access is denied, else ``None``.

    Fails closed: if the self-destruct policy chain raises, an attacker who
    can induce exceptions (malformed state, import failure, etc.) would
    otherwise bypass the policy entirely. Propagate ``_HookFailed`` so the
    view returns a 5xx and the credential is NOT disclosed.
    """
    if not getattr(settings, 'SELF_DESTRUCT_PASSWORDS_ENABLED', True):
        return None
    try:
        from self_destruct.services.policy_service import evaluate_access, record_access
        decision = evaluate_access(vault_item, request)
        if decision == 'allow':
            record_access(vault_item)
            return None
        return ('This credential is no longer available.', decision)
    except Exception as exc:
        _hp_logger.exception("self-destruct policy failed; denying read: %s", exc)
        raise _HookFailed("self-destruct policy error") from exc

def error_response(message, status_code=status.HTTP_400_BAD_REQUEST, code="error", details=None):
    """Helper function to create standardized error responses"""
    return Response({
        "success": False,
        "message": message,
        "code": code,
        "details": details or {}
    }, status=status_code)

def success_response(data=None, message="Operation successful", status_code=status.HTTP_200_OK):
    """Helper function to create standardized success responses"""
    response = {
        "success": True,
        "message": message,
    }
    
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response["data"] = data
            
    return Response(response, status=status_code)

# Create your views here.

class VaultItemViewSet(viewsets.ModelViewSet):
    """API endpoint for vault items"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [VaultOperationThrottle]
    serializer_class = EncryptedVaultItemSerializer
    
    def get_queryset(self):
        """Return only items belonging to authenticated user"""
        return EncryptedVaultItem.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a new encrypted vault item"""
        # Add current user to data
        data = request.data.copy()
        data['user'] = request.user.id
        
        serializer = self.get_serializer(data=data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid data provided",
                code="validation_error",
                details=serializer.errors
            )
            
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return success_response(
            data=serializer.data,
            message="Item created successfully",
            status_code=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        """List all vault items for the user with optional metadata-only mode"""
        metadata_only = request.query_params.get('metadata_only', 'false').lower() == 'true'
        
        queryset = self.get_queryset()
        
        if metadata_only:
            # Return only essential fields for lazy loading
            data = queryset.values(
                'id', 
                'item_id', 
                'item_type', 
                'favorite', 
                'created_at', 
                'updated_at',
                'encrypted_data'  # Still send, but won't decrypt client-side yet
            )
            return success_response(
                data={"items": list(data), "metadata_only": True},
                message="Metadata retrieved successfully"
            )
        
        # Default: full serialization
        serializer = self.get_serializer(queryset, many=True)
        items = list(serializer.data)

        # Mix in masked honeypot entries so attackers cannot distinguish them.
        if getattr(settings, 'HONEYPOT_CREDENTIALS_ENABLED', True):
            try:
                from honeypot_credentials.services import HoneypotService
                hp_service = HoneypotService()
                for hp in hp_service.list_for_user(request.user):
                    if hp.is_active:
                        items.append(hp_service.masked_list_entry(hp))
            except Exception:
                pass

        return success_response(
            data={"items": items},
            message="Items retrieved successfully"
        )
        
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single vault item. Honors honeypot + self-destruct hooks."""
        pk = kwargs.get(self.lookup_field or 'pk') or kwargs.get('pk')
        try:
            decoy = _honeypot_decoy(request, pk)
        except _HookFailed:
            return error_response(
                message="Access policy unavailable; please retry.",
                code="policy_unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if decoy is not None:
            return success_response(data=decoy, message='Item retrieved successfully')

        try:
            instance = self.get_object()
            try:
                denial = _self_destruct_block(request, instance)
            except _HookFailed:
                return error_response(
                    message="Access policy unavailable; please retry.",
                    code="policy_unavailable",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if denial is not None:
                message, reason = denial
                return error_response(
                    message=message,
                    code=reason,
                    status_code=410,
                )
            serializer = self.get_serializer(instance)
            return success_response(
                data=serializer.data,
                message="Item retrieved successfully"
            )
        except EncryptedVaultItem.DoesNotExist:
            return error_response(
                message="Item not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="item_not_found"
            )
    
    def update(self, request, *args, **kwargs):
        """Update a vault item"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            
            if not serializer.is_valid():
                return error_response(
                    message="Invalid data provided",
                    code="validation_error",
                    details=serializer.errors
                )
                
            self.perform_update(serializer)
            return success_response(
                data=serializer.data,
                message="Item updated successfully"
            )
        except EncryptedVaultItem.DoesNotExist:
            return error_response(
                message="Item not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="item_not_found"
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete a vault item"""
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return success_response(
                message="Item deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT
            )
        except EncryptedVaultItem.DoesNotExist:
            return error_response(
                message="Item not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="item_not_found"
            )
    
    @action(detail=False, methods=['get'])
    def get_salt(self, request):
        """Get the user's salt for key derivation.

        Audit-fix C10 (2026-05): when a `vault.UserSalt` row needs to be
        created on first access, seed `auth_hash` from the authoritative
        `auth_module.UserSalt` written at registration. Previously the
        row was created with `auth_hash=b''`, which let any authenticated
        caller "claim" the empty slot through `verify_auth` and lock the
        legitimate owner out of their own vault.
        """
        try:
            # Pre-fetch the authoritative auth_hash, if it exists. This
            # is the row that the registration view at
            # auth_module/views.py::AuthViewSet.register populates with
            # the client-derived Argon2id hash.
            #
            # We catch ONLY the expected "no auth row yet" and "auth
            # module unavailable" cases. Letting database errors and
            # other runtime failures propagate is deliberate: the prior
            # broad `except Exception` could mask a real DB outage by
            # silently seeding `b''`, which then trips `verify_auth`'s
            # `vault_not_initialized` refusal — confusing the user about
            # the real failure. Tightened per CodeRabbit review.
            seed_auth_hash = b''
            try:
                from auth_module.models import UserSalt as AuthSalt
            except ModuleNotFoundError as exc:
                # Only swallow if `auth_module` is *itself* the missing
                # module — i.e. the app isn't installed in this deploy.
                # If `auth_module` exists but fails to import because of
                # a broken transitive import (circular import, missing
                # dependency, etc.), re-raise so the real error surfaces
                # instead of being papered over with vault_not_initialized.
                # Tightened per CodeRabbit review of PR #262.
                if exc.name != 'auth_module':
                    raise
            else:
                try:
                    seed_auth_hash = bytes(
                        AuthSalt.objects.get(user=request.user).auth_hash or b''
                    )
                except AuthSalt.DoesNotExist:
                    # No row at registration time — leave empty so
                    # verify_auth correctly refuses with
                    # vault_not_initialized.
                    seed_auth_hash = b''

            salt_obj, created = UserSalt.objects.get_or_create(
                user=request.user,
                defaults={'salt': generate_salt(), 'auth_hash': seed_auth_hash},
            )

            return success_response({
                'salt': salt_obj.get_salt_b64(),
                'is_new': created
            })
        except Exception as e:
            _hp_logger.error("Failed to retrieve salt: %s", e)
            return error_response(
                message="Failed to retrieve salt.",
                code="salt_retrieval_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verify_master_password(self, request):
        """Deprecated: plaintext master-password verification is disallowed.

        Accepting the plaintext master password on the server violates the
        zero-knowledge contract the rest of the codebase enforces. Clients
        must derive an auth hash locally (Argon2id) and submit it to
        :meth:`verify_auth`, which compares with constant-time semantics and
        never sees the password itself.
        """
        return error_response(
            message=(
                "Endpoint disabled. Derive the auth hash client-side and call "
                "/vault/items/verify_auth/ instead."
            ),
            code="endpoint_disabled",
            status_code=status.HTTP_410_GONE,
        )
    
    @action(detail=False, methods=['post'])
    def verify_auth(self, request):
        """
        Verify client-generated auth hash (Zero-Knowledge Authentication).
        
        The client generates an auth hash from the master password using Argon2id.
        This hash is sent to the server for verification - the actual password
        is never transmitted.
        
        Request Body:
            auth_hash: Client-generated Argon2id hash of master password
        
        Response:
            valid: boolean indicating if auth hash matches stored value
        """
        from vault.services.vault_optimization_service import AuthHashService, vault_cache
        
        auth_hash = request.data.get('auth_hash')
        if not auth_hash:
            return error_response(
                message="Auth hash is required",
                code="missing_auth_hash"
            )
        
        try:
            user_id = request.user.id

            # Get user salt record
            try:
                salt_obj = UserSalt.objects.get(user=request.user)
            except UserSalt.DoesNotExist:
                return error_response(
                    message="Vault not initialized. Complete registration first.",
                    code="vault_not_initialized",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Audit-fix C10 (2026-05): the previous "first-time setup"
            # branch here would WRITE whatever auth_hash the caller sent
            # into an empty `vault.UserSalt` row, allowing a JWT-bearing
            # attacker to claim a victim's vault when the row hadn't been
            # seeded yet. The seeding now happens at `get_salt` time,
            # populated from the authoritative `auth_module.UserSalt`
            # row written at registration. Here we refuse to fall back
            # — any empty `auth_hash` means the vault is in a half-
            # provisioned state and the user must re-run the registration
            # finalization flow.
            if not salt_obj.auth_hash or bytes(salt_obj.auth_hash) == b'':
                return error_response(
                    message=(
                        "Vault is not initialized. Re-authenticate via the "
                        "registration finalization flow before retrying."
                    ),
                    code="vault_not_initialized",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Verify auth hash
            is_valid = AuthHashService.verify_auth_hash(user_id, auth_hash)

            if is_valid:
                return success_response({
                    'valid': True,
                    'user_id': user_id
                })
            else:
                return error_response(
                    message="Invalid auth hash",
                    code="invalid_auth",
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        except Exception as e:
            _hp_logger.error("Auth verification failed: %s", e)
            return error_response(
                message="Authentication verification failed.",
                code="verification_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get vault statistics (counts by type, favorites).
        Uses caching for performance.
        """
        from vault.services.vault_optimization_service import VaultQueryOptimizer
        
        try:
            stats = VaultQueryOptimizer.get_user_statistics(request.user)
            return success_response(data=stats)
        except Exception as e:
            _hp_logger.error("Failed to get statistics: %s", e)
            return error_response(
                message="Failed to get statistics.",
                code="stats_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def check_initialization(self, request):
        """Check if vault is initialized for the current user.

        After audit fix C10, `verify_auth` treats an empty `auth_hash`
        as "not initialized" and returns 400 `vault_not_initialized`.
        This endpoint must agree: a `UserSalt` row that exists but has
        a blank `auth_hash` is exactly the half-provisioned state the
        attack relied on, and reporting `initialized=True` for it would
        send clients into the unlock flow only to be rejected at
        `verify_auth`. Tightened per CodeRabbit review of PR #262.
        """
        try:
            from vault.models import UserSalt

            salt_obj = UserSalt.objects.filter(user=request.user).first()
            has_salt = salt_obj is not None
            has_auth_hash = bool(
                salt_obj and bytes(salt_obj.auth_hash or b'') != b''
            )

            # Check if user has any vault items
            has_items = self.get_queryset().exists()

            return success_response({
                # Single source of truth for "is the vault usable yet?".
                'initialized': has_salt and has_auth_hash,
                'has_salt': has_salt,
                'has_auth_hash': has_auth_hash,
                'has_items': has_items,
            })
        except Exception as e:
            _hp_logger.error("Failed to check initialization: %s", e)
            return error_response(
                message="Failed to check initialization status.",
                code="initialization_check_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
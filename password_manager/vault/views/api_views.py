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


def _honeypot_decoy(request, pk):
    """Shared helper: returns decoy payload if pk is a honeypot, else None."""
    if not getattr(settings, 'HONEYPOT_CREDENTIALS_ENABLED', True):
        return None
    try:
        from honeypot_credentials.services import HoneypotAccessInterceptor
        return HoneypotAccessInterceptor().intercept_retrieve(pk, request)
    except Exception:
        return None


def _self_destruct_block(request, vault_item):
    """Returns (message, reason) if access is denied, else None."""
    if not getattr(settings, 'SELF_DESTRUCT_PASSWORDS_ENABLED', True):
        return None
    try:
        from self_destruct.services.policy_service import evaluate_access, record_access
        decision = evaluate_access(vault_item, request)
        if decision == 'allow':
            record_access(vault_item)
            return None
        return ('This credential is no longer available.', decision)
    except Exception:
        return None

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
        decoy = _honeypot_decoy(request, pk)
        if decoy is not None:
            return success_response(data=decoy, message='Item retrieved successfully')

        try:
            instance = self.get_object()
            denial = _self_destruct_block(request, instance)
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
        """Get user's salt for key derivation"""
        try:
            # Get or create salt for user
            salt_obj, created = UserSalt.objects.get_or_create(
                user=request.user,
                defaults={'salt': generate_salt(), 'auth_hash': b''}
            )
            
            return success_response({
                'salt': salt_obj.get_salt_b64(),
                'is_new': created
            })
        except Exception as e:
            return error_response(
                message=f"Failed to retrieve salt: {str(e)}",
                code="salt_retrieval_error", 
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verify_master_password(self, request):
        """Verify master password using auth hash"""
        password = request.data.get('master_password')
        if not password:
            return error_response(
                message="Password is required",
                code="missing_password"
            )
            
        try:
            salt_obj = UserSalt.objects.get(user=request.user)
            auth_key = derive_auth_key(password, salt_obj.salt)
            
            if not salt_obj.auth_hash:  # First time setup
                salt_obj.auth_hash = auth_key
                salt_obj.save()
                return success_response({
                    'status': 'setup_complete'
                })
            
            # Compare derived key with stored auth hash
            is_valid = auth_key == salt_obj.auth_hash
            return success_response({
                'is_valid': is_valid
            })
            
        except UserSalt.DoesNotExist:
            return error_response(
                message="User not initialized with a salt",
                code="user_not_initialized"
            )
        except Exception as e:
            return error_response(
                message=f"Verification failed: {str(e)}",
                code="verification_error", 
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
                    message="User not initialized",
                    code="user_not_initialized",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # First-time setup: store the auth hash
            if not salt_obj.auth_hash or salt_obj.auth_hash == b'':
                # Store hashed version of auth hash
                server_hash = AuthHashService.hash_auth_hash(auth_hash)
                salt_obj.auth_hash = bytes.fromhex(server_hash)
                salt_obj.save()
                
                # Cache for future requests
                vault_cache.set_auth_hash(user_id, server_hash)
                
                return success_response({
                    'valid': True,
                    'setup': True,
                    'message': 'Auth hash stored successfully'
                })
            
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
            return error_response(
                message=f"Auth verification failed: {str(e)}",
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
            return error_response(
                message=f"Failed to get statistics: {str(e)}",
                code="stats_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def check_initialization(self, request):
        """Check if vault is initialized for the current user"""
        try:
            from vault.models import UserSalt
            
            # Check if user has a salt (vault initialized)
            has_salt = UserSalt.objects.filter(user=request.user).exists()
            
            # Check if user has any vault items
            has_items = self.get_queryset().exists()
            
            return success_response({
                'initialized': has_salt,
                'has_salt': has_salt,
                'has_items': has_items
            })
        except Exception as e:
            return error_response(
                message=f"Failed to check initialization: {str(e)}",
                code="initialization_check_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
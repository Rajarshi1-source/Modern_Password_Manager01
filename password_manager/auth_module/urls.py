from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
# Import the passkey views
from . import passkey_views
# Import OAuth views
from . import oauth_views
# Import OpenID Connect (OIDC) views
from . import oidc_views
# Import MFA views
from . import mfa_views
# Import Primary Passkey Recovery views
from . import passkey_primary_recovery_views
# Import Kyber (Post-Quantum) views
from . import kyber_views

@api_view(['GET'])
def auth_root(request, format=None):
    """Entry point for auth endpoints"""
    return Response({
        'register': reverse('auth-list', request=request, format=format),
        'login': reverse('auth-list', request=request, format=format),
        'token': reverse('token_obtain_pair', request=request, format=format),
        'passkeys': reverse('list_passkeys', request=request, format=format),
        'recovery': reverse('setup-recovery-key', request=request, format=format),
    })

router = DefaultRouter()
router.register(r'', views.AuthViewSet, basename='auth')

urlpatterns = [
    path('', auth_root, name='auth-root'),
    path('', include(router.urls)),
    # Add explicit paths for new endpoints
    path('complete-login/', views.AuthViewSet.as_view({'post': 'complete_login'}), name='complete-login'),
    path('push-auth/initiate/', views.AuthViewSet.as_view({'post': 'initiate_push_authentication'}), name='initiate-push-auth'),
    path('push-auth/check/', views.AuthViewSet.as_view({'post': 'check_push_authentication'}), name='check-push-auth'),
    path('push-auth/respond/', views.AuthViewSet.as_view({'post': 'respond_to_push'}), name='respond-to-push'),
    # Add JWT endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Recovery key endpoints
    path('setup-recovery-key/', views.AuthViewSet.as_view({'post': 'setup_recovery_key'}), name='setup-recovery-key'),
    path('update-recovery-status/', views.AuthViewSet.as_view({'post': 'update_recovery_status'}), name='update-recovery-status'),
    path('validate-recovery-key/', views.AuthViewSet.as_view({'post': 'validate_recovery_key'}), name='validate-recovery-key'),
    path('get-encrypted-vault/', views.AuthViewSet.as_view({'post': 'get_encrypted_vault'}), name='get-encrypted-vault'),
    path('reset-with-recovery-key/', views.AuthViewSet.as_view({'post': 'reset_with_recovery_key'}), name='reset-with-recovery-key'),
    # Email verification endpoint
    path('verify-email-exists/', views.AuthViewSet.as_view({'post': 'verify_email_exists'}), name='verify-email-exists'),
    # Add these new passkey URL patterns with corrected function names
    path('passkey/register/begin/', passkey_views.webauthn_begin_registration, name='register_passkey_begin'),
    path('passkey/register/complete/', passkey_views.webauthn_complete_registration, name='register_passkey_complete'),
    path('passkey/authenticate/begin/', passkey_views.webauthn_begin_authentication, name='authenticate_passkey_begin'),
    path('passkey/authenticate/complete/', passkey_views.webauthn_complete_authentication, name='authenticate_passkey_complete'),
    # Passkey management URLs
    path('passkeys/', passkey_views.list_passkeys, name='list_passkeys'),
    path('passkeys/<int:passkey_id>/', passkey_views.delete_passkey, name='delete_passkey'),
    path('passkeys/status/', passkey_views.get_passkey_status, name='passkey_status'),
    path('passkeys/<int:passkey_id>/rename/', passkey_views.rename_passkey, name='rename_passkey'),
    # OAuth URLs
    path('oauth/providers/', oauth_views.oauth_providers, name='oauth_providers'),
    path('oauth/login-url/', oauth_views.oauth_login_url, name='oauth_login_url'),
    path('oauth/google/', oauth_views.GoogleLogin.as_view(), name='google_login'),
    path('oauth/github/', oauth_views.GitHubLogin.as_view(), name='github_login'),
    path('oauth/apple/', oauth_views.AppleLogin.as_view(), name='apple_login'),
    path('oauth/callback/', oauth_views.oauth_callback, name='oauth_callback'),
    # OAuth Authy Fallback URLs
    path('oauth/fallback/authy/', oauth_views.oauth_fallback_authy, name='oauth_fallback_authy'),
    path('oauth/fallback/authy/verify/', oauth_views.verify_authy_fallback, name='verify_authy_fallback'),
    
    # ==================== OpenID Connect (OIDC) Endpoints ====================
    # OIDC Discovery & JWKS
    path('oidc/.well-known/openid-configuration', oidc_views.oidc_discovery, name='oidc_discovery'),
    path('oidc/.well-known/jwks.json', oidc_views.oidc_jwks, name='oidc_jwks'),
    # OIDC Provider Management
    path('oidc/providers/', oidc_views.oidc_providers, name='oidc_providers'),
    # OIDC Authorization Flow
    path('oidc/authorize/', oidc_views.oidc_authorize, name='oidc_authorize'),
    path('oidc/callback/', oidc_views.oidc_callback, name='oidc_callback'),
    path('oidc/token/', oidc_views.oidc_token, name='oidc_token'),
    # OIDC UserInfo & Token Validation
    path('oidc/userinfo/', oidc_views.oidc_userinfo, name='oidc_userinfo'),
    path('oidc/validate-token/', oidc_views.oidc_validate_token, name='oidc_validate_token'),
    
    # ==================== MFA Endpoints ====================
    # Biometric Registration
    path('mfa/biometric/face/register/', mfa_views.register_face, name='register_face'),
    path('mfa/biometric/voice/register/', mfa_views.register_voice, name='register_voice'),
    
    # Biometric Authentication
    path('mfa/biometric/authenticate/', mfa_views.authenticate_biometric, name='authenticate_biometric'),
    
    # Continuous Authentication
    path('mfa/continuous-auth/start/', mfa_views.start_continuous_auth, name='start_continuous_auth'),
    path('mfa/continuous-auth/update/', mfa_views.update_continuous_auth, name='update_continuous_auth'),
    
    # Adaptive MFA
    path('mfa/assess-risk/', mfa_views.assess_mfa_risk, name='assess_mfa_risk'),
    path('mfa/factors/', mfa_views.get_mfa_factors, name='get_mfa_factors'),
    path('mfa/policy/', mfa_views.mfa_policy, name='mfa_policy'),
    
    # Authentication History
    path('mfa/auth-attempts/', mfa_views.auth_attempts_history, name='auth_attempts_history'),
    
    # Integrated MFA + 2FA Verification
    path('mfa/verify/', mfa_views.verify_integrated_mfa, name='verify_integrated_mfa'),
    path('mfa/requirements/', mfa_views.get_mfa_requirements, name='get_mfa_requirements'),
    
    # ==================== Primary Passkey Recovery Endpoints ====================
    # Setup primary passkey recovery backup
    path('passkey-recovery/setup/', passkey_primary_recovery_views.setup_primary_passkey_recovery, name='setup_primary_passkey_recovery'),
    # List user's recovery backups
    path('passkey-recovery/backups/', passkey_primary_recovery_views.list_passkey_recovery_backups, name='list_passkey_recovery_backups'),
    # Initiate recovery (step 1: identify user)
    path('passkey-recovery/initiate/', passkey_primary_recovery_views.initiate_primary_passkey_recovery, name='initiate_primary_passkey_recovery'),
    # Complete recovery (step 2: decrypt with recovery key)
    path('passkey-recovery/complete/', passkey_primary_recovery_views.complete_primary_passkey_recovery, name='complete_primary_passkey_recovery'),
    # Fallback to social mesh recovery if primary fails
    path('passkey-recovery/fallback/', passkey_primary_recovery_views.fallback_to_social_mesh_recovery, name='fallback_to_social_mesh_recovery'),
    # Revoke a recovery backup
    path('passkey-recovery/backups/<int:backup_id>/revoke/', passkey_primary_recovery_views.revoke_recovery_backup, name='revoke_recovery_backup'),
    # Get overall recovery status
    path('passkey-recovery/status/', passkey_primary_recovery_views.get_recovery_status, name='get_passkey_recovery_status'),
    
    # ==================== Kyber Post-Quantum Cryptography Endpoints ====================
    # Keypair generation
    path('kyber/keypair/', kyber_views.generate_keypair_view, name='kyber_generate_keypair'),
    path('kyber/keypair/batch/', kyber_views.batch_keygen_view, name='kyber_batch_keygen'),
    path('kyber/public-key/', kyber_views.get_user_public_key, name='kyber_get_public_key'),
    path('kyber/keypair/invalidate/', kyber_views.invalidate_keypair, name='kyber_invalidate_keypair'),
    
    # Encryption/Decryption
    path('kyber/encrypt/', kyber_views.encrypt_view, name='kyber_encrypt'),
    path('kyber/decrypt/', kyber_views.decrypt_view, name='kyber_decrypt'),
    path('kyber/batch/encrypt/', kyber_views.batch_encrypt_view, name='kyber_batch_encrypt'),
    
    # Status and Metrics
    path('kyber/status/', kyber_views.get_kyber_status, name='kyber_status'),
    path('kyber/metrics/', kyber_views.get_kyber_metrics, name='kyber_metrics'),
    path('kyber/metrics/reset/', kyber_views.reset_kyber_metrics, name='kyber_reset_metrics'),
]

"""
OpenID Connect (OIDC) Service

Provides OpenID Connect integration on top of OAuth 2.0 for:
- ID Token validation and parsing
- OIDC Discovery endpoint handling
- Standard claims extraction
- Enterprise SSO provider support (Okta, Azure AD, Auth0, etc.)
- Nonce validation for replay attack protection
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.cache import cache
from jose import jwt, JWTError
from jose.constants import ALGORITHMS

logger = logging.getLogger(__name__)


class OIDCError(Exception):
    """Base exception for OIDC errors"""
    pass


class OIDCValidationError(OIDCError):
    """Raised when token validation fails"""
    pass


class OIDCProviderError(OIDCError):
    """Raised when provider communication fails"""
    pass


class OIDCProvider:
    """
    Represents an OIDC Provider configuration.
    Supports auto-discovery via .well-known/openid-configuration
    """
    
    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        discovery_url: Optional[str] = None,
        authorization_endpoint: Optional[str] = None,
        token_endpoint: Optional[str] = None,
        userinfo_endpoint: Optional[str] = None,
        jwks_uri: Optional[str] = None,
        issuer: Optional[str] = None,
        scopes: List[str] = None,
    ):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.discovery_url = discovery_url
        self._authorization_endpoint = authorization_endpoint
        self._token_endpoint = token_endpoint
        self._userinfo_endpoint = userinfo_endpoint
        self._jwks_uri = jwks_uri
        self._issuer = issuer
        self.scopes = scopes or ['openid', 'profile', 'email']
        self._config = None
        self._jwks = None
        self._jwks_last_updated = None
    
    def _load_discovery_config(self) -> Dict[str, Any]:
        """Load OIDC discovery configuration"""
        if self._config:
            return self._config
        
        cache_key = f"oidc_discovery_{self.name}"
        cached = cache.get(cache_key)
        if cached:
            self._config = cached
            return self._config
        
        if not self.discovery_url:
            raise OIDCProviderError(f"No discovery URL configured for {self.name}")
        
        try:
            response = requests.get(self.discovery_url, timeout=10)
            response.raise_for_status()
            self._config = response.json()
            # Cache for 1 hour
            cache.set(cache_key, self._config, 3600)
            logger.info(f"Loaded OIDC discovery config for {self.name}")
            return self._config
        except requests.RequestException as e:
            logger.error(f"Failed to load OIDC discovery for {self.name}: {e}")
            raise OIDCProviderError(f"Failed to load discovery config: {e}")
    
    @property
    def authorization_endpoint(self) -> str:
        if self._authorization_endpoint:
            return self._authorization_endpoint
        return self._load_discovery_config().get('authorization_endpoint', '')
    
    @property
    def token_endpoint(self) -> str:
        if self._token_endpoint:
            return self._token_endpoint
        return self._load_discovery_config().get('token_endpoint', '')
    
    @property
    def userinfo_endpoint(self) -> str:
        if self._userinfo_endpoint:
            return self._userinfo_endpoint
        return self._load_discovery_config().get('userinfo_endpoint', '')
    
    @property
    def jwks_uri(self) -> str:
        if self._jwks_uri:
            return self._jwks_uri
        return self._load_discovery_config().get('jwks_uri', '')
    
    @property
    def issuer(self) -> str:
        if self._issuer:
            return self._issuer
        return self._load_discovery_config().get('issuer', '')
    
    def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get JSON Web Key Set for token verification"""
        # Refresh JWKS every hour or on demand
        should_refresh = (
            force_refresh or
            self._jwks is None or
            self._jwks_last_updated is None or
            (datetime.utcnow() - self._jwks_last_updated) > timedelta(hours=1)
        )
        
        if not should_refresh and self._jwks:
            return self._jwks
        
        cache_key = f"oidc_jwks_{self.name}"
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached:
                self._jwks = cached
                return self._jwks
        
        try:
            response = requests.get(self.jwks_uri, timeout=10)
            response.raise_for_status()
            self._jwks = response.json()
            self._jwks_last_updated = datetime.utcnow()
            cache.set(cache_key, self._jwks, 3600)
            return self._jwks
        except requests.RequestException as e:
            logger.error(f"Failed to load JWKS for {self.name}: {e}")
            if self._jwks:
                return self._jwks  # Return stale data if available
            raise OIDCProviderError(f"Failed to load JWKS: {e}")


class OIDCService:
    """
    OpenID Connect Service for handling authentication flows.
    
    Features:
    - Multiple provider support (Google, Microsoft, Okta, Auth0, etc.)
    - ID Token validation with JWKS
    - Nonce-based replay protection
    - Standard claims extraction
    - UserInfo endpoint support
    """
    
    # Standard OIDC claims
    STANDARD_CLAIMS = [
        'sub', 'name', 'given_name', 'family_name', 'middle_name',
        'nickname', 'preferred_username', 'profile', 'picture',
        'website', 'email', 'email_verified', 'gender', 'birthdate',
        'zoneinfo', 'locale', 'phone_number', 'phone_number_verified',
        'address', 'updated_at'
    ]
    
    def __init__(self):
        self.providers: Dict[str, OIDCProvider] = {}
        self._load_providers()
    
    def _load_providers(self):
        """Load configured OIDC providers from settings"""
        oidc_config = getattr(settings, 'OIDC_PROVIDERS', {})
        
        # Add default providers if configured
        self._add_google_provider()
        self._add_microsoft_provider()
        self._add_okta_provider()
        self._add_auth0_provider()
        
        # Add custom providers from settings
        for name, config in oidc_config.items():
            if name not in self.providers:
                self.add_provider(
                    name=name,
                    client_id=config.get('client_id', ''),
                    client_secret=config.get('client_secret', ''),
                    discovery_url=config.get('discovery_url'),
                    scopes=config.get('scopes', ['openid', 'profile', 'email']),
                )
    
    def _add_google_provider(self):
        """Add Google as OIDC provider"""
        import os
        client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
        client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
        
        if client_id and client_secret:
            self.providers['google'] = OIDCProvider(
                name='google',
                client_id=client_id,
                client_secret=client_secret,
                discovery_url='https://accounts.google.com/.well-known/openid-configuration',
                scopes=['openid', 'profile', 'email'],
            )
    
    def _add_microsoft_provider(self):
        """Add Microsoft/Azure AD as OIDC provider"""
        import os
        client_id = os.environ.get('MICROSOFT_OAUTH_CLIENT_ID', '')
        client_secret = os.environ.get('MICROSOFT_OAUTH_CLIENT_SECRET', '')
        tenant_id = os.environ.get('MICROSOFT_TENANT_ID', 'common')
        
        if client_id and client_secret:
            self.providers['microsoft'] = OIDCProvider(
                name='microsoft',
                client_id=client_id,
                client_secret=client_secret,
                discovery_url=f'https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration',
                scopes=['openid', 'profile', 'email', 'User.Read'],
            )
    
    def _add_okta_provider(self):
        """Add Okta as OIDC provider"""
        import os
        client_id = os.environ.get('OKTA_OAUTH_CLIENT_ID', '')
        client_secret = os.environ.get('OKTA_OAUTH_CLIENT_SECRET', '')
        domain = os.environ.get('OKTA_DOMAIN', '')
        
        if client_id and client_secret and domain:
            self.providers['okta'] = OIDCProvider(
                name='okta',
                client_id=client_id,
                client_secret=client_secret,
                discovery_url=f'https://{domain}/.well-known/openid-configuration',
                scopes=['openid', 'profile', 'email'],
            )
    
    def _add_auth0_provider(self):
        """Add Auth0 as OIDC provider"""
        import os
        client_id = os.environ.get('AUTH0_CLIENT_ID', '')
        client_secret = os.environ.get('AUTH0_CLIENT_SECRET', '')
        domain = os.environ.get('AUTH0_DOMAIN', '')
        
        if client_id and client_secret and domain:
            self.providers['auth0'] = OIDCProvider(
                name='auth0',
                client_id=client_id,
                client_secret=client_secret,
                discovery_url=f'https://{domain}/.well-known/openid-configuration',
                scopes=['openid', 'profile', 'email'],
            )
    
    def add_provider(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        discovery_url: Optional[str] = None,
        **kwargs
    ):
        """Add a custom OIDC provider"""
        self.providers[name] = OIDCProvider(
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            discovery_url=discovery_url,
            **kwargs
        )
    
    def get_provider(self, name: str) -> Optional[OIDCProvider]:
        """Get provider by name"""
        return self.providers.get(name)
    
    def list_providers(self) -> List[Dict[str, str]]:
        """List all configured providers"""
        return [
            {
                'name': p.name,
                'client_id': p.client_id[:8] + '...' if len(p.client_id) > 8 else p.client_id,
                'scopes': p.scopes,
            }
            for p in self.providers.values()
        ]
    
    def generate_nonce(self) -> str:
        """Generate a cryptographic nonce for replay protection"""
        return secrets.token_urlsafe(32)
    
    def store_nonce(self, nonce: str, provider: str, ttl: int = 600) -> None:
        """Store nonce in cache for validation"""
        cache_key = f"oidc_nonce_{provider}_{nonce}"
        cache.set(cache_key, True, ttl)
    
    def validate_nonce(self, nonce: str, provider: str) -> bool:
        """Validate and consume nonce"""
        cache_key = f"oidc_nonce_{provider}_{nonce}"
        if cache.get(cache_key):
            cache.delete(cache_key)
            return True
        return False
    
    def generate_state(self, data: Optional[Dict] = None) -> str:
        """Generate state parameter with optional data"""
        state_data = {
            'random': secrets.token_urlsafe(16),
            'timestamp': time.time(),
            **(data or {})
        }
        return base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    def validate_state(self, state: str, max_age: int = 600) -> Optional[Dict]:
        """Validate state parameter and return embedded data"""
        try:
            data = json.loads(base64.urlsafe_b64decode(state).decode())
            if time.time() - data.get('timestamp', 0) > max_age:
                return None
            return data
        except Exception:
            return None
    
    def get_authorization_url(
        self,
        provider_name: str,
        redirect_uri: str,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        extra_params: Optional[Dict] = None,
    ) -> Tuple[str, str, str]:
        """
        Generate OIDC authorization URL.
        
        Returns:
            Tuple of (authorization_url, state, nonce)
        """
        provider = self.get_provider(provider_name)
        if not provider:
            raise OIDCError(f"Unknown provider: {provider_name}")
        
        state = state or self.generate_state({'provider': provider_name})
        nonce = nonce or self.generate_nonce()
        
        # Store nonce for later validation
        self.store_nonce(nonce, provider_name)
        
        params = {
            'client_id': provider.client_id,
            'response_type': 'code',
            'scope': ' '.join(provider.scopes),
            'redirect_uri': redirect_uri,
            'state': state,
            'nonce': nonce,
            **(extra_params or {})
        }
        
        auth_url = f"{provider.authorization_endpoint}?{urlencode(params)}"
        return auth_url, state, nonce
    
    def exchange_code_for_tokens(
        self,
        provider_name: str,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Returns:
            Dict containing access_token, id_token, refresh_token (if available)
        """
        provider = self.get_provider(provider_name)
        if not provider:
            raise OIDCError(f"Unknown provider: {provider_name}")
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': provider.client_id,
            'client_secret': provider.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
        }
        
        try:
            response = requests.post(
                provider.token_endpoint,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Token exchange failed for {provider_name}: {e}")
            raise OIDCProviderError(f"Token exchange failed: {e}")
    
    def validate_id_token(
        self,
        provider_name: str,
        id_token: str,
        nonce: Optional[str] = None,
        validate_nonce: bool = True,
    ) -> Dict[str, Any]:
        """
        Validate and decode ID token.
        
        Args:
            provider_name: Name of the OIDC provider
            id_token: The ID token to validate
            nonce: Expected nonce (if validating)
            validate_nonce: Whether to validate nonce
        
        Returns:
            Decoded token claims
        
        Raises:
            OIDCValidationError: If validation fails
        """
        provider = self.get_provider(provider_name)
        if not provider:
            raise OIDCError(f"Unknown provider: {provider_name}")
        
        try:
            # Get JWKS for signature verification
            jwks = provider.get_jwks()
            
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get('kid')
            
            # Find the matching key
            rsa_key = None
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    rsa_key = {
                        'kty': key['kty'],
                        'kid': key['kid'],
                        'use': key.get('use', 'sig'),
                        'n': key['n'],
                        'e': key['e'],
                    }
                    break
            
            if not rsa_key:
                # Try refreshing JWKS
                jwks = provider.get_jwks(force_refresh=True)
                for key in jwks.get('keys', []):
                    if key.get('kid') == kid:
                        rsa_key = {
                            'kty': key['kty'],
                            'kid': key['kid'],
                            'use': key.get('use', 'sig'),
                            'n': key['n'],
                            'e': key['e'],
                        }
                        break
            
            if not rsa_key:
                raise OIDCValidationError(f"Unable to find matching key for kid: {kid}")
            
            # Verify and decode token
            claims = jwt.decode(
                id_token,
                rsa_key,
                algorithms=['RS256', 'RS384', 'RS512'],
                audience=provider.client_id,
                issuer=provider.issuer,
            )
            
            # Validate nonce if required
            if validate_nonce:
                token_nonce = claims.get('nonce')
                if not token_nonce:
                    raise OIDCValidationError("ID token missing nonce claim")
                
                if nonce and token_nonce != nonce:
                    raise OIDCValidationError("Nonce mismatch")
                
                if not self.validate_nonce(token_nonce, provider_name):
                    raise OIDCValidationError("Nonce validation failed (expired or already used)")
            
            return claims
            
        except JWTError as e:
            logger.error(f"ID token validation failed: {e}")
            raise OIDCValidationError(f"ID token validation failed: {e}")
    
    def get_userinfo(
        self,
        provider_name: str,
        access_token: str,
    ) -> Dict[str, Any]:
        """
        Get user information from OIDC UserInfo endpoint.
        
        Args:
            provider_name: Name of the OIDC provider
            access_token: Access token for authentication
        
        Returns:
            UserInfo claims
        """
        provider = self.get_provider(provider_name)
        if not provider:
            raise OIDCError(f"Unknown provider: {provider_name}")
        
        if not provider.userinfo_endpoint:
            raise OIDCProviderError(f"Provider {provider_name} does not have userinfo endpoint")
        
        try:
            response = requests.get(
                provider.userinfo_endpoint,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"UserInfo request failed for {provider_name}: {e}")
            raise OIDCProviderError(f"UserInfo request failed: {e}")
    
    def extract_user_info(self, claims: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract standardized user information from ID token claims.
        
        Returns:
            Dict with standardized user fields
        """
        return {
            'sub': claims.get('sub'),  # Unique identifier
            'email': claims.get('email'),
            'email_verified': claims.get('email_verified', False),
            'name': claims.get('name'),
            'given_name': claims.get('given_name'),
            'family_name': claims.get('family_name'),
            'picture': claims.get('picture'),
            'locale': claims.get('locale'),
            'provider_claims': {k: v for k, v in claims.items() if k in self.STANDARD_CLAIMS},
        }


# Singleton instance
oidc_service = OIDCService()


def get_oidc_service() -> OIDCService:
    """Get the OIDC service singleton"""
    return oidc_service


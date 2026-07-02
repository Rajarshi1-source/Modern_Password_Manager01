"""
Custom middleware for WebSocket authentication
"""

from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
import logging

from .ws_ticket import consume_ticket

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using Django REST Token
    Supports both JWT and Token authentication
    """
    
    async def __call__(self, scope, receive, send):
        # Prefer a short-lived, single-use ticket (?ticket=) so the long-lived
        # auth token never appears in the ws:// URL (and therefore not in access
        # logs or browser history). Fall back to ?token= for backward-compatible
        # migration of clients that haven't switched yet.
        #
        # parse_qs handles URL-decoding and values containing '=' correctly
        # (the old ``param.split('=')[1]`` truncated such tokens).
        params = parse_qs(scope.get('query_string', b'').decode())
        ticket = params.get('ticket', [None])[0]
        token = params.get('token', [None])[0]

        if ticket:
            scope['user'] = await self.get_user_from_ticket(ticket)
        elif token:
            scope['user'] = await self.get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
            logger.warning("WebSocket connection attempt without ticket or token")

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_ticket(self, ticket):
        """Resolve a single-use WS ticket to its user, consuming it."""
        user_id = consume_ticket(ticket)
        if user_id is None:
            logger.warning("WebSocket ticket invalid, expired, or already used")
            return AnonymousUser()
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Validate token and return user"""
        try:
            # Try Django REST Framework Token first
            token_obj = Token.objects.select_related('user').get(key=token)
            logger.info(f"Authenticated user {token_obj.user.id} via Token")
            return token_obj.user
            
        except Token.DoesNotExist:
            # Try JWT token as fallback
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id)
                logger.info(f"Authenticated user {user.id} via JWT")
                return user
                
            except Exception as jwt_error:
                logger.error(f"JWT authentication failed: {jwt_error}")
                return AnonymousUser()
                
        except Exception as e:
            logger.error(f"Token authentication failed: {e}")
            return AnonymousUser()


# Factory function for use in routing
def TokenAuthMiddlewareStack(inner):
    """
    Convenience function for wrapping routing in TokenAuthMiddleware
    """
    return TokenAuthMiddleware(inner)


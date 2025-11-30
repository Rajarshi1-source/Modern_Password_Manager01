"""
Custom middleware for WebSocket authentication
"""

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using Django REST Token
    Supports both JWT and Token authentication
    """
    
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        token = None
        
        # Parse query string for token
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=')[1]
                break
        
        if token:
            scope['user'] = await self.get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
            logger.warning("WebSocket connection attempt without token")
        
        return await super().__call__(scope, receive, send)
    
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


# from authy.api import AuthyApiClient  # Commented out - install authy package if needed
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class AuthyService:
    """Service for interacting with Authy API for 2FA"""
    
    def __init__(self):
        # self.client = AuthyApiClient(settings.AUTHY_API_KEY)  # Commented out - install authy package if needed
        self.client = None  # Placeholder
    
    def register_user(self, email, phone, country_code='1'):
        """
        Register a user with Authy
        
        Args:
            email (str): User's email address
            phone (str): User's phone number
            country_code (str): Phone country code
            
        Returns:
            str: Authy ID for the user if successful, None otherwise
        """
        try:
            user = self.client.users.create(
                email=email,
                phone=phone,
                country_code=country_code
            )
            
            if user.ok():
                return user.id
            else:
                logger.error(f"Authy user creation failed: {user.errors()}")
                return None
        except Exception as e:
            logger.error(f"Error registering user with Authy: {str(e)}")
            return None
    
    def verify_token(self, authy_id, token):
        """
        Verify a TOTP token
        
        Args:
            authy_id (str): User's Authy ID
            token (str): Token to verify
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            verification = self.client.tokens.verify(authy_id, token=token)
            return verification.ok()
        except Exception as e:
            logger.error(f"Error verifying Authy token: {str(e)}")
            return False
    
    def send_approval_request(self, authy_id, message):
        """
        Send a push authentication request
        
        Args:
            authy_id (str): User's Authy ID
            message (str): Message to display in the push notification
            
        Returns:
            str: UUID of the approval request if successful, None otherwise
        """
        try:
            details = {
                'IP Address': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'Unknown',
                'Location': 'Password Manager App',
                'Time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            response = self.client.one_touch.send_request(
                authy_id,
                message=message,
                details=details,
                seconds_to_expire=120
            )
            
            if response.ok():
                return response.get_uuid()
            else:
                logger.error(f"Authy push request failed: {response.errors()}")
                return None
        except Exception as e:
            logger.error(f"Error sending Authy push request: {str(e)}")
            return None
    
    def check_approval_status(self, uuid):
        """
        Check the status of a push authentication request
        
        Args:
            uuid (str): UUID of the approval request
            
        Returns:
            str: Status of the request ('approved', 'pending', 'denied', or 'expired')
        """
        try:
            response = self.client.one_touch.get_approval_status(uuid)
            
            if response.ok():
                return response['approval_request']['status']
            else:
                logger.error(f"Authy status check failed: {response.errors()}")
                return None
        except Exception as e:
            logger.error(f"Error checking Authy approval status: {str(e)}")
            return None
    
    def delete_user(self, authy_id):
        """
        Delete a user from Authy
        
        Args:
            authy_id (str): User's Authy ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = self.client.users.delete(authy_id)
            return response.ok()
        except Exception as e:
            logger.error(f"Error deleting Authy user: {str(e)}")
            return False

# Initialize as singleton
authy_service = AuthyService()

"""
SimpleLogin API Integration

Provides email masking through SimpleLogin service
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SimpleLoginService:
    """Service for interacting with SimpleLogin API"""
    
    BASE_URL = "https://app.simplelogin.io/api"
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authentication": api_key,
            "Content-Type": "application/json"
        }
    
    def create_alias(self, note=None, mailbox_id=None):
        """
        Create a new random alias
        
        Args:
            note: Optional note for the alias
            mailbox_id: ID of mailbox to forward to (default mailbox if not specified)
        
        Returns:
            dict: Alias information including email address
        """
        try:
            endpoint = f"{self.BASE_URL}/alias/random/new"
            data = {}
            
            if note:
                data['note'] = note
            if mailbox_id:
                data['mailbox_id'] = mailbox_id
            
            response = requests.post(endpoint, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error creating alias: {e}")
            raise Exception(f"Failed to create alias: {str(e)}")
    
    def get_aliases(self, page=0):
        """
        Get list of aliases
        
        Args:
            page: Page number (0-indexed)
        
        Returns:
            dict: List of aliases and metadata
        """
        try:
            endpoint = f"{self.BASE_URL}/v2/aliases"
            params = {'page_id': page}
            
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error fetching aliases: {e}")
            raise Exception(f"Failed to fetch aliases: {str(e)}")
    
    def get_alias(self, alias_id):
        """
        Get specific alias details
        
        Args:
            alias_id: ID of the alias
        
        Returns:
            dict: Alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error fetching alias {alias_id}: {e}")
            raise Exception(f"Failed to fetch alias: {str(e)}")
    
    def update_alias(self, alias_id, note=None, enabled=None):
        """
        Update alias settings
        
        Args:
            alias_id: ID of the alias
            note: New note for the alias
            enabled: Enable/disable the alias
        
        Returns:
            dict: Updated alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            data = {}
            
            if note is not None:
                data['note'] = note
            if enabled is not None:
                data['enabled'] = enabled
            
            response = requests.patch(endpoint, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error updating alias {alias_id}: {e}")
            raise Exception(f"Failed to update alias: {str(e)}")
    
    def delete_alias(self, alias_id):
        """
        Delete an alias
        
        Args:
            alias_id: ID of the alias to delete
        
        Returns:
            bool: True if successful
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error deleting alias {alias_id}: {e}")
            raise Exception(f"Failed to delete alias: {str(e)}")
    
    def toggle_alias(self, alias_id):
        """
        Toggle alias enabled/disabled status
        
        Args:
            alias_id: ID of the alias
        
        Returns:
            dict: Updated alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}/toggle"
            
            response = requests.post(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error toggling alias {alias_id}: {e}")
            raise Exception(f"Failed to toggle alias: {str(e)}")
    
    def get_alias_activities(self, alias_id, page=0):
        """
        Get activity log for an alias
        
        Args:
            alias_id: ID of the alias
            page: Page number
        
        Returns:
            dict: Activity log entries
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}/activities"
            params = {'page_id': page}
            
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error fetching activities for alias {alias_id}: {e}")
            raise Exception(f"Failed to fetch alias activities: {str(e)}")
    
    def get_user_info(self):
        """
        Get user information and stats
        
        Returns:
            dict: User information including quota and stats
        """
        try:
            endpoint = f"{self.BASE_URL}/user_info"
            
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"SimpleLogin API error fetching user info: {e}")
            raise Exception(f"Failed to fetch user info: {str(e)}")


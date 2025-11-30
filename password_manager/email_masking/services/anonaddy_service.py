"""
AnonAddy API Integration

Provides email masking through AnonAddy (addy.io) service
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AnonAddyService:
    """Service for interacting with AnonAddy API"""
    
    BASE_URL = "https://app.addy.io/api/v1"
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }
    
    def create_alias(self, description=None, domain=None, format=None):
        """
        Create a new alias
        
        Args:
            description: Optional description for the alias
            domain: Domain to use (default domain if not specified)
            format: Alias format ('random', 'uuid', or 'custom')
        
        Returns:
            dict: Alias information including email address
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases"
            data = {}
            
            if description:
                data['description'] = description
            if domain:
                data['domain'] = domain
            if format:
                data['format'] = format
            
            response = requests.post(endpoint, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error creating alias: {e}")
            raise Exception(f"Failed to create alias: {str(e)}")
    
    def get_aliases(self, page=1):
        """
        Get list of aliases
        
        Args:
            page: Page number (1-indexed)
        
        Returns:
            dict: List of aliases and metadata
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases"
            params = {'page': page}
            
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error fetching aliases: {e}")
            raise Exception(f"Failed to fetch aliases: {str(e)}")
    
    def get_alias(self, alias_id):
        """
        Get specific alias details
        
        Args:
            alias_id: UUID of the alias
        
        Returns:
            dict: Alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error fetching alias {alias_id}: {e}")
            raise Exception(f"Failed to fetch alias: {str(e)}")
    
    def update_alias(self, alias_id, description=None, active=None):
        """
        Update alias settings
        
        Args:
            alias_id: UUID of the alias
            description: New description
            active: Enable/disable the alias
        
        Returns:
            dict: Updated alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            data = {}
            
            if description is not None:
                data['description'] = description
            if active is not None:
                data['active'] = active
            
            response = requests.patch(endpoint, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error updating alias {alias_id}: {e}")
            raise Exception(f"Failed to update alias: {str(e)}")
    
    def delete_alias(self, alias_id):
        """
        Delete an alias
        
        Args:
            alias_id: UUID of the alias to delete
        
        Returns:
            bool: True if successful
        """
        try:
            endpoint = f"{self.BASE_URL}/aliases/{alias_id}"
            
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error deleting alias {alias_id}: {e}")
            raise Exception(f"Failed to delete alias: {str(e)}")
    
    def activate_alias(self, alias_id):
        """
        Activate a specific alias
        
        Args:
            alias_id: UUID of the alias
        
        Returns:
            dict: Updated alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/active-aliases"
            data = {'id': alias_id}
            
            response = requests.post(endpoint, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error activating alias {alias_id}: {e}")
            raise Exception(f"Failed to activate alias: {str(e)}")
    
    def deactivate_alias(self, alias_id):
        """
        Deactivate a specific alias
        
        Args:
            alias_id: UUID of the alias
        
        Returns:
            dict: Updated alias information
        """
        try:
            endpoint = f"{self.BASE_URL}/active-aliases/{alias_id}"
            
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error deactivating alias {alias_id}: {e}")
            raise Exception(f"Failed to deactivate alias: {str(e)}")
    
    def get_account_details(self):
        """
        Get account information and stats
        
        Returns:
            dict: Account information including bandwidth and alias limits
        """
        try:
            endpoint = f"{self.BASE_URL}/account-details"
            
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"AnonAddy API error fetching account details: {e}")
            raise Exception(f"Failed to fetch account details: {str(e)}")


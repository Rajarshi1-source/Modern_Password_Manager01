from google.cloud import storage
from django.conf import settings
import os
import json
import tempfile
import uuid
import sys

# Handle the cgi module removal in Python 3.13
def patch_cgi_module():
    """
    Patch for Python 3.13+ where cgi module has been removed.
    This function adds legacy-cgi as a replacement for the built-in cgi module.
    """
    if sys.version_info >= (3, 13):
        try:
            import legacy_cgi
            sys.modules['cgi'] = legacy_cgi
            return True
        except ImportError:
            print("Warning: legacy-cgi package not found. Install with: pip install legacy-cgi")
            return False
    return True  # No patch needed for Python < 3.13

class CloudStorageService:
    """Service for handling cloud storage operations"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = settings.CLOUD_STORAGE_BUCKET
        
        # Apply the cgi module patch before initializing the storage client
        patch_cgi_module()
        
        self.initialize()
    
    def initialize(self):
        """Initialize storage client"""
        try:
            if settings.GOOGLE_CLOUD_CREDENTIALS:
                # Create a temporary file for the credentials
                fd, path = tempfile.mkstemp()
                with os.fdopen(fd, 'w') as tmp:
                    json.dump(settings.GOOGLE_CLOUD_CREDENTIALS, tmp)
                
                # Initialize client with credentials file
                self.client = storage.Client.from_service_account_json(path)
                os.remove(path)  # Clean up temp file
            else:
                # Use default credentials
                self.client = storage.Client()
        except Exception as e:
            print(f"Error initializing cloud storage: {e}")
    
    def upload_backup(self, user_id, backup_data, backup_id=None):
        """Upload a backup to cloud storage"""
        if not self.client:
            return None
            
        try:
            bucket = self.client.bucket(self.bucket_name)
            backup_id = backup_id or str(uuid.uuid4())
            blob_name = f"backups/{user_id}/{backup_id}"
            blob = bucket.blob(blob_name)
            
            # Upload the encrypted backup data
            blob.upload_from_string(backup_data)
            
            return blob_name
        except Exception as e:
            print(f"Error uploading backup: {e}")
            return None
    
    def download_backup(self, cloud_path):
        """Download a backup from cloud storage"""
        if not self.client:
            return None
            
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(cloud_path)
            
            # Download the encrypted backup data
            return blob.download_as_string()
        except Exception as e:
            print(f"Error downloading backup: {e}")
            return None
    
    def delete_backup(self, cloud_path):
        """Delete a backup from cloud storage"""
        if not self.client:
            return False
            
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(cloud_path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting backup: {e}")
            return False

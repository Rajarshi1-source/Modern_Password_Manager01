from google.cloud import storage
from django.conf import settings
import os
import json
import tempfile
import uuid
import sys
import logging
from datetime import timedelta
from typing import Optional

logger = logging.getLogger(__name__)

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
    """Service for handling cloud storage operations (GCS and S3)."""

    def __init__(self):
        self.client = None
        self.bucket_name = getattr(settings, 'CLOUD_STORAGE_BUCKET', '') or ''
        self._s3_client = None
        self._s3_bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or ''

        patch_cgi_module()

        self._init_gcs()
        self._init_s3()

    def _init_gcs(self):
        """Initialize Google Cloud Storage client when configured."""
        if not self.bucket_name:
            return
        try:
            creds = getattr(settings, 'GOOGLE_CLOUD_CREDENTIALS', None)
            if creds:
                fd, path = tempfile.mkstemp()
                with os.fdopen(fd, 'w') as tmp:
                    json.dump(creds, tmp)
                self.client = storage.Client.from_service_account_json(path)
                os.remove(path)
            else:
                self.client = storage.Client()
        except Exception as e:
            logger.warning("GCS client init failed: %s", e)
            self.client = None

    def _init_s3(self):
        """Initialize boto3 S3 client when bucket and credentials are set."""
        if not self._s3_bucket_name:
            return
        key_id = getattr(settings, 'AWS_ACCESS_KEY_ID', '') or ''
        secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '') or ''
        if not key_id or not secret:
            logger.warning("AWS_STORAGE_BUCKET_NAME set but missing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY")
            return
        try:
            import boto3
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=key_id,
                aws_secret_access_key=secret,
            )
        except Exception as e:
            logger.warning("S3 client init failed: %s", e)
            self._s3_client = None

    def initialize(self):
        """Backward-compatible no-op; clients are initialized in __init__."""
        pass

    @property
    def supports_presigned_urls(self) -> bool:
        """True if presigned URL generation is available (valet-key pattern)."""
        return bool(
            (self.client and self.bucket_name)
            or (self._s3_client and self._s3_bucket_name)
        )

    def _ttl_seconds(self) -> int:
        return int(getattr(settings, 'PRESIGNED_URL_TTL_SECONDS', 900))

    def generate_presigned_put_url(
        self,
        cloud_path: str,
        content_type: str = 'application/octet-stream',
        ttl_seconds: Optional[int] = None,
    ):
        """
        Scoped upload URL so the client sends bytes directly to object storage
        (valet key / constrained privilege). Path should match backups/{user_id}/{id}.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds()
        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(cloud_path)
                url = blob.generate_signed_url(
                    version='v4',
                    expiration=timedelta(seconds=ttl),
                    method='PUT',
                    content_type=content_type,
                )
                return {'url': url, 'backend': 'gcs', 'expires_in': ttl}
            except Exception as e:
                logger.error("GCS presigned PUT failed: %s", e)
                return None
        if self._s3_client and self._s3_bucket_name:
            try:
                url = self._s3_client.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': self._s3_bucket_name,
                        'Key': cloud_path,
                        'ContentType': content_type,
                    },
                    ExpiresIn=ttl,
                )
                return {'url': url, 'backend': 's3', 'expires_in': ttl}
            except Exception as e:
                logger.error("S3 presigned PUT failed: %s", e)
                return None
        return None

    def generate_presigned_get_url(self, cloud_path: str, ttl_seconds: Optional[int] = None):
        """Short-lived download URL for an existing object."""
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds()
        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(cloud_path)
                url = blob.generate_signed_url(
                    version='v4',
                    expiration=timedelta(seconds=ttl),
                    method='GET',
                )
                return {'url': url, 'backend': 'gcs', 'expires_in': ttl}
            except Exception as e:
                logger.error("GCS presigned GET failed: %s", e)
                return None
        if self._s3_client and self._s3_bucket_name:
            try:
                url = self._s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self._s3_bucket_name, 'Key': cloud_path},
                    ExpiresIn=ttl,
                )
                return {'url': url, 'backend': 's3', 'expires_in': ttl}
            except Exception as e:
                logger.error("S3 presigned GET failed: %s", e)
                return None
        return None

    def upload_backup(self, user_id, backup_data, backup_id=None):
        """Upload a backup to cloud storage"""
        if not self.client and not self._s3_client:
            return None

        backup_id = backup_id or str(uuid.uuid4())
        blob_name = f"backups/{user_id}/{backup_id}"

        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(blob_name)
                payload = backup_data if isinstance(backup_data, bytes) else str(backup_data).encode('utf-8')
                blob.upload_from_string(payload)
                return blob_name
            except Exception as e:
                logger.error("GCS upload failed: %s", e)
                return None

        if self._s3_client and self._s3_bucket_name:
            try:
                body = backup_data if isinstance(backup_data, bytes) else str(backup_data).encode('utf-8')
                self._s3_client.put_object(
                    Bucket=self._s3_bucket_name,
                    Key=blob_name,
                    Body=body,
                    ServerSideEncryption='AES256',
                )
                return blob_name
            except Exception as e:
                logger.error("S3 upload failed: %s", e)
                return None

        return None

    def download_backup(self, cloud_path):
        """Download a backup from cloud storage"""
        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(cloud_path)
                return blob.download_as_bytes()
            except Exception as e:
                logger.error("GCS download failed: %s", e)
                return None

        if self._s3_client and self._s3_bucket_name:
            try:
                resp = self._s3_client.get_object(
                    Bucket=self._s3_bucket_name,
                    Key=cloud_path,
                )
                return resp['Body'].read()
            except Exception as e:
                logger.error("S3 download failed: %s", e)
                return None

        return None

    def delete_backup(self, cloud_path):
        """Delete a backup from cloud storage"""
        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(cloud_path)
                blob.delete()
                return True
            except Exception as e:
                logger.error("GCS delete failed: %s", e)
                return False

        if self._s3_client and self._s3_bucket_name:
            try:
                self._s3_client.delete_object(Bucket=self._s3_bucket_name, Key=cloud_path)
                return True
            except Exception as e:
                logger.error("S3 delete failed: %s", e)
                return False

        return False

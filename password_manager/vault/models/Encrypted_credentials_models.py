from django.db import models
from django.contrib.auth.models import User
from cryptography.fernet import Fernet
import base64
import os

class EncryptionKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    key = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    @classmethod
    def generate_key(cls, user):
        key = Fernet.generate_key()
        encryption_key = cls(user=user, key=key)
        encryption_key.save()
        return encryption_key

# VaultItem model removed - consolidated into EncryptedVaultItem in vault_models.py

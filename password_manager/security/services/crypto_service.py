from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.ciphers.modes import GCM
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
import json
import logging

logger = logging.getLogger(__name__)

class CryptoService:
    """
    Cryptographic service for security operations
    Used for breach monitoring, password analysis, and other security features
    Maintains zero-knowledge principles where possible
    """
    
    @staticmethod
    def encrypt_data(plaintext, user_id=None):
        """
        Encrypt data for storage using a derived key
        
        Args:
            plaintext (str): Data to encrypt
            user_id: Optional user ID for user-specific encryption
        
        Returns:
            str: Base64-encoded encrypted data with nonce and tag
        """
        try:
            # Generate a random key or derive from environment
            from django.conf import settings
            secret_key = settings.SECRET_KEY.encode('utf-8')[:32]  # Use first 32 bytes
            
            # Generate random nonce
            nonce = os.urandom(12)
            
            # Encrypt
            ciphertext, tag = CryptoService.encrypt_aes_gcm(
                secret_key, nonce, plaintext.encode('utf-8')
            )
            
            if ciphertext is None:
                return None
            
            # Combine nonce, ciphertext, and tag
            encrypted_data = nonce + ciphertext + tag
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f'Data encryption failed: {e}')
            return None
    
    @staticmethod
    def decrypt_data(encrypted_data, user_id=None):
        """
        Decrypt encrypted data
        
        Args:
            encrypted_data (str): Base64-encoded encrypted data
            user_id: Optional user ID for user-specific decryption
        
        Returns:
            str: Decrypted plaintext or None if decryption failed
        """
        try:
            from django.conf import settings
            secret_key = settings.SECRET_KEY.encode('utf-8')[:32]
            
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # Extract nonce (12 bytes), ciphertext, and tag (16 bytes)
            nonce = encrypted_bytes[:12]
            tag = encrypted_bytes[-16:]
            ciphertext = encrypted_bytes[12:-16]
            
            # Decrypt
            decrypted_data = CryptoService.decrypt_aes_gcm(
                secret_key, nonce, ciphertext, tag
            )
            
            if decrypted_data is None:
                return None
            
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f'Data decryption failed: {e}')
            return None
    
    @staticmethod
    def decrypt_aes_gcm(key, nonce, ciphertext, tag):
        """
        Decrypt data using AES-GCM encryption
        
        Args:
            key (bytes): Encryption key (32 bytes for AES-256)
            nonce (bytes): Nonce/IV used for encryption
            ciphertext (bytes): Encrypted data
            tag (bytes): Authentication tag
            
        Returns:
            bytes: Decrypted data or None if decryption failed
        """
        try:
            cipher = Cipher(algorithms.AES(key), mode=GCM(nonce, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(ciphertext)
            decryptor.finalize()
            return decrypted_data
        except Exception as e:
            logger.error(f'AES-GCM decryption failed: {e}')
            return None
    
    @staticmethod
    def encrypt_aes_gcm(key, nonce, plaintext):
        """
        Encrypt data using AES-GCM encryption
        
        Args:
            key (bytes): Encryption key (32 bytes for AES-256)
            nonce (bytes): Nonce/IV for encryption
            plaintext (bytes): Data to encrypt
            
        Returns:
            tuple: (ciphertext, tag) or (None, None) if encryption failed
        """
        try:
            cipher = Cipher(algorithms.AES(key), mode=GCM(nonce), backend=default_backend())
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(plaintext)
            encryptor.finalize()
            return ciphertext, encryptor.tag
        except Exception as e:
            logger.error(f'AES-GCM encryption failed: {e}')
            return None, None
    
    @staticmethod
    def derive_key_from_password(password, salt, iterations=600000):
        """
        Derive encryption key from password using PBKDF2
        
        Args:
            password (str): Master password
            salt (bytes): Salt for key derivation
            iterations (int): Number of PBKDF2 iterations
            
        Returns:
            bytes: Derived key (32 bytes for AES-256)
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            return kdf.derive(password.encode('utf-8'))
        except Exception as e:
            logger.error(f'Key derivation failed: {e}')
            return None
    
    @staticmethod
    def parse_encrypted_vault_item(encrypted_data):
        """
        Parse encrypted vault item data to extract components for decryption
        
        Args:
            encrypted_data (str): Base64-encoded encrypted data with metadata
            
        Returns:
            dict: Parsed components or None if parsing failed
        """
        try:
            # Try to parse as JSON first (new format)
            try:
                data = json.loads(base64.b64decode(encrypted_data))
                
                # Check if it's WebCrypto format with version info
                if 'version' in data and data['version'] == 'webcrypto-1':
                    return {
                        'format': 'webcrypto',
                        'iv': base64.b64decode(data['iv']),
                        'ciphertext': base64.b64decode(data['data']),
                        'version': data['version']
                    }
                
                # Standard format with IV and data
                if 'iv' in data and 'data' in data:
                    return {
                        'format': 'standard',
                        'iv': base64.b64decode(data['iv']),
                        'ciphertext': base64.b64decode(data['data']),
                        'compressed': data.get('compressed', False)
                    }
            
            except (json.JSONDecodeError, KeyError):
                # Fall back to legacy format
                logger.warning('Could not parse as JSON, treating as legacy format')
                return {
                    'format': 'legacy',
                    'ciphertext': base64.b64decode(encrypted_data)
                }
                
        except Exception as e:
            logger.error(f'Failed to parse encrypted vault item: {e}')
            return None
    
    @staticmethod
    def decrypt_vault_item_for_security_scan(encrypted_data, user_key):
        """
        Decrypt a vault item specifically for security scanning purposes
        This should only be used for security operations like breach checking
        
        Args:
            encrypted_data (str): Encrypted vault item data
            user_key (bytes): User's derived encryption key
            
        Returns:
            dict: Decrypted vault item data or None if decryption failed
        """
        try:
            parsed = CryptoService.parse_encrypted_vault_item(encrypted_data)
            if not parsed:
                return None
            
            # Handle different encryption formats
            if parsed['format'] == 'webcrypto':
                # For WebCrypto AES-GCM format, we need to split the IV and tag
                # The IV is typically the first 12 bytes, but this depends on implementation
                iv = parsed['iv'][:12]  # GCM typically uses 12-byte IV
                tag = parsed['iv'][12:] if len(parsed['iv']) > 12 else b''  # Extract tag if present
                
                # Try to decrypt with AES-GCM
                decrypted = CryptoService.decrypt_aes_gcm(
                    user_key, iv, parsed['ciphertext'], tag
                )
                
                if decrypted:
                    return json.loads(decrypted.decode('utf-8'))
            
            elif parsed['format'] == 'standard':
                # Handle standard format (likely AES-CBC from CryptoJS)
                # This would need to be implemented based on your current encryption method
                logger.warning('Standard format decryption not implemented yet')
                return None
            
            elif parsed['format'] == 'legacy':
                # Handle legacy format
                logger.warning('Legacy format decryption not implemented yet')
                return None
            
        except Exception as e:
            logger.error(f'Failed to decrypt vault item for security scan: {e}')
            return None
        
        return None
    
    @staticmethod
    def generate_secure_random(length=32):
        """
        Generate cryptographically secure random bytes
        
        Args:
            length (int): Number of bytes to generate
            
        Returns:
            bytes: Random bytes
        """
        return os.urandom(length) 
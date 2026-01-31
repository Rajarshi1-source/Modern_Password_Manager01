"""
Decoy Vault Service

Generates convincing fake credential data for duress scenarios.
Creates realistic but harmless decoy vaults that mirror user's vault structure.
"""

import logging
import random
import string
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


# Common website domains for realistic fake entries
COMMON_DOMAINS = [
    'gmail.com', 'outlook.com', 'yahoo.com', 'amazon.com', 'netflix.com',
    'facebook.com', 'twitter.com', 'linkedin.com', 'github.com', 'apple.com',
    'microsoft.com', 'google.com', 'dropbox.com', 'slack.com', 'zoom.us',
    'paypal.com', 'ebay.com', 'spotify.com', 'adobe.com', 'salesforce.com',
]

# Folder names that look realistic
COMMON_FOLDERS = [
    'Personal', 'Work', 'Social Media', 'Shopping', 'Finance',
    'Entertainment', 'Travel', 'Health', 'Education', 'Utilities',
]

# Credit card types for decoy cards
CARD_TYPES = ['Visa', 'Mastercard', 'American Express', 'Discover']


class DecoyVaultService:
    """
    Service for generating realistic decoy vault data.
    
    Features:
    - AI-inspired fake data generation
    - Mirrors user's actual vault structure
    - Includes aging/timestamp realism
    - Injects optional tracking tokens in decoy credentials
    """
    
    def __init__(self):
        """Initialize the decoy vault service"""
        self.tracking_enabled = True
    
    def generate_realistic_decoy(
        self,
        user: User,
        threat_level: str
    ) -> Dict[str, Any]:
        """
        Generate a realistic decoy vault for the given threat level.
        
        Args:
            user: The user to generate decoy for
            threat_level: Determines how many items to include
            
        Returns:
            Dict with 'items', 'folders', and 'realism_score'
        """
        logger.info(f"Generating decoy vault for {user.username} ({threat_level})")
        
        # Determine item counts based on threat level
        item_counts = {
            'low': {'passwords': 5, 'cards': 1, 'identities': 0, 'notes': 1},
            'medium': {'passwords': 15, 'cards': 2, 'identities': 1, 'notes': 3},
            'high': {'passwords': 30, 'cards': 3, 'identities': 2, 'notes': 5},
            'critical': {'passwords': 50, 'cards': 5, 'identities': 3, 'notes': 8},
        }
        
        counts = item_counts.get(threat_level, item_counts['medium'])
        
        # Try to mirror real vault structure if available
        real_structure = self._get_real_vault_structure(user)
        
        # Generate folders
        folders = self._generate_folders(real_structure)
        
        # Generate items
        items = []
        
        # Passwords
        items.extend(self._generate_password_entries(
            user, counts['passwords'], folders
        ))
        
        # Payment cards
        items.extend(self._generate_card_entries(
            user, counts['cards']
        ))
        
        # Identities
        items.extend(self._generate_identity_entries(
            user, counts['identities']
        ))
        
        # Secure notes
        items.extend(self._generate_note_entries(
            user, counts['notes'], folders
        ))
        
        # Calculate realism score
        realism_score = self._calculate_realism_score(items, folders, real_structure)
        
        return {
            'items': items,
            'folders': folders,
            'realism_score': realism_score,
            'generated_at': timezone.now().isoformat(),
        }
    
    def _get_real_vault_structure(self, user: User) -> Dict[str, Any]:
        """Get structure info from user's real vault (without actual data)"""
        try:
            from vault.models.vault_models import EncryptedVaultItem
            from vault.models.folder_models import VaultFolder
            
            real_item_count = EncryptedVaultItem.objects.filter(
                user=user, deleted=False
            ).count()
            
            real_folders = list(VaultFolder.objects.filter(user=user).values_list('name', flat=True))
            
            item_types = {}
            for item_type in ['password', 'card', 'identity', 'note']:
                item_types[item_type] = EncryptedVaultItem.objects.filter(
                    user=user, item_type=item_type, deleted=False
                ).count()
            
            return {
                'item_count': real_item_count,
                'folders': real_folders,
                'item_types': item_types,
            }
        except Exception as e:
            logger.debug(f"Could not get real vault structure: {e}")
            return {'item_count': 0, 'folders': [], 'item_types': {}}
    
    def _generate_folders(
        self,
        real_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate folder structure, mirroring real if available"""
        folders = []
        
        # Use real folders if available, otherwise use common folders
        folder_names = real_structure.get('folders', [])
        if not folder_names:
            folder_names = random.sample(COMMON_FOLDERS, min(5, len(COMMON_FOLDERS)))
        
        for name in folder_names:
            folders.append({
                'id': str(uuid.uuid4()),
                'name': name,
                'icon': self._get_folder_icon(name),
                'created_at': self._random_past_date(365).isoformat(),
            })
        
        return folders
    
    def _generate_password_entries(
        self,
        user: User,
        count: int,
        folders: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate fake password entries"""
        entries = []
        
        # Select domains
        domains = random.sample(COMMON_DOMAINS, min(count, len(COMMON_DOMAINS)))
        if count > len(COMMON_DOMAINS):
            domains.extend(random.choices(COMMON_DOMAINS, k=count - len(COMMON_DOMAINS)))
        
        for i, domain in enumerate(domains[:count]):
            # Generate realistic username variants
            username = self._generate_username(user, domain)
            
            # Generate fake password (looks real but is fake)
            fake_password = self._generate_fake_password()
            
            # Maybe add tracking token
            if self.tracking_enabled:
                fake_password = self._inject_tracking_token(fake_password, user)
            
            entry = {
                'id': str(uuid.uuid4()),
                'item_type': 'password',
                'name': self._get_site_name(domain),
                'website': f'https://www.{domain}',
                'username': username,
                'password': fake_password,
                'folder_id': random.choice(folders)['id'] if folders else None,
                'notes': self._maybe_generate_note(),
                'favorite': random.random() < 0.1,
                'created_at': self._random_past_date(730).isoformat(),
                'updated_at': self._random_past_date(90).isoformat(),
                'last_used_at': self._random_past_date(30).isoformat(),
            }
            entries.append(entry)
        
        return entries
    
    def _generate_card_entries(
        self,
        user: User,
        count: int
    ) -> List[Dict[str, Any]]:
        """Generate fake payment card entries"""
        entries = []
        
        for i in range(count):
            card_type = random.choice(CARD_TYPES)
            
            entry = {
                'id': str(uuid.uuid4()),
                'item_type': 'card',
                'name': f'{card_type} ending in {random.randint(1000, 9999)}',
                'card_type': card_type,
                'number': self._generate_fake_card_number(card_type),
                'expiry': self._generate_future_expiry(),
                'cvv': str(random.randint(100, 999)),
                'cardholder': f'{user.first_name or "John"} {user.last_name or "Doe"}',
                'billing_address': self._generate_fake_address(),
                'favorite': random.random() < 0.2,
                'created_at': self._random_past_date(365).isoformat(),
                'updated_at': self._random_past_date(30).isoformat(),
            }
            entries.append(entry)
        
        return entries
    
    def _generate_identity_entries(
        self,
        user: User,
        count: int
    ) -> List[Dict[str, Any]]:
        """Generate fake identity entries"""
        entries = []
        
        identity_types = ['Personal', 'Work', 'Passport', 'Driver License']
        
        for i in range(count):
            id_type = identity_types[i % len(identity_types)]
            
            entry = {
                'id': str(uuid.uuid4()),
                'item_type': 'identity',
                'name': f'{id_type} Identity',
                'identity_type': id_type,
                'first_name': user.first_name or 'John',
                'last_name': user.last_name or 'Doe',
                'email': f'decoy_{i}@example.com',
                'phone': self._generate_fake_phone(),
                'address': self._generate_fake_address(),
                'created_at': self._random_past_date(1000).isoformat(),
                'updated_at': self._random_past_date(180).isoformat(),
            }
            entries.append(entry)
        
        return entries
    
    def _generate_note_entries(
        self,
        user: User,
        count: int,
        folders: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate fake secure note entries"""
        entries = []
        
        note_titles = [
            'WiFi Passwords', 'Server Access', 'API Keys', 'Recovery Codes',
            'License Keys', 'Meeting Notes', 'Account Info', 'Personal Notes',
        ]
        
        for i in range(count):
            title = note_titles[i % len(note_titles)]
            
            entry = {
                'id': str(uuid.uuid4()),
                'item_type': 'note',
                'name': title,
                'content': self._generate_fake_note_content(title),
                'folder_id': random.choice(folders)['id'] if folders else None,
                'favorite': random.random() < 0.05,
                'created_at': self._random_past_date(500).isoformat(),
                'updated_at': self._random_past_date(60).isoformat(),
            }
            entries.append(entry)
        
        return entries
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _generate_username(self, user: User, domain: str) -> str:
        """Generate realistic username for a domain"""
        base_parts = []
        
        if user.first_name:
            base_parts.append(user.first_name.lower())
        if user.last_name:
            base_parts.append(user.last_name.lower())
        
        if not base_parts:
            base_parts = ['user']
        
        username = ''.join(base_parts)
        
        # Add variations
        if random.random() < 0.3:
            username += str(random.randint(1, 99))
        
        if '@' in domain or 'mail' in domain.lower():
            username = f'{username}@{domain}'
        
        return username
    
    def _generate_fake_password(self) -> str:
        """Generate a realistic-looking but fake password"""
        # Mix of patterns people actually use
        patterns = [
            lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=12)),
            lambda: f"{''.join(random.choices(string.ascii_uppercase, k=3))}{''.join(random.choices(string.digits, k=4))}{''.join(random.choices(string.ascii_lowercase, k=3))}!",
            lambda: f"{''.join(random.choices(string.ascii_lowercase, k=6))}{''.join(random.choices(string.digits, k=2))}@{''.join(random.choices(string.ascii_uppercase, k=2))}",
        ]
        return random.choice(patterns)()
    
    def _inject_tracking_token(
        self,
        password: str,
        user: User
    ) -> str:
        """Inject a tracking token into fake credentials"""
        # Create a unique identifier that can track if these credentials are used
        token = hashlib.md5(
            f"{user.id}:{password}:{timezone.now().timestamp()}".encode()
        ).hexdigest()[:6]
        
        # Subtly embed token (not visible in normal display)
        return f"{password}"  # In production, would use invisible unicode
    
    def _generate_fake_card_number(self, card_type: str) -> str:
        """Generate fake but valid-looking card number"""
        prefixes = {
            'Visa': '4',
            'Mastercard': '5',
            'American Express': '3',
            'Discover': '6',
        }
        prefix = prefixes.get(card_type, '4')
        
        # Generate remaining digits
        remaining = 16 - len(prefix)
        if card_type == 'American Express':
            remaining = 15 - len(prefix)
        
        number = prefix + ''.join(random.choices(string.digits, k=remaining - 1))
        
        # Luhn checksum
        checksum = self._luhn_checksum(number)
        return number + str(checksum)
    
    def _luhn_checksum(self, number: str) -> int:
        """Calculate Luhn checksum"""
        digits = [int(d) for d in number]
        odd_sum = sum(digits[-1::-2])
        even_sum = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
        return (10 - (odd_sum + even_sum) % 10) % 10
    
    def _generate_future_expiry(self) -> str:
        """Generate expiry date 1-5 years in future"""
        months_ahead = random.randint(12, 60)
        future_date = timezone.now() + timedelta(days=months_ahead * 30)
        return future_date.strftime('%m/%y')
    
    def _generate_fake_address(self) -> Dict[str, str]:
        """Generate fake address"""
        return {
            'street': f'{random.randint(100, 9999)} Main Street',
            'city': random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']),
            'state': random.choice(['NY', 'CA', 'IL', 'TX', 'AZ']),
            'zip': f'{random.randint(10000, 99999)}',
            'country': 'United States',
        }
    
    def _generate_fake_phone(self) -> str:
        """Generate fake phone number"""
        return f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
    
    def _generate_fake_note_content(self, title: str) -> str:
        """Generate fake note content based on title"""
        templates = {
            'WiFi Passwords': 'Home WiFi: FakePassword123\nOffice: WorkWifi456',
            'Server Access': 'SSH: fake.server.com\nUser: admin\nPort: 22',
            'API Keys': 'Production: sk_fake_1234567890\nStaging: sk_test_0987654321',
            'Recovery Codes': '1234-5678-9012\n2345-6789-0123\n3456-7890-1234',
            'License Keys': 'XXXX-YYYY-ZZZZ-1234',
            'Meeting Notes': 'Weekly standup notes...',
            'Account Info': 'Account #: 12345\nPIN: 9876',
            'Personal Notes': 'Important reminder...',
        }
        return templates.get(title, 'Secure note content...')
    
    def _get_site_name(self, domain: str) -> str:
        """Get display name for domain"""
        name = domain.split('.')[0]
        return name.title()
    
    def _get_folder_icon(self, name: str) -> str:
        """Get icon name for folder"""
        icons = {
            'Personal': 'user',
            'Work': 'briefcase',
            'Social Media': 'share-2',
            'Shopping': 'shopping-cart',
            'Finance': 'dollar-sign',
            'Entertainment': 'film',
            'Travel': 'map-pin',
            'Health': 'heart',
            'Education': 'book',
            'Utilities': 'settings',
        }
        return icons.get(name, 'folder')
    
    def _maybe_generate_note(self) -> str:
        """Maybe generate a note for an entry"""
        if random.random() < 0.2:
            return random.choice([
                'Remember to update password',
                'Two-factor enabled',
                'Business account',
                '',
            ])
        return ''
    
    def _random_past_date(self, max_days: int) -> datetime:
        """Generate a random date in the past"""
        days_ago = random.randint(1, max_days)
        return timezone.now() - timedelta(days=days_ago)
    
    def _calculate_realism_score(
        self,
        items: List[Dict],
        folders: List[Dict],
        real_structure: Dict[str, Any]
    ) -> float:
        """Calculate how realistic the decoy looks"""
        score = 0.5  # Base score
        
        # Bonus for matching real item count
        real_count = real_structure.get('item_count', 0)
        if real_count > 0:
            count_ratio = min(len(items) / real_count, real_count / len(items))
            score += 0.2 * count_ratio
        else:
            score += 0.1
        
        # Bonus for matching folder structure
        real_folders = real_structure.get('folders', [])
        if real_folders and folders:
            matching = sum(1 for f in folders if f['name'] in real_folders)
            score += 0.2 * (matching / len(folders))
        else:
            score += 0.1
        
        # Bonus for variety
        item_types = set(item['item_type'] for item in items)
        score += 0.1 * (len(item_types) / 4)
        
        return min(score, 1.0)


# Singleton instance
_decoy_vault_service = None


def get_decoy_vault_service() -> DecoyVaultService:
    """Get the singleton decoy vault service instance"""
    global _decoy_vault_service
    if _decoy_vault_service is None:
        _decoy_vault_service = DecoyVaultService()
    return _decoy_vault_service

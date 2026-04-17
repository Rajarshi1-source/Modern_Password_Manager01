"""
Generates plausible decoy credentials.

Plausibility matters: an attacker who pulls a vault will compare entries
against their expectations. A honeypot that says
"test/test" gets ignored; one that says "admin_backup@company.com /
CompanyPassword2024!" gets used.
"""

from __future__ import annotations

import random
import secrets
import string
from datetime import datetime
from typing import Dict, Optional

from ..models import DecoyStrategy, HoneypotTemplate


_CORPORATE_WORDS = [
    'Password', 'Secure', 'Vault', 'Backup', 'Access',
    'Admin', 'Company', 'Temp', 'Default',
]
_LEET_MAP = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '$', 't': '7'}
_PHRASE_ADJ = [
    'silent', 'quiet', 'hidden', 'misty', 'amber', 'rusty',
    'velvet', 'crimson', 'paper', 'copper',
]
_PHRASE_NOUN = [
    'fox', 'harbor', 'maple', 'lantern', 'canyon', 'meadow',
    'anchor', 'beacon', 'relay', 'summit',
]


class DecoyGenerator:
    """Stateless generator for decoy passwords & usernames."""

    @staticmethod
    def generate_password(pattern: str = 'corporate') -> str:
        if pattern == 'leet':
            base = secrets.choice(_CORPORATE_WORDS + _PHRASE_NOUN).lower()
            leet = ''.join(_LEET_MAP.get(c, c) for c in base)
            return f"{leet.capitalize()}{secrets.choice(string.digits)}{secrets.choice('!@#$')}"
        if pattern == 'phrase':
            adj = secrets.choice(_PHRASE_ADJ).capitalize()
            noun = secrets.choice(_PHRASE_NOUN).capitalize()
            return f"{adj}-{noun}-{secrets.randbelow(99):02d}"
        # default: "corporate"
        year = datetime.utcnow().year
        word = secrets.choice(_CORPORATE_WORDS)
        return f"{word}{year}!"

    @staticmethod
    def _extract_domain(user) -> str:
        email = getattr(user, 'email', '') or ''
        if '@' in email:
            return email.split('@', 1)[1]
        return 'company.com'

    @classmethod
    def from_template(
        cls,
        user,
        template: HoneypotTemplate,
    ) -> Dict[str, str]:
        domain = cls._extract_domain(user)
        return {
            'fake_site': template.fake_site_template.format(domain=domain),
            'fake_username': template.fake_username_template.format(domain=domain),
            'password': cls.generate_password(template.password_pattern or 'corporate'),
        }

    @classmethod
    def builtin(
        cls,
        user,
        label_hint: Optional[str] = None,
    ) -> Dict[str, str]:
        """Tiny, self-contained fallback when no templates are seeded."""
        domain = cls._extract_domain(user)
        choice = random.choice([
            {
                'fake_site': f'internal-portal.{domain}',
                'fake_username': f'admin_backup@{domain}',
                'password': f'Company{datetime.utcnow().year}!',
            },
            {
                'fake_site': f'vpn.{domain}',
                'fake_username': f'ops_{secrets.token_hex(2)}@{domain}',
                'password': cls.generate_password('corporate'),
            },
            {
                'fake_site': 'legacy-admin.corp.local',
                'fake_username': 'root_recovery',
                'password': cls.generate_password('leet'),
            },
        ])
        if label_hint:
            choice['label_hint'] = label_hint
        return choice

    @classmethod
    def generate(
        cls,
        user,
        strategy: str = DecoyStrategy.STATIC,
        template: Optional[HoneypotTemplate] = None,
    ) -> Dict[str, str]:
        if strategy == DecoyStrategy.FROM_TEMPLATE and template is not None:
            return cls.from_template(user, template)
        return cls.builtin(user)

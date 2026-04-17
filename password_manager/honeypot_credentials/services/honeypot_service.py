"""
CRUD + rotation for honeypot credentials.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from ..crypto_utils import decrypt_decoy, encrypt_decoy
from ..models import (
    DecoyStrategy,
    HoneypotAccessType,
    HoneypotCredential,
    HoneypotTemplate,
)
from .decoy_generator import DecoyGenerator

logger = logging.getLogger(__name__)


DEFAULT_CHANNELS = ('email',)


class HoneypotService:
    """High-level operations callable from views and Celery tasks."""

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------

    @transaction.atomic
    def create(
        self,
        user,
        label: str,
        strategy: str = DecoyStrategy.STATIC,
        template_id: Optional[UUID] = None,
        alert_channels: Optional[List[str]] = None,
        fake_site: Optional[str] = None,
        fake_username: Optional[str] = None,
        decoy_password: Optional[str] = None,
    ) -> HoneypotCredential:
        template = None
        if template_id:
            template = HoneypotTemplate.objects.filter(id=template_id).first()

        generated = DecoyGenerator.generate(user, strategy=strategy, template=template)

        plain_pw = decoy_password or generated['password']
        ciphertext = encrypt_decoy(plain_pw)

        hp = HoneypotCredential.objects.create(
            user=user,
            label=label,
            fake_site=fake_site or generated['fake_site'],
            fake_username=fake_username or generated['fake_username'],
            decoy_password_encrypted=ciphertext,
            decoy_strategy=strategy,
            template=template,
            alert_channels=list(alert_channels or DEFAULT_CHANNELS),
            last_rotated_at=timezone.now(),
        )
        logger.info("Honeypot %s created for user %s", hp.id, user.id)
        return hp

    def update(
        self,
        user,
        honeypot_id: UUID,
        **changes: Any,
    ) -> HoneypotCredential:
        hp = HoneypotCredential.objects.select_for_update().get(
            id=honeypot_id, user=user,
        )
        mutable = {'label', 'is_active', 'alert_channels', 'fake_site', 'fake_username'}
        for key in list(changes.keys()):
            if key not in mutable:
                changes.pop(key)
        for key, value in changes.items():
            setattr(hp, key, value)
        hp.save()
        return hp

    def delete(self, user, honeypot_id: UUID) -> None:
        HoneypotCredential.objects.filter(id=honeypot_id, user=user).delete()

    def list_for_user(self, user) -> List[HoneypotCredential]:
        return list(HoneypotCredential.objects.filter(user=user))

    # ---------------------------------------------------------------------
    # Rotation
    # ---------------------------------------------------------------------

    def rotate_decoy(self, honeypot: HoneypotCredential) -> HoneypotCredential:
        """Regenerate the decoy password. Intended for nightly cron."""
        generated = DecoyGenerator.generate(
            honeypot.user,
            strategy=honeypot.decoy_strategy,
            template=honeypot.template,
        )
        honeypot.decoy_password_encrypted = encrypt_decoy(generated['password'])
        honeypot.last_rotated_at = timezone.now()
        honeypot.save(update_fields=['decoy_password_encrypted', 'last_rotated_at', 'updated_at'])
        return honeypot

    # ---------------------------------------------------------------------
    # Presentation
    # ---------------------------------------------------------------------

    def reveal_decoy(self, honeypot: HoneypotCredential) -> Dict[str, str]:
        """
        Produce a vault-item-shaped payload suitable for returning in
        place of a real vault item on interception. Decrypts the decoy
        password lazily so we never fan it out through serializers.
        """
        try:
            plain = decrypt_decoy(honeypot.decoy_password_encrypted)
        except Exception as exc:
            logger.error("Honeypot %s decrypt failed: %s", honeypot.id, exc)
            plain = 'decoy'

        return {
            'id': str(honeypot.id),
            'item_id': f'hp-{honeypot.id.hex[:12]}',
            'item_type': 'password',
            'site': honeypot.fake_site,
            'username': honeypot.fake_username,
            'password': plain,
            'is_honeypot': True,
        }

    def masked_list_entry(self, honeypot: HoneypotCredential) -> Dict[str, Any]:
        """
        Shape used when listing — NEVER includes the decoy password.
        Returned alongside real entries so the attacker can't distinguish.
        """
        return {
            'id': str(honeypot.id),
            'item_id': f'hp-{honeypot.id.hex[:12]}',
            'item_type': 'password',
            'favorite': False,
            'created_at': honeypot.created_at.isoformat(),
            'updated_at': honeypot.updated_at.isoformat(),
            # deliberately omit decoy fields; retrieval triggers alert.
        }

    # ---------------------------------------------------------------------
    # Type tests (used by the interceptor)
    # ---------------------------------------------------------------------

    def is_honeypot_id(self, candidate_id: str) -> bool:
        """
        Cheap primary-key lookup. The vault retrieve path calls this
        before hitting EncryptedVaultItem so a honeypot UUID that
        accidentally coincides with a vault UUID always resolves here.
        """
        try:
            return HoneypotCredential.objects.filter(id=candidate_id).exists()
        except (ValueError, TypeError):
            return False

    def get_by_id(self, candidate_id) -> Optional[HoneypotCredential]:
        try:
            return HoneypotCredential.objects.filter(id=candidate_id).first()
        except (ValueError, TypeError):
            return None

"""Check: weak or reused passwords in the vault.

The vault is end-to-end encrypted, so the server cannot inspect plaintext. This
check therefore relies only on server-visible *strength metadata* the platform
already derives (via the ML security analysis pipeline). When no such metadata
is available it degrades to "no finding" rather than guessing.
"""

from __future__ import annotations

import logging

from .base import BaseCheck, FindingResult

logger = logging.getLogger(__name__)


class WeakReusedPasswordsCheck(BaseCheck):
    check_id = 'weak_reused_passwords'
    title = 'Weak passwords detected'

    def _collect(self, user):
        """Return the count of distinct weak passwords, or None if unavailable.

        Reuses the ML strength-prediction store. ``password_hash`` lets us count
        *distinct* weak credentials rather than every historical prediction.
        Reuse is not assessable server-side (zero-knowledge), so it is omitted.
        """
        try:
            from ml_security.models import PasswordStrengthPrediction
            return (
                PasswordStrengthPrediction.objects
                .filter(user=user, strength__in=['very_weak', 'weak'])
                .values('password_hash').distinct().count()
            )
        except Exception:
            logger.debug('Strength metadata unavailable for self-test', exc_info=True)
            return None

    def run(self, user):
        weak = self._collect(user)
        if not weak:
            return []
        return [
            FindingResult(
                check_id=self.check_id,
                title=self.title,
                severity='medium',
                remediation=(
                    'Regenerate weak passwords with the generator and give every '
                    'site a unique password so a single breach cannot cascade.'
                ),
                fingerprint='weak-passwords',
                evidence={'weak_count': int(weak)},
            )
        ]

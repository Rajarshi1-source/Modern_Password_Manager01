"""Check: two-factor authentication is not enabled."""

from __future__ import annotations

import logging

from .base import BaseCheck, FindingResult

logger = logging.getLogger(__name__)


class MissingMFACheck(BaseCheck):
    check_id = 'mfa_disabled'
    title = 'Two-factor authentication is not enabled'

    def _has_mfa(self, user):
        """True/False when determinable, else None (skip silently).

        Reads the project's local ``two_factor`` app: a user has 2FA when they
        own at least one *confirmed* TOTP device.
        """
        try:
            from two_factor.models import TOTPDevice
        except ImportError:  # app not installed → expected "signal unavailable"
            logger.debug('MFA signal unavailable for self-test', exc_info=True)
            return None
        # A real ORM/runtime error below is a bug, not an unavailable signal —
        # let it bubble to run_self_test(), which isolates and logs the check.
        return TOTPDevice.objects.filter(user=user, confirmed=True).exists()

    def run(self, user):
        has_mfa = self._has_mfa(user)
        if has_mfa is None or has_mfa:
            return []
        return [
            FindingResult(
                check_id=self.check_id,
                title=self.title,
                severity='high',
                remediation=(
                    'Enable TOTP-based two-factor authentication in Security '
                    'settings. Without a second factor, a leaked master password '
                    'is enough to unlock the account.'
                ),
                fingerprint='mfa-disabled',
                evidence={'confirmed_2fa_devices': 0},
            )
        ]

"""Check: passwords overdue for rotation.

NOTE (Phase 1 scaffold): the vault is end-to-end encrypted, so the server has
neither plaintext nor a per-credential rotation-age store, and the predictive-
expiration service scores a *given* password rather than enumerating a user's
vault. There is therefore no faithful server-side signal yet, so ``_collect``
returns ``None`` and this check is a no-op in production. It is kept as the
documented integration point for a future server-side rotation-age aggregate;
its scoring logic is exercised by unit tests via a mocked ``_collect``.
"""

from __future__ import annotations

import logging

from .base import BaseCheck, FindingResult

logger = logging.getLogger(__name__)


class StaleRotationCheck(BaseCheck):
    check_id = 'stale_rotation'
    title = 'Passwords are overdue for rotation'

    def _collect(self, user):
        """Count of overdue credentials, or None when no server-side signal
        exists (the case in Phase 1 — see the module docstring)."""
        return None

    def run(self, user):
        overdue = self._collect(user)
        if not overdue:
            return []
        severity = 'medium' if overdue >= 5 else 'low'
        return [
            FindingResult(
                check_id=self.check_id,
                title=self.title,
                severity=severity,
                remediation=(
                    'Rotate the credentials flagged as overdue. Long-lived '
                    'passwords widen the window an old leak stays exploitable.'
                ),
                fingerprint='stale-rotation',
                evidence={'overdue_count': overdue},
            )
        ]

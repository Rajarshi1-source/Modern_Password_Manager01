"""Abstract ZK proof provider interface."""

from __future__ import annotations

import abc


class ZKProofProvider(abc.ABC):
    """
    Minimal contract a ZK backend must satisfy to slot into the zk_proofs app.

    Adding a SNARK-based provider later means implementing these four methods
    and registering an instance in ``zk_proofs.providers.__init__``. No caller
    (serializers, views, vault integration) needs to change.
    """

    scheme: str = ""

    @abc.abstractmethod
    def is_valid_commitment(self, data: bytes) -> bool:
        """Return True if ``data`` is a syntactically valid commitment payload."""

    @abc.abstractmethod
    def commitment_size(self) -> int:
        """Expected size in bytes of a commitment payload for this scheme."""

    @abc.abstractmethod
    def proof_T_size(self) -> int:
        """Expected size in bytes of the ``T`` half of an equality proof."""

    @abc.abstractmethod
    def proof_s_size(self) -> int:
        """Expected size in bytes of the ``s`` half of an equality proof."""

    @abc.abstractmethod
    def verify_equality(
        self,
        c_a: bytes,
        c_b: bytes,
        proof_T: bytes,
        proof_s: bytes,
    ) -> bool:
        """Verify that ``c_a`` and ``c_b`` hide the same secret."""

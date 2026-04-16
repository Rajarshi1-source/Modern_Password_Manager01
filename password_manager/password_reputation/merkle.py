"""
Simple SHA-256 binary Merkle tree used to build AnchorBatch roots.

Chosen to match the layout already understood by ``CommitmentRegistry``
(keccak-based hashing is available through the existing
``blockchain_anchor_service.verify_proof_locally``, but for the reputation
app we anchor a **root only** — we never need to generate Merkle proofs for
individual leaves, because on-chain we only record the root, not per-leaf
inclusion proofs). Keeping the tree in SHA-256 avoids a dependency on the
web3/keccak stack inside the reputation code path.

If verifiable per-leaf inclusion is ever needed, swap to the existing
``blockchain.services.merkle_tree_builder.MerkleTreeBuilder`` (keccak) here;
the calling surface is identical.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Sequence


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hash_leaf(leaf: bytes) -> bytes:
    """Leaf hash uses a 0x00 domain-separation byte (matches RFC 6962 style)."""
    return sha256(b"\x00" + leaf)


def hash_pair(left: bytes, right: bytes) -> bytes:
    """Interior node hash uses a 0x01 domain-separation byte."""
    return sha256(b"\x01" + left + right)


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """Compute a SHA-256 Merkle root over the provided 32-byte leaf hashes.

    ``leaves`` should already be hashed with ``hash_leaf``. Empty input
    returns the hash of the empty string (matches RFC 6962 semantics).
    """
    if not leaves:
        return sha256(b"")

    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplicate last to even out
        level = [hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def compute_event_leaf(event_id_bytes: bytes, user_id: int, event_type: str,
                       score_delta: int, tokens_delta: int) -> bytes:
    """Canonical leaf for a ReputationEvent.

    Deterministic across migrations so an event's leaf_hash remains stable
    even if the event is later re-batched.
    """
    h = hashlib.sha256()
    h.update(b"pwm-reputation-v1|event-leaf|")
    h.update(event_id_bytes)
    h.update(user_id.to_bytes(8, "big", signed=False))
    h.update(event_type.encode("utf-8"))
    h.update(len(event_type).to_bytes(2, "big"))
    # Signed deltas — encode as fixed-width two's complement little-endian.
    h.update(int(score_delta).to_bytes(8, "big", signed=True))
    h.update(int(tokens_delta).to_bytes(16, "big", signed=True))
    return h.digest()

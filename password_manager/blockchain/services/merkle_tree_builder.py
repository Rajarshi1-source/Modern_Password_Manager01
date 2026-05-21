"""
Merkle Tree Builder for batching commitments.

Hash algorithm: keccak256 with sorted-pair concatenation, matching the
on-chain `CommitmentRegistry.verifyCommitment` implementation exactly.

History note: an earlier revision of this file used SHA-256, which did not
match the Solidity contract's keccak256. As of the 2026-05 audit fix, both
sides agree byte-for-byte. Any pre-fix anchored rows are flagged
`verifiable=False` in the database and must be re-anchored to be
on-chain-verifiable again.
"""

from typing import List, Dict

from eth_utils import keccak


def _keccak(data: bytes) -> bytes:
    """Single canonical hasher used everywhere in this module."""
    return keccak(data)


class MerkleTreeBuilder:
    """
    Builds Merkle trees for batching behavioral commitments.

    Hash function: keccak256 over sorted-pair concatenation
    ``keccak256(min(a,b) || max(a,b))`` — identical to OpenZeppelin's
    `MerkleProof.verifyCalldata` style and to the CommitmentRegistry
    contract's `verifyCommitment` loop.
    """

    def __init__(self, leaves: List[bytes]):
        if not leaves:
            raise ValueError("Cannot build Merkle tree with empty leaves")

        self.leaves = leaves
        self.tree = self._build_tree(leaves)
        self.root = self.tree[-1][0] if self.tree else None

    @staticmethod
    def hash_pair(left: bytes, right: bytes) -> bytes:
        """
        Hash a pair of nodes, sorted-pair, with keccak256.

        Must match Solidity:
            keccak256(abi.encodePacked(min(a, b), max(a, b)))
        """
        if left <= right:
            combined = left + right
        else:
            combined = right + left
        return _keccak(combined)

    def _build_tree(self, leaves: List[bytes]) -> List[List[bytes]]:
        """Build the complete Merkle tree (bottom to top)."""
        tree = [leaves[:]]

        while len(tree[-1]) > 1:
            current_level = tree[-1]
            next_level = []

            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # Odd tail: duplicate the last node.
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(self.hash_pair(left, right))

            tree.append(next_level)

        return tree

    def get_proof(self, leaf_index: int) -> List[bytes]:
        """Get Merkle proof for a specific leaf."""
        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise ValueError(f"Invalid leaf index: {leaf_index}")

        proof = []
        index = leaf_index

        for level in range(len(self.tree) - 1):
            level_nodes = self.tree[level]

            sibling_index = index + 1 if index % 2 == 0 else index - 1
            if 0 <= sibling_index < len(level_nodes):
                proof.append(level_nodes[sibling_index])

            index = index // 2

        return proof

    def verify_proof(self, leaf: bytes, proof: List[bytes], root: bytes = None) -> bool:
        """Verify a Merkle proof locally using the canonical hasher."""
        if root is None:
            root = self.root

        computed_hash = leaf
        for sibling in proof:
            computed_hash = self.hash_pair(computed_hash, sibling)

        return computed_hash == root

    @classmethod
    def build_from_commitments(cls, commitments: List[Dict]) -> 'MerkleTreeBuilder':
        """Build Merkle tree from commitment dicts with 'commitment_hash' key."""
        leaves = [bytes.fromhex(c['commitment_hash']) for c in commitments]
        return cls(leaves)

    def get_root_hex(self) -> str:
        """Get Merkle root as hex string (0x prefixed)."""
        return '0x' + self.root.hex() if self.root else None

    def get_proof_hex(self, leaf_index: int) -> List[str]:
        """Get Merkle proof as hex strings (0x prefixed)."""
        proof = self.get_proof(leaf_index)
        return ['0x' + p.hex() for p in proof]

    def __len__(self) -> int:
        return len(self.leaves)

    def __repr__(self) -> str:
        root_hex = self.get_root_hex() or ''
        return f"<MerkleTreeBuilder: {len(self.leaves)} leaves, root={root_hex[:10]}...>"


def create_commitment_hash(commitment_id: str, encrypted_data: str) -> str:
    """
    Create keccak256 hash of a behavioral commitment leaf.

    Hex string is returned WITHOUT a '0x' prefix because the existing
    callers and DB columns assume bare hex; the on-chain verifier doesn't
    care about prefix presence.
    """
    data = f"{commitment_id}{encrypted_data}".encode('utf-8')
    return _keccak(data).hex()

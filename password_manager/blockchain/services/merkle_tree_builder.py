"""
Merkle Tree Builder for batching commitments
Uses SHA-256 hashing for efficiency and Ethereum compatibility
"""

import hashlib
from typing import List, Dict, Tuple


class MerkleTreeBuilder:
    """
    Builds Merkle trees for batching behavioral commitments
    Compatible with Solidity keccak256 verification
    """
    
    def __init__(self, leaves: List[bytes]):
        """
        Initialize Merkle tree with leaf hashes
        
        Args:
            leaves: List of leaf hashes (bytes)
        """
        if not leaves:
            raise ValueError("Cannot build Merkle tree with empty leaves")
        
        self.leaves = leaves
        self.tree = self._build_tree(leaves)
        self.root = self.tree[-1][0] if self.tree else None
    
    @staticmethod
    def hash_pair(left: bytes, right: bytes) -> bytes:
        """
        Hash a pair of nodes (Ethereum-compatible ordering)
        
        Args:
            left: Left node hash
            right: Right node hash
        
        Returns:
            bytes: Combined hash
        """
        # Sort lexicographically (smaller first) for deterministic ordering
        if left <= right:
            combined = left + right
        else:
            combined = right + left
        
        return hashlib.sha256(combined).digest()
    
    def _build_tree(self, leaves: List[bytes]) -> List[List[bytes]]:
        """
        Build the complete Merkle tree
        
        Args:
            leaves: List of leaf hashes
        
        Returns:
            List of tree levels (bottom to top)
        """
        tree = [leaves[:]]  # Start with leaves level
        
        while len(tree[-1]) > 1:
            current_level = tree[-1]
            next_level = []
            
            # Process pairs
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                
                # If odd number of nodes, duplicate the last one
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = left
                
                parent = self.hash_pair(left, right)
                next_level.append(parent)
            
            tree.append(next_level)
        
        return tree
    
    def get_proof(self, leaf_index: int) -> List[bytes]:
        """
        Get Merkle proof for a specific leaf
        
        Args:
            leaf_index: Index of the leaf (0-based)
        
        Returns:
            List of sibling hashes needed to verify the leaf
        """
        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise ValueError(f"Invalid leaf index: {leaf_index}")
        
        proof = []
        index = leaf_index
        
        # Traverse from leaves to root
        for level in range(len(self.tree) - 1):
            level_nodes = self.tree[level]
            
            # Find sibling
            if index % 2 == 0:  # Left node
                sibling_index = index + 1
            else:  # Right node
                sibling_index = index - 1
            
            # Add sibling to proof (if it exists)
            if 0 <= sibling_index < len(level_nodes):
                proof.append(level_nodes[sibling_index])
            
            # Move to parent level
            index = index // 2
        
        return proof
    
    def verify_proof(self, leaf: bytes, proof: List[bytes], root: bytes = None) -> bool:
        """
        Verify a Merkle proof
        
        Args:
            leaf: Leaf hash to verify
            proof: List of sibling hashes
            root: Expected root hash (uses self.root if not provided)
        
        Returns:
            bool: True if proof is valid
        """
        if root is None:
            root = self.root
        
        computed_hash = leaf
        
        for sibling in proof:
            computed_hash = self.hash_pair(computed_hash, sibling)
        
        return computed_hash == root
    
    @classmethod
    def build_from_commitments(cls, commitments: List[Dict]) -> 'MerkleTreeBuilder':
        """
        Build Merkle tree from commitment dictionaries
        
        Args:
            commitments: List of commitment dicts with 'commitment_hash' key
        
        Returns:
            MerkleTreeBuilder instance
        """
        leaves = [
            bytes.fromhex(c['commitment_hash'])
            for c in commitments
        ]
        return cls(leaves)
    
    def get_root_hex(self) -> str:
        """Get Merkle root as hex string (0x prefixed)"""
        return '0x' + self.root.hex() if self.root else None
    
    def get_proof_hex(self, leaf_index: int) -> List[str]:
        """Get Merkle proof as hex strings (0x prefixed)"""
        proof = self.get_proof(leaf_index)
        return ['0x' + p.hex() for p in proof]
    
    def __len__(self) -> int:
        """Get number of leaves in the tree"""
        return len(self.leaves)
    
    def __repr__(self) -> str:
        return f"<MerkleTreeBuilder: {len(self.leaves)} leaves, root={self.get_root_hex()[:10]}...>"


# Helper function for creating commitment hashes
def create_commitment_hash(commitment_id: str, encrypted_data: str) -> str:
    """
    Create SHA-256 hash of a behavioral commitment
    
    Args:
        commitment_id: Unique commitment identifier
        encrypted_data: Encrypted behavioral embedding
    
    Returns:
        Hex string (without 0x prefix)
    """
    data = f"{commitment_id}{encrypted_data}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()


from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class BlockchainAnchor(models.Model):
    """
    Represents a batch of commitments anchored to Arbitrum blockchain
    """
    merkle_root = models.CharField(
        max_length=66,
        unique=True,
        db_index=True,
        help_text="Root hash of Merkle tree (0x prefixed)"
    )
    tx_hash = models.CharField(
        max_length=66,
        unique=True,
        db_index=True,
        help_text="Arbitrum transaction hash"
    )
    block_number = models.BigIntegerField(
        help_text="Block number where transaction was mined"
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When the batch was anchored"
    )
    batch_size = models.IntegerField(
        help_text="Number of commitments in this batch"
    )
    network = models.CharField(
        max_length=20,
        choices=[
            ('testnet', 'Arbitrum Sepolia Testnet'),
            ('mainnet', 'Arbitrum One Mainnet'),
        ],
        default='testnet',
        help_text="Network where commitment was anchored"
    )
    gas_used = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Gas used for the transaction"
    )
    gas_price_wei = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Gas price in wei"
    )
    submitter_address = models.CharField(
        max_length=42,
        null=True,
        blank=True,
        help_text="Address that submitted the transaction"
    )
    
    class Meta:
        db_table = 'blockchain_anchors'
        ordering = ['-timestamp']
        verbose_name = 'Blockchain Anchor'
        verbose_name_plural = 'Blockchain Anchors'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['network', '-timestamp']),
        ]
    
    def __str__(self):
        return f"Anchor {self.merkle_root[:10]}... ({self.batch_size} commitments)"
    
    @property
    def gas_price(self):
        """Alias for gas_price_wei (for admin compatibility)"""
        return self.gas_price_wei
    
    @property
    def cost_eth(self):
        """Calculate total cost in ETH"""
        if self.gas_used and self.gas_price_wei:
            return (self.gas_used * self.gas_price_wei) / 1e18
        return None
    
    @property
    def arbiscan_url(self):
        """Get Arbiscan URL for this transaction"""
        if self.network == 'mainnet':
            return f"https://arbiscan.io/tx/{self.tx_hash}"
        else:
            return f"https://sepolia.arbiscan.io/tx/{self.tx_hash}"


class MerkleProof(models.Model):
    """
    Stores Merkle proof for individual commitments within a batch
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='merkle_proofs'
    )
    commitment = models.ForeignKey(
        'behavioral_recovery.BehavioralCommitment',
        on_delete=models.CASCADE,
        related_name='merkle_proofs',
        help_text="The behavioral commitment this proof is for"
    )
    commitment_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of the commitment"
    )
    merkle_root = models.CharField(
        max_length=66,
        db_index=True,
        help_text="Root hash this proof verifies against"
    )
    proof = models.JSONField(
        help_text="Array of sibling hashes for Merkle proof"
    )
    leaf_index = models.IntegerField(
        help_text="Position of this leaf in the Merkle tree"
    )
    blockchain_anchor = models.ForeignKey(
        BlockchainAnchor,
        on_delete=models.CASCADE,
        related_name='proofs',
        help_text="The blockchain anchor this proof belongs to"
    )
    created_at = models.DateTimeField(
        default=timezone.now
    )
    verified = models.BooleanField(
        default=False,
        help_text="Whether this proof has been verified"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this proof was verified"
    )
    
    class Meta:
        db_table = 'merkle_proofs'
        ordering = ['-created_at']
        verbose_name = 'Merkle Proof'
        verbose_name_plural = 'Merkle Proofs'
        unique_together = [['commitment', 'blockchain_anchor']]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['commitment_hash']),
            models.Index(fields=['merkle_root']),
        ]
    
    def __str__(self):
        return f"Proof for {self.commitment_hash[:10]}... in {self.merkle_root[:10]}..."
    
    @property
    def is_verified(self):
        """Check if this proof can be verified on-chain"""
        return self.blockchain_anchor.tx_hash is not None


class PendingCommitment(models.Model):
    """
    Temporary storage for commitments waiting to be batched and anchored
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pending_commitments'
    )
    commitment = models.ForeignKey(
        'behavioral_recovery.BehavioralCommitment',
        on_delete=models.CASCADE,
        related_name='pending_anchor'
    )
    commitment_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the commitment"
    )
    created_at = models.DateTimeField(
        default=timezone.now
    )
    is_anchored = models.BooleanField(
        default=False,
        help_text="Whether this commitment has been anchored to blockchain"
    )
    anchored_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this commitment was anchored"
    )
    blockchain_anchor = models.ForeignKey(
        BlockchainAnchor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_commitments',
        help_text="The blockchain anchor this was included in"
    )
    
    @property
    def anchored(self):
        """Alias for is_anchored (for admin compatibility)"""
        return self.is_anchored
    
    class Meta:
        db_table = 'pending_commitments'
        ordering = ['created_at']
        verbose_name = 'Pending Commitment'
        verbose_name_plural = 'Pending Commitments'
        indexes = [
            models.Index(fields=['is_anchored', 'created_at']),
        ]
    
    def __str__(self):
        status = "Anchored" if self.is_anchored else "Pending"
        return f"{status}: {self.commitment_hash[:10]}..."

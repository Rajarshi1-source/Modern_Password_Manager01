"""
Smart Contract Vault Models
============================

Core models for blockchain-based conditional password access.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ConditionType(models.TextChoices):
    TIME_LOCK = 'time_lock', 'Time Lock'
    DEAD_MANS_SWITCH = 'dead_mans_switch', 'Dead Man\'s Switch'
    MULTI_SIG = 'multi_sig', 'Multi-Signature'
    DAO_VOTE = 'dao_vote', 'DAO Voting'
    PRICE_ORACLE = 'price_oracle', 'Price Oracle'
    ESCROW = 'escrow', 'Escrow'


class VaultStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    PENDING_APPROVAL = 'pending_approval', 'Pending Approval'
    UNLOCKED = 'unlocked', 'Unlocked'
    EXPIRED = 'expired', 'Expired'
    CANCELLED = 'cancelled', 'Cancelled'


class SmartContractVault(models.Model):
    """
    Represents a password vault controlled by on-chain smart contract conditions.

    Links an encrypted password to a specific condition type on the TimeLockedVault
    smart contract deployed on Arbitrum.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='smart_contract_vaults',
        help_text='Vault creator/owner'
    )
    title = models.CharField(
        max_length=255,
        help_text='Human-readable vault title'
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Description of this vault\'s purpose'
    )

    # On-chain references
    vault_id_onchain = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Vault ID on the TimeLockedVault smart contract'
    )
    password_hash = models.CharField(
        max_length=66,
        help_text='Keccak256 hash of the encrypted password (0x prefixed)'
    )
    password_encrypted = models.TextField(
        help_text='Server-side encrypted password data (AES-256-GCM)'
    )

    # Condition configuration
    condition_type = models.CharField(
        max_length=20,
        choices=ConditionType.choices,
        db_index=True,
        help_text='Type of unlock condition'
    )
    status = models.CharField(
        max_length=20,
        choices=VaultStatus.choices,
        default=VaultStatus.ACTIVE,
        db_index=True,
        help_text='Current vault status'
    )

    # Blockchain metadata
    contract_address = models.CharField(
        max_length=42,
        blank=True,
        default='',
        help_text='TimeLockedVault contract address'
    )
    tx_hash = models.CharField(
        max_length=66,
        blank=True,
        default='',
        help_text='Transaction hash for vault creation'
    )
    network = models.CharField(
        max_length=20,
        choices=[
            ('testnet', 'Arbitrum Sepolia Testnet'),
            ('mainnet', 'Arbitrum One Mainnet'),
        ],
        default='testnet',
        help_text='Blockchain network'
    )

    # Time-lock fields
    unlock_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='For TIME_LOCK: when the vault unlocks'
    )

    # Dead man's switch fields
    check_in_interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='For DEAD_MANS_SWITCH: days between required check-ins'
    )
    last_check_in = models.DateTimeField(
        null=True,
        blank=True,
        help_text='For DEAD_MANS_SWITCH: last check-in timestamp'
    )
    grace_period_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='For DEAD_MANS_SWITCH: extra days after missed check-in'
    )

    # Price oracle fields
    price_threshold = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='For PRICE_ORACLE: price threshold (e.g., 10000.00 USD)'
    )
    price_above = models.BooleanField(
        default=True,
        help_text='For PRICE_ORACLE: true=unlock when price > threshold'
    )
    oracle_address = models.CharField(
        max_length=42,
        blank=True,
        default='',
        help_text='Chainlink oracle contract address'
    )

    # Beneficiary (shared across dead man's switch, escrow, inheritance)
    beneficiary_email = models.EmailField(
        blank=True,
        default='',
        help_text='Beneficiary email for notifications'
    )
    beneficiary_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='beneficiary_vaults',
        help_text='Beneficiary user (if registered)'
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)

    # On-chain reveal audit (hybrid unlock path).
    # Populated by OnchainUnlockService after the DB unlock succeeds, so a
    # failed broadcast never blocks the owner from seeing their password.
    released_tx_hash = models.CharField(
        max_length=66,
        blank=True,
        default='',
        help_text='VaultAuditLog.anchorUnlock() transaction hash (0x-prefixed)'
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Wall-clock time the on-chain anchor was confirmed'
    )

    class Meta:
        db_table = 'smart_contract_vaults'
        ordering = ['-created_at']
        verbose_name = 'Smart Contract Vault'
        verbose_name_plural = 'Smart Contract Vaults'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['condition_type', 'status']),
            models.Index(fields=['network', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_condition_type_display()}) - {self.get_status_display()}"

    @property
    def is_active(self):
        return self.status == VaultStatus.ACTIVE

    @property
    def is_unlocked(self):
        return self.status == VaultStatus.UNLOCKED

    @property
    def arbiscan_url(self):
        if not self.tx_hash:
            return None
        if self.network == 'mainnet':
            return f"https://arbiscan.io/tx/{self.tx_hash}"
        return f"https://sepolia.arbiscan.io/tx/{self.tx_hash}"

    @property
    def dead_mans_switch_deadline(self):
        """Calculate the deadline for dead man's switch trigger."""
        if self.condition_type != ConditionType.DEAD_MANS_SWITCH:
            return None
        if not self.last_check_in or not self.check_in_interval_days:
            return None
        from datetime import timedelta
        return (
            self.last_check_in
            + timedelta(days=self.check_in_interval_days)
            + timedelta(days=self.grace_period_days or 0)
        )


class VaultCondition(models.Model):
    """
    Individual condition within a compound vault. Supports AND/OR trees
    for complex multi-condition vaults.
    """

    class Operator(models.TextChoices):
        AND = 'and', 'AND'
        OR = 'or', 'OR'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        SmartContractVault,
        on_delete=models.CASCADE,
        related_name='conditions'
    )
    condition_type = models.CharField(
        max_length=20,
        choices=ConditionType.choices,
        help_text='Condition type for this node'
    )
    operator = models.CharField(
        max_length=3,
        choices=Operator.choices,
        default=Operator.AND,
        help_text='How this condition combines with siblings'
    )
    parameters = models.JSONField(
        default=dict,
        help_text='Type-specific parameters (threshold, deadline, addresses, etc.)'
    )
    is_met = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'smart_contract_vault_conditions'
        ordering = ['order']
        verbose_name = 'Vault Condition'
        verbose_name_plural = 'Vault Conditions'

    def __str__(self):
        status = '✅' if self.is_met else '❌'
        return f"{status} {self.get_condition_type_display()} ({self.get_operator_display()})"

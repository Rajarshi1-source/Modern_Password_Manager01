"""
Escrow & Inheritance Models
============================
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class EscrowAgreement(models.Model):
    """
    Escrow agreement with a trusted arbitrator who controls password release.
    """

    class EscrowStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        RELEASED = 'released', 'Released'
        DISPUTED = 'disputed', 'Disputed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.OneToOneField(
        'smart_contracts.SmartContractVault',
        on_delete=models.CASCADE,
        related_name='escrow_agreement'
    )
    depositor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escrow_deposited',
        help_text='User who deposited the password'
    )
    beneficiary = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escrow_beneficiary',
        help_text='User who receives the password'
    )
    arbitrator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escrow_arbitrating',
        help_text='Trusted arbitrator who controls release'
    )
    arbitrator_wallet = models.CharField(
        max_length=42,
        blank=True,
        default='',
        help_text='Arbitrator\'s Ethereum wallet address'
    )
    release_conditions = models.TextField(
        help_text='Human-readable description of release conditions'
    )
    status = models.CharField(
        max_length=20,
        choices=EscrowStatus.choices,
        default=EscrowStatus.PENDING
    )
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smart_contract_escrow_agreements'
        ordering = ['-created_at']
        verbose_name = 'Escrow Agreement'
        verbose_name_plural = 'Escrow Agreements'

    def __str__(self):
        return (
            f"Escrow: {self.depositor.username} → {self.beneficiary.username} "
            f"(arbitrator: {self.arbitrator.username}) [{self.get_status_display()}]"
        )


class InheritancePlan(models.Model):
    """
    Dead man's switch-based inheritance plan.
    Automatically releases password access to beneficiary
    after a period of owner inactivity.
    """

    class InheritanceStatus(models.TextChoices):
        ACTIVE = 'active', 'Active (Monitoring)'
        GRACE_PERIOD = 'grace_period', 'Grace Period (Owner Notified)'
        TRIGGERED = 'triggered', 'Triggered (Released to Beneficiary)'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.OneToOneField(
        'smart_contracts.SmartContractVault',
        on_delete=models.CASCADE,
        related_name='inheritance_plan'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inheritance_plans_owned'
    )
    beneficiary_email = models.EmailField(
        help_text='Beneficiary email for notifications'
    )
    beneficiary_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inheritance_plans_beneficiary',
        help_text='Beneficiary user account (if registered)'
    )
    inactivity_period_days = models.PositiveIntegerField(
        default=90,
        help_text='Days of inactivity before grace period starts'
    )
    grace_period_days = models.PositiveIntegerField(
        default=7,
        help_text='Days in grace period before auto-release'
    )
    last_check_in = models.DateTimeField(
        default=timezone.now,
        help_text='Last time owner confirmed they are alive'
    )
    grace_period_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When grace period notification was sent'
    )
    notification_sent = models.BooleanField(
        default=False,
        help_text='Whether grace period notification was sent to owner'
    )
    beneficiary_notified = models.BooleanField(
        default=False,
        help_text='Whether beneficiary was notified of pending release'
    )
    status = models.CharField(
        max_length=20,
        choices=InheritanceStatus.choices,
        default=InheritanceStatus.ACTIVE
    )
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smart_contract_inheritance_plans'
        ordering = ['-created_at']
        verbose_name = 'Inheritance Plan'
        verbose_name_plural = 'Inheritance Plans'

    def __str__(self):
        return (
            f"Inheritance: {self.owner.username} → {self.beneficiary_email} "
            f"({self.inactivity_period_days}d) [{self.get_status_display()}]"
        )

    @property
    def inactivity_deadline(self):
        """When the grace period should start if no check-in."""
        from datetime import timedelta
        return self.last_check_in + timedelta(days=self.inactivity_period_days)

    @property
    def release_deadline(self):
        """When the password is auto-released to beneficiary."""
        from datetime import timedelta
        if self.grace_period_started_at:
            return self.grace_period_started_at + timedelta(days=self.grace_period_days)
        return None

    @property
    def is_overdue(self):
        """Whether the inactivity period has elapsed."""
        return timezone.now() >= self.inactivity_deadline

    @property
    def is_release_due(self):
        """Whether the grace period has also elapsed."""
        deadline = self.release_deadline
        return deadline is not None and timezone.now() >= deadline

"""
Governance Models — Multi-Sig & DAO Voting
============================================
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class MultiSigGroup(models.Model):
    """
    M-of-N multi-signature configuration for a vault.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.OneToOneField(
        'smart_contracts.SmartContractVault',
        on_delete=models.CASCADE,
        related_name='multi_sig_group'
    )
    required_approvals = models.PositiveSmallIntegerField(
        help_text='Number of approvals required (M)'
    )
    signers = models.ManyToManyField(
        User,
        related_name='multisig_memberships',
        help_text='Authorized signers (N)'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'smart_contract_multi_sig_groups'
        verbose_name = 'Multi-Sig Group'
        verbose_name_plural = 'Multi-Sig Groups'

    def __str__(self):
        return f"{self.required_approvals}-of-{self.signers.count()} for {self.vault.title}"

    @property
    def total_signers(self):
        return self.signers.count()

    @property
    def approval_count(self):
        return self.approvals.filter(approved=True).count()

    @property
    def is_threshold_met(self):
        return self.approval_count >= self.required_approvals


class MultiSigApproval(models.Model):
    """
    Individual approval from a multi-sig signer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        MultiSigGroup,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    signer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='multisig_approvals'
    )
    approved = models.BooleanField(default=False)
    tx_hash = models.CharField(
        max_length=66,
        blank=True,
        default='',
        help_text='On-chain approval transaction hash'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'smart_contract_multi_sig_approvals'
        unique_together = [['group', 'signer']]
        verbose_name = 'Multi-Sig Approval'
        verbose_name_plural = 'Multi-Sig Approvals'

    def __str__(self):
        status = '✅' if self.approved else '⏳'
        return f"{status} {self.signer.username} for {self.group.vault.title}"


class DAOProposal(models.Model):
    """
    DAO governance proposal for vault access voting.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.OneToOneField(
        'smart_contracts.SmartContractVault',
        on_delete=models.CASCADE,
        related_name='dao_proposal'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    voting_deadline = models.DateTimeField(
        help_text='When voting ends'
    )
    quorum_threshold = models.PositiveSmallIntegerField(
        default=5100,
        help_text='Quorum in basis points (5100 = 51%)'
    )
    eligible_voters = models.ManyToManyField(
        User,
        related_name='dao_eligible_proposals',
        help_text='Users eligible to vote'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'smart_contract_dao_proposals'
        verbose_name = 'DAO Proposal'
        verbose_name_plural = 'DAO Proposals'

    def __str__(self):
        return f"DAO: {self.title} ({self.votes_for}/{self.total_eligible})"

    @property
    def total_eligible(self):
        return self.eligible_voters.count()

    @property
    def votes_for(self):
        return self.votes.filter(approve=True).count()

    @property
    def votes_against(self):
        return self.votes.filter(approve=False).count()

    @property
    def voting_ended(self):
        return timezone.now() >= self.voting_deadline

    @property
    def quorum_met(self):
        if not self.voting_ended or self.total_eligible == 0:
            return False
        approval_bps = (self.votes_for * 10000) // self.total_eligible
        return approval_bps >= self.quorum_threshold


class DAOVote(models.Model):
    """
    Individual vote on a DAO proposal.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        DAOProposal,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dao_votes'
    )
    approve = models.BooleanField(
        help_text='True = approve, False = reject'
    )
    tx_hash = models.CharField(
        max_length=66,
        blank=True,
        default='',
        help_text='On-chain vote transaction hash'
    )
    voted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'smart_contract_dao_votes'
        unique_together = [['proposal', 'voter']]
        verbose_name = 'DAO Vote'
        verbose_name_plural = 'DAO Votes'

    def __str__(self):
        choice = '👍' if self.approve else '👎'
        return f"{choice} {self.voter.username} on {self.proposal.title}"

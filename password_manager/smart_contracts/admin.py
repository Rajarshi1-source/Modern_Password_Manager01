"""
Smart Contract Automation — Django Admin
==========================================
"""

from django.contrib import admin
from smart_contracts.models.vault import SmartContractVault, VaultCondition
from smart_contracts.models.governance import MultiSigGroup, MultiSigApproval, DAOProposal, DAOVote
from smart_contracts.models.escrow import EscrowAgreement, InheritancePlan


class VaultConditionInline(admin.TabularInline):
    model = VaultCondition
    extra = 0
    readonly_fields = ['is_met', 'evaluated_at']


@admin.register(SmartContractVault)
class SmartContractVaultAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'condition_type', 'status', 'network', 'created_at']
    list_filter = ['condition_type', 'status', 'network']
    search_fields = ['title', 'user__username', 'user__email']
    readonly_fields = ['id', 'password_hash', 'created_at', 'updated_at']
    inlines = [VaultConditionInline]
    date_hierarchy = 'created_at'


class MultiSigApprovalInline(admin.TabularInline):
    model = MultiSigApproval
    extra = 0
    readonly_fields = ['approved_at']


@admin.register(MultiSigGroup)
class MultiSigGroupAdmin(admin.ModelAdmin):
    list_display = ['vault', 'required_approvals', 'created_at']
    inlines = [MultiSigApprovalInline]


class DAOVoteInline(admin.TabularInline):
    model = DAOVote
    extra = 0
    readonly_fields = ['voted_at']


@admin.register(DAOProposal)
class DAOProposalAdmin(admin.ModelAdmin):
    list_display = ['title', 'vault', 'voting_deadline', 'quorum_threshold', 'created_at']
    list_filter = ['quorum_threshold']
    inlines = [DAOVoteInline]
    date_hierarchy = 'created_at'


@admin.register(EscrowAgreement)
class EscrowAgreementAdmin(admin.ModelAdmin):
    list_display = ['vault', 'depositor', 'beneficiary', 'arbitrator', 'status', 'created_at']
    list_filter = ['status']
    date_hierarchy = 'created_at'


@admin.register(InheritancePlan)
class InheritancePlanAdmin(admin.ModelAdmin):
    list_display = ['vault', 'owner', 'beneficiary_email', 'inactivity_period_days', 'status', 'last_check_in']
    list_filter = ['status']
    readonly_fields = ['triggered_at']
    date_hierarchy = 'created_at'

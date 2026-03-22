"""
Smart Contract Automation URL Configuration
=============================================
"""

from django.urls import path
from .api import views


urlpatterns = [
    # Configuration
    path('config/', views.smart_contract_config, name='smart-contract-config'),

    # Vault CRUD
    path('vaults/', views.vault_list, name='smart-contract-vaults'),
    path('vaults/<uuid:vault_id>/', views.vault_detail, name='smart-contract-vault-detail'),

    # Condition evaluation
    path('vaults/<uuid:vault_id>/conditions/', views.vault_conditions, name='smart-contract-vault-conditions'),
    path('vaults/<uuid:vault_id>/unlock/', views.vault_unlock, name='smart-contract-vault-unlock'),

    # Dead man's switch
    path('vaults/<uuid:vault_id>/check-in/', views.vault_check_in, name='smart-contract-vault-checkin'),

    # Multi-sig
    path('multi-sig/<uuid:vault_id>/approve/', views.multi_sig_approve, name='smart-contract-multisig-approve'),
    path('multi-sig/<uuid:vault_id>/status/', views.multi_sig_status, name='smart-contract-multisig-status'),

    # DAO voting
    path('dao/<uuid:vault_id>/vote/', views.dao_vote, name='smart-contract-dao-vote'),
    path('dao/<uuid:vault_id>/results/', views.dao_results, name='smart-contract-dao-results'),

    # Escrow
    path('escrow/<uuid:vault_id>/release/', views.escrow_release, name='smart-contract-escrow-release'),
    path('escrow/<uuid:vault_id>/status/', views.escrow_status, name='smart-contract-escrow-status'),

    # Inheritance
    path('inheritance/<uuid:vault_id>/', views.inheritance_status, name='smart-contract-inheritance-status'),

    # Oracle
    path('oracle/price/', views.oracle_price, name='smart-contract-oracle-price'),
]

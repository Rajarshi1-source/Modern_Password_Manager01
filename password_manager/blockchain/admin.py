"""
Django Admin Configuration for Blockchain App

Admin interface for viewing blockchain anchors, pending commitments, and Merkle proofs
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import BlockchainAnchor, PendingCommitment, MerkleProof


@admin.register(BlockchainAnchor)
class BlockchainAnchorAdmin(admin.ModelAdmin):
    """Admin interface for BlockchainAnchor model"""
    
    list_display = [
        'merkle_root_short',
        'batch_size',
        'network',
        'block_number',
        'timestamp',
        'view_on_explorer'
    ]
    
    list_filter = ['network', 'timestamp']
    
    search_fields = ['merkle_root', 'tx_hash']
    
    readonly_fields = [
        'merkle_root',
        'tx_hash',
        'block_number',
        'timestamp',
        'batch_size',
        'network',
        'gas_used',
        'gas_price',
        'submitter_address',
        'view_on_explorer_link'
    ]
    
    fieldsets = (
        ('Blockchain Information', {
            'fields': ('merkle_root', 'tx_hash', 'block_number', 'network', 'timestamp')
        }),
        ('Batch Details', {
            'fields': ('batch_size', 'submitter_address')
        }),
        ('Gas Information', {
            'fields': ('gas_used', 'gas_price'),
            'classes': ('collapse',)
        }),
        ('External Links', {
            'fields': ('view_on_explorer_link',)
        }),
    )
    
    def merkle_root_short(self, obj):
        """Display shortened Merkle root"""
        return f"{obj.merkle_root[:10]}...{obj.merkle_root[-8:]}"
    merkle_root_short.short_description = "Merkle Root"
    
    def view_on_explorer(self, obj):
        """Link to blockchain explorer"""
        if obj.network == 'mainnet':
            url = f"https://arbiscan.io/tx/{obj.tx_hash}"
        else:
            url = f"https://sepolia.arbiscan.io/tx/{obj.tx_hash}"
        
        return format_html('<a href="{}" target="_blank">View on Arbiscan</a>', url)
    view_on_explorer.short_description = "Explorer"
    
    def view_on_explorer_link(self, obj):
        """Full explorer link in readonly field"""
        if obj.network == 'mainnet':
            url = f"https://arbiscan.io/tx/{obj.tx_hash}"
        else:
            url = f"https://sepolia.arbiscan.io/tx/{obj.tx_hash}"
        
        return format_html(
            '<a href="{}" target="_blank" class="button">{}</a>',
            url,
            f"View Transaction on Arbitrum {obj.network.title()}"
        )
    view_on_explorer_link.short_description = "Blockchain Explorer"


@admin.register(PendingCommitment)
class PendingCommitmentAdmin(admin.ModelAdmin):
    """Admin interface for PendingCommitment model"""
    
    list_display = [
        'user',
        'commitment_id_short',
        'commitment_hash_short',
        'created_at',
        'anchored',
        'anchored_at'
    ]
    
    list_filter = ['is_anchored', 'created_at']
    
    search_fields = ['user__username', 'commitment_id', 'commitment_hash']
    
    readonly_fields = [
        'user',
        'commitment_id',
        'commitment_hash',
        'created_at',
        'anchored',
        'anchored_at',
        'blockchain_anchor'
    ]
    
    fieldsets = (
        ('Commitment Information', {
            'fields': ('user', 'commitment_id', 'commitment_hash')
        }),
        ('Status', {
            'fields': ('anchored', 'created_at', 'anchored_at', 'blockchain_anchor')
        }),
    )
    
    def commitment_id_short(self, obj):
        """Display shortened commitment ID"""
        return str(obj.commitment_id)[:13] + "..."
    commitment_id_short.short_description = "Commitment ID"
    
    def commitment_hash_short(self, obj):
        """Display shortened commitment hash"""
        return f"{obj.commitment_hash[:10]}...{obj.commitment_hash[-8:]}"
    commitment_hash_short.short_description = "Hash"
    
    def has_add_permission(self, request):
        """Disable adding pending commitments through admin"""
        return False


@admin.register(MerkleProof)
class MerkleProofAdmin(admin.ModelAdmin):
    """Admin interface for MerkleProof model"""
    
    list_display = [
        'user',
        'commitment_hash_short',
        'merkle_root_short',
        'leaf_index',
        'created_at',
        'verified'
    ]
    
    list_filter = ['created_at', 'verified']
    
    search_fields = ['user__username', 'commitment_hash', 'merkle_root']
    
    readonly_fields = [
        'user',
        'commitment',
        'commitment_hash',
        'merkle_root',
        'proof_display',
        'leaf_index',
        'blockchain_anchor',
        'created_at',
        'verified',
        'verified_at'
    ]
    
    fieldsets = (
        ('Commitment Information', {
            'fields': ('user', 'commitment', 'commitment_hash')
        }),
        ('Merkle Proof', {
            'fields': ('merkle_root', 'leaf_index', 'proof_display')
        }),
        ('Blockchain Anchor', {
            'fields': ('blockchain_anchor',)
        }),
        ('Verification Status', {
            'fields': ('verified', 'verified_at', 'created_at')
        }),
    )
    
    def commitment_hash_short(self, obj):
        """Display shortened commitment hash"""
        return f"{obj.commitment_hash[:10]}...{obj.commitment_hash[-8:]}"
    commitment_hash_short.short_description = "Commitment Hash"
    
    def merkle_root_short(self, obj):
        """Display shortened Merkle root"""
        return f"{obj.merkle_root[:10]}...{obj.merkle_root[-8:]}"
    merkle_root_short.short_description = "Merkle Root"
    
    def proof_display(self, obj):
        """Display Merkle proof as formatted JSON"""
        import json
        proof_json = json.dumps(obj.proof, indent=2)
        return format_html('<pre style="max-height: 300px; overflow-y: auto;">{}</pre>', proof_json)
    proof_display.short_description = "Merkle Proof"
    
    def has_add_permission(self, request):
        """Disable adding Merkle proofs through admin"""
        return False


# Admin site customization
admin.site.site_header = "Password Manager - Blockchain Anchoring"
admin.site.site_title = "Blockchain Admin"
admin.site.index_title = "Blockchain Anchoring Management"

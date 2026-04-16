from django.contrib import admin

from .models import AnchorBatch, ReputationAccount, ReputationEvent, ReputationProof


@admin.register(ReputationAccount)
class ReputationAccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "score",
        "tokens",
        "proofs_accepted",
        "proofs_rejected",
        "last_proof_at",
        "last_breach_at",
    )
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReputationProof)
class ReputationProofAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "scheme",
        "scope_id",
        "claimed_entropy_bits",
        "status",
        "score_delta",
        "tokens_delta",
        "created_at",
    )
    list_filter = ("status", "scheme")
    search_fields = ("user__email", "user__username", "scope_id")
    readonly_fields = ("id", "created_at")


@admin.register(ReputationEvent)
class ReputationEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "event_type",
        "score_delta",
        "tokens_delta",
        "anchor_status",
        "created_at",
    )
    list_filter = ("event_type", "anchor_status")
    search_fields = ("user__email", "user__username", "note")
    readonly_fields = ("id", "leaf_hash", "created_at")


@admin.register(AnchorBatch)
class AnchorBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "adapter",
        "merkle_root",
        "batch_size",
        "status",
        "tx_hash",
        "block_number",
        "network",
        "created_at",
    )
    list_filter = ("adapter", "status")
    search_fields = ("merkle_root", "tx_hash")
    readonly_fields = ("id", "created_at", "submitted_at", "confirmed_at")

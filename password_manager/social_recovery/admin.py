from django.contrib import admin

from .models import (
    RecoveryCircle,
    RelationshipCommitment,
    SocialRecoveryAuditLog,
    SocialRecoveryRequest,
    VouchAttestation,
    Voucher,
)


@admin.register(RecoveryCircle)
class RecoveryCircleAdmin(admin.ModelAdmin):
    list_display = ("circle_id", "user", "status", "threshold", "total_vouchers", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("voucher_id", "circle", "user", "did_string", "status", "vouch_weight")
    list_filter = ("status",)
    search_fields = ("did_string", "email", "display_name", "user__username")


admin.site.register(RelationshipCommitment)
admin.site.register(SocialRecoveryRequest)
admin.site.register(VouchAttestation)
admin.site.register(SocialRecoveryAuditLog)

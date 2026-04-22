from django.contrib import admin

from .models import DataSubjectRequest


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request_type",
        "status",
        "subject_email",
        "submitted_at",
        "due_by",
        "is_overdue",
        "completed_at",
    )
    list_filter = ("request_type", "status", "verification_method")
    search_fields = ("subject_email", "request_details")
    readonly_fields = ("submitted_at",)
    date_hierarchy = "submitted_at"

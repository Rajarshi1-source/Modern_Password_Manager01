"""
GDPR Data Subject Request (DSAR) tracking.

Complements the existing audit-logging infrastructure (``logging_manager``
and ``security`` apps) with a first-class record of rights exercised under
GDPR Articles 15, 16, 17, 18, 20, and 21. The 30-day statutory deadline
from Article 12(3) is materialised on the ``due_by`` column so the
regulator-facing report can be produced from a single table.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DataSubjectRequest(models.Model):
    """A single rights request submitted by (or on behalf of) a data subject."""

    class RequestType(models.TextChoices):
        ACCESS = "access", "Article 15 - Access"
        RECTIFICATION = "rectification", "Article 16 - Rectification"
        ERASURE = "erasure", "Article 17 - Erasure"
        RESTRICTION = "restriction", "Article 18 - Restriction"
        PORTABILITY = "portability", "Article 20 - Portability"
        OBJECTION = "objection", "Article 21 - Objection"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFYING = "verifying", "Verifying identity"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class VerificationMethod(models.TextChoices):
        EMAIL = "email", "Email confirmation"
        PASSKEY = "passkey", "WebAuthn / passkey"
        TOTP = "totp", "TOTP"
        GOVT_ID = "govt_id", "Government ID"
        IN_PERSON = "in_person", "In-person"
        OTHER = "other", "Other"

    RESPONSE_WINDOW = timedelta(days=30)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dsar_requests",
    )
    subject_email = models.EmailField(
        help_text="Contact email of the data subject (kept even if the user is deleted)."
    )
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    due_by = models.DateTimeField(
        help_text="Article 12(3) deadline — auto: submitted_at + 30 days."
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    verification_method = models.CharField(
        max_length=20,
        choices=VerificationMethod.choices,
        blank=True,
        default="",
    )
    request_details = models.TextField(
        blank=True,
        default="",
        help_text="Free-form description the subject provided with the request.",
    )
    evidence = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Structured evidence: signed proof, export artefact hashes, deletion "
            "receipts, ticket IDs. Never store raw personal data in this column."
        ),
    )

    handler = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dsar_handled",
        help_text="Internal operator who processed the request.",
    )

    class Meta:
        ordering = ("-submitted_at",)
        indexes = [
            models.Index(fields=("status", "due_by")),
            models.Index(fields=("request_type", "submitted_at")),
            models.Index(fields=("subject_email",)),
        ]
        verbose_name = "Data Subject Request"
        verbose_name_plural = "Data Subject Requests"

    def __str__(self) -> str:
        return f"DSAR #{self.pk} [{self.request_type}] {self.subject_email}"

    def save(self, *args, **kwargs):
        if not self.due_by:
            base = self.submitted_at or timezone.now()
            self.due_by = base + self.RESPONSE_WINDOW
        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        return (
            self.status not in {self.Status.COMPLETED, self.Status.REJECTED, self.Status.WITHDRAWN}
            and timezone.now() > self.due_by
        )

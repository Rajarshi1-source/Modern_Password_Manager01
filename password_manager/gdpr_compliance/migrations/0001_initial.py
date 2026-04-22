from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DataSubjectRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject_email", models.EmailField(max_length=254, help_text="Contact email of the data subject (kept even if the user is deleted).")),
                (
                    "request_type",
                    models.CharField(
                        choices=[
                            ("access", "Article 15 - Access"),
                            ("rectification", "Article 16 - Rectification"),
                            ("erasure", "Article 17 - Erasure"),
                            ("restriction", "Article 18 - Restriction"),
                            ("portability", "Article 20 - Portability"),
                            ("objection", "Article 21 - Objection"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("received", "Received"),
                            ("verifying", "Verifying identity"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("rejected", "Rejected"),
                            ("withdrawn", "Withdrawn"),
                        ],
                        default="received",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("due_by", models.DateTimeField(help_text="Article 12(3) deadline \u2014 auto: submitted_at + 30 days.")),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "verification_method",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("email", "Email confirmation"),
                            ("passkey", "WebAuthn / passkey"),
                            ("totp", "TOTP"),
                            ("govt_id", "Government ID"),
                            ("in_person", "In-person"),
                            ("other", "Other"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                ("request_details", models.TextField(blank=True, default="", help_text="Free-form description the subject provided with the request.")),
                (
                    "evidence",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Structured evidence: signed proof, export artefact hashes, deletion receipts, ticket IDs. Never store raw personal data in this column.",
                    ),
                ),
                (
                    "handler",
                    models.ForeignKey(
                        blank=True,
                        help_text="Internal operator who processed the request.",
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="dsar_handled",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="dsar_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Data Subject Request",
                "verbose_name_plural": "Data Subject Requests",
                "ordering": ("-submitted_at",),
            },
        ),
        migrations.AddIndex(
            model_name="datasubjectrequest",
            index=models.Index(fields=["status", "due_by"], name="gdpr_dsar_status_due_idx"),
        ),
        migrations.AddIndex(
            model_name="datasubjectrequest",
            index=models.Index(fields=["request_type", "submitted_at"], name="gdpr_dsar_type_sub_idx"),
        ),
        migrations.AddIndex(
            model_name="datasubjectrequest",
            index=models.Index(fields=["subject_email"], name="gdpr_dsar_email_idx"),
        ),
    ]

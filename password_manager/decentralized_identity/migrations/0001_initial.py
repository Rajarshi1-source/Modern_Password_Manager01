import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CredentialSchema",
            fields=[
                (
                    "schema_id",
                    models.CharField(max_length=128, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=128)),
                ("version", models.CharField(default="1.0.0", max_length=32)),
                ("json_schema", models.JSONField(default=dict)),
                ("context_urls", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="IssuerKey",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("kid", models.CharField(max_length=128, unique=True)),
                (
                    "did_web_identifier",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("public_key_multibase", models.CharField(max_length=128)),
                ("private_key_encrypted", models.BinaryField()),
                (
                    "algorithm",
                    models.CharField(
                        choices=[("Ed25519", "Ed25519")],
                        default="Ed25519",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RevocationList",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("list_id", models.CharField(max_length=64, unique=True)),
                ("size", models.PositiveIntegerField(default=131072)),
                ("encoded_list", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="SignInChallenge",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("did_string", models.CharField(db_index=True, max_length=255)),
                ("nonce", models.CharField(max_length=128, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("consumed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="signinchallenge",
            index=models.Index(
                fields=["did_string", "consumed"], name="did_challenge_consumed_idx"
            ),
        ),
        migrations.CreateModel(
            name="UserDID",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("did_string", models.CharField(max_length=255, unique=True)),
                ("public_key_multibase", models.CharField(max_length=128)),
                (
                    "algorithm",
                    models.CharField(
                        choices=[("Ed25519", "Ed25519")],
                        default="Ed25519",
                        max_length=16,
                    ),
                ),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dids",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="userdid",
            index=models.Index(
                fields=["user", "is_primary"], name="did_userdid_primary_idx"
            ),
        ),
        migrations.CreateModel(
            name="VerifiableCredential",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("subject_did", models.CharField(db_index=True, max_length=255)),
                ("issuer_did", models.CharField(max_length=255)),
                ("jwt_vc", models.TextField(help_text="Compact JWS VC-JWT.")),
                ("jsonld_vc", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("revoked", "Revoked"),
                            ("suspended", "Suspended"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_list_index", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "storage_refs",
                    models.JSONField(
                        default=dict,
                        help_text="{'ipfs_cid', 'arweave_tx', 'chain_anchor_tx'}",
                    ),
                ),
                (
                    "schema",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credentials",
                        to="decentralized_identity.credentialschema",
                    ),
                ),
            ],
            options={"ordering": ["-issued_at"]},
        ),
        migrations.AddIndex(
            model_name="verifiablecredential",
            index=models.Index(fields=["status"], name="did_vc_status_idx"),
        ),
        migrations.AddIndex(
            model_name="verifiablecredential",
            index=models.Index(
                fields=["subject_did", "status"], name="did_vc_subject_status_idx"
            ),
        ),
        migrations.CreateModel(
            name="VCPresentation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("holder_did", models.CharField(db_index=True, max_length=255)),
                ("presented_to", models.CharField(blank=True, default="", max_length=255)),
                ("vp_jwt", models.TextField(blank=True, default="")),
                ("zk_proof_ref", models.CharField(blank=True, default="", max_length=128)),
                ("disclosed_fields", models.JSONField(default=list)),
                ("verified", models.BooleanField(default=False)),
                ("verification_errors", models.JSONField(default=list)),
                ("presented_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]

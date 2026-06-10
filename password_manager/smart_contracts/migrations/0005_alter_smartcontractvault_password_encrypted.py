"""Record the SmartContractVault.password_encrypted help_text change (drift).

Audit-fix C12 (2026-05) corrected the field's misleading "AES-256-GCM
(server-side)" docstring to describe the opaque client-encrypted envelope, but
no migration captured it, so ``makemigrations --check`` reported drift. This is
a help_text-only change — no DB schema or data change.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("smart_contracts", "0004_remove_password_hash"),
    ]

    operations = [
        migrations.AlterField(
            model_name="smartcontractvault",
            name="password_encrypted",
            field=models.TextField(
                help_text='Opaque client-encrypted ciphertext envelope. The server does NOT decrypt this field — the user holds the only key. Callers are expected to POST a structured envelope (e.g. base64-encoded {iv, ct, tag} or a versioned binary blob); the serializer rejects payloads that look like plaintext. Audit-fix C12 (2026-05) — the previous "AES-256-GCM (server-side)" docstring was misleading; no server-side encryption is performed at any layer.'
            ),
        ),
    ]

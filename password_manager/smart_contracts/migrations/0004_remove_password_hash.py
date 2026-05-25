"""
Phase C / C5 (2026-05): drop ``SmartContractVault.password_hash``.

The field was dead metadata:
* The docstring claimed it was a "Keccak256 hash of the encrypted password"
  with implied cross-verifiability against the on-chain ``getVault().passwordHash``
  slot.
* In reality ``VaultService._compute_password_hash`` produced SHA-256
  (not Keccak), no caller ever read it back, and no on-chain verification
  step compared the two.
* The on-chain ``passwordHash`` returned by ``web3_bridge.get_vault_onchain``
  is a separate per-vault constant written by the contract deployer and
  unrelated to this row.

Removing the field reclaims storage on every vault row, eliminates a
confusing-looking-but-unused field from the admin and detail serializer,
and prevents the misleading docstring from being copied into a future
feature that thinks it can rely on the hash. Any future client-side
commitment scheme should land as a new, documented field.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smart_contracts', '0003_reveal_nonce_commitment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='smartcontractvault',
            name='password_hash',
        ),
    ]
